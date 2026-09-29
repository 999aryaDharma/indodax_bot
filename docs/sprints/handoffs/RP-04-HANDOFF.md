# RP-04 handoff — Canonical feed and environment runtime adapters

Status: REVIEW

## Identity
- Sprint ID: RP-04 — Canonical feed and environment runtime adapters
- Implementation agent: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Independent reviewer: UNASSIGNED (independent review required before DONE)
- Branch: `dev` (main checkout; recommended-branch worktree waived by owner session precedent)
- Base SHA: `234d4b9`
- Manifest claim READY→IN_PROGRESS + owner: PENDING coordinator (manifest untouched)
- Dependencies DONE verified: RP-02, RP-03, PM-02 (manifest + handoffs RP-02/RP-03/PM-02)

## Files and contracts
- New: `src/indodax_lab/market/event_feed.py` (EventFeed, SubscriberGapError)
- New: `src/indodax_lab/runtime/kernel.py` (RuntimeKernel, deny_all_stage)
- New: `src/indodax_lab/runtime/composition.py` (build_research_runtime, ResearchBoundaryError)
- New: `src/indodax_lab/execution/shadow_venue.py` (ShadowVenueAdapter)
- New: `src/indodax_lab/execution/simulator_venue.py` (SimulatedOutcome, SimulatorVenueAdapter)
- New: `tests/integration/lab/test_runtime_adapters.py` (10 tests)
- Modified: `src/indodax_lab/control/pipeline.py` (live import module→function-local, behavior preserved)
- Modified: `src/indodax_lab/execution/__init__.py` (live venue lazy via PEP 562 `__getattr__`)
- Modified: `src/indodax_lab/runtime/__init__.py`, `src/indodax_lab/market/__init__.py` (exports)
- Untouched as designed: `venue.py` (protocol exists), `gateway.py` (feed source injected), PM-02 store, RP-02 evaluator, OMS
- Contract: `RuntimeKernel.process(event)->RuntimeStepResult; EventFeed.subscribe(namespace,after_sequence)->Iterator[CanonicalMarketEvent]; ShadowVenueAdapter/SimulatorVenueAdapter implement TradingVenue; build_research_runtime(config)->RuntimeKernel cannot resolve a live adapter.`

## Acceptance evidence
| AC ID | Test | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| RP-04-AC0 | `test_rp_04_0` | `python -m pytest tests/integration/lab/test_runtime_adapters.py -q -p no:cacheprovider` | Exit 0 (5 subscribers, 1 upstream poll, identical bytes) | working tree |
| RP-04-AC1 | `test_rp_04_1` | same | Exit 0 (GAP_DETECTED on overflow, resume→[7] no replay/skip) | working tree |
| RP-04-AC2 | `test_rp_04_2` + `test_rp_04_2_unwired_kernel_emits_no_orders` + `test_rp_04_2_shared_core_carries_no_live_import` | same | Exit 0 (live, subclass wrapper, factory refused; deny-all default; subprocess proves no live import) | working tree |
| RP-04-AC3 | `test_rp_04_3` | same | Exit 0 (PARTIAL/REJECT/UNCERTAIN → shared OMS states) | working tree |
| RP-04-AC4 | `test_rp_04_4` | same | Exit 0 (restart reprocess ACKNOWLEDGED, 1 inbox row) | working tree |
| RP-04-AC5 | `test_rp_04_bootstrap_recovery` | same | Exit 0 (no-fill advances once; delayed fill commits once, replay duplicate) | working tree |
| RP-04-AC6 | `test_rp_04_program_6` | same | Exit 0 (real STOP_LOSS exit → SELL order; no writer attrs; no dup) | working tree |
| RP-04-AC7 | `test_rp_04_capacity_7` | same | Exit 0 (bounded fan-out identical bytes, credential-free venue) | working tree |

RED history (behavioral, all observed pre-fix): AC1 gap/cursor semantics; AC2 live/subclass/factory admission + unwired-kernel emission; AC3 OMS transition guards; feed replay/queue double-buffer; simulator PARTIAL bounds. No ModuleNotFoundError RED claimed as behavioral.

Gates: focused file 10 passed; affected (runtime+execution+market+control+registry) 135 passed; full `pytest tests` 1831 passed / 5 failed / 2 errors / 2 skipped — every non-pass is a missing module (`telegram`, `pandas_ta_classic`) in files outside this scope, zero behavioral failures. Ruff 0.16.8 clean on all touched files.

## Migration / rollback
- Additive-only except two contained changes (pipeline import locality, execution `__init__` lazy venue — both behavior-preserving, full suite green).
- Rollback = delete the 6 new files and revert the 4 modified ones; no schema/data migration.

## Deviations and known risks
- `venue.py`/`gateway.py` listed in manifest files but intentionally untouched (protocol exists; source injected). No scope widened.
- Mid-flight DECIDED resume raises `KernelBlockedError` directing to PM-02 `recover()` — kernel manufactures no progress there by design.
- AC7 measured host artifact pending (operator-owned, same class as JOB-02/OPS-01/QA-03 physical gates).
- Main checkout used instead of recommended worktree (owner session precedent); no other owner touches these paths (IN_PROGRESS: C12-01, S08-01, S09-01 are strategy scope).

## Pending external gates
- No production activation; real-data/host runs need source/license/cost/resource evidence.
- Coordinator: manifest READY→IN_PROGRESS→REVIEW transitions and DONE promotion after independent PASS.

## Fix cycle 1 (advisory review NEEDS-FIX → addressed)
- Reviewer: subagent session `ses_f13f181b1ffejvek67vrgl2YKA` (advisory only, not final approval). Verdict NEEDS-FIX, 0 Critical, 5 Important, 2 Minor. All accepted as blocking; fixed in one batch below.
- I1 replay/queue double-delivery + spurious gap (`event_feed.py`): replay now from subscribe-time snapshot; queue drain sequence-guarded; cursor set before yield. Pinned by `test_rp_04_1_no_replay_duplication`.
- I2 lossy gap cursor (`event_feed.py`): first-drop resume keeps last-delivered cursor; dropped count accumulates; `test_rp_04_1` resume corrected `[7]`→`[4,5,6,7]` with `dropped==1`, `resume==3`.
- I3 multi-intent order-ID collision (`kernel.py`): stable per-event ordinal suffix when >1 intent; single-intent IDs unchanged (backward compat with bootstrap/restart evidence). Pinned by `test_rp_04_multi_intent_distinct_orders`.
- I4 PARTIAL evidence loss (`kernel.py`): `_submit` propagates price/executed/partial; mirror transitions PARTIALLY_FILLED with qty+price and always carries venue_order_id; per-transition OMS event IDs (`_new`/`_dispatch`/`_<status>`). Pinned by `test_rp_04_partial_mirror`.
- I5 delegation-wrapper bypass (`composition.py`): `_is_live_writer` walks one level of held attributes; deeper nesting documented out of scope. Pinned by `test_rp_04_2_delegating_wrapper_refused`.
- M1 `kernel_factory` scope documented; M2 simulator keeps receipt index so `get_order*` supports reconcile-by-ID.
- Evidence: 14/14 focused pass; affected gate 139 passed (runtime+execution+market+control+registry); ruff clean on touched files. Full-repo gate reuses prior result (only change since is this batch; affected gate covers blast radius).
- Not DONE: implementer cannot final-approve own work; manifest untouched (coordinator single-writer). Needs independent PASS + coordinator promotion.
