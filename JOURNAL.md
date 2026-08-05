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

## Week 9 — Solution building & PR submission

### Check-in 1 (mid-week)

**Current progress:**
Implementation is done and matches PLAN.md. Added `VectorStore.delete_collection()` (idempotent — a missing collection is a no-op, not an error) and pulled the `profile_<id>` naming into a shared `collection_name_for_profile()` helper so `hybrid.py`'s retrieval path and the delete path can't drift apart. Wired it into `delete_profile()`: after the SQL rows commit, it drops the profile's collection. `delete_profile()` takes an optional `vector_store` argument (defaults to a real `VectorStore`, injectable for tests) so the route's call signature barely changes. Both open questions from last week are resolved: nothing currently instantiates `VectorStore` for ingestion (that path is still stubbed), so the `vector_db_url` vs. `PersistentClient` mismatch doesn't bite yet — injectability defers it cleanly. On failure policy: SQL commits first, Chroma cleanup is best-effort after — a Chroma failure is logged, not raised, so it can't turn an already-successful delete into a 500.

Tests: the Week 8 reproduction test now goes red → green (injecting the same `VectorStore` the fix cleans up, backed by a temp dir), plus a no-embeddings no-op test and a full `test_profile_service.py` suite covering not-found, no-orphans cascade, single-commit, empty-cascade, rollback-and-reraise, and Chroma-failure-after-commit. 8 new tests, all passing.

Self-review against `make check`/`make test-unit`: ran both before touching anything and again after. `make test-unit` has 53 pre-existing failures on `main`, unrelated to #80 (bias detector, PII scrubber, resume parser, review service, skill extractor, tech detector) — same 53 after this change, confirmed by diffing the failing-test list, plus 8 new passing tests, zero new failures. `make lint`/`make typecheck` fail repo-wide on pre-existing debt in files this PR doesn't touch; scoped to the 5 files this PR changes, every remaining ruff/mypy finding is confirmed present on `main` before this change (same file, same line). This PR's own new code is ruff/black/mypy-clean. Documented in full in the PR description.

**Next steps:**
Draft PR is open: https://github.com/ascherj/pathreview/pull/880 — next is requesting peer review in Slack, then marking it ready for review once feedback is addressed.

**Blockers:**
None on the code. Tooling friction only: a stale `.git/index.lock` from an earlier interrupted stash had to be cleared by hand, and the pre-commit hook's `--fix`/black auto-formatting touched unrelated pre-existing code the first time I committed — reverted that and committed only the intended diff, using `--no-verify` for the pre-existing lint/type debt (documented in both commit messages and the PR description).

---

### Check-in 2 (end of week)

**PR link:** [paste after opening]

**Branch:** `fix/80-cascade-delete-profile`

**What you built:**
[fill in after PR is open — summary already drafted in the PR description]

**Tests added or updated:**
`tests/unit/test_profile_cascade_delete.py` (Week 8 reproduction test, flipped to green + no-op case) and `tests/unit/test_profile_service.py` (full `delete_profile()` cascade coverage) — 8 tests total, all passing.

**Self-review confirmation:** [ ] make check passes  [ ] make test-unit passes
*(In this codebase, "passes" = introduces no new failures — 53 pre-existing `make test-unit` failures and repo-wide `make lint`/`make typecheck` failures are documented in the PR description, confirmed unrelated to and unaffected by this change.)*

**Draft PR feedback received from:** [name or Slack handle, or "none"]
