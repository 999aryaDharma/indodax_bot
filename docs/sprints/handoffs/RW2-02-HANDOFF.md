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

- Round 1: pending — comprehensive review of code SHA `784424e8b6a7042ee90d91d2da9ef361412ed53d`.
