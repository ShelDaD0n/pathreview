## Week 7 — Issue selection

**Issue link:** https://github.com/ascherj/pathreview/issues/80

**Issue title:** `DELETE /profiles/{profile_id}` doesn't cascade to delete associated reviews and embeddings

**Tier:** [ ] Tier 1  [x] Tier 2  [ ] Tier 3

**Problem summary:**
Right now, deleting a profile only removes the profile row. The reviews and vector
embeddings tied to it just get left behind, so the DB and vector store fill up with
orphaned junk pointing at a profile that's gone. The fix lives across the route
(`api/routes/profiles.py`) and the service layer (`core/services/profile_service.py`),
plus the models and vector store. Once it's fixed, deleting a profile should also wipe
its reviews and embeddings — ideally in one transaction — so nothing gets orphaned. I'll
back it with a unit test that deletes a profile and checks nothing's left over.

**Selection reasoning (Is this right for me?):**
I went Tier 2 because I've worked in big codebases before and wanted something that crosses
a couple of modules instead of a one-file change. This one fits: the before/after is easy to
show, the files are named and bounded (route + service + models/vector store), and it's easy
to test — which covers the "add a test" requirement. It's estimated at 4–6 hours, so it's
doable in Weeks 8–9, and there are no blockers or dependencies.

**Branch name:** fix/80-cascade-delete-profile

**Setup confirmation:** [x] App runs locally at localhost:5173

**Cohort ledger:** [ ] Issue added to cohort ledger

## Week 8 — Reproduction & solution planning

**Reproduction commit link:** https://github.com/ShelDaD0n/pathreview/commit/89824ba

**Reproduction summary:**
I traced the delete path and wrote a failing unit test (`tests/unit/test_profile_cascade_delete.py`) that seeds a `profile_{id}` ChromaDB collection, deletes the profile through the real `delete_profile()` service, and checks the collection is gone. It fails: the DB rows get cleaned up (the service even logs `profile_deleted_cascade`), but the embeddings collection is still there — so every deleted profile leaks its vectors. The reviews/ingested-sources are already handled by the code + `ondelete=CASCADE`, so the embeddings are the real gap.

**PLAN.md link:** https://github.com/ShelDaD0n/pathreview/blob/fix/80-cascade-delete-profile/PLAN.md

**Walkthrough video (recommended):** [optional — Loom link if I record one, ≤2 min]

**Blockers or open questions:**
Two things I want to nail down before writing the fix in Week 9: (1) `core/config.py` points at an HTTP Chroma server (`vector_db_url`) while `VectorStore` uses a local `PersistentClient` — I need to confirm which one the running app actually uses so I clean up the right store. (2) Postgres and Chroma aren't in one transaction, so I need to decide the failure policy if the SQL delete succeeds but the Chroma delete fails.
