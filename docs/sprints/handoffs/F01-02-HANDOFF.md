# F01-02 handoff

Status: REVIEW

## Identity
- Sprint ID: F01-02 — Staged foundation adaptation
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/f01-02-staged-foundation-adaptation`
- Base SHA: `c547eaf`
- Code target: `feat(f01-02): staged foundation adaptation`
- Evidence SHA relation: `e9fcd91`

## Files and contracts
- Planned files:
  - `src/indodax_lab/models/foundation/f01_kronos.py` (StagedFoundationAdapter, FoundationAdaptationConfig, StageEvaluationResult, AdaptationStage, StagePreconditionNotMetError, FullFineTuneForbiddenError, ContaminatedDatesClaimError)
  - `tests/unit/lab/models/test_f01_02.py` (AC0..AC3 test cases)
- Contract:
  - `Zero-shot then frozen probe then bounded adapter tuning -> comparable post-cutoff results`
  - Sequential adaptation pipeline: Evaluates zero-shot baseline, frozen probe, and low-rank bounded adapter consecutively, routing forecasts to `CostAwareExecutionMapper` (F01-02-AC0).
  - Stage documentation & lineage: Skipping stages (e.g. running frozen probe without zero-shot, or adapter without probe) is rejected fail-closed with `StagePreconditionNotMetError` (F01-02-AC1).
  - Non-default fine tuning: Full fine-tuning is barred by default and raises `FullFineTuneForbiddenError` without explicit owner authorization (F01-02-AC2).
  - Pre-cutoff date isolation: Test observations occurring before or during the external training cutoff date are barred fail-closed (`ContaminatedDatesClaimError`) to protect sealed benchmark validity (F01-02-AC3).
- Migration and compatibility:
  - Additive module `src/indodax_lab/models/foundation/f01_kronos.py` with zero breaking changes to existing models.
  - Dependencies: F01-01 (REVIEW), D01-01 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| F01-02-AC0 (RED) | `test_f01_02_valid_contract` | `python -m pytest tests/unit/lab/models/test_f01_02.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.foundation.f01_kronos') | `working tree` |
| F01-02-AC0 (GREEN) | `test_f01_02_valid_contract` | `python -m pytest tests/unit/lab/models/test_f01_02.py::test_f01_02_valid_contract` | Exit 0 (Passed, zero-shot, probe, and bounded adapter stages completed and mapped to execution decisions) | `e9fcd91` |
| F01-02-AC1 (RED) | `test_f01_02_contract_1` | `python -m pytest tests/unit/lab/models/test_f01_02.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| F01-02-AC1 (GREEN) | `test_f01_02_contract_1` | `python -m pytest tests/unit/lab/models/test_f01_02.py::test_f01_02_contract_1` | Exit 0 (Passed, skipping adaptation stages rejected fail-closed) | `e9fcd91` |
| F01-02-AC2 (RED) | `test_f01_02_contract_2` | `python -m pytest tests/unit/lab/models/test_f01_02.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| F01-02-AC2 (GREEN) | `test_f01_02_contract_2` | `python -m pytest tests/unit/lab/models/test_f01_02.py::test_f01_02_contract_2` | Exit 0 (Passed, full fine-tuning rejected fail-closed without explicit authorization) | `e9fcd91` |
| F01-02-AC3 (RED) | `test_f01_02_contract_3` | `python -m pytest tests/unit/lab/models/test_f01_02.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| F01-02-AC3 (GREEN) | `test_f01_02_contract_3` | `python -m pytest tests/unit/lab/models/test_f01_02.py::test_f01_02_contract_3` | Exit 0 (Passed, contaminated pre-cutoff dates barred from sealed benchmark claims) | `e9fcd91` |

All 4 tests in `tests/unit/lab/models/test_f01_02.py` passed (1.89s).
Full lab suite verification: 251 passed across all domains.

## Review
- Spec verdict: PASS (meets all requirements of F01-02 and docs/specs/15-deep-learning-and-provenance.md).
- Quality verdict: PASS (sequential stages verified, strict non-default fine-tune guard, pre-cutoff contamination defense).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for F01-02.
- Next unlocked consumers: Research comparison complete.
