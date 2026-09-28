# S07-01 handoff

Status: REVIEW

## Identity

- Sprint ID: S07-01 — Small cap rotation
- Implementation agent: OpenCode subagent (MiMo), session ses_f18e4eab8ffeD0ZH0ussZkyPdn
- Independent reviewer: UNASSIGNED (coordinator dispatches after this handoff)
- Branch / worktree: `feat/s07-01-small-cap-rotation` / `D:\bot-trading\.worktrees\feat-s07-01`
- Base SHA: `63dd041`
- Code SHA (review target): `5f94a2a0b7ca6cde3a5a915556cae1f9ce32a8fe`
- Evidence SHA relation: this handoff is committed as a follow-up `docs(sprints)` commit on
  the same branch immediately after the code commit; the code commit contains tests +
  implementation + config + export wiring, and this document records evidence produced on
  exactly that tree (clean `git status` after commit, gates run before commit).

Environment: Windows, Python 3.14.0, repo-local `python -m pytest` / `python -m ruff` run
from the worktree root. The `1 warning` in every run is a pre-existing environment warning
(`langsmith` importing `pydantic.v1` on Python >= 3.14); it also appears in baseline runs.

## Files and contracts

- Planned files (all new, as named by the spec):
  - `configs/strategies/S07_v1.yaml` — canonical S07 v1.0.0 specification
    (`lookback_bars=24`, `top_k=2`, `min_volume=100.0`, `max_spread_bps=30.0`,
    `cash_reserve_pct=0.20`, `atr_multiplier=2.0`; family `small_cap_rotation`,
    universe tier `small_cap`).
  - `src/indodax_lab/strategies/s07.py` — `load_s07_specification`, `s07_evaluate`,
    `s07_decide`.
  - `tests/unit/lab/strategies/test_s07.py` — AC0..AC3 plus one delta guard.
- Export wiring (not in spec Planned Files; see Deviations):
  - `src/indodax_lab/strategies/__init__.py` — exports `s07_decide` +
    `load_s07_specification`, mirroring every C01–C10 / S01–S06 sibling.
- Contract:
  - `Liquidity capacity constrained cross-sectional rank turnover -> versioned LONG/FLAT
    intent, never direct orders.`
  - Stateless, pure `DecisionFrame -> list[SignalIntent]`; FLAT is `[]`; intents carry
    `strategy_id="S07"` from the versioned spec; no DB/network/ledger side effects.
  - PIT ranking (C04 lineage): positive lookback return over `lookback_bars`,
    momentum descending, canonical pair ascending on ties.
  - Liquidity screen (S01 lineage) applied while rotation slots fill: volume present,
    finite and `>= min_volume`; spread present, finite and `<= max_spread_bps`; depth
    (`depth_50bps`, fallback `depth`) present, finite and `> 0`. Missing/NaN fail closed
    and are never zero-filled. An illiquid top rank never takes a slot; the next liquid
    rank backfills.
  - Capacity: per-order notional above the pair's visible 50bps depth (quote IDR) is
    rejected with `S07_OVER_CAPACITY:<pair>` — rejected, never silently shrunk.
  - Shared cash: `available_cash_idr * (1 - cash_reserve_pct)` is the single deployable
    pool split over `top_k` slots; per-slot notional and a running `remaining` bound the
    rotation; total deployed notional `<=` deployable `<=` shared cash; all money math is
    `Decimal`. Missing/zero shared cash returns `[]` with
    `S07_SHARED_CASH_UNAVAILABLE` (fail closed).
  - Diagnostics channel: `s07_evaluate(frame, spec) -> (intents, rejections)` where
    rejection strings are `S07_<REASON>` or `S07_<REASON>:<pair>` (codes:
    `SHARED_CASH_UNAVAILABLE`, `ILLIQUID_VOLUME`, `WIDE_SPREAD`, `MISSING_LIQUIDITY`,
    `OVER_CAPACITY`, `ATR_INVALID`, `ORDER_NOT_POSITIVE`). `s07_decide` is the thin
    registry-conventional wrapper returning only the intents.
  - ATR stop fail-closed: missing/NaN/nonpositive ATR, or a nonpositive computed stop,
    rejects the pair (`S07_ATR_INVALID:<pair>`) instead of emitting stop-at-entry
    (repairs the known C04 MINOR pattern for S07).
  - Invalid configuration parameters raise `ValueError("INVALID_S07_PARAMETERS")`.
- Migration and compatibility:
  - Additive catalog entry; no schema, persistence, registry-allowlist or existing-behavior
    change. `registry.py` untouched: `component_id_for_strategy` allowlists only seed
    components C02/C07/S08, same as C01/C03–C06/C08–C11/S01–S06.
  - Dependencies: C04-01 (DONE), S01-01 (DONE) — conventions reused from their handoffs
    and modules, no code rebuilt.

## Acceptance evidence

TDD sequence: Stage 0 = spec load + empty-decision skeleton; Stage 1 = rank + top_k +
cash-slot sizing (no gates); Stage 2 = liquidity screen; Stage 3 = capacity gate;
Stage 4 = shared-cash reserve/diagnostics + ATR fail-closed. RED is behavioral (assertion
on wrong output), never a missing import: the module/config existed and imported at every
recorded RED.

| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| S07-01-AC0 (RED) | `test_s07_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_s07.py::test_s07_01_valid_contract -q` | Exit 1 — `AssertionError: top-2 rotation must emit 2 intents, got []` (skeleton produced no intents) | working tree (Stage 0) |
| S07-01-AC0 (GREEN) | `test_s07_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_s07.py::test_s07_01_valid_contract -q` | Exit 0 — `1 passed` (valid BUY intents, rank order `sol_idr, eth_idr`, UTC ts, stop < limit, decide == evaluate) | `5f94a2a` |
| S07-01-AC1 (RED) | `test_s07_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_s07.py::test_s07_01_contract_1 -q` | Exit 1 — `AssertionError: illiquid top rank must not be eligible, got ['illiquid_idr', 'eth_idr']` (no liquidity screen yet) | working tree (Stage 1) |
| S07-01-AC1 (GREEN) | `test_s07_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_s07.py::test_s07_01_contract_1 -q` | Exit 0 — `1 passed` (volume/spread/missing-depth cases rejected with codes; liquid backfill; positive control) | `5f94a2a` |
| S07-01-AC2 (RED) | `test_s07_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_s07.py::test_s07_01_contract_2 -q` | Exit 1 — `AssertionError: order above capacity must be rejected, not shrunk or filled: ['topcap_idr', 'eth_idr']` (no capacity gate yet) | working tree (Stage 1) |
| S07-01-AC2 (GREEN) | `test_s07_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_s07.py::test_s07_01_contract_2 -q` | Exit 0 — `1 passed` (over-depth order rejected with `S07_OVER_CAPACITY:topcap_idr`; remaining slot emits; ample-depth control emits both) | `5f94a2a` |
| S07-01-AC3 (RED) | `test_s07_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_s07.py::test_s07_01_contract_3 -q` | Exit 1 — `AssertionError: rotation must reserve 20% of shared cash, deployed 9999988.000000000019763` (full cash deployed, no reserve/diagnostic) | working tree (Stage 1) |
| S07-01-AC3 (GREEN) | `test_s07_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_s07.py::test_s07_01_contract_3 -q` | Exit 0 — `1 passed` (10,000,000 pool: total <= 8,000,000 and slot <= 4,000,000; 1,000,000 pool scales to <= 800,000; missing cash => `[]` + `S07_SHARED_CASH_UNAVAILABLE`) | `5f94a2a` |
| Delta guard (RED) | `test_s07_01_missing_atr_abstains` | `python -m pytest tests/unit/lab/strategies/test_s07.py::test_s07_01_missing_atr_abstains -q` | Exit 1 — emitted intent with `stop_loss=Decimal('105000.00') == limit_price` (stop-at-entry) | working tree (Stage 1) |
| Delta guard (GREEN) | `test_s07_01_missing_atr_abstains` | `python -m pytest tests/unit/lab/strategies/test_s07.py::test_s07_01_missing_atr_abstains -q` | Exit 0 — `1 passed` (missing ATR abstains with `S07_ATR_INVALID:btc_idr`) | `5f94a2a` |

Required gates (all run inside the worktree, in brief order, before commit):

| Gate | Command | Result | Exit |
|---|---|---|---|
| 1. Focused | `python -m pytest tests/unit/lab/strategies/test_s07.py -q` | `5 passed, 1 warning in 1.31s` | 0 |
| 2. Strategies subsystem | `python -m pytest tests/unit/lab/strategies -q` | `173 passed, 1 warning in 8.31s` (168 pre-existing baseline + 5 new S07 tests) | 0 |
| 3. Lab suite | `python -m pytest tests/unit/lab -q` | `1464 passed, 1 warning in 64.61s` (1459 pre-existing baseline + 5 new S07 tests) | 0 |
| Lint | `python -m ruff check src/indodax_lab/strategies/s07.py src/indodax_lab/strategies/__init__.py tests/unit/lab/strategies/test_s07.py` | `All checks passed!` (repo pre-existing baseline findings in other files untouched) | 0 |

No tests skipped; no existing tests modified, weakened or deleted; `sprint-manifest.json`
untouched.

## Review

- Spec verdict: self-assessed against `docs/sprints/strategies/S07-01-small-cap-rotation.md`
  and `docs/specs/10-strategy-catalog-and-protocol.md` (S07-01 section): all four ACs
  mapped to named tests with behavioral RED/GREEN; public contract is versioned
  LONG/FLAT intent only.
- Quality verdict: self-reviewed (see below). Independent review PENDING on code SHA
  `5f94a2a`.
- Findings: none outstanding from self-review; fix rounds used: 0 (pre-commit self-review
  found one lint issue, fixed before commit, see below).

## Deviations and known risks

- Deviation 1: `src/indodax_lab/strategies/__init__.py` export wiring is not in the spec's
  Planned Files, but the task brief explicitly permits "export wiring", every C/S sibling
  handoff lists it, and the coordinator's activation plan already names this path as the
  C12-01/S07-01 shared file. Only the two conventional symbols were added; `s07_evaluate`
  is importable from `indodax_lab.strategies.s07` (module-level), matching how sibling
  tests import.
- Deviation 2: one delta-guard test beyond the four mapped AC tests
  (`test_s07_01_missing_atr_abstains`) — additive regression guard for the ATR fail-closed
  path, following sibling convention (C04/S01 added analogous guards). Baseline counts rise
  by exactly these 5 tests (168 -> 173, 1459 -> 1464).
- Interpretation 1 (AC2): "capacity" is the pair's visible 50bps depth in quote IDR —
  the liquidity-capacity reading of the contract and the S01 feature — and an over-capacity
  order is *rejected* (no intent), not capped, per the AC wording and brief constraint.
  A capacity-rejected slot is not backfilled from a lower rank (conservative fail-closed;
  the liquidity screen does backfill, because AC1 is explicitly a slot-eligibility rule).
- Interpretation 2 (AC3): shared cash is a required input for a shared-cash-aware
  rotation; missing/zero `available_cash_idr` abstains with an explicit diagnostic
  (brief "fail-closed on unknown or missing inputs"; CR-C11/ADR-013 precedent for
  cash-context strategies). Sizing has no `base_qty` fallback by design (YAGNI).
- Known risks / reviewer pointers: attempt to disprove AC1–AC3 via the fixtures and the
  production path (`_liquidity_metrics` screen, capacity gate, Decimal pool math in
  `s07_evaluate`); `s07_evaluate`'s rejection strings are a new public diagnostic surface
  (pinned exactly in tests); capacity and reserve values are frozen v1 hypotheses in
  `S07_v1.yaml`, not profitability claims.
- External gate unchanged: "Portfolio backlog activation by owner; not in default
  scheduler" — S07 is not wired into any scheduler, runner or evaluation pipeline by this
  sprint.
- Rollback: revert the scoped code commit (`git revert 5f94a2a`); no migration, no
  historical artifact overwritten.
- Next unlocked consumers: none required by this sprint.

## Independent task review record (2026-09-28)

- Reviewed SHA: `9fe21db` (tip of `feat/s07-01-small-cap-rotation`; code at
  `5f94a2a`), delta against BASE `63dd041`; 5 files, +648/-0.
- Reviewer: independent session `ses_f18c52fc7ffeAKvlC0JkKSWtwM` (did not
  implement the change). Verdict: **Spec PASS (AC0-AC3), task quality
  Approved-with-Minors — 0 Critical, 0 Important, 2 Minor.**
- Evidence re-run by the reviewer in the sprint worktree: focused
  `test_s07.py` 5 passed; `tests/unit/lab/strategies` 173 passed (168+5);
  `ruff check` on the 3 touched py files clean with zero new findings vs BASE
  (`__init__.py` at BASE also clean); all 4 manifest test names present
  verbatim + 1 additive guard; diff touches exactly the 4 owned files +
  handoff; worktree clean.
- Behavior confirmed: real behavior through public inputs with independent
  expectations (rank order, exact `S07_<REASON>:<pair>` codes, Decimal reserve
  math, positive controls); RED outputs behaviorally credible. All five
  implementer interpretations adjudicated spec-consistent and fail-closed
  (50bps quote-IDR depth capacity; reject-not-cap; no backfill after capacity
  rejection; missing-cash abstain without base_qty fallback; diagnostics
  surface required by Observability clause). `__init__.py` wiring purely
  additive, no conflict with parked sibling wiring. House rules hold
  (UTC frame-level, no bfill, Decimal cash, intent-only, test-only fixtures).
- Backlog (Minor, non-blocking): (1) `pd.concat` with all-NaN depth column
  raises FutureWarning (test line 142) — filter NA frame or pin dtype;
  (2) zero-cash path (`Decimal("0")`) untested though handled by `cash <= 0`
  — pin one assertion in AC3 case C.
- Integration: merged to `dev` via merge commit (reviewed content
  byte-identical; dev-side claim bookkeeping united, no conflicts).

## Minor fix round (2026-09-28)

Hardening only; S07-01 was already DONE + independent PASS. Findings from review
session `ses_f18c52fc7ffeAKvlC0JkKSWtwM`, scope fixed by the coordinator task-5 brief.

- **M1 (Minor)** — `tests/unit/lab/strategies/test_s07.py:142`
  (`features_c = pd.concat(...)`): `depth=None` made the fixture column an all-None
  **object** column, so `pd.concat` raised
  `FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries
  is deprecated ...` (case C, missing depth). Origin verified as **test fixture
  construction only**: `src/indodax_lab/strategies/s07.py` contains no `pd.concat`
  (its `pd.concat` call sites are `features/builder.py`, `features/technical.py`,
  `paper/live_shadow_engine.py`), so production code was left byte-untouched.
  Fix: in `_build_s07_bars`, missing depth is pinned to `float("nan")` (float64)
  instead of `None`, mirroring the adjacent existing `atr_14` handling; fail-closed
  semantics unchanged (`_finite_float` rejects NaN → `S07_MISSING_LIQUIDITY`).
  - RED: `python -m pytest tests/unit/lab/strategies/test_s07.py -q -W error::FutureWarning`
    → exit 1, `1 failed, 4 passed` with `FutureWarning ... pandas/core/internals/concat.py:491`.
  - GREEN: same command → `6 passed`, warning-free; plain `-q` run reports no
    `FutureWarning` (only the pre-existing environment `langsmith`/`pydantic.v1` UserWarning).
- **M2 (Minor)** — zero-cash path (`cash=Decimal("0")`) untested although handled by
  `cash <= 0` in `s07_evaluate` (only `None` was pinned). Added
  `test_s07_01_zero_cash_abstains`: expects `([], ["S07_SHARED_CASH_UNAVAILABLE"])`,
  no fallback intents.
  - RED (assertion-bite evidence): the added assertion was run against an in-memory
    mutant of `s07.py` whose guard was weakened from `cash is None or cash <= 0` to
    `cash is None` → `AssertionError: ['S07_ORDER_NOT_POSITIVE:sol_idr',
    'S07_ORDER_NOT_POSITIVE:eth_idr']` (no file on disk modified; production source
    restored untouched). On unmodified code the assertion passes because the behavior
    already existed — this is coverage hardening, not a behavior fix.
  - GREEN: `6 passed` on `test_s07.py`.

Gates (worktree `fix/minors-s07-01`, run before commit):

| Gate | Command | Result | Exit |
|---|---|---|---|
| 1. Focused | `python -m pytest tests/unit/lab/strategies/test_s07.py -q` | `6 passed, 1 warning` (env warning only) | 0 |
| Warning-free proof | `python -m pytest tests/unit/lab/strategies/test_s07.py -q -W error::FutureWarning` | `6 passed` | 0 |
| 2. Strategies subsystem | `python -m pytest tests/unit/lab/strategies -q` | `174 passed` (173 + 1 new zero-cash test) | 0 |
| Lint | `python -m ruff check tests/unit/lab/strategies/test_s07.py` | `All checks passed!` | 0 |
| Diff hygiene | `git diff --check` | clean | 0 |

Files changed: `tests/unit/lab/strategies/test_s07.py` only (+21/-1). No test skipped,
weakened or deleted; `docs/sprints/sprint-manifest.json` and `src/indodax_lab/strategies/s07.py`
untouched. Fix branch `fix/minors-s07-01`, commit `fix(S07-01): ...` (SHA recorded in
`D:\bot-trading\.superpowers\sdd\ready-sprints\task-5-report.md`).
