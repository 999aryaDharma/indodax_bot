# S01-01 handoff

Status: REVIEW

## Identity
- Sprint ID: S01-01 — Liquidity screened breakout
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/s01-01-liquidity-screened-breakout`
- Base SHA: `6c5fc01`
- Code target: `feat(s01-01): liquidity screened breakout`
- Evidence SHA relation: `0eac1731134de11e67e3b07d218ec9eda07aa5ff`

## Files and contracts
- Planned files:
  - `src/indodax_lab/strategies/s01.py` (load_s01_specification, s01_decide)
  - `src/indodax_lab/strategies/__init__.py` (Package exports)
  - `configs/strategies/S01_v1.yaml` (Canonical S01 configuration)
  - `tests/unit/lab/strategies/test_s01.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `Breakout with spread/depth gate relative to simulated size -> versioned LONG/FLAT intent, never direct orders.`
  - Stateless decision function over causal `DecisionFrame`; long-only spot intents (`BUY` / `SELL`, positive desired qty).
  - Wide spread gate: spread above `max_spread_bps` strictly rejects breakout entry.
  - Depth restriction: order size is capped to available order book depth if depth is less than `base_qty`.
  - Missing liquidity protection: missing or NaN spread or depth strictly blocks trade (fail-closed).
  - Strategies only produce declarative order intents (`SignalIntent`); zero authority over fills, executions, or ledger balances.
- Migration and compatibility:
  - Additive classical/screening strategies catalog; backward compatible.
  - Dependencies: STRAT-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| S01-01-AC0 (RED) | `test_s01_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_s01.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| S01-01-AC0 (GREEN) | `test_s01_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_s01.py::test_s01_01_valid_contract` | Exit 0 (Passed, produces valid BUY SignalIntent with ATR stop) | `0eac173` |
| S01-01-AC1 (RED) | `test_s01_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_s01.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| S01-01-AC1 (GREEN) | `test_s01_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_s01.py::test_s01_01_contract_1` | Exit 0 (Passed, wide spread rejects entry) | `0eac173` |
| S01-01-AC2 (RED) | `test_s01_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_s01.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| S01-01-AC2 (GREEN) | `test_s01_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_s01.py::test_s01_01_contract_2` | Exit 0 (Passed, insufficient depth restricts order size) | `0eac173` |
| S01-01-AC3 (RED) | `test_s01_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_s01.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| S01-01-AC3 (GREEN) | `test_s01_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_s01.py::test_s01_01_contract_3` | Exit 0 (Passed, missing liquidity blocks trade) | `0eac173` |

All 4 tests in `tests/unit/lab/strategies/test_s01.py` passed (0.98s).
Combined suite verification (84 passed across backtest, risk, execution, ledger, costs, features, labels, strategies, and evaluation).

## Review
- Spec verdict: PASS (meets all functional requirements of S01-01 and specs/10-strategy-catalog-and-protocol.md).
- Quality verdict: PASS (pure stateless decision protocol, zero ledger mutation, strict liquidity gating, spread filtering, and depth bounding).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for S01-01.
- Next unlocked consumers: S07-01, QA-01.
