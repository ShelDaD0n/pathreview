"""Reproduction for issue #80 — deleting a profile leaves its embeddings orphaned.

Issue #80: DELETE /profiles/{profile_id} doesn't cascade to delete associated
reviews and embeddings.

What I found tracing it (AI201 Module 3, Week 8):
- delete_profile() in core/services/profile_service.py already removes the
  Review and IngestedSource rows in Postgres (and the models have ondelete=CASCADE
  on top of that), so the "reviews" half is effectively handled.
- The real, live gap is the embeddings. Each profile's vectors live in their own
  ChromaDB collection named f"profile_{profile_id}" (see rag/retriever/hybrid.py
  line 42 and rag/retriever/vector_store.py). Nothing in the delete path ever
  removes that collection, so the vectors stick around forever pointing at a
  profile that no longer exists.

This test proves the bug at its source. It seeds a per-profile ChromaDB
collection the way the ingestion path would, deletes the profile through the
real service, then checks the collection is gone. It FAILS today because
delete_profile() never touches the vector store. The Week 9 fix should make it
pass.
"""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import chromadb
import pytest

from core.services.profile_service import delete_profile


@pytest.mark.unit
class TestProfileCascadeDeleteEmbeddings:
    """Proves profile deletion leaves ChromaDB embeddings orphaned (#80)."""

    def _mock_db_returning(self, profile: Mock) -> AsyncMock:
        """Fake async DB session.

        get_profile() reads scalars().first(); the review/source lookups read
        scalars().all(). One result object covers all three calls: first()
        returns the profile, all() returns an empty list.
        """
        scalars = Mock()
        scalars.first.return_value = profile
        scalars.all.return_value = []

        result = Mock()
        result.scalars.return_value = scalars

        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        db.delete = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_delete_profile_removes_chromadb_collection(self, tmp_path: Path) -> None:
        profile_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Fake profile row that get_profile() will return.
        profile = Mock()
        profile.id = profile_id
        profile.user_id = user_id

        # Seed the per-profile collection the way ingestion does.
        # Name matches rag/retriever/hybrid.py -> f"profile_{profile_id}".
        collection_name = f"profile_{profile_id}"
        client = chromadb.PersistentClient(path=str(tmp_path))
        collection = client.create_collection(name=collection_name)
        collection.add(
            ids=["chunk-1"],
            embeddings=[[0.1, 0.2, 0.3]],
            documents=["some ingested chunk"],
            metadatas=[{"source_id": "resume_x"}],
        )
        assert collection_name in [c.name for c in client.list_collections()]

        db = self._mock_db_returning(profile)

        # Act: delete the profile through the real service.
        deleted = await delete_profile(db=db, profile_id=profile_id, user_id=user_id)
        assert deleted is True  # DB rows get handled...

        # Assert: ...but the embeddings do NOT. This is the bug (#80).
        remaining = [c.name for c in client.list_collections()]
        assert collection_name not in remaining, (
            f"Orphaned embeddings: ChromaDB collection '{collection_name}' still "
            f"exists after the profile was deleted. delete_profile() never removes "
            f"it, so every deleted profile leaks its vectors."
        )
