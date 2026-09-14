# C07-01 handoff

Status: REVIEW

## Identity
- Sprint ID: C07-01 — Bollinger RSI reversion
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/c07-01-bollinger-rsi-reversion`
- Base SHA: `92b4a5c`
- Code target: `feat(c07-01): bollinger rsi reversion`
- Evidence SHA relation: `6b0be47f0c512fb345b3e8aa9297c787a83b7593`

## Files and contracts
- Planned files:
  - `src/indodax_lab/strategies/c07.py` (load_c07_specification, c07_decide)
  - `src/indodax_lab/strategies/__init__.py` (Package exports)
  - `configs/strategies/C07_v1.yaml` (Canonical C07 configuration)
  - `tests/unit/lab/strategies/test_c07.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `Extreme BB and RSI deviation only under available sideways regime -> versioned LONG/FLAT intent, never direct orders.`
  - Stateless decision function over causal `DecisionFrame`; long-only spot intents (`BUY` / `SELL`, positive desired qty).
  - Strong downtrend (`regime in ("downtrend", "strong_downtrend")` or negative DI spread with high ADX) strictly rejects entry to avoid falling-knife risk.
  - Sideways regime combined with extreme oversold (`bb_z <= -bb_std` and `rsi <= rsi_oversold`) produces bounded LONG `SignalIntent` with ATR stop-loss and take-profit.
  - Zero or degenerate band width produces abstain (FLAT / empty intents).
  - Strategies only produce declarative order intents (`SignalIntent`); zero authority over fills, executions, or ledger balances.
- Migration and compatibility:
  - Additive classical strategies catalog; backward compatible.
  - Dependencies: STRAT-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| C07-01-AC0 (RED) | `test_c07_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_c07.py` | Exit 1 (Failed: assert 0 == 1) | `working tree` |
| C07-01-AC0 (GREEN) | `test_c07_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_c07.py::test_c07_01_valid_contract` | Exit 0 (Passed, produces valid BUY SignalIntent with ATR stop and take-profit) | `6b0be47` |
| C07-01-AC1 (RED) | `test_c07_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_c07.py` | Exit 0 (Initial pass / returns empty) | `working tree` |
| C07-01-AC1 (GREEN) | `test_c07_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_c07.py::test_c07_01_contract_1` | Exit 0 (Passed, strong downtrend strictly rejects entry) | `6b0be47` |
| C07-01-AC2 (RED) | `test_c07_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_c07.py` | Exit 1 (Failed: assert 0 == 1) | `working tree` |
| C07-01-AC2 (GREEN) | `test_c07_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_c07.py::test_c07_01_contract_2` | Exit 0 (Passed, sideways oversold produces bounded entry intent) | `6b0be47` |
| C07-01-AC3 (RED) | `test_c07_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_c07.py` | Exit 0 (Initial pass / returns empty) | `working tree` |
| C07-01-AC3 (GREEN) | `test_c07_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_c07.py::test_c07_01_contract_3` | Exit 0 (Passed, zero band width produces abstain / FLAT) | `6b0be47` |

All 4 tests in `tests/unit/lab/strategies/test_c07.py` passed (1.10s).
Combined suite verification (80 passed across backtest, risk, execution, ledger, costs, features, labels, strategies, and evaluation) passed (2.38s).

## Review
- Spec verdict: PASS (meets all functional requirements of C07-01 and specs/10-strategy-catalog-and-protocol.md).
- Quality verdict: PASS (pure stateless decision protocol, zero ledger mutation, strict causality, sideways regime gating and degenerate band protection).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for C07-01.
- Next unlocked consumers: C10-01, QA-01.
