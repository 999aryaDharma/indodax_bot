# Immutable ingestion and quality evidence

## Purpose and responsibilities

Immutable ingestion and quality evidence. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `src/indodax_lab/data, src/indodax_lab/cli`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| DATA-01 | Collector dan lab berbagi identity pair, UTC, Decimal dan version lineage yang ketat. | `docs/sprints/market-data/DATA-01-canonical-market-contracts.md` |
| DATA-02 | Dataset dan manifest tidak dapat tertimpa oleh retry dengan konten berbeda. | `docs/sprints/market-data/DATA-02-durable-immutable-publication.md` |
| DATA-03 | Backfill menyimpan wire asli sebelum parsing dan resume hanya dari window yang durable. | `docs/sprints/market-data/DATA-03-auditable-candle-backfill.md` |
| DATA-04 | Snapshot rusak menghasilkan quality finding dan tidak dapat menjadi input eligible. | `docs/sprints/market-data/DATA-04-snapshot-quality-decisions.md` |
| DATA-05 | Collector mempertahankan bukti sequence gap dan reconnect tanpa menganggap event hilang sebagai normal. | `docs/sprints/market-data/DATA-05-reliable-forward-market-collection.md` |
| DATA-06 | Pipeline offline benar-benar menghubungkan wire sampai final snapshot melalui artifact yang diverifikasi. | `docs/sprints/market-data/DATA-06-provider-derived-reproducible-snapshot.md` |

## Inputs, outputs and public interfaces

### DATA-01 — Canonical market contracts

CanonicalPair, Candle, TradeEvent + path roots -> validated immutable records.

Acceptance boundary:
- schema_version wajib.
- Interval tidak dikenal ditolak.
- ingested_at sebelum event_ts memerlukan anomaly flag.

### DATA-02 — Durable immutable publication

Arrow explicit schema + ZSTD + partial/fsync/rename + canonical checksum manifest.

Acceptance boundary:
- Konten sama dapat retry tanpa melewati directory fsync.
- Konten berbeda ditolak.
- Failure injection tidak meninggalkan sukses atau partial tersembunyi.

### DATA-03 — Auditable candle backfill

run_backfill(pair, interval, start, end, transport) -> wire, bronze, manifest, checkpoint; [start,end).

Acceptance boundary:
- Dry-run tidak menulis atau mengakses jaringan.
- Malformed row masuk reject list tanpa harga nol.
- Checkpoint diverifikasi bersama wire metadata dan checksum.

### DATA-04 — Snapshot quality decisions

validate_snapshot(snapshot, coverage, as_of) -> canonical quality report, CLI exit 0/3/4.

Acceptance boundary:
- FAIL QUARANTINED upstream tidak menjadi PASS.
- Coverage invalid exit 4 dan corrupt content exit 3.
- Path traversal dan symlink loop ditolak terkendali.

### DATA-05 — Reliable forward market collection

DISCONNECTED -> SYNCING -> RELIABLE; gap -> GAP -> RECOVERING; bounded durable writer.

Acceptance boundary:
- Normal close memicu reconnect dengan stream identity benar.
- Pending gap dipertahankan sampai quarantine durable.
- SIGTERM menutup transport dan flush dengan checkpoint setelah durable write.

### DATA-06 — Provider-derived reproducible snapshot

Typed loaders -> recomputed sentry decisions -> fixed cutoff -> immutable snapshot with 45 source references.

Acceptance boundary:
- Wire garbage atau event berbeda dari parse ditolak.
- Cap observation direkonstruksi dari body provider.
- Dua root berbeda memberi snapshot dan global decision ID identik.

## Data model, persistence and lifecycle

Raw bytes before parse; canonical typed schemas; immutable Parquet/manifest; partial never means success.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

One writer per partition; only checkpoint durable data. Verify bytes on retry; conflicting hash fails closed.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

Treat JSON and paths as untrusted. Bounded payloads, reject symlink escape, never persist secret request headers.

## Failure, retry, migration and recovery

Quarantine failed content; recover from verified wire; never repair prices with zero or overwrite existing partition.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)
