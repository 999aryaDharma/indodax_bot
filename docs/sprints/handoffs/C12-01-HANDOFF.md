# C12-01 handoff

Status: SUBMITTED FOR INDEPENDENT REVIEW (implementation complete; review dispatched by coordinator)

## Identity

- Sprint ID: C12-01 — Relative strength rotation
- Implementation agent: resumed Task-1 session (this owner). The tested WIP
  (`c12.py`, `test_c12.py`, `C12_v1.yaml`, `+4` export lines) was inherited
  from a prior owner whose session was cancelled; this owner audited it against
  the sprint spec, made one docstring correction, proved RED retroactively and
  completed the gates/commit. Prior-owner identity is not fabricated here.
- Independent reviewer: UNASSIGNED (coordinator dispatches after this report)
- Branch: `feat/c12-01-relative-strength-rotation` (base bdcc97d; no rebase/merge)
- Code commit SHA: `903099b` — `feat(c12-01): relative strength rotation`
- Handoff commit SHA: recorded in the task report (`task-1-report.md`); this
  docs commit is the evidence follow-up to code commit `903099b` and contains
  no code changes.
- Environment: Windows, Python 3.14.0, pydantic 2.12.3,
  `C:\Python314\python.exe`, worktree
  `D:\bot-trading\.worktrees\feat-c12-01`

## Files and contract

- `configs/strategies/C12_v1.yaml` — frozen v1 specification (strategy_id C12,
  version 1.0.0, family `relative_strength_rotation`): lookback 24 bars,
  top_k 2, minimum_valid_pairs 2, cash_breadth_threshold 0.50,
  min_relative_strength 0.0, max_turnover_fraction "0.50", atr_multiplier 2.0.
  These are registered research-hypothesis defaults, not profitability claims
  and not fixture numbers.
- `src/indodax_lab/strategies/c12.py` — pure, stateless
  `c12_decide(frame, spec) -> list[SignalIntent]` plus diagnostics boundary
  `c12_decision_history(...)` returning one explicit record
  (LONG/FLAT/BLOCKED/EXCLUDED + reason code) per eligible pair, and
  `load_c12_specification` via the existing `StrategyRegistry` YAML loader.
  Contract: PIT relative strength = lookback return − universe median return;
  stable tie rank (strength desc, canonical pair asc); cash regime = positive
  breadth at or below threshold blocks reentry (all valid pairs BLOCKED, no
  LONG); total intent notional ≤ available cash × max_turnover_fraction with
  unknown/nonpositive cash fail-closed; versioned LONG/FLAT intent only
  (`intent_id` embeds registry version), never orders/ledger/network; no bfill,
  UTC timestamps, invalid parameters rejected with
  `INVALID_C12_ROTATION_PARAMETERS`.
- `src/indodax_lab/strategies/__init__.py` — +4 lines export wiring
  (`c12_decide`, `c12_decision_history`, `load_c12_specification`), same
  convention as sibling C01–C11.
- `tests/unit/lab/strategies/test_c12.py` — 8 tests (4 AC-mapped + 4
  fail-closed/diagnostic guards).
- Migration: none. Code-only pure addition; no schema, persistence, manifest or
  public-interface changes outside the declared files. Manifest untouched.

## Acceptance evidence (RED → GREEN)

Prior owner left no RED record. Per brief §3 the mandatory retroactive proof was
run on the final implementation: real `c12.py` stashed, tests executed, then
restored (SHA256 verified byte-identical after LF normalization:
`f7742d65…f6a8dd` before/after; stash list empty after pop).

| AC | Test | RED (behavior absent) | GREEN |
|---|---|---|---|
| C12-01-AC0 | `test_c12_01_valid_contract` | `AssertionError: assert [] == ['sol_idr', 'eth_idr']` — no rotation intents | 8/8 focused pass |
| C12-01-AC1 | `test_c12_01_contract_1` | `AssertionError: assert [] == ['ada_idr', 'dot_idr']` — no intents; history empty so delisted pair absent | 8/8 focused pass |
| C12-01-AC2 | `test_c12_01_contract_2` | `AssertionError: assert [] == ['btc_idr', 'doge_idr', 'sol_idr']` — no BLOCKED cash-regime diagnostics | 8/8 focused pass |
| C12-01-AC3 | `test_c12_01_contract_3` | `AssertionError: assert [] == ['ada_idr', 'dot_idr']` — no tied ranked intents | 8/8 focused pass |

RED commands and outputs (condensed):

1. Literal brief command — `git stash push src/indodax_lab/strategies/c12.py`
   → exit 1, `pathspec … did not match any file(s) known to git` (file is
   untracked). Applied `git stash push -u -- src/indodax_lab/strategies/c12.py`
   → exit 0, stash saved.
2. With only `c12.py` reverted, the 4 AC tests gave
   `ModuleNotFoundError: No module named 'indodax_lab.strategies.c12'`,
   pytest exit 2. Recorded honestly: whole-file reversion alone is an
   import-level failure, **not** behavioral RED (AGENTS.md: missing import is
   not proof of behavior RED).
3. Behavioral RED: with the real file still stashed, a temporary no-behavior
   stub at `src/indodax_lab/strategies/c12.py` (real config loader,
   `c12_decide`/`c12_decision_history` returning only empty results) was
   written and the 4 AC tests were run:
   `python -m pytest tests/unit/lab/strategies/test_c12.py -q -k "test_c12_01_valid_contract or test_c12_01_contract_1 or test_c12_01_contract_2 or test_c12_01_contract_3"`
   → `4 failed, 4 deselected`, exit 1, all failures `AssertionError` on the
   behavioral expectations above (full output:
   `%TEMP%\c12_red_proof.txt`).
4. Stub deleted, `git stash pop` → exit 0, implementation restored (hash
   verified), stash list empty.

GREEN: `python -m pytest tests/unit/lab/strategies/test_c12.py -q` →
`8 passed`, exit 0.

## Exact gate commands, counts, exits (inside worktree)

1. `python -m pytest tests/unit/lab/strategies/test_c12.py -q` → `8 passed in 1.89s`, exit 0
2. `python -m pytest tests/unit/lab/strategies -q` → `176 passed in 9.04s`, exit 0
   (`168` pre-existing baseline confirmed via `--ignore=tests/unit/lab/strategies/test_c12.py`
   → `168 passed`; +8 C12 tests = 176)
3. `python -m pytest tests/unit/lab -q` → `1467 passed in 70.14s`, exit 0
   (brief baseline 1459 = suite without C12; +8 = 1467)
4. `python -m ruff check src/indodax_lab/strategies/c12.py src/indodax_lab/strategies/__init__.py tests/unit/lab/strategies/test_c12.py`
   → `All checks passed!`, exit 0
5. `git diff --check` (staged owned paths) → exit 0; post-commit focused
   re-run → `8 passed`, exit 0 on commit `903099b`.

## Self-review notes and deviations

- Audit verdict: WIP complied with the spec on naming, PIT semantics
  (closed-bar window, `as_of` staleness check, no bfill), turnover/cash-regime
  gate ordering (universe floor → breadth regime → cash availability),
  versioned LONG/FLAT-only intent, fail-closed edges and stable ties. One fix
  applied: the module docstring asserted breadth is "equal to"
  `market_breadth_pos_24_1h`; it is only equal when every eligible pair has
  current valid evidence (denominator is valid pairs), so wording was softened
  to "mirroring … " — documentation precision only, zero behavior change.
- Deviation 1: brief's literal stash command fails on an untracked file;
  `-u` was required (recorded above). Deviation 2: whole-file stash yields
  import errors, so a temporary stub was used to obtain genuine behavioral
  RED; the stub is not in any commit (blob verified).
- Known minor observations (not blocking, recorded for review): (a) a
  non-positive-return pair that passes the strength gate under a *negative*
  configured `min_relative_strength` would be reported
  `C12_STRENGTH_BELOW_MINIMUM` rather than a return-specific code —
  unreachable with default config because the cash-regime gate blocks
  majority-nonpositive universes; (b) C12 does not repeat C04's explicit
  `listed_at` future-listing guard — the DecisionFrame already excludes
  future rows and pairs without rows remain in history as EXCLUDED, and
  future-listing is C04's acceptance boundary, not C12-01's.
- Scope: no manifest edit, no push/merge, no other sprint's files, no live
  keys/DB/orders, no subagent dispatch. Research-only candidate; not
  activated, not in default scheduler (external gate unchanged).

## Next eligible consumers

None required by this sprint.
