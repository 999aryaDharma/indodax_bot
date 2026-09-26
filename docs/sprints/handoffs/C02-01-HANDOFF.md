# C02-01 handoff

Status: REVIEW

## Identity
- Sprint ID: C02-01 — EMA pullback
- Implementation agent: Antigravity (original); fix agent: opencode/muse-spark-1.3-contributor-free
- Independent reviewer: UNASSIGNED (pending delta verification)
- Branch / worktree: `fix/C02-01-failclosed` (worktree `.worktrees/fix/C02-01`, base `1dd3150`)
- Base SHA: `72bba7e` (original); fix base `1dd3150`
- Code target: `feat(c02-01): ema pullback`
- Evidence SHA relation: `03478f53b4208f898b520b268584be4c5a6d8671` (original)
- Fix SHA: `937e27501f1003fad27a7605c4f2e977bb6febf5` (`fix(c02-01): fail-closed EMA regime and ATR gates`)

## Files and contracts
- Planned files:
  - `src/indodax_lab/strategies/c02.py` (load_c02_specification, c02_decide)
  - `src/indodax_lab/strategies/__init__.py` (Package exports — untouched by this fix)
  - `configs/strategies/C02_v1.yaml` (Canonical C02 configuration)
  - `tests/unit/lab/strategies/test_c02.py` (Explicit AC0..AC3 test cases — untouched)
  - `tests/unit/lab/strategies/test_c02_failclosed.py` (NEW: fail-closed regression for blocking findings)
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

## Fix cycle (blocking set only)
Independent blocking findings accepted for this SHA:
- Critical/Important-1 (fail-open EMA regime): missing `ema_slow` defaulted to `0.0`, so `close > 0` and `fast > 0` passed as "uptrend" and a recovered pullback emitted LONG on unknown regime. Reproduced: missing-slow frame emitted 1 intent (expected 0). Missing `ema_fast` blocked only by accident (`0 > slow` false), now explicitly pinned.
- Critical/Important-2 (fail-open ATR): missing `atr_14`/`atr` defaulted to `0.0`, emitting LONG with `stop_loss == entry` (106000000.0). Reproduced: missing-ATR frame emitted 1 intent with stop == limit (expected 0). Prior-row `low`/`ema_fast` fallback (`prev_row.get(..., fast_ema)`) could also mask unknown prior values.
- Important-3 (RED invalid / handoff overclaim): original AC1/AC2 RED recorded `Exit 0 (Initial pass / returns empty)` — a passing empty result is not a behavior-demonstrating RED. This fix adds genuine behavioral RED (below) and scopes evidence to the focused gate. Manifest untouched per coordinator ownership.

Fix (single batch, `937e275`):
- `src/indodax_lab/strategies/c02.py`: fail-closed EMA (require present finite `ema_fast`/`ema_slow` > 0, present finite prior `low`/`ema_fast` > 0), fail-closed ATR (require present finite ATR > 0, require `0 < stop < close`), finite/positive close guards.
- `tests/unit/lab/strategies/test_c02_failclosed.py` (new, 3 tests): missing slow blocks, missing fast blocks, missing ATR blocks.

Acceptance evidence (fix SHA `937e275`, Python 3.14.0, worktree `.worktrees/fix/C02-01`):
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| C02-01-FIX-RED | `tests/unit/lab/strategies/test_c02_failclosed.py` (3 tests vs pre-fix code) | `python -m pytest tests/unit/lab/strategies/test_c02_failclosed.py -q` | Exit 1 — 2 failed, 1 passed (missing-slow and missing-ATR emit on pre-fix code, proving fail-open; missing-fast already blocked) | pre-fix worktree |
| C02-01-FIX-GREEN | `test_c02.py` (6) + `test_c02_failclosed.py` (3) | `python -m pytest tests/unit/lab/strategies/test_c02.py tests/unit/lab/strategies/test_c02_failclosed.py -q` | Exit 0 — 9 passed in 0.76s | `937e275` |
| C02-01-FIX-LINT | `c02.py` + failclosed test | `ruff check src/indodax_lab/strategies/c02.py tests/unit/lab/strategies/test_c02_failclosed.py --select F,B,UP` | Exit 0 — All checks passed | `937e275` |

Backlog (Minor, non-blocking): pre-existing `E501`/`I001` full-file style debt untouched; `stop_loss ... if stop_loss > 0 else None` now redundant but kept as defense-in-depth.

## Review
- Spec verdict: PASS (meets all functional requirements of C02-01 and specs/10-strategy-catalog-and-protocol.md).
- Quality verdict: PASS (pure stateless decision protocol, zero ledger mutation, strict causality, downtrend rejection, and pullback recovery confirmation).
- Findings: None on original SHA per owner self-review; independent blocking set above fixed in `937e275`, pending delta verification.
- Self-review: completed by implementation owner (Antigravity); fix self-reviewed by opencode/muse-spark-1.3-contributor-free (diff: c02.py fail-closed guards + 1 new regression file, `__init__.py`/config untouched).
- Independent review: PENDING delta verification of the blocking set only.

## Deviations and known risks
- Deviations: None (additive fail-closed guards; no contract/config change).
- Unresolved issues / blockers: None for C02-01 after this fix.
- Next unlocked consumers: QA-01.
