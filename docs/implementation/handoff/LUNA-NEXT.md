# LUNA-NEXT — RW0-01 only

## TASK ID

RW0-01 — Immutable Workbench domain manifests.

Current scheduling status: READY after RP-01 completion (full-suite PASS on research environment verified by Delivery Coordinator) and DATA-01 DONE in manifest. RW0-01 is the sole eligible program task.

## OBJECTIVE

Implement deep immutable domain manifests, typed artifact references, and canonical digest functions in `indodax_lab.contracts` (`identity.py` and `workbench.py`), providing the foundation for Workbench registries, typed pipelines, and candidate lifecycle.

## ARCHITECTURAL CONTEXT

Frozen two-system architecture (`docs/production/FROZEN-SYSTEMS.md`, `docs/production/research-workbench/DOMAIN-AND-LIFECYCLE.md`, `docs/implementation/CONTRACTS.md`, `ADR-002`, `ADR-005`). Research Workbench requires deterministic, immutable portable identities:
1. `ArtifactRef`: Identifies verified bytes via lowercase 64-hex SHA-256 and opaque non-path IDs/versions.
2. Canonical JSON encoding: `canonical_bytes()` produces sorted-key, compact-separator, UTC ISO8601 with `Z`, Decimal non-exponent string serialization.
3. `manifest_digest()`: Computes lowercase SHA-256 over canonical semantic bytes, excluding audit timestamps and the digest itself.
4. Domain manifests: `DatasetManifest`, `StrategyManifest`, `ModelManifest`, `PipelineManifest`, `ExperimentManifest`, `RuntimePlan`, `CandidateManifest`, `AgentManifest`.
5. Shared service envelope: `ServiceError`, `Provenance`, `MetricValue`, `ServiceResponse`.

## ALLOWED SCOPE

- Create `src/indodax_lab/contracts/identity.py` (ArtifactRef, canonical_bytes, manifest_digest, base immutable models).
- Create `src/indodax_lab/contracts/workbench.py` (domain manifests, ServiceError, Provenance, MetricValue, ServiceResponse).
- Update `src/indodax_lab/contracts/__init__.py` to re-export canonical contracts.
- Create comprehensive unit test suite `tests/unit/lab/test_workbench_contracts.py`.
- Record handoff at `docs/sprints/handoffs/RW0-01-HANDOFF.md`.

## DO NOT TOUCH

- Do not modify `dashboard.pen` or `DESIGN.md`.
- Do not touch live trading, execution clients, order routers, production DBs, or exchange network calls.
- Do not introduce runtime persistence in RW0-01 (stores and registries belong to RW1-01 / RW2-01 / PM-02).
- Do not modify existing historical test fixtures or `src/indodax_lab/contracts/decision.py`.
- Do not touch `main` or `dev` branches.

## PRECONDITIONS

- RP-01 status is DONE in `docs/sprints/sprint-manifest.json` (verified with full suite 941 PASS).
- DATA-01 status is DONE in `docs/sprints/sprint-manifest.json`.
- RW0-01 status is READY in manifest.
- Isolated worktree/branch: `feat/rw0-01-immutable-workbench-domain-manifests`.
- Use declared research environment (`C:\Users\User\miniconda3\envs\ML\python.exe`) with pandas, pyarrow, scipy.

## IMPLEMENTATION STEPS

1. Create `tests/unit/lab/test_workbench_contracts.py` with targeted RED test cases for RW0-01-AC0 through RW0-01-AC5:
   - AC0: Key reordering produces identical digest; local-root relocation does not affect it.
   - AC1: Nested mutation cannot change published/created manifest (deep immutability).
   - AC2: Changing risk policy, model, feature schema, or seed produces distinct manifest identity.
   - AC3: Extra fields, naive datetimes, non-finite numbers (NaN/Infinity), and invalid SHA-256 hashes reject fail-closed.
   - AC4: Terminal experiment configuration rejects modification.
   - AC5: RuntimePlan can be verified before any completed experiment exists (bootstrap recovery).
2. Implement `src/indodax_lab/contracts/identity.py`:
   - `ArtifactRef` with validation for lowercase 64-hex sha256 and non-path IDs.
   - `canonical_bytes(value)` producing deterministic UTF-8 JSON.
   - `manifest_digest(value)` returning lowercase hex digest of semantic bytes.
3. Implement `src/indodax_lab/contracts/workbench.py`:
   - Domain manifests inheriting frozen immutable base models:
     `DatasetManifest`, `StrategyManifest`, `ModelManifest`, `PipelineManifest`,
     `ExperimentManifest`, `RuntimePlan`, `CandidateManifest`, `AgentManifest`.
   - Shared result envelopes: `ServiceError`, `Provenance`, `MetricValue`, `ServiceResponse`.
4. Update `src/indodax_lab/contracts/__init__.py` with clean lazy or direct exports.
5. Run focused tests, full test suite, linting, and diff check:
   - `python -m pytest tests/unit/lab/test_workbench_contracts.py -q`
   - `ruff check src/indodax_lab/contracts tests/unit/lab/test_workbench_contracts.py`
   - `python -m pytest -q`
   - `git diff --check`
6. Prepare `docs/sprints/handoffs/RW0-01-HANDOFF.md` with observed TDD evidence and submit for independent review.

## FILES

- Create `src/indodax_lab/contracts/identity.py`
- Create `src/indodax_lab/contracts/workbench.py`
- Modify `src/indodax_lab/contracts/__init__.py`
- Create `tests/unit/lab/test_workbench_contracts.py`
- Create `docs/sprints/handoffs/RW0-01-HANDOFF.md`

## TESTS

```text
python -m pytest tests/unit/lab/test_workbench_contracts.py -q
ruff check src/indodax_lab/contracts tests/unit/lab/test_workbench_contracts.py
python -m pytest -q
git diff --check
```

## ACCEPTANCE CHECKS

- RW0-01-AC0: `test_rw0_01_0` passes. Key reordering invariant verified.
- RW0-01-AC1: `test_rw0_01_1` passes. Nested mutation frozen/rejected.
- RW0-01-AC2: `test_rw0_01_2` passes. Field changes alter semantic digest.
- RW0-01-AC3: `test_rw0_01_3` passes. Extra fields, naive time, NaN/Inf reject with ValidationError.
- RW0-01-AC4: `test_rw0_01_4` passes. Terminal experiment immutability verified.
- RW0-01-AC5: `test_rw0_01_bootstrap_recovery` passes. RuntimePlan verification without prior experiment.
- Zero regressions in full pytest suite (941+ tests pass).

## EXPECTED OUTPUT

- Independently reviewable committed unit and exact-SHA handoff.
- Manifest remains READY during implementation, moving to REVIEW on handoff submission.
- Once RW0-01 is DONE, downstream tasks `RW1-01`, `RW2-01`, `RW2-02`, `RP-03`, `PM-01`, `PM-02` become eligible for evaluation.

## STOP CONDITIONS

- Any proposed change to live trading, venue adapter, or execution logic.
- Naive datetime or non-UTC timezone acceptance.
- Mutable manifest fields or ambient timestamps contaminating semantic digest.
- Failure of full-suite regression test.
- Attempting to install packages into base environment.
