# C02-01 handoff

Status: REVIEW

## Identity
- Sprint ID: C02-01 — EMA pullback
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/c02-01-ema-pullback`
- Base SHA: `72bba7e`
- Code target: `feat(c02-01): ema pullback`
- Evidence SHA relation: `03478f53b4208f898b520b268584be4c5a6d8671`

## Files and contracts
- Planned files:
  - `src/indodax_lab/strategies/c02.py` (load_c02_specification, c02_decide)
  - `src/indodax_lab/strategies/__init__.py` (Package exports)
  - `configs/strategies/C02_v1.yaml` (Canonical C02 configuration)
  - `tests/unit/lab/strategies/test_c02.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `Long EMA regime plus short EMA pullback and recovery -> versioned LONG/FLAT intent, never direct orders.`
  - Stateless decision function over causal `DecisionFrame`; long-only spot intents (`BUY` / `SELL`, positive desired qty).
  - Downtrend filter (`close <= slow_ema` or `fast_ema <= slow_ema`) strictly rejects buy intents.
  - Pullback below fast EMA must be confirmed by a subsequent closed bar recovering above fast EMA before entry.
  - Unrecovered pullback produces FLAT (empty intents).
  - Strategies only produce declarative order intents (`SignalIntent`); zero authority over fills, executions, or ledger balances.
- Migration and compatibility:
  - Additive classical strategies catalog; backward compatible.
  - Dependencies: STRAT-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| C02-01-AC0 (RED) | `test_c02_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_c02.py` | Exit 1 (Failed: assert 0 == 1) | `working tree` |
| C02-01-AC0 (GREEN) | `test_c02_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_c02.py::test_c02_01_valid_contract` | Exit 0 (Passed, produces valid BUY SignalIntent with ATR stop) | `03478f5` |
| C02-01-AC1 (RED) | `test_c02_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_c02.py` | Exit 0 (Initial pass / returns empty) | `working tree` |
| C02-01-AC1 (GREEN) | `test_c02_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_c02.py::test_c02_01_contract_1` | Exit 0 (Passed, downtrend strictly rejects buy) | `03478f5` |
| C02-01-AC2 (RED) | `test_c02_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_c02.py` | Exit 0 (Initial pass / returns empty) | `working tree` |
| C02-01-AC2 (GREEN) | `test_c02_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_c02.py::test_c02_01_contract_2` | Exit 0 (Passed, unrecovered pullback does not enter) | `03478f5` |
| C02-01-AC3 (RED) | `test_c02_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_c02.py` | Exit 1 (Failed: assert 0 == 1) | `working tree` |
| C02-01-AC3 (GREEN) | `test_c02_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_c02.py::test_c02_01_contract_3` | Exit 0 (Passed, recovery closed bar emits LONG intent) | `03478f5` |

All 4 tests in `tests/unit/lab/strategies/test_c02.py` passed (1.34s).
Combined suite verification (84 passed across backtest, risk, execution, ledger, costs, features, labels, strategies, and evaluation) passed (2.26s).

## Review
- Spec verdict: PASS (meets all functional requirements of C02-01 and specs/10-strategy-catalog-and-protocol.md).
- Quality verdict: PASS (pure stateless decision protocol, zero ledger mutation, strict causality, downtrend rejection, and pullback recovery confirmation).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for C02-01.
- Next unlocked consumers: QA-01.
