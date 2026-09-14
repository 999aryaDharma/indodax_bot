# STRAT-01 handoff

Status: REVIEW

## Identity
- Sprint ID: STRAT-01 — Declarative strategy protocol
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/strat-01-declarative-strategy-protocol`
- Base SHA: `6cf2899`
- Code target: `feat(strat-01): declarative strategy protocol`
- Evidence SHA relation: `5687c100782c6b62de53d643d855df232f6ff7ba`

## Files and contracts
- Planned files:
  - `src/indodax_lab/strategies/base.py` (StrategySpecification, DecisionFrame, create_decision_frame, RegisteredStrategy)
  - `src/indodax_lab/strategies/registry.py` (StrategyRegistry)
  - `src/indodax_lab/strategies/__init__.py` (Package exports)
  - `tests/unit/lab/strategies/test_registry.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `StrategySpecification + DecisionFrame -> list[SignalIntent]; ID/version/family/timeframes/risk/split required.`
  - Stateless decision functions over causal `DecisionFrame`; long-only spot intents (`BUY` / `SELL`, positive desired qty).
  - Registered strategies only produce declarative order intents (`SignalIntent`); zero authority over fills, executions, or ledger balances.
  - Unknown config fields strictly rejected via `extra="forbid"`.
  - Future rows (`decision_ts > as_of` or `row_ready_at > as_of`) and ineligible rows (`eligible == False`) are strictly prohibited from entering `DecisionFrame`.
  - Parameter or logic changes under the same strategy ID require an explicit semantic version bump.
- Migration and compatibility:
  - Additive strategies subsystem; backward compatible.
  - Dependencies: SIM-03 (DONE), FEAT-04 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| STRAT-01-AC0 (RED) | `test_strat_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_registry.py` | Exit 1 (Failed: DID NOT RAISE `TypeError: ONLY_SIGNAL_INTENT_ALLOWED`) | `working tree` |
| STRAT-01-AC0 (GREEN) | `test_strat_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_registry.py::test_strat_01_valid_contract` | Exit 0 (Passed, strategies only produce SignalIntent and cannot execute fills/ledger) | `5687c10` |
| STRAT-01-AC1 (RED) | `test_strat_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_registry.py` | Exit 1 (Failed: DID NOT RAISE `ValidationError`) | `working tree` |
| STRAT-01-AC1 (GREEN) | `test_strat_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_registry.py::test_strat_01_contract_1` | Exit 0 (Passed, unknown config fields strictly rejected) | `5687c10` |
| STRAT-01-AC2 (RED) | `test_strat_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_registry.py` | Exit 1 (Failed: AssertionError, future/ineligible rows present in DecisionFrame) | `working tree` |
| STRAT-01-AC2 (GREEN) | `test_strat_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_registry.py::test_strat_01_contract_2` | Exit 0 (Passed, future and ineligible rows strictly excluded from DecisionFrame) | `5687c10` |
| STRAT-01-AC3 (RED) | `test_strat_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_registry.py` | Exit 1 (Failed: DID NOT RAISE `ValueError: PARAMETER_OR_LOGIC_CHANGE_REQUIRES_VERSION_BUMP`) | `working tree` |
| STRAT-01-AC3 (GREEN) | `test_strat_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_registry.py::test_strat_01_contract_3` | Exit 0 (Passed, parameter and logic modifications require semantic version bump) | `5687c10` |

All 4 tests in `tests/unit/lab/strategies/test_registry.py` passed (1.02s).
Combined suite verification (63 passed across backtest, risk, execution, ledger, costs, features, labels, and strategies) passed (2.20s).

## Review
- Spec verdict: PASS (meets all functional requirements of STRAT-01 and specs/10-strategy-catalog-and-protocol.md).
- Quality verdict: PASS (pure stateless decision protocol, zero ledger mutation, strict causality, fail-closed config validation).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: Added test package `__init__.py` markers under `tests/unit/lab/` to resolve pytest import module collision between feature and strategy registries.
- Unresolved issues / blockers: None for STRAT-01.
- Next unlocked consumers: C01-01, C07-01, C02-01, C03-01, C04-01, S01-01, S02-01, C05-01, C06-01, C08-01, C09-01, C11-01, S03-01, S04-01, S05-01, S06-01, S08-01, S09-01.
