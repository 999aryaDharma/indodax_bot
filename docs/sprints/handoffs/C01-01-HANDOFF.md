# C01-01 handoff

Status: DONE

## Identity
- Sprint ID: C01-01 — Donchian breakout
- Implementation agent: Antigravity
- Corrective implementation owner: Codex `/root`
- Independent reviewer: `/root/docs_review` — PASS on corrective SHA `ce8ce3a3771464de5ed8aa0db7a30845062dcd40`.
- Branch / worktree: `feat/c01-01-donchian-breakout`
- Base SHA: `9b0ee0f`
- Code target: corrective commit `ce8ce3a3771464de5ed8aa0db7a30845062dcd40`
- Evidence SHA relation: `cd48fccd89d5b2bfdec16a221e75d2d07bc3d19f`

## Files and contracts
- Planned files:
  - `src/indodax_lab/strategies/c01.py` (load_c01_specification, c01_decide)
  - `src/indodax_lab/strategies/__init__.py` (Package exports)
  - `configs/strategies/C01_v1.yaml` (Canonical C01 configuration)
  - `tests/unit/lab/strategies/test_c01.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `Previous N-bar high breakout with volume gate; ATR stop -> versioned LONG/FLAT intent, never direct orders.`
  - Stateless decision function over causal `DecisionFrame`; long-only spot intents (`BUY` / `SELL`, positive desired qty).
  - Previous N-bar high is strictly calculated over previous N completed bars, strictly excluding the current decision bar.
  - Breakout confirmed by price (`close > prev_high`) and volume gate (`volume >= avg_volume * volume_multiplier`) emits LONG `SignalIntent` with ATR-based stop-loss.
  - Incomplete bars or insufficient lookback bars produce FLAT (empty intents), never speculative orders.
  - Strategies only produce declarative order intents (`SignalIntent`); zero authority over fills, executions, or ledger balances.
- Migration and compatibility:
  - Additive classical strategies catalog; backward compatible.
  - Dependencies: STRAT-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| C01-01-AC0 (RED) | `test_c01_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_c01.py` | Exit 1 (Failed: assert 0 == 1) | `working tree` |
| C01-01-AC0 (GREEN) | `test_c01_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_c01.py::test_c01_01_valid_contract` | Exit 0 (Passed, produces valid BUY SignalIntent with ATR stop-loss) | `cd48fcc` |
| C01-01-AC1 (RED) | `test_c01_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_c01.py` | Exit 1 (Failed: assert 0 == 1) | `working tree` |
| C01-01-AC1 (GREEN) | `test_c01_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_c01.py::test_c01_01_contract_1` | Exit 0 (Passed, previous high strictly excludes current decision bar) | `cd48fcc` |
| C01-01-AC2 (RED) | `test_c01_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_c01.py` | Exit 1 (Failed: assert 0 == 1) | `working tree` |
| C01-01-AC2 (GREEN) | `test_c01_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_c01.py::test_c01_01_contract_2` | Exit 0 (Passed, breakout confirmed produces LONG, failed volume produces FLAT) | `cd48fcc` |
| C01-01-AC3 (RED) | `test_c01_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_c01.py` | Exit 0 (Initial pass / returns empty) | `working tree` |
| C01-01-AC3 (GREEN) | `test_c01_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_c01.py::test_c01_01_contract_3` | Exit 0 (Passed, incomplete bars or insufficient lookback produce FLAT) | `cd48fcc` |

All 4 tests in `tests/unit/lab/strategies/test_c01.py` passed (1.11s).
Combined suite verification (76 passed across backtest, risk, execution, ledger, costs, features, labels, strategies, and evaluation) passed (2.34s).

## Review
- Spec verdict: PASS (meets all functional requirements of C01-01 and specs/10-strategy-catalog-and-protocol.md).
- Quality verdict: PASS (pure stateless decision protocol, zero ledger mutation, strict causality, fail-closed volume gate and ATR stop).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: initial evidence was pending; corrective SHA passed independent review with no remaining Critical/Important findings.

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for C01-01.
- Next unlocked consumers: C10-01, QA-01, M05-01.

## Current remediation evidence

- Corrective implementation SHA: `ce8ce3a3771464de5ed8aa0db7a30845062dcd40` (builds on the original implementation and review fixes in `0e2a0ab`).
- Targeted command: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/strategies/test_c01.py -q` — 9 passed.
- Targeted lint: `C:/Users/User/miniconda3/envs/ML/python.exe -m ruff check src/indodax_lab/strategies/c01.py tests/unit/lab/strategies/test_c01.py` — passed.
- Added guards/tests for nonfinite or oversized ATR, missing/nonfinite lookback highs and volume, nonfinite current volume, and an ineligible latest row that could otherwise replay a prior breakout.
- The original evidence above is provenance only; current acceptance evidence is the corrective SHA and focused checks recorded here.
- Independent review of the corrective SHA: PASS on `ce8ce3a3771464de5ed8aa0db7a30845062dcd40`; 9 tests and 18 independent negative probes passed, with no remaining Critical/Important findings.
