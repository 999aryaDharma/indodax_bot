# RW1-01 Independent Review — Reusable Immutable Dataset Registry

Status: PASS on Round 2; reviewed content SHA `90607262af43e8e4fd861a156dcf1e8cd250c6fe` (docs update SHA `2773d9e`). Maximum five rounds; history preserved below.

## Identity

- Sprint ID: RW1-01 — Reusable immutable dataset registry
- Implementation owner: Codex `/root` (LUNA execution) & Antigravity (Round 2 remediation)
- Independent reviewer: Antigravity Independent Reviewer (`agy`)
- Reviewed SHA (Round 1): `8a8cc29`
- Reviewed SHA (Round 2): `9060726` (with docs update `2773d9e`)
- Base SHA: `b0f023f`
- Branch: `docs/architecture-runtime-plan`
- Scope: Range-aware reusable dataset versions, atomic catalog publication, quality lineage
- Round: 2

## Formal Verdicts

- Spec Verdict: **PASS**
- Quality Verdict: **PASS**
- Overall Verdict: **PASS**

Summary: All 6 findings (2 Critical, 2 Important, 2 Minor) from Round 1 have been completely resolved and independently verified. Full suite regression gate, focused test suite, ruff lint check, and independent edge-case probes all passed cleanly.

---

## Findings Table

| # | Finding | Severity | Location | Failure Mechanism | Reproduction | Required Regression | Status |
|---|---|---|---|---|---|---|---|
| F1 | `registry.get(ref)` returns corrupted manifest; `to_artifact_ref()` digest does not match registered `ref.sha256` | **Critical** | `src/indodax_lab/data/dataset_registry.py:620-658, 664-728` | `_publish_dataset` omitted semantic fields from catalog entry; `_entry_to_manifest` ignored parent linkage. Reconstructed manifest produced different semantic hash. | Create dataset `m1`, call `m_loaded = reg.get(m1.to_artifact_ref())`. `m_loaded.to_artifact_ref().sha256 != m1.to_artifact_ref().sha256`. | Regression test verifying `reg.get(m.to_artifact_ref()).to_artifact_ref() == m.to_artifact_ref()` and all manifest fields match. | **RESOLVED** (Round 2: `_publish_dataset` persists all fields; `_entry_to_manifest` reconstructs all fields; roundtrip identity hash verified) |
| F2 | `extend()` drops parent partitions; extended manifest only covers delta interval and breaks subsequent `find()` | **Critical** | `src/indodax_lab/data/dataset_registry.py:382-427` | `extend()` passed only delta partitions to `_publish_dataset()`. Manifest `actual_start` and `partition_refs` omitted parent partitions. Calling `find()` for extended range failed. | Create base `T0..T1`, call `extend(T0..T2)`. Call `reg.find(..., T0, T2)`. Raised `DatasetCoverageError`. | Regression test asserting `reg.find(..., T0, T2)` succeeds after `extend()` and manifest contains cumulative partitions and bar count. | **RESOLVED** (Round 2: `extend()` accumulates parent partitions and uncovered intervals into combined manifest; bidirectional coverage tested) |
| F3 | In-memory catalog mutated before disk commit in `_Catalog.register()`; corrupts in-memory state and prevents retries on failure | **Important** | `src/indodax_lab/data/dataset_registry.py:167-177` | `self._entries[ref_key] = entry` executed before `self._persist()`. If `_persist()` raised `OSError`, in-memory entry remained visible, blocking retry. | Inject failing `_persist` raising `OSError`. Check in-memory `cat.get()`. Retrying `register()` left disk catalog empty. | Regression test verifying rollback of in-memory entry on `_persist` error, and retry succeeds in writing to disk. | **RESOLVED** (Round 2: wrapped `_persist()` with rollback on exception; retry succeeds and persists to disk) |
| F4 | CLI missing `create` and `extend` subcommands mandated by spec Step 5 and module docstring | **Important** | `src/indodax_lab/cli/dataset_registry.py:1-8, 131-189` | Module docstring declared `find`, `create`, `extend`, `validate`. Parser only implemented `find`, `validate`, `legacy`. | Run `python -m indodax_lab.cli.dataset_registry create --help` -> `invalid choice: 'create'`. | Implement `create` and `extend` subcommands or align CLI specification with testable entry points. | **RESOLVED** (Round 2: added `create` and `extend` CLI subcommands with JSON output; verified end-to-end) |
| F5 | Dead helper functions `_sha256_file` and `_artifact_sha256` | **Minor** | `src/indodax_lab/data/dataset_registry.py:68-73, 93-94` | Defined private helpers were never called anywhere in the codebase. | Inspect symbol usage in repository. | Remove dead code or integrate into partition disk validation. | **RESOLVED** (Round 2: dead helpers removed) |
| F6 | Naive datetime in `find()` swallowed as coverage miss instead of validation error | **Minor** | `src/indodax_lab/data/dataset_registry.py:493-504` | `_covers` compared naive datetime against aware datetime, catching `TypeError` and treating as `False` instead of explicit error. | Call `find(..., start=naive_dt)`. | Enforce UTC timezone awareness on `find()` arguments matching `DatasetRequest`. | **RESOLVED** (Round 2: explicit `ValueError("NAIVE_DATETIME_FORBIDDEN: ...")` raised when start/end lack timezone) |

---

## Detailed Evaluation of Acceptance Criteria

### AC0: Covered request performs zero provider fetches; create() checks existing coverage first
- **Verdict**: **PASS**
- **Evidence**: `test_rw1_01_0` passes. Initial create fetches once. Second create for same range returns existing manifest without invoking provider. Manifest fields and bar counts preserved accurately.

### AC1: extend() fetches ONLY uncovered intervals and preserves v1 bytes; parent_dataset_ref set
- **Verdict**: **PASS**
- **Evidence**: `test_rw1_01_1` passes.
  - Initial range `T0..T1` fetched.
  - Extension `T0..T2` triggers provider only for `T1..T2`.
  - Returned manifest accumulates both intervals (`actual_start=T0`, `actual_end=T2`, `bar_count=100`, 2 partition refs).
  - `parent_dataset_ref` is correctly linked to `base_ref` and persists roundtrip to/from catalog.

### AC2: validate() raises DatasetZeroBarsError for 0 bars; DatasetPartitionHashError for hash mismatch
- **Verdict**: **PASS**
- **Evidence**: `test_rw1_01_2` passes.
  - Zero bars raises `DatasetZeroBarsError: ZERO_BARS_NOT_EXPERIMENT_READY`.
  - Tampered/corrupted partition byte hash in catalog raises `DatasetPartitionHashError`.

### AC3: _Catalog.register() raises DatasetPublicationConflictError for same ref_key + different content; idempotent for same content
- **Verdict**: **PASS**
- **Evidence**: `test_rw1_01_3` passes.
  - Idempotent re-registration of identical entry succeeds without error.
  - Conflicting entry under identical `ref_key` raises `DatasetPublicationConflictError`.

### AC4: _Catalog._persist() crash leaves no visible entry in catalog and no partial files
- **Verdict**: **PASS**
- **Evidence**: `test_rw1_01_4` and `test_rw1_01_f3_retry_after_crash` pass.
  - Simulated crash in `_persist()` rolls back in-memory entry.
  - No partial `.partial` files remain on disk.
  - Reloading catalog from disk shows no ghost entries.
  - Subsequent retry succeeds and properly commits to disk.

---

## Independent Test & Gate Results

Commands executed independently on Python 3.12.13 (Windows):

1. **Focused integration test suite:**
   ```bash
   C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/integration/lab/test_dataset_registry_versions.py -v
   ```
   Result: **10 passed in 0.85s** (exit 0).

2. **Ruff lint check:**
   ```bash
   C:\Users\User\miniconda3\envs\ML\python.exe -m ruff check src/indodax_lab/data/dataset_registry.py src/indodax_lab/cli/dataset_registry.py tests/integration/lab/test_dataset_registry_versions.py
   ```
   Result: **All checks passed!** (exit 0).

3. **Full test suite gate:**
   ```bash
   C:\Users\User\miniconda3\envs\ML\python.exe -m pytest -q
   ```
   Result: **972 passed, 2 skipped (Windows platform limitations: symlinks & /proc), 3 warnings, 0 failed in 32.20s** (exit 0).

4. **Independent Edge & Negative Cases Attempted:**
   - Identity roundtrip across base and extended manifests: `m_loaded.to_artifact_ref().sha256 == m_orig.to_artifact_ref().sha256` verified (PASS).
   - Bi-directional interval extension (prepending earlier range + appending later range): verified `bar_count`, `actual_start`, `actual_end`, partition refs, and subsequent `find()` (PASS).
   - CLI subcommands end-to-end: `create`, `extend`, `find`, `validate` executed sequentially with JSON assertions (PASS).
   - Rollback and retry idempotency under simulated persist exception: verified in-memory rollback and successful retry persistence (PASS).
   - Naive datetime validation: verified explicit `ValueError` on naive inputs to `find()` (PASS).

---

## Safety and Scope Boundary Verification

- Zero trade or withdraw credentials or live execution capabilities.
- Research workbench / paper shadow boundary strictly observed.
- Single-writer thread-locked catalog structure verified.
- No modifications to files outside declared RW1-01 scope.
- `dashboard.pen` and `DESIGN.md` untouched.

---

## Round 1 Historical Record

<details>
<summary>Round 1 Review Details (SHA: 8a8cc29)</summary>

- Spec verdict: CHANGES_REQUESTED
- Quality verdict: CHANGES_REQUESTED
- Overall verdict: CHANGES_REQUESTED
- Round 1 findings:
  - F1 (Critical): `registry.get(ref)` returned corrupted manifest; digest did not match `ref.sha256`.
  - F2 (Critical): `extend()` dropped parent partitions; extended manifest only covered delta interval.
  - F3 (Important): In-memory catalog mutated before disk commit in `_Catalog.register()`.
  - F4 (Important): CLI missing `create` and `extend` subcommands.
  - F5 (Minor): Dead helper functions `_sha256_file` and `_artifact_sha256`.
  - F6 (Minor): Naive datetime in `find()` swallowed as coverage miss.
</details>
