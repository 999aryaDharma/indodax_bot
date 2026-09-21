# RW0-01 Handoff — Immutable Workbench domain manifests

Status: REVIEW — implementation complete; independent review requested

## Identity

- Task: RW0-01
- Implementation owner: Codex `/root` (LUNA execution)
- Independent reviewer: `/root/architecture_doc_review`
- Base SHA: `9e29469`
- Code SHA: `db5905c`
- Branch: `docs/architecture-runtime-plan`
- Scope: deep immutable domain manifests, artifact references, and canonical digest functions

## Implemented

- Added `ArtifactRef` at `src/indodax_lab/contracts/identity.py`: validates opaque non-path IDs/versions, lowercase 64-hex SHA-256, and frozen immutability.
- Added deterministic canonical JSON encoding `canonical_bytes()`: sorts keys, compact separators (`,`, `:`), enforces UTC timestamps formatted with `Z`, serializes Decimals as normalized non-exponent strings, and rejects non-finite floats/Decimals.
- Added `manifest_digest()`: computes lowercase SHA-256 over canonical semantic fields while strictly excluding audit timestamps and digest fields.
- Added base class `ImmutableManifest` with automatic semantic digest derivation and `to_artifact_ref()` mapping.
- Added domain manifests at `src/indodax_lab/contracts/workbench.py`:
  - `DatasetManifest`: dataset partition boundaries, actual/requested ranges, quality report ref, and missing intervals.
  - `StrategyManifest`: strategy family/version, parameter schema, parameters, and contract versions.
  - `ModelManifest`: architecture, artifact refs, ordered feature schema, evidence refs, and runtime requirements.
  - `PipelineManifest`: typed nodes, edges, dataset timeframe constraints, sizing/exit/risk/cost policy refs.
  - `ExperimentManifest`: dataset/pipeline refs, virtual cash Decimal, currency, policies, seed, and lifecycle status.
  - `RuntimePlan`: resolved pipeline/dataset/policy refs, feature schema hash, git/env identity, and seed without requiring prior experiments.
  - `CandidateManifest`: RuntimePlan ref, completed experiment ref, pipeline ref, hashes, and evaluation evidence refs.
  - `AgentManifest`: candidate ref, cohort ID, virtual cash, policy refs, namespace ID, and feed identity.
- Added terminal experiment immutability: `TerminalExperimentLockedError` raised when attempting to modify or update the status of an experiment in terminal state (`COMPLETED`, `FAILED`, `CANCELLED`).
- Added bootstrap recovery: `VerifiedRuntimePlan` and `verify_runtime_plan()` to verify runtime plans before completed experiments exist.
- Added shared service envelopes: `ServiceError`, `Provenance`, `MetricValue` (with strict non-finite guards), `ServiceResponse` (with mutually exclusive data or error).
- Re-exported all canonical domain contracts at `src/indodax_lab/contracts/__init__.py`.

## Observed TDD evidence

- RED: `python -m pytest tests/unit/lab/test_workbench_contracts.py -q` failed during collection with expected `ModuleNotFoundError: No module named 'indodax_lab.contracts.identity'`.
- GREEN focused: `python -m pytest tests/unit/lab/test_workbench_contracts.py -q` → 11 passed in 0.41s.
- Targeted Ruff: `ruff check src/indodax_lab/contracts tests/unit/lab/test_workbench_contracts.py` → all checks passed (exit 0).
- Bytecode compilation: `python -m compileall -q src` → exit 0.
- Full suite gate: `python -m pytest -q` → 952 passed, 2 skipped, 0 failed in 34.76s (exit 0).
- Whitespace check: `git diff --check` → exit 0.

## Acceptance Criteria Mapping

- RW0-01-AC0 (`test_rw0_01_0`): Key reordering gives same digest; local-root relocation cannot affect it. PASS.
- RW0-01-AC1 (`test_rw0_01_1`): Nested mutation cannot change published manifest. PASS.
- RW0-01-AC2 (`test_rw0_01_2`): Changed risk/model/feature/seed changes identity. PASS.
- RW0-01-AC3 (`test_rw0_01_3`): Extra fields, naive time, NaN and invalid hash reject. PASS.
- RW0-01-AC4 (`test_rw0_01_4`): Terminal experiment configuration cannot be edited. PASS.
- RW0-01-AC5 (`test_rw0_01_bootstrap_recovery`): Runtime plan can be verified before any completed experiment exists. PASS.

## Compatibility and migration

Additive domain contracts in `indodax_lab.contracts`. Existing `SignalIntent`, `CanonicalPair`, `CandleRecord`, and `TradeEvent` contracts remain 100% backward compatible and unchanged.

## Safety and scope checks

- No credentials, real order authority, network calls, runtime databases, or production activation were used.
- No `main` or `dev` branch change, merge, push, or deployment.
- No product-path files outside declared RW0-01 scope were modified.
- `dashboard.pen` and `DESIGN.md` were preserved and untouched.

## Reviewer decision

Submitted for independent review on code SHA `db5905c`.
