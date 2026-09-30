# RW3-01 handoff — experiment lifecycle and backtest orchestration

Status: SUBMITTED FOR INDEPENDENT REVIEW (implementation complete; coordinator dispatches reviewer, manifest untouched).

## Identity

- Sprint: RW3-01 — Experiment lifecycle and backtest orchestration
- Implementation owner: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Independent reviewer: UNASSIGNED (coordinator dispatches; implementer cannot self-approve)
- Branch: `dev` (main checkout; no other owner on these paths)
- Code SHA: `0dd060b` — `feat(rw3-01): experiment lifecycle and backtest orchestration`
- This handoff is the evidence follow-up to `0dd060b`; it contains no code changes.
- Environment: Windows, Python 3.14.0, pytest 9.0.3, ruff 0.16.9, `D:\bot-trading`
- Dependencies DONE verified at claim: RW1-01, RW2-03, RP-04, EVAL-01, JOB-01, DATA-07.

## Files and contracts

- `src/indodax_lab/evaluation/experiment_service.py` (NEW) — ExperimentStore
  (single-writer SQLite, per-operation connections so worker threads never
  share handles) + ExperimentService: create/edit/clone/validate/
  run_backtest/cancel/result/compare + legacy EVAL-01 passthrough. States
  DRAFT→VALIDATED→QUEUED→RUNNING→SUCCESS/FAILED/CANCELLED with guarded
  transitions (FAILED→QUEUED retry allowed; SUCCESS/CANCELLED terminal).
  Trial execution drives the RP-04 RuntimeKernel (simulator, fixed clock)
  over injected events; capital split must be exact or the run rejects
  before any effect; cancel keys are idempotent per key and conflicting
  across experiments.
- `src/indodax_lab/evaluation/experiment_service_reports.py` (NEW) — pure
  trade-report builder: fills, FIFO closed lifecycles, open remnants,
  FEES_UNKNOWN marker (no schedule bound), win rate numeric or explicit
  UNAVAILABLE (never zero/NaN).
- `src/indodax_lab/orchestration/queue.py` (additive, one method) —
  `cancel_job`: PENDING→CANCELLED directly; RUNNING→CANCELLED with a
  generation bump that fences the holder (its complete fails the live-lease
  check, so no SUCCESS can publish); terminal states reject.
- `tests/integration/lab/test_experiment_lifecycle.py` (NEW) — 9 AC-mapped
  tests, fake clocks/candidates, tmp state only.
- Untouched planned files (reused read-only, no change needed):
  `evaluation/registry.py` (legacy rows surfaced via passthrough, never
  rewritten), `cli/run_backtest.py` (operator pandas path preserved).

## Acceptance evidence (behavioral RED observed, then GREEN)

- Setup RED: service module absent → collection error (not proof).
- Behavioral RED (throwaway canned-wrong stub, never committed): 9 failed
  with assertion failures on the specified outcomes.
- Real REDs fixed during implementation (all in new/test code except the
  queue addition): OMS client-ID charset; kernel 12-char order-ID prefix
  (fixtures vary the ID head); ExperimentStore single-connection
  thread-affinity crash (real defect found by the AC1 thread test — fixed
  with per-operation connections); record-before-publish ordering (terminal
  record transitioned before complete_job → reordered to queue-first);
  FAILED retry needs an explicit FAILED→QUEUED edge; uuid-bearing child IDs
  excluded from the normalized digest (pair-keyed instead).
- GREEN: `python -m pytest tests/integration/lab/test_experiment_lifecycle.py
  -q -p no:cacheprovider` → `9 passed`, exit 0.

| AC | Test | Assertion |
|---|---|---|
| AC5 | `test_rw3_01_bootstrap_recovery` | Resolved dataset+pipeline (real VerifiedRuntimePlan, digest-checked), default path calls real CandidateRuntime.load_plan, result binds pinned plan digest, artifact bytes verified by hash |
| AC0 | `test_rw3_01_0` | Completed edit rejects; clone mints new ID with parent link |
| AC1 | `test_rw3_01_1` | Threaded cancel during RUNNING fences the holder (LeaseFencingError), experiment CANCELLED, job never SUCCESS, result unavailable |
| AC2 | `test_rw3_01_2` | Crash after artifact write resumes via lease expiry with zero duplicate orders, SUCCESS once |
| AC3 | `test_rw3_01_3` | Poisoned trial FAILED with reason; record + job row + filtered list all queryable |
| AC4 | `test_rw3_01_4` | Same manifest/seed/events → equal digest; different seed → different |
| AC6 | `test_rw3_01_program_6` | Two pairs, equal capital shares, stable child IDs across retry, one job row |
| AC7 | `test_rw3_01_program_7` | Poisoned pair FAILED with sibling SUCCESS preserved and visible |
| AC8 | `test_rw3_01_program_8` | Closed BUY→SELL trade with Decimal pnl + win rate 1; all-buy trial reports UNAVAILABLE win rate, never numeric |

## Gates

1. Focused: 9 passed, exit 0.
2. Affected: `tests/unit/lab/evaluation + tests/unit/lab/orchestration +
   test_runtime_adapters.py` → `240 passed`, exit 0 (queue addition regresses nothing).
3. Full: `pytest tests` (2 pre-existing collection blocks ignored:
   `pandas_ta_classic` legacy files) → `1868 passed, 2 skipped, 5 failed` —
   all 5 are the pre-existing missing-`telegram` legacy signal-observation
   files outside this scope; zero behavioral failures.
4. `ruff check` (E,F,I,B,UP) on all 4 touched files → clean.
5. `git diff --check` → exit 0.

## Self-review notes and deviations

- No credentials, live network, real orders, Production paths. Simulator with
  injected clock; tmp stores; explicit test-double candidates (default path
  uses the real load_plan product).
- Trial fees are explicitly UNKNOWN (no schedule bound — binding one is a
  future CR, not invented here). Zero-event trials fail closed.
- Design note for reviewer: SUCCESS rerun returns the existing job
  (idempotent, no re-execution); FAILED rerun retries via lease expiry;
  CANCELLED rerun rejects (clone to rerun). FAILED→QUEUED is the only
  terminal exit, deliberate for retryable jobs.
- Out of scope, recorded: EVAL-01 rows are read-only passthrough (no invented
  run-record mapping); run_backtest.py CLI untouched.
- No subagent dispatch; no manifest edit; no push/merge/deploy.

## Next eligible consumers

RW4-01, RW8-02 (unblocked on code; still subject to coordinator DAG + review PASS).
