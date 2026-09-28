Status: SUBMITTED FOR REVIEW

## Identity

- Sprint ID: RW2-02 — Model registry and offline training services
- Owner: implementation owner (OpenCode session), final approval reserved for the independent reviewer
- Base SHA: `b6e974e`
- Code SHA: `784424e8b6a7042ee90d91d2da9ef361412ed53d`
- Branch: `feat/rw2-02-model-registry-and-offline-training-services`
- Environment: Windows, Python 3.14.0, ruff 0.16.9; worktree `.worktrees/feat-rw2-02`
- Handoff commit: `docs(rw2-02): submit model registry and training services for review`

## Scope Delivered

- `ModelRegistry` — content-addressed object store (`<root>/objects/<kind>/<artifact_id>/<version>/<sha256>`) plus SQLite identity rows (`<root>/registry.sqlite`, PK `(model_id, version)`); `put_bytes`/`object_path`/`read_object`/`register`/`load_verified`/`list_models`.
- Fail-closed verified loading: `read_object` re-hashes bytes against the reference; `load_verified` verifies manifest and every `artifact_refs` byte BEFORE any loader invocation (FR0), resolves the loader through a pinned allowlist (FR1), enforces the runtime gate (FR4), then checks bundle feature schema and bundle id/version against the manifest.
- Pinned loader allowlist (Step 1): `LOADER_ALLOWLIST = {"portable_bundle_json_v2": PortableBundleLoader().load_from_bytes}` (MappingProxyType), `ARCHITECTURE_LOADERS = {"m01_logistic": "portable_bundle_json_v2"}`; module function `resolve_loader(loader_id)` fails closed for anything else, at registration, load and listing time.
- Immutable versions (FR3): `register` refuses conflicting semantics under an existing `(model_id, version)` identity with `ImmutableVersionConflictError`; identical re-registration is idempotent; concurrent insert races wrap as the same conflict error.
- `ModelPredictor.predict_proba(FeatureFrame) -> ProbabilityVector` requires exact equality with `manifest.ordered_feature_schema` — no silent reorder, drop or extra columns (FR2).
- `list_models() -> tuple[ModelEntry, ...]` with four independent flags — `registered`/`verified` (byte re-hash)/`compatible` (static schema + loader contract)/`runtime_eligible` (probe) — plus an unregistered-object scan that lists raw model objects as `registered=False, reason NOT_REGISTERED:...` instead of substituting a look-alike model (AC5).
- `unmet_runtime_requirements(requirements, probe=...)`: accelerator/device needs `gpu_available is True` (False → `GPU_UNAVAILABLE`, None/failed read → `SENSOR_UNKNOWN:gpu_available`), torch keys use `check_torch_availability()`, unknown keys → `RUNTIME_REQUIREMENT_UNSUPPORTED:<key>` (fail-closed).
- `TrainingService.create/run/evaluate` — queue-backed JOB-01 lifecycle: `create` hash-verifies dataset refs and submits `job_type="train_model"` (recipe hash, resource class, config + refs in parameters); `run` claims the job, executes the runtime gate and pinned trainer dispatch, trains M01, stores bundle/calibration/preprocessing objects, publishes a new manifest version, stages `<root>/jobs/<job_id>.bundle.json` and completes the job with `expected_hash=manifest sha`; any failure ends `FAILED_FINAL` with a specific `<CODE>:` reason and the original exception is re-raised.
- `evaluate(model_ref, dataset_ref) -> EvaluationArtifact` — immutable evidence with `EvaluationStatus` COMPLETED/FAILED/INVALID: holdout split descriptor stored as a `split` object; empty holdout → INVALID `EVALUATION_SPLIT_EMPTY` with no metrics; predictor schema rejection → FAILED with the typed reason and `metrics={}`; otherwise `brier_score` (`probability_squared`) and `accuracy` (`ratio`) as `MetricValue`s. Validator forbids numeric defaults without evidence.
- `TrainingConfig` (frozen): `model_id`, `version`, `architecture`, `ordered_feature_schema`, `universe`, `runtime_requirements`, `trainer` (`M01Config`).

## Actual Paths

- `src/indodax_lab/models/registry.py` (created)
- `src/indodax_lab/models/training_service.py` (created)
- `tests/unit/lab/models/test_model_registry.py` (created)
- `src/indodax_lab/models/artifacts.py` — declared MODIFY, **unchanged**: ML-04 primitives (`PortableBundle`, `PortableBundleLoader`, `ArtifactRef` usage) already satisfy the spec; no new primitive was required.
- Untouched as required: `models/__init__.py`, `strategies/`, `orchestration/` source, `docs/sprints/sprint-manifest.json`.

## Acceptance Evidence (TDD RED → GREEN)

Behavioral RED — first cut with the five fail-closed guards intentionally absent, `python -m pytest tests/unit/lab/models/test_model_registry.py -q`, exit 1, `8 failed, 2 passed in 5.91s`:

- AC0 `test_rw2_02_0` — tampered bundle reached the loader (`ValueError: SCHEMA_VERSION_UNSUPPORTED...` instead of `ArtifactHashMismatchError`); hash check was missing (G1).
- AC1 `test_rw2_02_1` — `DID NOT RAISE LoaderNotAllowedError`; registration-time allowlist was missing (G2).
- AC2 `test_rw2_02_2` — permuted/extra frames silently predicted (`DID NOT RAISE FeatureSchemaMismatchError`); strict schema equality was missing (G3).
- AC3 `test_rw2_02_3` — conflicting re-registration `DID NOT RAISE ImmutableVersionConflictError` (`INSERT OR REPLACE` semantics) (G2).
- AC4 `test_rw2_02_4` — `DID NOT RAISE RuntimeBlockedError`; training ran without the runtime gate (G5).
- AC5 `test_rw2_02_program_5` — blocked entry reported `(True, True, True, True)` instead of `(True, True, True, False)` and no unregistered object was listed (G4).
- Also RED: `test_register_is_idempotent_and_conflicting_semantics_reject` (G2) and `test_evaluate_reports_failed_artifact_for_feature_schema_mismatch` (got COMPLETED — silent reorder — instead of FAILED; G3).
- Passed during RED: `test_evaluate_returns_completed_evaluation_artifact`, `test_evaluate_reports_invalid_artifact_for_empty_holdout` (guards not involved).

GREEN — after applying G1–G5, `python -m pytest tests/unit/lab/models/test_model_registry.py -q`, exit 0, `10 passed in 5.18s` at the code content committed as `784424e`.

## Checks (final code, in worktree, in gate order)

- `python -m pytest tests/unit/lab/models/test_model_registry.py -q` → 10 passed, exit 0.
- `python -m pytest tests/unit/lab/models -q` → 268 passed (baseline 258 + 10 new), exit 0.
- `python -m pytest tests/unit/lab -q` → 1469 passed (baseline 1459 + 10 new), exit 0, 69.58s.
- `python -m ruff check src/indodax_lab/models/registry.py src/indodax_lab/models/training_service.py tests/unit/lab/models/test_model_registry.py` → `All checks passed!` (import order fixed once via `--select I --fix`).
- `git diff --check` / `git diff --cached --check` → clean (only autocrlf LF/CRLF notice).
- Baselines before the change: models dir 258 passed, lab dir 1459 passed; `artifacts.py` untouched (9 pre-existing ruff findings unchanged).
- Test isolation: every stateful test uses `pytest.tmp_path` namespaces; datasets/models are synthetic in-process; no network, Telegram, production DB, credentials or real market data; no production or real-data runs.

## Decisions, Deviations and External Gates

- **BLOCKED_RESOURCE representation**: `JobStatus` (JOB-01 frozen contract) has no `BLOCKED_RESOURCE` member, so a missing runtime surfaces as `RuntimeBlockedError` (`code="BLOCKED_RESOURCE"`, message `BLOCKED_RESOURCE: GPU_UNAVAILABLE...`) plus job `FAILED_FINAL` with `error_message` starting `BLOCKED_RESOURCE` and `result_artifact_path is None`. No JOB-01 contract change.
- **Planned-file deviation**: `artifacts.py` required no modification (see Actual Paths).
- **Loader scope**: only M01's portable JSON bundle is allowlisted, as required by AC1's exact allowlist assertions. The M02 trainer exists in the repo but has no ML-04 portable packager/loader, and D01–D04 packagers are absent; those architectures therefore reject fail-closed at registration (`LOADER_NOT_ALLOWED`) and at training (`TRAINING_ARCHITECTURE_UNSUPPORTED`). Enabling them is a follow-up task that must extend both maps.
- **Loader input**: the loader contract is single-`bytes`; `load_verified` feeds the FIRST `artifact_refs` entry (all entries are hash-verified; M01 declares exactly one).
- **Dataset contract**: local JSON schema v1 (`feature_names`, `rows`, `labels`, `train_end`) defined by this task for ML splits — distinct from `DatasetManifest` (market-data lineage, RW0-01). Multiple refs are ordered partitions merged train-blocks-first then holdouts; training requires a non-empty holdout (`DATASET_HOLDOUT_REQUIRED`), evaluate maps an empty holdout to INVALID evidence.
- **Unregistered listing identity**: object-path-derived `(artifact_id, version)`; content-sha-only paths would alias identical bytes published under different identities, so identity is part of the path and content sha is the file name.
- **Queue wiring**: `resource_class` is declared in job parameters (`HIGH`, or `GPU` when an accelerator is declared) for JOB-01 admission metadata; this service does not call admission control itself.
- **Persistence**: new local SQLite registry + object tree under the configured root; single local connection, default journal (no shared cross-host WAL), UTC timestamps everywhere; job queue state is JOB-01's existing SQLite.
- Registered models, evaluation artifacts and this handoff do not qualify a candidate, grant Production authority, run on live data or prove profitability. Runtime/accelerator qualification, venue cost and promotion gates remain external.
- No live keys, live orders/ledger/state, production DB or running-host changes were accessed.

## Review Rounds

- Round 1: independent task review PASS by `ses_f18b2e183ffevXuqTz9CwgEQro`
  (did not implement the change) at tip `d47b863a695d980d3d51e9eacdfb0b85b610522f`
  (code `784424e8b6a7042ee90d91d2da9ef361412ed53d`), delta against BASE
  `b6e974e`; 4 files, +1890/-0. Verdict: **Spec PASS (AC0-AC5), task quality
  Approved-with-Minors — 0 Critical, 0 Important, 3 Minor.**
- Evidence re-run by the reviewer in the sprint worktree: focused
  `test_model_registry.py` 10 passed; `tests/unit/lab/models` 268 passed
  (258+10); `ruff check` on the 3 touched py files clean; `git diff --check`
  clean; all 6 manifest test names present verbatim; diff touches exactly the
  4 owned files (`artifacts.py` correctly untouched — pure ML-04 reuse).
- Behavior confirmed at the public service boundary: hash-before-loader with
  loader-call counting; pickle/remote rejection with exact allowlist sets;
  strict schema equality; new-version training with v1 byte/prediction
  invariance; BLOCKED_RESOURCE+FAILED_FINAL with no model published;
  four-flag listing with NOT_REGISTERED orphans and no substitution.
- Open concerns adjudicated clean: BLOCKED_RESOURCE-as-typed-error is
  CONTRACTS-consistent (frozen JobStatus has no resource member; BLOCKED_DATA
  / BLOCKED_POLICY would be wrong semantics); first-artifact feeding is safe
  (all refs hash-verified, M01 declares exactly one); task-local dataset JSON
  is properly distinct from RW0-01 DatasetManifest lineage; `run` correctly
  delegates to the leased JOB-01 runner (claim/complete/fail_job with
  fencing) while host-capacity admission takes out-of-interface inputs;
  reuse of PortableBundle/Loader, M01 trainer, queue and MetricValue is
  genuine.
- Backlog (Minor, non-blocking): (1) `ARCHITECTURE_LOADERS` mutable dict vs
  MappingProxyType allowlist — freeze it too (`registry.py:189`); (2) only
  `artifact_refs[0]` feeds the single-bytes loader — document or fire on
  `len != 1` for future multi-file formats (`training_service.py:579`);
  (3) duplicate-run-after-SUCCESS and concurrent-identical-register paths are
  guarded but untested — add both regression tests.
- Integration: merged to `dev` via merge commit (reviewed content
  byte-identical; dev-side S07-01 bookkeeping united, no conflicts).

## Minor fix round (Task 6 — 3 Minor backlog findings)

Status: fix owner submission for independent delta review.

- Owner: fix owner (OpenCode subagent session); branch `fix/minors-rw2-02`,
  worktree `.worktrees/fix-minors-rw2-02`, base `0c0d10d`.
- Files changed (scope exactly as briefed): `src/indodax_lab/models/registry.py`,
  `tests/unit/lab/models/test_model_registry.py`, this handoff.
  `src/indodax_lab/models/training_service.py` is in scope but **unchanged**;
  no other file touched (`docs/sprints/sprint-manifest.json` untouched).

### M1 — `ARCHITECTURE_LOADERS` frozen (registry.py)

- `ARCHITECTURE_LOADERS` is now `MappingProxyType({"m01_logistic":
  "portable_bundle_json_v2"})` typed `Mapping[str, str]`, so runtime mutation
  can no longer widen the pinned architecture→loader set (same treatment as
  `LOADER_ALLOWLIST`).
- Test `test_architecture_loaders_is_frozen_and_pinned_set_still_resolves`:
  item assignment and item deletion must raise `TypeError`; the pinned set
  still resolves end to end (`set == {"m01_logistic"}`, map entry in
  `LOADER_ALLOWLIST`, `load_verified` returns
  `loader_id == "portable_bundle_json_v2"`, `resolve_loader("smuggled_arch")`
  still raises `LOADER_NOT_ALLOWED`).

### M2 — no silent first-artifact feeding (`load_verified`)

- `load_verified` now rejects `len(manifest.artifact_refs) != 1` with
  `ModelManifestInvalidError` / reason code `ARTIFACT_REFS_SINGLE_REQUIRED`
  **before** any loader invocation; `artifact_bytes[0]` feeding is guarded, not
  a convention. Registration-time `ARTIFACT_REFS_REQUIRED` for empty refs is
  unchanged, so len 0 is blocked at the entry point and can no longer reach
  the load path in practice; `register` still accepts multi-ref manifests
  (every ref hash-verified) but such a manifest can no longer load —
  fail-closed preserved, no rejection became a success.
- Test `test_load_verified_rejects_artifact_ref_counts_other_than_one`: len 0
  refused at registration (`ARTIFACT_REFS_REQUIRED`) and, via a forced
  manifest reader, at load (`ARTIFACT_REFS_SINGLE_REQUIRED`); len 2 registered
  then refused at load with **zero loader calls** (call-counting
  `resolve_loader`); the pinned single-ref path still loads afterwards.

### M3 — duplicate-path regression tests (no production change)

- Both guards already existed; only tests were missing.
- Test `test_duplicate_run_after_success_and_concurrent_identical_register_stay_guarded`:
  (a) a second `TrainingService.run` on a `SUCCESS` job raises
  `TrainingJobStateError` (`TRAINING_JOB_STATE`) while job status,
  `result_artifact_path`, registry listing and model bytes stay unchanged;
  (b) two barrier-synchronized threads register the identical manifest — both
  pass the existing-row SELECT before either INSERT — exactly one row is
  published, the loser receives `ImmutableVersionConflictError`
  ("registered concurrently"), bytes equal `canonical_bytes(manifest)`, and a
  later identical register is idempotent with no duplicate row.

### TDD evidence (RED → GREEN)

- RED A (tests added, guards absent): focused suite `2 failed, 11 passed`,
  exit 1 — `DID NOT RAISE TypeError` (M1) and `DID NOT RAISE
  ModelManifestInvalidError` for the len-2 manifest (M2). M3's guards already
  exist, so its RED was demonstrated by temporarily removing each guard.
- RED B (both M3 guards temporarily removed): `3 failed, 10 passed`, exit 1 —
  duplicate run leaked `TrainingNotClaimableError` instead of
  `TrainingJobStateError`; with the duplicate-run guard restored alone, the
  concurrent loser leaked `sqlite3.IntegrityError` instead of
  `ImmutableVersionConflictError`. Both guards restored immediately after.
- GREEN (fixes applied): focused suite `13 passed`, exit 0.

### Gates (worktree, in briefed order)

- `python -m pytest tests/unit/lab/models/test_model_registry.py -q` →
  13 passed, exit 0 (baseline 10 + 3 new).
- `python -m pytest tests/unit/lab/models -q` → 271 passed, exit 0
  (baseline 268 + 3).
- `python -m pytest tests/unit/lab -q` → 1477 passed (1 pre-existing
  `FutureWarning` from untouched `tests/unit/lab/strategies/test_s07.py`),
  exit 0.
- `python -m ruff check src/indodax_lab/models/registry.py
  src/indodax_lab/models/training_service.py
  tests/unit/lab/models/test_model_registry.py` → `All checks passed!`, exit 0.
- `git diff --check` → clean, exit 0.
- Test isolation unchanged: `pytest.tmp_path` namespaces, synthetic in-process
  datasets/models, no network, Telegram, production DB, credentials or real
  market data; fixture numbers are test-only.
