# C04-01 handoff

Status: REVIEW

## Identity
- Sprint ID: C04-01 — Cross sectional momentum
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/c04-01-cross-sectional-momentum`
- Base SHA: `1fb5cc8`
- Code target: `feat(c04-01): cross sectional momentum`
- Evidence SHA relation: `2369a5d3de3a800de6ef5c43b1a8015f2b79166f`

## Files and contracts
- Planned files:
  - `src/indodax_lab/strategies/c04.py` (load_c04_specification, c04_decide)
  - `src/indodax_lab/strategies/__init__.py` (Package exports)
  - `configs/strategies/C04_v1.yaml` (Canonical C04 configuration)
  - `tests/unit/lab/strategies/test_c04.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `PIT rank return top-K with liquidity and stable tie break -> versioned LONG/FLAT intent, never direct orders.`
  - Stateless decision function over causal `DecisionFrame`; long-only spot intents (`BUY` / `SELL`, positive desired qty).
  - Ineligible pairs or future listings (`listing_date > as_of`, `eligible == False`) strictly excluded from rank.
  - Deterministic tie-breaking across runs: primary key momentum return descending, secondary key canonical pair ascending.
  - Cash reserved once on rotation: total deployed across top-K bounded by `base_qty * (1 - cash_reserve_pct)`, allocating each slot `(1 - cash_reserve_pct) / top_k`.
  - Liquidity filter: assets with volume below `min_volume` excluded from ranking.
  - Strategies only produce declarative order intents (`SignalIntent`); zero authority over fills, executions, or ledger balances.
- Migration and compatibility:
  - Additive classical strategies catalog; backward compatible.
  - Dependencies: STRAT-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| C04-01-AC0 (RED) | `test_c04_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_c04.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| C04-01-AC0 (GREEN) | `test_c04_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_c04.py::test_c04_01_valid_contract` | Exit 0 (Passed, produces valid top-K SignalIntents) | `2369a5d` |
| C04-01-AC1 (RED) | `test_c04_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_c04.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| C04-01-AC1 (GREEN) | `test_c04_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_c04.py::test_c04_01_contract_1` | Exit 0 (Passed, future listing does not enter rank) | `2369a5d` |
| C04-01-AC2 (RED) | `test_c04_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_c04.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| C04-01-AC2 (GREEN) | `test_c04_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_c04.py::test_c04_01_contract_2` | Exit 0 (Passed, deterministic tie-breaking across runs) | `2369a5d` |
| C04-01-AC3 (RED) | `test_c04_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_c04.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| C04-01-AC3 (GREEN) | `test_c04_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_c04.py::test_c04_01_contract_3` | Exit 0 (Passed, cash reserved once on rotation) | `2369a5d` |

All 4 tests in `tests/unit/lab/strategies/test_c04.py` passed (1.00s).
Full lab test suite verification (80 passing in domain suite; 80 passing in universe/data suite).

## Review
- Spec verdict: PASS (meets all functional requirements of C04-01 and specs/10-strategy-catalog-and-protocol.md).
- Quality verdict: PASS (pure stateless decision protocol, zero ledger mutation, strict point-in-time universe ranking, deterministic tie-breaking, and cash reservation).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for C04-01.
- Next unlocked consumers: C12-01, S07-01, QA-01, G01-01.
