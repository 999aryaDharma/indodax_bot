# C01-01 handoff

Status: REVIEW

## Identity
- Sprint ID: C01-01 — Donchian breakout
- Implementation agent: Antigravity (original); fix agent: opencode/muse-spark-1.3-contributor-free
- Independent reviewer: UNASSIGNED (pending delta verification)
- Branch / worktree: `fix/C01-01-failclosed` (worktree `.worktrees/fix/C01-01`, base `fa6d4b5`)
- Base SHA: `9b0ee0f` (original); fix base `fa6d4b5`
- Code target: `feat(c01-01): donchian breakout`
- Evidence SHA relation: `cd48fccd89d5b2bfdec16a221e75d2d07bc3d19f` (original)
- Fix SHA: `5e06bea3e0656659ff74e9c89f86975b36b3d66a` (`fix(c01-01): fail-closed volume and ATR gates`)

## Files and contracts
- Planned files:
  - `src/indodax_lab/strategies/c01.py` (load_c01_specification, c01_decide)
  - `src/indodax_lab/strategies/__init__.py` (Package exports — untouched by this fix)
  - `configs/strategies/C01_v1.yaml` (Canonical C01 configuration — untouched)
  - `tests/unit/lab/strategies/test_c01.py` (Explicit AC0..AC3 test cases — untouched)
  - `tests/unit/lab/strategies/test_c01_failclosed.py` (NEW: fail-closed regression for blocking findings)
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

## Fix cycle (blocking set only)
Independent blocking findings accepted for this SHA:
- Critical/Important-1 (fail-open volume gate): missing `base_volume`/`volume` column or zero/NaN average volume defaulted to `0.0`, so `curr_vol >= avg_vol * mult` was `0 >= 0` and a breakout emitted LONG on unknown liquidity. Reproduced: missing-volume frame emitted 1 intent (expected 0).
- Critical/Important-2 (fail-open ATR): missing `atr_14`/`atr` defaulted to `0.0`, emitting LONG with `stop_loss == entry` (103000000.0). Reproduced: missing-ATR frame emitted 1 intent with stop == limit (expected 0).
- Important-3 (RED invalid / handoff overclaim): original AC3 RED recorded `Exit 0 (Initial pass / returns empty)` — a passing empty result is not a behavior-demonstrating RED; combined-suite counts were carried without exact command/SHA linkage. This fix adds genuine behavioral RED (see below) and scopes evidence to the focused gate. Manifest untouched per coordinator ownership.

Fix (single batch, `5e06bea`):
- `src/indodax_lab/strategies/c01.py`: fail-closed volume (require known column, finite curr_vol, finite avg_vol > 0), fail-closed ATR (require present finite ATR > 0, require `0 < stop < close`), finite/positive close and previous-high guards. Follows `c05.py`/`c06.py` fail-closed pattern.
- `tests/unit/lab/strategies/test_c01_failclosed.py` (new, 3 tests): missing volume blocks, zero avg volume blocks, missing ATR blocks.

Acceptance evidence (fix SHA `5e06bea`, Python 3.14.0, worktree `.worktrees/fix/C01-01`):
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| C01-01-FIX-RED | `tests/unit/lab/strategies/test_c01_failclosed.py` (3 tests vs pre-fix code) | `python -m pytest tests/unit/lab/strategies/test_c01_failclosed.py -q` | Exit 1 — FFF (all 3 fail-closed tests fail on pre-fix code, proving fail-open) | pre-fix worktree |
| C01-01-FIX-GREEN | `test_c01.py` (4) + `test_c01_failclosed.py` (3) | `python -m pytest tests/unit/lab/strategies/test_c01.py tests/unit/lab/strategies/test_c01_failclosed.py -q` | Exit 0 — 7 passed in 0.98s | `5e06bea` |
| C01-01-FIX-LINT | `c01.py` + failclosed test | `ruff check src/indodax_lab/strategies/c01.py tests/unit/lab/strategies/test_c01_failclosed.py --select F,B,UP` | Exit 0 — All checks passed | `5e06bea` |

Backlog (Minor, non-blocking): pre-existing `E501` docstring length and full `I001`/format layout in `c01.py` left untouched to keep the diff minimal; `stop_loss ... if stop_loss > 0 else None` is now redundant (guard guarantees `stop > 0`) but kept as defense-in-depth.

## Review
- Spec verdict: PASS (meets all functional requirements of C01-01 and specs/10-strategy-catalog-and-protocol.md).
- Quality verdict: PASS (pure stateless decision protocol, zero ledger mutation, strict causality, fail-closed volume gate and ATR stop).
- Findings: None on original SHA per owner self-review; independent blocking set above fixed in `5e06bea`, pending delta verification.
- Self-review: completed by implementation owner (Antigravity); fix self-reviewed by opencode/muse-spark-1.3-contributor-free (diff: c01.py fail-closed guards + 1 new regression file, `__init__.py`/config untouched).
- Independent review: PENDING delta verification of the blocking set only.

## Deviations and known risks
- Deviations: None (additive fail-closed guards; no contract/config change).
- Unresolved issues / blockers: None for C01-01 after this fix.
- Next unlocked consumers: C10-01, QA-01, M05-01.
