# Task 11 report — forward public trade and reliable order-book collection

## Scope delivered

- Added the research-only `websockets>=13,<17` range. Collector imports remain lightweight;
  importing every Task 11 module loads neither websockets nor sklearn, XGBoost, or PyTorch.
- Captured offline official public shapes for trade, full-book snapshot/update, heartbeat,
  identical duplicate, offset gap, and recoverable reconnect. No account/private payload is in
  the fixture directory or collector route.
- Added a pure parser that produces the Task 7 `TradeEvent` contract and a frozen `BookEvent`
  with Decimal values, UTC availability, stable source identity, source sequence/offset,
  `book_session_id`, quality, and explicit snapshot/update level identity.
- Added the fail-closed state machine and official offset recovery request/replay boundary.
- Added content-addressed immutable JSONL batches containing raw public envelopes and canonical
  events, a bounded synchronous queue, and an atomic fsynced per-channel checkpoint.
- Added injected transport/clock/sleeper/RNG boundaries, bounded WebSocket receive buffering,
  heartbeat timeout, exponential backoff with symmetric jitter, and SIGINT/SIGTERM shutdown.
- Added a public-only CLI. Dry-run does not import websockets, construct storage, connect, or print
  the documented public token; there are no account or order endpoints.

## RED → GREEN evidence

1. The public trade test and fixture preceded the protocol module. RED collection failed with
   `ModuleNotFoundError: indodax_lab.data.stream_protocol`; GREEN produced the exact Decimal/UTC
   `TradeEvent` and stable `indodax:public-trade:btcidr:21999427` identity.
2. The reliable snapshot test preceded `BookSessionProtocol`. RED failed importing that class;
   GREEN changed `DISCONNECTED → SYNCING → RELIABLE` and emitted only session-scoped rows.
3. The official gap-replay test preceded the recovery module. RED failed with
   `ModuleNotFoundError: indodax_lab.data.book_recovery`; GREEN built the literal recover request
   from durable offset `67410` and accepted contiguous publications `67411` and `67412`.
4. The durable batch test preceded the stream writer. RED failed importing
   `indodax_stream`; GREEN left two records queued and no checkpoint after an injected immutable
   publish failure, then published and checkpointed them on retry without exceeding the bound.
5. The injected heartbeat/reconnect test preceded `CollectorConfig` and
   `PublicMarketCollector`. RED failed importing those symbols; GREEN used receive timeout `7.0`,
   slept the literal jittered delay `2.25`, closed both fake transports, and flushed the stable
   batch/checkpoint.
6. The dry-run test preceded the CLI. RED failed with `ModuleNotFoundError` for
   `collect_market_stream`; GREEN listed only the two public channels and omitted its supplied
   token and all account/order names.
7. A documented public authentication acknowledgement initially raised `result channel is
   missing`. Its focused RED failed at the parser boundary; GREEN classifies it as `CONTROL`, so
   it cannot become market data or cause a reconnect loop.

Final focused command:

```bash
PYTHONPATH=src:/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m pytest tests/unit/lab/data/test_stream_parser.py \
  tests/unit/lab/data/test_book_recovery.py -q
```

Result: `11 passed in 0.28s`; all tests use fixtures, fake transports, injected time/sleep/random,
and real temporary storage with no network or realtime sleep.

## Reliability and lifecycle evidence

| Behavior | Evidence |
| --- | --- |
| State path | Tests observe `DISCONNECTED → SYNCING → RELIABLE → GAP → RECOVERING → RELIABLE`. `feature_eligible` is false in every state except `RELIABLE`. |
| Identical duplicate | Offset `67410` with identical canonical bytes returns `duplicate=true`, emits no second rows, and remains reliable. |
| Conflicting duplicate | Changed bytes under offset `67410` raise `ConflictingSequenceError`, mark the exact offset as a gap, and disable eligibility. |
| Gap | Jump `67410 → 67412` records exactly missing `[67411, 67411]`; the observed publication is not emitted before recovery. |
| Recovery | Request uses official `recover=true, offset=67410`; only contiguous replay through the observed publication restores the same session. |
| Failed recovery | Exact missing window is `QUARANTINED`, the old session is closed, a new `book_session_id` enters `SYNCING`, and offsets reset. |
| Bounded durability | Capacity is a hard upper bound. Failed publication retains the stable batch; immutable fsynced JSONL succeeds before the atomic fsynced checkpoint advances. |
| Reconnect | Injected heartbeat timeout closes/flushed the first connection, sleeps bounded exponential+jitter delay, and starts a fresh syncing session. |
| SIGTERM | CLI handlers call `shutdown`: stop intake, flush/persist checkpoint synchronously, then close transport to wake a blocked receive. Finalization repeats flush idempotently. |

## Verification

```bash
PYTHONPATH=src:/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m pytest -q
PYTHONPATH=src:/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m ruff check src tests
PYTHONPATH=src:/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m compileall -q src/indodax_lab
git diff --check
```

Final results were focused `11 passed in 0.30s` and full non-DL `161 passed, 1 warning in 2.26s`.
Ruff reported `All checks passed!`; compile and diff checks exited zero. The single warning remains
the pre-existing `pandas_ta` Pandas 3 deprecation warning.

The direct import audit returned `heavy_imports=[]` and `websockets_loaded=False`. A direct CLI
dry-run returned canonical public-only configuration with exit zero.

## Self-review and concerns

- The official order-book public shape documents a complete `ask`/`bid` book plus an offset but no
  exchange event timestamp. `BookEvent.event_ts` therefore uses the injected UTC ingestion time
  and carries `SOURCE_TIMESTAMP_UNAVAILABLE`; no exchange timestamp is invented.
- Official recovery is accepted only when every offset after the acknowledged value is contiguous
  and the response reaches through the publication that exposed the gap. Invalid/unsupported
  replay cannot make the old session eligible.
- Batch files are append-only and content-addressed. The mutable latest checkpoint is separate,
  uses atomic replace plus file/directory fsync, retains per-channel acknowledged offsets, and is
  written only after immutable batch publication succeeds.
- Mutation review covered float conversion, arrival-dependent trade IDs, missing baseline,
  eligibility during gap/recovery, duplicate re-emission, changed duplicate acceptance, skipped
  replay offsets, session reuse after failed recovery, checkpoint-before-batch, queue overflow,
  unbounded socket buffering, fixed reconnect delay, lost shutdown batch, token persistence, and
  control acknowledgements treated as data.
- No live-network assertion was made: protocol compatibility is based on the current official
  documented shapes and the production transport stays behind the same fakeable boundary used by
  the offline suite.

## Fix round 1/5 — transport, context binding, recovery abandonment, and lifecycle

### Critical findings resolved

- WebSocket normal/abnormal receive and send closures, plus handshake failures, are normalized to
  project `StreamTransportClosed`. `websockets.exceptions.WebSocketException` is imported only
  inside the real connector and works across the pinned 13–16 range; collector module import still
  does not load websockets or any ML/DL library.
- Every trade/book parser call binds the exact configured pair. Channel suffix and payload pair
  must agree before book state changes. Recovery retains request ID, session ID, canonical pair,
  and channel; only the exact outstanding response may restore `RELIABLE`.

### Important findings resolved

- Offset regression/wrap is a structured `SequenceRegressionError`, with non-inverted quarantine
  window, observed offset, prior reliable offset, session, pair, channel, and `OFFSET_REGRESSION`.
  Its checkpoint remains at the prior reliable offset rather than regressing to zero.
- `RECOVERING` now demultiplexes matching recovery replies from heartbeat/control/trade/book
  frames. Trades continue independently; books are persisted as `BOOK_UNRELIABLE`, never advance
  the book checkpoint, and cannot become LOB-eligible before complete replay.
- Gap abandonment is a two-phase operation: prepare exact quarantine, durably append and flush it,
  then rotate. A write failure retains the same `GAP`/`RECOVERING` state, request, session, and
  window for retry without duplicate quarantine rows. Send/receive close, recovery failure,
  heartbeat timeout, SIGTERM, and finalization all use this boundary.
- Backoff resets at the first valid frame after successful subscription. The injected sequence
  fail → healthy → fail sleeps `[2.0, 2.0]`, not `[2.0, 4.0]`.
- Heartbeat freshness uses an injected monotonic clock. Only the documented bare pong ID `3`
  refreshes it; trades and controls do not. Initial subscription sends official method-7 ping and
  every recognized pong schedules the next ping.
- SIGTERM retains one shutdown task and awaits it. Flush/quarantine failure is surfaced, while
  transport close stays in `finally`; no task exception is left unobserved.

### RED → GREEN evidence

Each finding received a focused failing regression before its production change:

1. transport close symbols were absent, then library handshake/closure escaped unchanged;
2. wrong book channel and payload pair both reached `RELIABLE`;
3. stale recovery ID and changed session/channel restored reliability;
4. offset `67410 → 0` produced an inverted `(67411, -1)` gap;
5. heartbeat/trade/book frames during recovery were parsed as recovery responses;
6. failed quarantine publication had already changed the session to `SYNCING`;
7. recovery send/receive closure produced no quarantine record;
8. fail → healthy → fail slept `[2.0, 4.0]`;
9. active trade/control traffic exhausted the fake transport rather than the heartbeat deadline;
10. arbitrary bare ID `99` refreshed heartbeat and pong did not schedule another ping;
11. CLI SIGTERM logged `Task exception was never retrieved` and returned success;
12. offset-regression quarantine advanced the checkpoint to zero and lacked pair/channel lineage.

GREEN focused result: `34 passed in 0.35s`.

### Fix verification and deferred minor

```bash
PYTHONPATH=src:/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m pytest tests/unit/lab/data/test_stream_parser.py \
  tests/unit/lab/data/test_book_recovery.py tests/unit/lab/data/test_parquet_store.py \
  tests/unit/lab/data/test_manifest.py tests/unit/lab/data/test_indodax_candles.py \
  tests/integration/lab/test_candle_backfill.py -q
PYTHONPATH=src:/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m pytest -q
PYTHONPATH=src:/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m ruff check src tests
PYTHONPATH=src:/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m compileall -q src/indodax_lab
git diff --check
```

Results: Task 11 plus durable Task 8/9 publication suite `70 passed in 0.74s`; full
non-DL suite `184 passed, 1 warning in 2.03s`; Ruff clean; compile and diff checks exit zero.
The warning is the unchanged `pandas_ta`/Pandas deprecation.

As explicitly deferred for final review, importing the CLI still loads pyarrow through the
existing eager `indodax_lab.data.__init__` exports. The audit records
`heavy_imports=[]`, `websockets_loaded=False`, and `pyarrow_loaded_deferred=True`; this fix round
does not expand into package import restructuring.
