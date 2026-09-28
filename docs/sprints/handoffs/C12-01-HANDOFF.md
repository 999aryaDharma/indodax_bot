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
  Both observations were revisited in the *Minor fix round* section below:
  (a) fixed as prescribed, (b) the inherited coverage claim did not hold for
  the canonical `listed_at` representation, so the explicit guard was added.
- Scope: no manifest edit, no push/merge, no other sprint's files, no live
  keys/DB/orders, no subagent dispatch. Research-only candidate; not
  activated, not in default scheduler (external gate unchanged).

## Next eligible consumers

None required by this sprint.

## Minor fix round (Task 8 — two Minor notes on this parked SHA)

Status: fixed on the same parked branch, ON TOP of `8af79dd`. Review and merge
remain deferred exactly as before (owner skip order): this round is NOT
submitted for review, no push/merge, no manifest edit, no other sprint's files.
Commit: `fix(C12-01): ...` (short SHA recorded in
`D:\bot-trading\.superpowers\sdd\ready-sprints\task-8-report.md`).

Files touched: `src/indodax_lab/strategies/c12.py`,
`tests/unit/lab/strategies/test_c12.py`, this handoff (append only).
`src/indodax_lab/strategies/__init__.py` wiring left exactly as parked (future
convergence with S07-01, not owned here); `configs/strategies/C12_v1.yaml`
unchanged; `sprint-manifest.json` untouched.

### M1 — breadth-reason misattribution with negative `min_relative_strength`

Claim verified independently before any fix (constructed case, pre-fix run):
returns aaa +10%, bbb +8%, ccc −1% ⇒ median +8%, breadth 2/3 > 0.50 (cash gate
passes). With `min_relative_strength = -0.10`, ccc_idr strength = −0.09 ≥ floor,
non-positive return ⇒ FLAT recorded as `C12_STRENGTH_BELOW_MINIMUM` even though
the strength gate passed — the positive-return (breadth) criterion was what
failed. Claim reproduced.

Fix (fail closed, no silent misattribution): parameter parsing/validation was
extracted into `_validated_rotation_parameters(spec)`, which now also rejects
`min_relative_strength < 0`, and is called from **both** `load_c12_specification`
(config/load time) and `c12_decision_history` (decision time, so a directly
injected spec cannot bypass it). Rejection reason stays the established explicit
`INVALID_C12_ROTATION_PARAMETERS`. Module docstring documents the non-negative
floor.

- RED: `python -m pytest tests/unit/lab/strategies/test_c12.py -q -k
  negative_min_relative_strength` → `1 failed, 8 deselected`, exit 1,
  `AssertionError: load_c12_specification accepted negative min_relative_strength`.
- GREEN (after fix): same command → `1 passed, 8 deselected`, exit 0.

### M2 — C04 `listed_at` guard not repeated in C12

Claim verified independently before any fix (constructed case, pre-fix run):
`DecisionFrame` filters only `decision_ts`/`row_ready_at`/`eligible`, so a pair
with `listed_at = as_of + 1d`, eligible rows at `as_of` and the strongest return
(+90%) **entered C12 rotation as rank 1 LONG**, while sibling C04 (explicit
guard) rejected the same frame. The inherited "structurally covered by
DecisionFrame" claim therefore did not hold for the canonical `listed_at`
representation; per the brief, an explicit guard was added instead of arguing.

Fix: C12 now mirrors C04's guard in the evidence stage (columns
`listed_at`/`listing_date`, missing value ⇒ no listing evidence ⇒ unchanged,
unparseable value ⇒ `C12_INVALID_MARKET_DATA` fail-closed, value after `as_of`
⇒ `EXCLUDED` with new reason `C12_NOT_YET_LISTED`). Delisted/stale behavior and
the frame-level drop of future-only rows are unchanged and now pinned by the
same dedicated test.

- RED: `python -m pytest tests/unit/lab/strategies/test_c12.py -q -k
  not_yet_listed_and_delisted` → `1 failed, 9 deselected`, exit 1,
  `AssertionError: assert ['future_idr', 'ada_idr'] == ['ada_idr', 'dot_idr']`
  (behavioral; the frame-boundary assertion passed, isolating the missing
  strategy-level guard).
- GREEN (after fix): same command → `1 passed, 9 deselected`, exit 0.

### Gates (inside the worktree, this round)

1. `python -m pytest tests/unit/lab/strategies/test_c12.py -q` → `10 passed in 1.77s`, exit 0
2. `python -m pytest tests/unit/lab/strategies -q` → `178 passed in 9.41s`, exit 0 (176 baseline + 2 new)
3. `python -m ruff check src/indodax_lab/strategies/c12.py tests/unit/lab/strategies/test_c12.py` → `All checks passed!`, exit 0
4. `git diff --check` → exit 0 (only an informational `LF will be replaced by CRLF` notice from `core.autocrlf=true`)

### Residual observation recorded, NOT fixed (out of the note's prescribed scope)

The M1 note's qualifier "only reachable with negative `min_relative_strength`"
is incomplete: the same misattribution is reachable with the **default**
`min_relative_strength = 0.0` when `cash_breadth_threshold` is lowered below
0.50 (reproduced: threshold 0.30, returns −5%, −5%, −5%, +1%, +1% ⇒ the −5%
pairs report `C12_STRENGTH_BELOW_MINIMUM` with strength exactly 0.0000 ≥ floor).
Default config (`min 0.0`, threshold `0.50`) is unaffected — with breadth > 0.50
the universe median is strictly positive, so any non-positive-return pair is
genuinely below a non-negative floor. Fixing this needs either a distinct
reason code for the positive-return criterion or a floor on
`cash_breadth_threshold`; both are behavior changes beyond the prescribed note
remedy and are left for the coordinator to scope.
