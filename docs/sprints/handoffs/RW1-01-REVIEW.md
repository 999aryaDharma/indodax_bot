# RW1-01 Independent Review — Reusable Immutable Dataset Registry

Reviewer: Antigravity Independent Reviewer (`agy`)
Implementation Owner: Codex `/root` (LUNA execution)
Reviewed Code SHA: `8a8cc29`
Base SHA: `b0f023f`
Branch: `docs/architecture-runtime-plan`
Scope: Range-aware reusable dataset versions, atomic catalog publication, quality lineage
Round: 1

## Formal Verdict

- Spec Verdict: **CHANGES_REQUESTED**
- Quality Verdict: **CHANGES_REQUESTED**

Summary: 2 Critical findings, 2 Important findings, 2 Minor findings.
Critical and Important findings block DONE under `AGENTS.md` and repository review protocol.

---

## Findings Table

| # | Finding | Severity | Location | Failure Mechanism | Reproduction | Required Regression | Status |
|---|---|---|---|---|---|---|---|
| F1 | `registry.get(ref)` returns corrupted manifest; `to_artifact_ref()` digest does not match registered `ref.sha256` | **Critical** | `src/indodax_lab/data/dataset_registry.py:620-658, 664-728` | `_publish_dataset` omits `source_id`, `source_version`, `version`, `requested_start`, `requested_end`, `created_at_utc` from catalog entry; `_entry_to_manifest` ignores `parent_ref_key` and leaves `parent_dataset_ref=None`. Reconstructed manifest has different semantic hash. | Create dataset `m1`, call `m_loaded = reg.get(m1.to_artifact_ref())`. `m_loaded.to_artifact_ref().sha256 != m1.to_artifact_ref().sha256` (`source_id` is `""` instead of original). | Regression test verifying `reg.get(m.to_artifact_ref()).to_artifact_ref() == m.to_artifact_ref()` and all manifest fields match. | OPEN |
| F2 | `extend()` drops parent partitions; extended manifest only covers delta interval and breaks subsequent `find()` | **Critical** | `src/indodax_lab/data/dataset_registry.py:382-427` | `extend()` passes only `new_partitions` to `_publish_dataset()`. Manifest `actual_start` and `partition_refs` omit parent partitions. Calling `find()` for extended range fails with `DatasetCoverageError`. | Create base `T0..T1`, call `extend(T0..T2)`. Call `reg.find(..., T0, T2)`. Raises `DatasetCoverageError`. | Regression test asserting `reg.find(..., T0, T2)` succeeds after `extend()` and manifest contains cumulative partitions and bar count. | OPEN |
| F3 | In-memory catalog mutated before disk commit in `_Catalog.register()`; corrupts in-memory state and prevents retries on failure | **Important** | `src/indodax_lab/data/dataset_registry.py:167-177` | `self._entries[ref_key] = entry` executed before `self._persist()`. If `_persist()` raises `OSError`, in-memory entry remains visible, and retrying `register()` exits early due to idempotency check without writing to disk. | Inject failing `_persist` raising `OSError`. Check in-memory `cat.get()`. Retrying `register()` leaves disk catalog empty. | Regression test verifying rollback of in-memory entry on `_persist` error, and retry succeeds in writing to disk. | OPEN |
| F4 | CLI missing `create` and `extend` subcommands mandated by spec Step 5 and module docstring | **Important** | `src/indodax_lab/cli/dataset_registry.py:1-8, 131-189` | Module docstring declares `find`, `create`, `extend`, `validate`. Spec Step 5 specifies "Add CLI lookup/create/extend/validate". Parser only implements `find`, `validate`, `legacy`. | Run `python -m indodax_lab.cli.dataset_registry create --help` -> `invalid choice: 'create'`. | Implement `create` and `extend` subcommands or align CLI specification with testable entry points. | OPEN |
| F5 | Dead helper functions `_sha256_file` and `_artifact_sha256` | **Minor** | `src/indodax_lab/data/dataset_registry.py:68-73, 93-94` | Defined private helpers are never called anywhere in the codebase. | Inspect symbol usage in repository. | Remove dead code or integrate into partition disk validation. | OPEN |
| F6 | Naive datetime in `find()` swallowed as coverage miss instead of validation error | **Minor** | `src/indodax_lab/data/dataset_registry.py:493-504` | `_covers` compares naive datetime against aware datetime, catching `TypeError` and treating as `False` instead of explicit error. | Call `find(..., start=naive_dt)`. | Enforce UTC timezone awareness on `find()` arguments matching `DatasetRequest`. | OPEN |

---

## Detailed Evaluation of Acceptance Criteria

### AC0: Covered request performs zero provider fetches; create() checks existing coverage first
- **Verdict**: **PARTIAL / DEFECTIVE**
- **Evidence**: `test_rw1_01_0` passes on fresh runs.
- **Defect noted**: In `create()`:
  ```python
  if existing_refs:
      return self.get(existing_refs[0])
  ```
  Because `get()` returns a corrupted manifest where `source_id` is blank and digest differs (F1), returning `self.get()` produces an invalid manifest. Furthermore, because `extend()` does not produce a manifest covering the parent range (F2), `create()` will not detect coverage for extended intervals.

### AC1: extend() fetches ONLY uncovered intervals and preserves v1 bytes; parent_dataset_ref set
- **Verdict**: **CHANGES_REQUESTED (F1, F2)**
- **Evidence**:
  - `extend()` calculates uncovered intervals correctly and fetches only `T1..T2`.
  - However, the returned manifest only includes `new_partitions`, setting `actual_start = T1` and `bar_count = 50`. Parent partition references are discarded.
  - Furthermore, `parent_dataset_ref` is set on the immediate in-memory object, but is discarded when persisted to catalog (`_entry_to_manifest` leaves `parent_dataset_ref = None`).

### AC2: validate() raises DatasetZeroBarsError for 0 bars; DatasetPartitionHashError for hash mismatch
- **Verdict**: **PASS**
- **Evidence**:
  - Zero bars raises `DatasetZeroBarsError: ZERO_BARS_NOT_EXPERIMENT_READY` (tested independently).
  - Corrupted partition hash in catalog raises `DatasetPartitionHashError` (tested independently).

### AC3: _Catalog.register() raises DatasetPublicationConflictError for same ref_key + different content; idempotent for same content
- **Verdict**: **PASS (with F3 note)**
- **Evidence**:
  - Re-registering identical entry is a no-op (PASS).
  - Registering same `ref_key` with differing content raises `DatasetPublicationConflictError` (PASS).
  - Note: F3 applies when disk persist fails during registration.

### AC4: _Catalog._persist() crash leaves no visible entry in catalog and no partial files
- **Verdict**: **CHANGES_REQUESTED (F3)**
- **Evidence**:
  - Disk atomicity works (partial + replace + unlinking on failure).
  - However, in-memory state in `_Catalog` is corrupted if `_persist()` raises: the unpersisted entry remains in `self._entries`, preventing retry from persisting to disk.

---

## Independent Test & Gate Results

Commands executed independently on Python 3.12.13 (Windows):

1. **Focused integration test suite:**
   ```bash
   C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/integration/lab/test_dataset_registry_versions.py -v
   ```
   Result: **5 passed in 1.05s** (exit 0).

2. **Ruff lint check:**
   ```bash
   C:\Users\User\miniconda3\envs\ML\python.exe -m ruff check src/indodax_lab/data/dataset_registry.py src/indodax_lab/cli/dataset_registry.py tests/integration/lab/test_dataset_registry_versions.py
   ```
   Result: **All checks passed** (exit 0).

3. **Full test suite gate:**
   ```bash
   C:\Users\User\miniconda3\envs\ML\python.exe -m pytest -q
   ```
   Result: **966 passed, 2 skipped (Windows platform limitations: symlinks & /proc), 0 failed in 40.80s** (exit 0).

4. **Negative and Edge Cases Attempted:**
   - Range partially covered: `reg.find(..., _T0, _T2)` raised `DatasetCoverageError` (PASS).
   - Zero bars: `reg.validate(ref_zero)` raised `DatasetZeroBarsError` (PASS).
   - Conflicting publication: `catalog.register(key, diff_content)` raised `DatasetPublicationConflictError` (PASS).
   - Idempotent re-registration: `catalog.register(key, same_content)` succeeded without error (PASS).
   - Identity roundtrip: `reg.get(m.to_artifact_ref()).to_artifact_ref() == m.to_artifact_ref()` **FAILED** (reproduced F1).
   - Range lookup after extension: `reg.find(..., _T0, _T2)` after `extend()` **FAILED** (reproduced F2).
   - In-memory state recovery on persist crash: in-memory ghost entry remained and retry skipped disk persist (reproduced F3).

---

## Safety and Scope Boundary Verification

- No trade/withdraw keys or live order paths used.
- Research workbench / paper shadow isolation maintained.
- No direct `main` or `dev` branch modifications.
- Single-writer catalog lock maintained.

---

## Remediation Plan for Round 2

1. **Fix F1 (`_publish_dataset` & `_entry_to_manifest`):**
   - In `_publish_dataset`, write all semantic fields to `entry`: `source_id`, `source_version`, `version`, `requested_start`, `requested_end`, `created_at_utc`, and `parent_dataset_ref` (serialized as ref dictionary).
   - In `_entry_to_manifest`, reconstruct `parent_dataset_ref = ArtifactRef(...)` when `entry.get("parent_dataset_ref")` or `parent_ref_key` is present.
   - Ensure `m_loaded.to_artifact_ref() == m.to_artifact_ref()` holds universally.

2. **Fix F2 (`extend`):**
   - In `extend()`, assemble the combined list of partitions: `parent.partition_refs` + new partition refs.
   - Derive the new manifest covering the full range `[min(parent.actual_start, req.start), max(parent.actual_end, req.end)]` with cumulative `bar_count`.
   - Ensure `reg.find(venue, pair, timeframe, req.start, req.end)` locates the extended dataset.

3. **Fix F3 (`_Catalog.register`):**
   - Wrap `self._persist()` in `try ... except Exception: self._entries.pop(ref_key, None); raise` to ensure failed disk commits roll back in-memory state.

4. **Fix F4 (CLI subcommands):**
   - Implement `create` and `extend` subcommands in `cli/dataset_registry.py` matching the docstring and Step 5 specification.

5. **Clean up F5 & F6:**
   - Remove unused `_sha256_file` and `_artifact_sha256`. Validate UTC awareness on `find()` input arguments.

Submit round-2 review request with new code SHA once remediated.
