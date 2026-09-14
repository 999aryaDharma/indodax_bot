# Task 9 report — auditable Indodax candle backfill

## Scope

Implemented only the Task 9 public candle ingestion path:

- two offline `history_v2` fixtures cover Pascal rows and `t/o/h/l/c/v`
  columns, including out-of-order data, an identical duplicate, and a malformed
  row;
- pure named parsers and `IndodaxCandleAdapter` produce validated Task 7
  `CandleRecord` values, stable source event IDs, original epoch/unit audit
  metadata, and explicit row rejects;
- `WireStore` immutably publishes exact response bytes plus status, safe selected
  response headers, body SHA-256, request identity, and receipt time before any
  status/JSON/candle parsing;
- monthly end-exclusive backfill windows publish through the Task 8
  `ParquetStore`, then publish checksum-protected completion markers used for
  verified resume;
- the CLI dry-run reports only window/request counts and returns before path,
  clock, transport, sleeper, or store construction.

No account/trade endpoint, credential, Telegram, model, live bot, or later-task
quality-gate behavior was added. The injected fake transport, clock, sleeper,
and temporary roots keep all tests offline.

## RED → GREEN evidence

1. Parser and wire boundary tests were written before either module existed.
   - RED command:
     `PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src python -m pytest tests/unit/lab/data/test_indodax_candles.py -q`
   - RED result: collection failed with `ModuleNotFoundError: No module named
     'indodax_lab.data.indodax_candles'`.
   - GREEN after the minimal parser/client/wire implementation: `10 passed in
     0.31s`.
2. The two named offline replay entry points from the brief were added in their
   own cycle.
   - RED result: collection failed with `ImportError: cannot import name
     'parse_columnar'`.
   - GREEN after adapter dispatch through `parse_pascal_rows` and
     `parse_columnar`: combined Task 9 suite `15 passed in 3.22s`.
3. Integration tests were written before the CLI package existed.
   - RED command:
     `PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src python -m pytest tests/integration/lab/test_candle_backfill.py -q`
   - RED result: collection failed with `ModuleNotFoundError: No module named
     'indodax_lab.cli'`.
   - GREEN after monthly planning, publication, rate limiting, and checkpoints:
     `4 passed in 0.51s`.
4. Resume-marker semantics received a final independent hardening cycle.
   - RED: a marker whose checksum was correctly recomputed after changing
     `accepted_rows` to `999` resumed successfully instead of failing against
     its two-row manifest (`Failed: DID NOT RAISE
     ImmutableContentConflictError`).
   - GREEN: resume now cross-checks accepted rows against manifest row count and
     rejected rows against the literal reject list; targeted result `1 passed in
     0.45s`.

All expected IDs, checksums, timestamps, request parameters, counts, rejection
codes, and CLI output are literal expectations. HTTP is represented only at the
transport boundary; filesystem publication, Parquet, manifest validation, and
resume checks use real temporary files.

## Wire-first, resume, and conflict evidence

- `test_client_writes_wire_before_unsupported_json_shape_is_parsed` forces a
  fail-closed unsupported JSON object and still finds both exact `body.json` and
  `metadata.json` on disk.
- The wire metadata test verifies literal status/header/checksum values, scans
  every persisted artifact to prove authorization/cookie secrets are absent,
  reuses identical content with the original receipt timestamp, and verifies a
  different body raises `ImmutableContentConflictError` without changing bytes.
- The fake-transport integration writes one raw body, one metadata file, one
  two-row ZSTD Parquet file, one validated two-row manifest, and one completion
  marker. Its rerun makes zero additional HTTP calls and leaves the same one
  Parquet file/manifest.
- Resume validates checkpoint identity and checksum, raw-body checksum,
  content-addressed manifest identity, and every Parquet checksum before it may
  skip a request. A tampered marker fails before HTTP and remains untouched.
- Two actual monthly requests call the injected sleeper exactly once between
  requests; dry-run calls neither transport nor sleeper and creates no root.

## Final verification

Commands:

```bash
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m pytest tests/unit/lab/data/test_indodax_candles.py \
  tests/integration/lab/test_candle_backfill.py -q
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m pytest -q
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m ruff check src tests
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m compileall -q src/indodax_lab
git diff --check
```

Pre-report verification results: focused Task 9 suite `15 passed`; full non-DL
suite `115 passed, 1 warning in 2.08s`; Ruff reported `All checks passed!`;
compile and diff checks exited 0. The warning is the pre-existing
`pandas-ta`/pandas 3.0 `Pandas4Warning` already recorded by Tasks 7 and 8.

## Files and self-review

- `src/indodax_lab/data/indodax_candles.py`: pure shape parsers, deterministic
  deduplication/rejection policy, public transport contract, and wire-first
  client.
- `src/indodax_lab/data/wire_store.py`: credential-free request audit schema and
  append-only raw response publication.
- `src/indodax_lab/cli/backfill_candles.py` and `cli/__init__.py`: monthly planner,
  verified checkpoints, rate limiting, dry-run, and public-only default
  transport.
- `tests/fixtures/indodax/history_v2_*.json`: exact supported wire shapes.
- `tests/unit/lab/data/test_indodax_candles.py`: parser, ID, reject, dedup,
  credential, conflict, and ordering contracts.
- `tests/integration/lab/test_candle_backfill.py`: dry-run and complete offline
  wire-to-bronze publication/resume flow.

Self-review mutations considered: arrival-based IDs, row-order IDs, zero-filled
prices, first-conflict-wins, uppercase/implicit pair conversion, parsing before
wire publication, credential header persistence, marker trust without checksum,
HTTP on resume, Parquet overwrite, and extra sleeps all fail at least one test.

The binding requirement identifies the endpoint symbol as lowercase `btcidr`,
so the adapter keeps an explicit `btc_idr -> btcidr` map even though the older
bot path uppercases its symbol. Unsupported pairs fail at the adapter boundary;
adding further verified venue mappings belongs in a future adapter extension.

## Fix round 1 — venue identity, range, resume lineage, epoch safety, durability

Commit: recorded separately after the original Task 9 commit; no amend.

This round supersedes the original report's lowercase-symbol concern. The exact
Task 9 wire and bronze requirement is the explicit mapping
`btc_idr -> BTCIDR`; both request `symbol` and persisted `venue_symbol` now use
`BTCIDR`, and deterministic source IDs were updated for that source identity.

### RED → GREEN evidence

1. **Venue and endpoint symbol**
   - RED: the two fixture parser cases returned `btcidr` instead of literal
     `BTCIDR`, and the fake transport received lowercase `symbol`; focused run
     produced `3 failed` for those exact comparisons.
   - GREEN: the explicit adapter mapping now supplies uppercase source identity
     to request, wire metadata, event ID, and `CandleRecord`; focused parser plus
     integration run `12 passed`.
2. **End-exclusive request range**
   - RED: an adversarial response containing one row before `start`, one at
     `start`, and one exactly at `end` reported `accepted_rows == 3` instead of
     literal `1`.
   - GREEN: the client constrains the parsed batch to `[start, end)` before
     Parquet publication. Both excluded rows retain row index, source event ID,
     epoch audit metadata, and `OUTSIDE_REQUEST_WINDOW`; targeted run `1 passed`.
3. **Complete wire lineage on resume**
   - RED: changing persisted `metadata.json` status from `200` to `500` still
     resumed successfully (`Failed: DID NOT RAISE ImmutableContentConflictError`).
   - GREEN: checkpoint now references body and metadata paths/checksums plus
     request ID and status. Resume validates metadata shape/checksum, exact
     endpoint/pair/symbol/interval/window/unit identity, derived request ID, 2xx
     status, body checksum/size declarations, manifest, and partition checksums;
     focused lineage cases `3 passed`.
4. **Platform timestamp errors**
   - RED: `Time=10**100` escaped the parser as `OverflowError: timestamp out of
     range for platform time_t` and aborted a batch containing a valid row.
   - GREEN: `OverflowError` and `OSError` from platform timestamp conversion join
     existing row-level conversion failures; the valid row survives and the
     huge epoch is retained in an `INVALID_ROW` reject. Targeted run `1 passed`.
5. **Shared durable publication**
   - RED: five injected cases showed a visible raw body after metadata failure,
     missing parent/idempotent fsync, visible body after partial-cleanup failure,
     plain `OSError` instead of indeterminate rollback state, and a visible
     checkpoint after namespace-fsync failure (`5 failed`).
   - GREEN: `data/publication.py` is the shared Task 8-style primitive for durable
     directory creation, flushed partials, atomic no-clobber links, new/reused
     namespace fsync, durable cleanup, rollback, and explicit indeterminate
     publication. Wire/checkpoint use it, and Task 8 partition publication now
     delegates to it while preserving Task 8's monkeypatchable wrappers. The
     combined injected cases plus all Task 8 Parquet tests finished `16 passed`.

### Fix verification and self-review

```bash
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m pytest tests/unit/lab/data/test_indodax_candles.py \
  tests/integration/lab/test_candle_backfill.py \
  tests/unit/lab/data/test_parquet_store.py tests/unit/lab/data/test_manifest.py -q
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m pytest -q
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m ruff check src tests
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m compileall -q src/indodax_lab
git diff --check
```

Pre-report results: focused Task 9 + Task 8 data suite `36 passed in 0.81s`;
full non-DL suite `123 passed, 1 warning in 1.91s`; Ruff reported
`All checks passed!`; compile and diff checks exited 0. The sole warning remains
the pre-existing `pandas-ta`/pandas 3.0 `Pandas4Warning`.

Self-review confirmed filtering occurs only after exact wire publication and
before Task 8 validation/publication; checkpoints remain after manifest success
only; dry-run construction is unchanged. New publication failures remove every
newly visible final when state is knowable and raise
`IndeterminatePublicationError` when rollback cannot establish durable state.
