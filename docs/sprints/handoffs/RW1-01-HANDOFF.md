# RW1-01 Handoff — Reusable Immutable Dataset Registry

Status: REVIEW — awaiting independent reviewer verdict

## Identity

- Task: RW1-01
- Implementation owner: Codex `/root` (LUNA execution)
- Independent reviewer: PENDING
- Base SHA: `b0f023f`
- Code SHA: `8a8cc29`
- Branch: `docs/architecture-runtime-plan`
- Scope: Range-aware reusable dataset versions, atomic catalog publication, quality lineage

## Implemented

- Created `src/indodax_lab/data/dataset_registry.py`:
  - `DatasetRegistry.find(venue,pair,timeframe,start,end)`: returns `tuple[ArtifactRef,...]`; raises `DatasetCoverageError` when no covering dataset exists (AC0 — zero-fetch guarantee).
  - `DatasetRegistry.create(request)`: checks existing coverage first (AC0), then fetches from provider and atomically publishes via `_Catalog.register()` with partial+rename+fsync pattern (AC4).
  - `DatasetRegistry.extend(parent_ref, request)`: fetches only uncovered intervals before/after parent range, links `parent_dataset_ref` for lineage (AC1).
  - `DatasetRegistry.get(ref)`: reconstruct `DatasetManifest` from catalog entry.
  - `DatasetRegistry.validate(ref)`: raises `DatasetZeroBarsError` for zero-bar datasets (AC2), raises `DatasetPartitionHashError` for mismatched hashes (AC2).
  - `_Catalog`: thread-safe (`threading.Lock`), durable (`partial + replace + fsync`) append-only JSON index. Idempotent register (same content = no-op). Conflicting registration (same ref_key, different content) raises `DatasetPublicationConflictError` (AC3). Crash during `_persist` leaves no partial file and no visible entry (AC4).
  - `DatasetRequest`: validated UTC datetime request model.
  - `RegistryQualityReport`: inline quality evidence bound to dataset.
  - Exception hierarchy: `DatasetNotFoundError`, `DatasetCoverageError`, `DatasetPublicationConflictError`, `DatasetPublicationPartialError`, `DatasetQualityError`, `DatasetZeroBarsError`, `DatasetPartitionHashError`.

- Modified `src/indodax_lab/cli/dataset_registry.py`:
  - Added `find` subcommand: structured JSON output for coverage lookup.
  - Added `validate` subcommand: JSON output for partition integrity.
  - Added `legacy` subcommand: backward-compatible root-inventory mode.
  - Legacy `build_registry()` and `publish_no_clobber()` preserved.

- Created `tests/integration/lab/test_dataset_registry_versions.py`:
  - 5 acceptance tests using fake providers, in-memory state, temp paths.
  - No real network, no real DB, no credentials.

## Observed TDD evidence

- RED: `python -m pytest tests/integration/lab/test_dataset_registry_versions.py -q` → collection error (ModuleNotFoundError: indodax_lab.data.dataset_registry).
- GREEN focused: `python -m pytest tests/integration/lab/test_dataset_registry_versions.py -q` → 5 passed in 0.85s.
- Ruff: `ruff check src/indodax_lab/data/dataset_registry.py src/indodax_lab/cli/dataset_registry.py tests/integration/lab/test_dataset_registry_versions.py` → All checks passed (exit 0).
- Full suite gate: `python -m pytest -q` → 966 passed, 2 skipped (platform), 0 failed in 33.76s (exit 0).
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
