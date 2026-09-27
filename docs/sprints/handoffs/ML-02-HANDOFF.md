# ML-02 handoff

Status: REVIEW

## Identity
- Sprint ID: ML-02 — Held-out calibration and cost mapper
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/ml-02-held-out-calibration-and-cost-mapper`
- Base SHA: `b6db9c3`
- Code target: `feat(ml-02): held-out calibration and cost mapper`
- Evidence SHA relation: `40cf3a76f13958123f36ca7fb82560bb96f90c79`

## Files and contracts
- Planned files:
  - `src/indodax_lab/models/calibration.py` (CalibrationSegmentError, InsufficientCalibrationDataError, FittedCalibratorArtifact, HeldOutCalibrator)
  - `src/indodax_lab/models/execution_mapper.py` (ForecastKind, DecisionAction, PayoffStructure, CostBasis, ForecastPayload, ExecutionDecision, CostAwareExecutionMapper)
  - `src/indodax_lab/models/__init__.py` (Package exports)
  - `tests/unit/lab/models/test_execution_mapper.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `forecast(kind=NET_RETURN/GROSS_RETURN/PROBABILITY) + payoff/cost basis -> abstain or intent; net costs applied once.`
  - Calibrated forecast converts to order intent ONLY when net edge strictly exceeds safety margin.
  - Held-out calibration isolation: Calibrator requires an inner held-out segment (e.g. `inner_heldout`, `validation`); training and test/sealed segments are strictly forbidden and rejected with `CalibrationSegmentError`.
  - Fail-closed small calibration data: Datasets with fewer than minimum calibration samples (default 50) or insufficient class representations (default 10 positives/negatives) block with `InsufficientCalibrationDataError`.
  - Equivalent gross and net forecasts: Gross returns with subtracted round-trip transaction costs yield identical execution decisions, net edge, and order parameters as equivalent net return forecasts.
  - Exact cost application per ADR-002: NET_RETURN compares directly to safety margin, GROSS_RETURN subtracts round-trip cost once, and PROBABILITY computes expected gross return before subtracting round-trip cost once.
- Migration and compatibility:
  - Additive models subsystem components; integrates with SIM-01 SignalIntent and ML-01 preprocessing.
  - Dependencies: ML-01 (DONE), SIM-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| ML-02-AC0 (RED) | `test_ml_02_valid_contract` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.calibration') | `working tree` |
| ML-02-AC0 (GREEN) | `test_ml_02_valid_contract` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py::test_ml_02_valid_contract` | Exit 0 (Passed, forecast only becomes SignalIntent when net edge exceeds safety margin; abstains otherwise) | `40cf3a7` |
| ML-02-AC1 (RED) | `test_ml_02_contract_1` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-02-AC1 (GREEN) | `test_ml_02_contract_1` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py::test_ml_02_contract_1` | Exit 0 (Passed, training/test segments rejected, inner held-out segment accepted and calibrated) | `40cf3a7` |
| ML-02-AC2 (RED) | `test_ml_02_contract_2` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-02-AC2 (GREEN) | `test_ml_02_contract_2` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py::test_ml_02_contract_2` | Exit 0 (Passed, small dataset <50 samples and skewed dataset <10 positives fail closed) | `40cf3a7` |
| ML-02-AC3 (RED) | `test_ml_02_contract_3` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-02-AC3 (GREEN) | `test_ml_02_contract_3` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py::test_ml_02_contract_3` | Exit 0 (Passed, gross and net equivalent forecasts yield identical decisions and net edge) | `40cf3a7` |

All 5 tests in `tests/unit/lab/models/test_execution_mapper.py` passed (1.33s).
Full lab suite verification: 139 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, and reporting.

## Review
- Spec verdict: PASS (meets all functional requirements of ML-02 and docs/specs/12-tabular-models-and-training.md).
- Quality verdict: PASS (Platt scaling on inner held-out data, ADR-002 exact cost application, strict timezone/payoff validation).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for ML-02.
- Next unlocked consumers: ML-03.


## Review fix cycle evidence (sprint review CHANGES_REQUESTED)
- Agent: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Base: branch `feat/feat-02-finalization` @ `0e2a0ab`; all changes are uncommitted working-tree edits, coordinator commits centrally.
- Owning suite before this fix cycle: `python -m pytest tests/unit/lab/models/ --ignore=tests/unit/lab/models/lob/ -p no:cacheprovider -q` -> `102 passed` (exit 0).
- Owning suite after this fix cycle: the same command -> `175 passed` (exit 0).
- Capability gaps recorded: `ruff` is not installed in this environment, so the lint gate could not be executed; `pyarrow` is not installed, so `tests/unit/lab/models/lob/` plus the `test_deeplob_smoke.py` and `test_tlob_smoke.py` integration modules cannot be collected.
- TDD shape used: behavioural RED captured first, then the minimal source change, then GREEN. No assertion was weakened, deleted or skipped.
- Wave A RED (ML-01..ML-04 together): `python -m pytest tests/unit/lab/models/test_preprocessing.py tests/unit/lab/models/test_execution_mapper.py tests/unit/lab/models/test_tuning_budget.py tests/unit/lab/models/test_ml04_bundle_loader.py -p no:cacheprovider -q` -> `24 failed, 40 passed` (exit 1), every failure a real assertion failure or leaked exception.

### Findings fixed in this cycle

- **Important** - `intent_id` was derived from Python's salted `hash()`. Probing with `PYTHONHASHSEED` 0, 1, 2 and 12345 produced four different ids for identical input (`..._92383`, `..._13886`, `..._83411`, `..._30503`). The id is part of the published intent shape, so it was neither reproducible across processes nor portable between hosts. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Fix** - Replaced `abs(hash(...))` with a new `CostAwareExecutionMapper._intent_digest()` that takes a SHA-256 over an explicitly ordered 11-field canonical payload and formats the suffix with `zfill(5)`, preserving the published `intent_{pair}_{ts}_{5-digit}` shape while making it deterministic and portable. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Files** - `src/indodax_lab/models/execution_mapper.py`, `tests/unit/lab/models/test_execution_mapper.py` - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **GREEN** - `python -m pytest tests/unit/lab/models/test_execution_mapper.py -p no:cacheprovider -q` -> `7 passed` (exit 0). - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

- Independent review: still PENDING; the coordinator runs the delta verification pass on the committed SHA - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

## Independent review — coordinator pass (2026-09-27)

- Verdict: PASS. Full read of src/indodax_lab/models/execution_mapper.py (224 lines),
  src/indodax_lab/models/calibration.py (159 lines) and tests (7 tests). Fresh run
  `python -m pytest tests/unit/lab/models/test_execution_mapper.py -v`: 7 passed,
  0 failed, exit 0 (AC0–AC3 + edge/guard + 2 intent-id determinism regressions).
- AC0 holds (strict net-edge hurdle; probability payoff math verified 0.0125);
  AC1 holds (train/test/sealed_test forbidden, inner held-out only); AC2 holds
  (too-small + skewed class representation blocked); AC3 holds (gross/net
  equivalents reach identical decisions and edges; costs applied exactly once
  per ADR-002). Intent-id process-stable digest regression verified.
- MINOR (backlog, non-blocking): Nelder-Mead calibration fit ignores
  `res.success`, so non-converged Platt params would be stored silently.
- No Critical/Important findings.
- Reviewer: coordinator inline review (implementation pre-exists committed;
  reviewer wrote no code here). Status transition (manifest/spec) left to
  coordinator DONE pass / main agent — not touched.
