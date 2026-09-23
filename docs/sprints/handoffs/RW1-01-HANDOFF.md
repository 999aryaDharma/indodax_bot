# RW1-01 Handoff — Reusable Immutable Dataset Registry

Status: REVIEW (Round 2 pending independent approval)

## Identity

- Task: RW1-01
- Implementation owner: Codex `/root` (LUNA execution) & Antigravity (Round 2 remediation)
- Independent reviewer: Antigravity Independent Reviewer (subagent `e435a0c1` Round 1 CHANGES_REQUESTED)
- Base SHA: `b0f023f`
- Code SHA (Round 1): `8a8cc29`
- Remediation SHA (Round 2): `9060726`
- Branch: `docs/architecture-runtime-plan`
- Scope: Range-aware reusable dataset versions, atomic catalog publication, quality lineage

## Round 2 Remediation Summary

Remediated all findings from Round 1 review (`docs/sprints/handoffs/RW1-01-REVIEW.md`):
- **F1 (Critical, FIXED)**: `_publish_dataset` and `_entry_to_manifest` preserve all semantic fields (`source_id`, `source_version`, `version`, `requested_start`, `requested_end`, `parent_dataset_ref`, `created_at_utc`). `m_loaded.to_artifact_ref().sha256 == m_original.to_artifact_ref().sha256` guaranteed.
- **F2 (Critical, FIXED)**: `extend()` accumulates parent partitions and uncovered intervals into a single combined manifest covering the full `[actual_start, actual_end]` range. Subsequent `find()` finds extended dataset.
- **F3 (Important, FIXED)**: `_Catalog.register()` rolls back in-memory entry if `_persist()` raises, preventing corrupted state and enabling retry.
- **F4 (Important, FIXED)**: Added `create` and `extend` subcommands with JSON output to `cli/dataset_registry.py`.
- **F5 (Minor, FIXED)**: Removed dead `_sha256_file` and `_artifact_sha256` helper functions.
- **F6 (Minor, FIXED)**: Enforced timezone-aware UTC datetime validation in `find()`.

## Observed TDD evidence (Round 2)

- GREEN focused: `python -m pytest tests/integration/lab/test_dataset_registry_versions.py -v` → 10 passed in 0.73s (exit 0).
- Ruff: `ruff check src/indodax_lab/data/dataset_registry.py src/indodax_lab/cli/dataset_registry.py tests/integration/lab/test_dataset_registry_versions.py` → All checks passed (exit 0).
- Full suite gate: `python -m pytest -q` → 972 passed, 2 skipped (platform), 0 failed in 34.47s (exit 0).
- Diff check: `git diff --check` → exit 0 (CRLF warnings only).

## Acceptance Criteria Mapping

- RW1-01-AC0 (`test_rw1_01_0`): Covered request performs zero provider fetches. OBSERVED_PASS.
- RW1-01-AC1 (`test_rw1_01_1`): Extension fetches only uncovered intervals and preserves v1 bytes (parent_ref linkage). OBSERVED_PASS.
- RW1-01-AC2 (`test_rw1_01_2`): Zero bars raises `DatasetZeroBarsError`; mismatched partition hash raises `DatasetPartitionHashError`. OBSERVED_PASS.
- RW1-01-AC3 (`test_rw1_01_3`): Concurrent same-version changed publication raises `DatasetPublicationConflictError`; identical re-registration is idempotent. OBSERVED_PASS.
- RW1-01-AC4 (`test_rw1_01_4`): Simulated crash during `_persist` leaves no entry visible in fresh catalog load and no partial files. OBSERVED_PASS.

## Compatibility and migration

- `cli/dataset_registry.py`: Backward compatible. All existing positional roots usage still works via `legacy` subcommand. `build_registry()` and `publish_no_clobber()` functions preserved with no signature changes.
- `data/dataset_registry.py`: New module, no existing code broken.
- `DatasetManifest` from RW0-01 used directly; no schema changes.

## Safety and scope checks

- No credentials, real order authority, network calls, runtime databases, or production activation.
- No `main` or `dev` branch change, merge, push, or deployment.
- No product-path files outside declared RW1-01 scope were modified.
- `dashboard.pen` and `DESIGN.md` were preserved and untouched.

## Reviewer checklist (independent reviewer must verify)

- [ ] AC0: Calling `create()` twice for same range — confirm fetch_provider called exactly once.
- [ ] AC1: Calling `extend()` after `create()` — confirm only uncovered sub-interval fetched; `parent_dataset_ref` is set.
- [ ] AC2: Zero-bar dataset raises `DatasetZeroBarsError` on `validate()`; corrupted hash raises `DatasetPartitionHashError`.
- [ ] AC3: Same ref_key + different content raises `DatasetPublicationConflictError`; same content is idempotent.
- [ ] AC4: Crash during `_persist` leaves catalog path unmodified and no partial files.
- [ ] Run `pytest tests/integration/lab/test_dataset_registry_versions.py -v` independently.
- [ ] Run full suite `pytest -q`.
- [ ] Verify no real network/DB calls, no production path, no credential use.
