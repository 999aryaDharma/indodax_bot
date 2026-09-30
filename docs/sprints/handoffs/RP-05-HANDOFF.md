# RP-05 handoff — runtime parity qualification fixtures

Status: SUBMITTED FOR INDEPENDENT REVIEW (implementation complete; coordinator dispatches reviewer, manifest untouched).

## Identity

- Sprint: RP-05 — Runtime parity qualification fixtures
- Implementation owner: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Independent reviewer: UNASSIGNED (coordinator dispatches; implementer cannot self-approve)
- Branch: `dev` (main checkout; no other owner on these paths)
- Code SHA: `e4c06a1` — `feat(rp-05): runtime parity qualification fixtures`
- This handoff is the evidence follow-up to `e4c06a1`; it contains no code changes.
- Environment: Windows, Python 3.14.0, pytest 9.0.3, ruff 0.16.9, `D:\bot-trading`
- Dependencies DONE verified: RP-04 (code complete, REVIEW), PM-04 (DONE). Manifest READY + UNASSIGNED at claim.

## Files and contracts

- `tests/integration/lab/test_runtime_parity.py` (NEW) — ParityTrace /
  compare_traces / evidence-manifest harness (test-owned, per spec Modify:
  None) + `test_rp_05_0..4`, `test_rp_05_program_5`. Replays one canonical
  3–5-event sequence into historical (simulator ACK), shadow (fixed clock),
  and production-fake (simulator PARTIAL) compositions from the RP-04
  adapters; compares pre-venue decisions exactly; venue receipt IDs, OMS
  mirror states, journal totals and ledger digests are EXECUTION_OUTCOME
  (ignored unless asked), never decision evidence.
- `tests/architecture/test_research_write_firewall.py` (NEW) — AC4 static
  transitive-closure check (research entries → no `indodax_trading` in
  closure, closure pinned non-trivial) + fresh-interpreter import check.
- `src/`: untouched (Modify: None honored).

## Acceptance evidence (behavioral RED observed, then GREEN)

RED history (real behavior, fixed in fixtures/harness — no src touched):
- `OMS_CLIENT_ORDER_ID_INVALID`: colon-bearing intent IDs rejected by OmsOrder
  validation → fixtures use colon-free IDs.
- Order-ID prefix collision: distinct intents sharing a 12-char head collapse
  to one kernel order (pre-existing RP-04 kernel derivation; recorded below
  as backlog, not fixed here).
- `sorted(set[dict])` TypeError in harness digest helper → key-sorted list.

GREEN: `python -m pytest tests/integration/lab/test_runtime_parity.py
tests/architecture/test_research_write_firewall.py -q -p no:cacheprovider`
→ `8 passed`, exit 0.

| AC | Test | Assertion |
|---|---|---|
| AC0 | `test_rp_05_0` | Intent IDs + content digest identical across 3 envs; zero divergences; manifest complete + code SHA pinned |
| AC1 | `test_rp_05_1` | Two identically-built RiskEngines give equal (approved, Decimal qty, reason); kill-switched engine differs (sensitivity control) |
| AC2 | `test_rp_05_2` | Same normalized fills → Decimal-exact equal cash/positions/totals, non-vacuous (cash moved, position opened); divergent price breaks parity |
| AC3 | `test_rp_05_3` | Differing shadow clocks → zero DECISION_DRIFT; tampered intent digest flagged DECISION_DRIFT with identical timing |
| AC4 | `test_rp_05_4` + firewall file | Composed simulator/shadow runtimes carry no writer attrs; static closure + fresh-interpreter checks pass |
| AC5 | `test_rp_05_program_5` | Two identical runs fully equal (incl. execution); manifest deterministic across builds; duplicate/restart add nothing; halt-continue ledger equals uninterrupted |

## Gates

1. Focused: 8 passed, exit 0.
2. Affected: `test_runtime_adapters.py + tests/architecture +
   tests/unit/lab/risk + tests/unit/lab/execution` → `124 passed`, exit 0
   (RP-04 suite still green; no src changed so blast radius is proof-only).
3. `ruff check` (E,F,I,B,UP) on both new files → clean (3 introduced
   findings fixed; repo pre-existing baseline untouched).
4. `git diff --check` → exit 0.

## Self-review notes and deviations

- No credentials, live network, real orders, Production paths. Fake clocks (shadow), tmp stores, fixed fixtures.
- Single-writer/idempotency honored via kernel/store semantics under test; duplicate-fill conflict behavior (halt + ConflictingFillError) not re-proven here — owned by state-store suites.
- Finding for coordinator/RP-04 owner (NOT fixed here, Modify: None):
  kernel `_intent_to_order` truncates intent IDs to a fixed-width prefix, so
  distinct candidate intents sharing a 12-char head collapse into one order
  (observed: `rp05_feed-p_1`/`_2` → single `ord_rp05_feed-p_`). Parity holds
  (all envs lose the same order) but a candidate can silently lose an order.
  Needs RP-04-owner scoping, not an RP-05 side edit.
- Open external gates (unchanged): no production activation; measured host
  artifacts remain operator-owned (same class as RP-04 AC7). Offline proof only.
- No subagent dispatch; no manifest edit; no push/merge/deploy.

## Next eligible consumers

RW5-01, PM-06 (unblocked on code; still subject to coordinator DAG + review PASS).
