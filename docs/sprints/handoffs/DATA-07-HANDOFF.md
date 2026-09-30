# DATA-07 handoff — selectable public collection and coverage workflow

Status: SUBMITTED FOR INDEPENDENT REVIEW (implementation complete; coordinator dispatches reviewer, manifest untouched).

## Identity

- Sprint: DATA-07 — Selectable public collection and coverage workflow
- Implementation owner: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Independent reviewer: UNASSIGNED (coordinator dispatches; implementer cannot self-approve)
- Branch: `dev` (main checkout; recommended `feat/data-07-selectable-public-collection-and-coverage-workflow` not used — isolated additive paths, no other owner on these files)
- Code SHA: `af9819e` — `feat(data-07): selectable public collection and coverage workflow`
- This handoff is the evidence follow-up to `af9819e`; it contains no code changes.
- Environment: Windows, Python 3.14.0, pytest 9.0.3, ruff 0.16.9, `D:\bot-trading`

## Files and contracts

- `src/indodax_lab/data/selectable_collection.py` (NEW) — `CollectionCapabilities`
  (immutable catalog; `defaults()` from the existing pair/interval maps;
  `extend_pairs()` returns a new instance), `SelectableCollector.collect(
  DatasetRequest, request_id) -> CollectionResult` (status COLLECTED |
  RESUMED | DEFERRED | REJECTED | FAILED, always explicit, never silent
  success). Uses existing contracts only: IndodaxCandleClient (wire-first
  public fetch), SqliteJobQueue (durable job ref: submit → claim → complete
  with SHA-256 result artifact; identical request_id short-circuits from the
  stored artifact, conflicting payload rejects), DatasetRegistry
  (coverage-hit returns existing refs without fetch; miss fetches only the
  requested range and publishes atomically with explicit missing_intervals),
  evaluate_admission (optional guarded admission; negative decision defers
  with the guard's reason, job stays PENDING for resume).
- `src/indodax_lab/data/indodax_candles.py` (additive only, +27/-15) —
  optional keyword-only `venue_symbol` override threaded through
  `fetch_window -> adapter.parse -> parse_pascal_rows/parse_columnar ->
  _parse_rows`. Default `None` preserves the module map byte-for-byte for all
  existing callers (DATA-03 evidence unchanged). Required by AC4 so extended
  pairs resolve without a competing pair type; CanonicalPair validation
  untouched.
- `tests/integration/lab/test_selectable_collection.py` (NEW) — 6 AC-mapped
  tests, fake transport + tmp state only.
- Untouched planned files (reused as-is, no change needed):
  `cli/backfill_candles.py` (operator bulk path preserved),
  `data/dataset_registry.py`, `contracts/common.py` (CanonicalPair owner).

## Acceptance evidence (RED → GREEN, TDD)

- Setup RED: module absent → collection error (not behavioral proof).
- Behavioral RED (throwaway stub returning canned REJECTED, never committed):
  `6 failed` with AssertionError on the behavioral expectations.
- GREEN: `python -m pytest tests/integration/lab/test_selectable_collection.py -q -p no:cacheprovider` → `6 passed`, exit 0.

| AC | Test | Assertion |
|---|---|---|
| AC0 | `test_data_07_0` | Unsupported pair/timeframe REJECTED before fetch (0 transport calls, 0 jobs, no catalog entry) |
| AC1 | `test_data_07_1` | Gap range explicit, `complete_coverage False`, quality WARN + not silver, manifest missing_intervals = 1 |
| AC2 | `test_data_07_2` | Identical retry RESUMED with same dataset_ref, 1 fetch total, catalog bytes identical; conflicting payload REJECTED |
| AC3 | `test_data_07_3` | Transport params exactly {symbol,tf,from,to} (no credential surface); wire body file bytes == served bytes |
| AC4 | `test_data_07_4` | CanonicalPair validation pinned; pre-extension dataset SHA identical after extension; new pair collectable; unknown pair still REJECTED |
| AC5 | `test_data_07_capacity_5` | Stale reading DEFERRED (SENSOR_STALE), 0 fetches, durable PENDING job; fresh reading resumes same request_id to COLLECTED with 1 fetch and still 1 job row |

## Gates

1. Focused: 6 passed (above), exit 0.
2. Affected subsystem (shared `indodax_candles.py` + registry/queue/worker surface):
   `test_candle_backfill.py + test_dataset_registry_versions.py +
   test_raw_to_silver_pipeline.py + test_snapshot_validation.py +
   test_queue.py + test_resources.py` → `81 passed, 2 skipped` (both skips
   pre-existing platform: Linux /proc, Windows symlink privilege), exit 0.
3. `ruff check` on all 3 touched files → clean (12 auto-fixable findings in
   new files fixed, re-verified GREEN after).
4. `git diff --check` → exit 0.

## Self-review notes and deviations

- No credentials, live network, real orders, Production paths, or secret logging. Transport params pinned by test_3.
- Single-writer safe: one queue claim per collect; foreign-claim and live-lease cases fail closed without touching other jobs.
- Deviation: per-request fetch uses one `fetch_window` over the requested range (no `plan_windows` split); bulk resume stays on the `run_backfill` path. Recorded for reviewer.
- Deviation: timeframe extension not implemented (AC4 requires pairs only); `extend_pairs` validates form via CanonicalPair and rejects blank venue symbols.
- Open external gate (unchanged, not established here): AC5 measured host artifact — no qualified ASUS headroom numbers exist, so guard limits stay unset-by-default and fail closed (same posture as JOB-02 AC4/AC5). Do not mark DONE from the offline suite.
- No subagent dispatch; no manifest edit; no push/merge/deploy.

## Next eligible consumers

RW3-01, RW7-01 (unblocked on code; still subject to coordinator DAG + review PASS).
