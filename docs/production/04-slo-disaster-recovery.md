# SLO, observability and disaster recovery

Tidak ada angka uptime, latency, RPO atau RTO yang dianggap benar tanpa pengukuran pada target host.

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
