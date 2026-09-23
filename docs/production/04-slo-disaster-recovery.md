# SLO, observability and disaster recovery

Tidak ada angka uptime, latency, RPO atau RTO yang dianggap benar tanpa pengukuran pada target host.

Production Main recovery di bawah tetap terpisah dari ASUS Research Runtime. [Shared Market Runtime](research-workbench/SHARED-MARKET-RUNTIME.md#o-observability-and-service-lifecycle) memiliki kontrak lengkap untuk feed/feature/inference/shadow health, namespace recovery dan service lifecycle; [ADR-008](../decisions/ADR-008-shared-market-runtime-and-asus-edge.md) menetapkan batasnya.

## ASUS runtime qualification

Catat koneksi/valid-input age, reconnect/gap/duplicate/out-of-order, REST fallback, queue depth/bytes/consumer lag; feature freshness/latency/snapshot/cache/schema mismatch; loaded-model memory/load/inference p50/p95/p99/cache/timeouts/evictions; candidate lag/deferred decisions/reconciliation/checkpoint age; CPU/load/RSS/available RAM/swap I/O/disk latency-growth/temperature/throttling.

Gunakan bounded metric labels dan structured audit untuk event/candidate/artifact IDs. Readiness tergantung input dan state yang dibutuhkan setiap consumer; socket connected bukan bukti reliable. Unknown required sensors menghentikan admission compute. Swap aktif adalah overload. Shed analytics/optional candidates sebelum mengorbankan feed integrity atau durable state; required model failure mem-pause consumer yang bergantung padanya.

Qualification mencakup idle-host dan realistic co-resident services, load 30 menit, beberapa jam thermal steady state dan 24h+ soak. Jalankan matrix rule/ML/DL/event-rate pada [desain](research-workbench/SHARED-MARKET-RUNTIME.md#m-resource-governance-and-asus-qualification), termasuk 1x/2x/5x/10x observed-rate replay. Simpan exact SHA/environment/host inventory dan limits terukur. Soak infrastruktur bukan pengganti >=90 hari AND >=100 closed forward trades.

ASUS restart memverifikasi feed journal, source cursor, feature checkpoint dan execution state per namespace. Missing replay/gap dicatat; candle/decision lama tidak ditulis ulang menjadi forward evidence. SIGTERM menghentikan admission/intake, flush durably, drain dengan deadline, lalu close; crash/disk-full tidak mengakui state yang belum commit. Backup menggunakan consistent SQLite API plus immutable referenced artifacts dan restore di root terpisah. Tidak ada WAL lintas host.

## Required telemetry

Market data: event/receive lag, closed-bar age, duplicate/out-of-order, reconnect, gaps, clock offset.

Model/decision: candidate bundle ID, feature hash, inference latency, abstention/model mismatch, non-finite feature reject dan decision reason.

Risk: equity/high-water mark, daily/weekly loss, drawdown, exposure, rejected intent dan halt transition.

Execution: submit/ack latency, open-order age, cancel/replace, rejects, partial fills, realized maker/taker, slippage/spread, unknown write outcomes.

Ledger/reconciliation: posting balance, last reconciled cursor, venue delta, duplicate attempts, checkpoint errors, backup freshness.

## Alert severity

INFO: expected event.
WARN: degraded but controlled.
HALT: new exposure disabled.
CRITICAL: financial/order state uncertain, secret compromise, atau repeated safety invariant failure.

Alert delivery failure tidak mengubah underlying risk decision.

## Recovery rule

Jika financial state uncertain: halt new exposure, preserve evidence, reconcile, baru resume. HALT_NEW_ORDERS bukan FLATTEN.

## Restart sequence

1. boot ke READ_ONLY/RECOVERY;
2. verify release bundle checksum/config;
3. verify ledger DB integrity;
4. restore persisted risk halt/high-water state;
5. fetch venue balance/open orders/recent fills;
6. reconcile sejak checkpoint terakhir;
7. verify clock + market freshness;
8. kembali ke mode sebelumnya hanya setelah gates pass.

Crash tidak boleh mereset cash, drawdown, processed fill IDs atau open-order state.

## Backup and restore

Back up durable ledger/OMS DB, release bundle, risk/config versions, reconciled cursor dan audit log ke failure domain berbeda. Backup dianggap berhasil hanya setelah restore drill.

RPO/RTO tetap UNMEASURED / BLOCKING sampai rehearsal pada production host menghasilkan evidence.
