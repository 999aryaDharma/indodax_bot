# Existing signal bot and SQLite compatibility

## Purpose and responsibilities

Existing signal bot and SQLite compatibility. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `src/main.py, src/paper_trader.py, src/signal_observer.py`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| BASE-01 | CI membuktikan perilaku bot dengan fixture tanpa HTTP atau Telegram nyata. | `docs/sprints/baseline/BASE-01-offline-verification-harness.md` |
| BASE-02 | Rencana bullish yang memenuhi minimum RR dapat melewati risk gate. | `docs/sprints/baseline/BASE-02-reachable-bullish-risk-reward.md` |
| BASE-03 | Riwayat transaksi v2 menghasilkan sisi dan urutan kepemilikan yang benar. | `docs/sprints/baseline/BASE-03-trade-v2-ownership-parsing.md` |
| BASE-04 | Paper trade mempertahankan debit kas dan fee secara exact setelah upgrade schema lama. | `docs/sprints/baseline/BASE-04-exact-paper-accounting-migration.md` |
| BASE-05 | Setiap keputusan dan outcome tercatat walau Telegram gagal atau pengguna tidak mengklik. | `docs/sprints/baseline/BASE-05-unbiased-signal-observations.md` |
| BASE-06 | Perilaku API, risk, accounting dan observasi terbukti bersama melalui regression checkpoint. | `docs/sprints/baseline/BASE-06-baseline-trust-checkpoint.md` |

## Inputs, outputs and public interfaces

### BASE-01 — Offline verification harness

pytest + injected transports -> reproducible result; no credentials required.

Acceptance boundary:
- Transport nyata dipanggil -> test gagal.
- Import modul tidak mengeksekusi scheduler.
- Fixture deterministik menghasilkan hasil sama.

### BASE-02 — Reachable bullish risk reward

ATR stop/target configuration -> TradingPlan or explicit reject.

Acceptance boundary:
- RR dihitung dari jarak entry-stop dan target-entry.
- ATR nol ditolak.
- Perubahan multiplier tidak menyisakan gate mustahil.

### BASE-03 — Trade v2 ownership parsing

JSON isBuyer:bool, qty, fee, price, time:milliseconds -> typed trade; seconds only compatibility view.

Acceptance boundary:
- String false ditolak sebagai boolean.
- BUY SELL dalam detik sama diurutkan milidetik.
- Top-level non-object gagal terkendali.

### BASE-04 — Exact paper accounting migration

Decimal buy/sell -> canonical TEXT, gross cash cost basis, LEGACY_ESTIMATE or EXACT accounting status.

Acceptance boundary:
- Migrasi REAL ke TEXT membuat backup sebelum perubahan.
- Double close hanya satu sukses dan rollback utuh.
- Deleted highest ID tidak menurunkan sqlite_sequence.

### BASE-05 — Unbiased signal observations

Decision key -> observation; exec/skip/paper:<id> -> separate intent; closed bar -> SL_FIRST outcome.

Acceptance boundary:
- Decision collision tidak mengaitkan intent ke keputusan lama.
- Bar sebelum boundary keputusan tidak menentukan outcome.
- Close dan checkpoint atomik saat restart.

### BASE-06 — Baseline trust checkpoint

Committed source SHA + command exits -> phase0 evidence.

Acceptance boundary:
- Semua field v2 termasuk maker flag fee dan unit diverifikasi.
- Mutation kontrak membuat checkpoint merah.
- Evidence membedakan SHA kode dari SHA dokumen.

## Data model, persistence and lifecycle

SQLite backup-first; exact accounting TEXT; preserve triggers, FK children and high-water mark. No production DB touched by tests.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

Two connections exercise atomic close; decisions have immutable unique key. Replays retain monotonic checkpoints.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

Callbacks are untrusted; validate observation identity and allowlisted chat. No real order executor.

## Failure, retry, migration and recovery

Protect existing flat modules; migration on copy only; abort/rollback on failure and retain verified backup.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)
