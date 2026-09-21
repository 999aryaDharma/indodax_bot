# Ledger, OMS and exchange reconciliation

## Canonical event chain

~~~text
SignalIntent
 -> RiskDecision
 -> OrderIntent
 -> OMS Order
 -> Venue Event
 -> Fill
 -> LedgerTransaction
 -> Position / PortfolioSnapshot
~~~

Setiap accepted fill menghasilkan satu idempotent ledger transaction. Report berasal dari postings, bukan menghitung ulang PnL secara independen dari strategy logs.

## Ledger invariants

- fill ID diproses satu kali;
- valued postings balance exact;
- cash dan asset quantity merupakan dimensi terpisah;
- fee/tax dibebankan satu kali;
- quantity tidak pernah negatif;
- restart menghasilkan cash, positions dan processed-event set yang sama;
- ledger mismatch tidak boleh diperbaiki dengan mengedit report.

Shadow saat ini telah dipindahkan ke transactional SQLite checkpoint/event store untuk durability. Real-money tetap membutuhkan integration dengan double-entry ledger dan venue fills; checkpoint JSON bukan financial source of truth.

## Reconciliation loops

Bandingkan secara periodik:

| Internal | Venue |
|---|---|
| OMS open/pending orders | open orders |
| terminal orders | order history |
| normalized fills | trade/fill history |
| ledger cash | quote balance |
| ledger asset quantities | asset balances |

Difference diklasifikasikan sebagai known in-flight, expected rounding, missing internal event, missing venue event, duplicate, atau unexplained.

Unexplained mismatch di atas reviewed tolerance melakukan HALT_NEW_ORDERS, preserve evidence, refresh private state, deterministic replay/reconcile, lalu operator acknowledgement jika masih unresolved.

Jangan auto-flatten hanya karena reconciliation gagal.

## OMS uncertain-write rule

Jika submit/cancel timeout setelah request mungkin sudah diterima exchange, adapter tidak boleh blind retry. Status menjadi UNKNOWN dan reconciliation/query venue dilakukan lebih dulu untuk mencegah duplicate order.

Actual maker/taker role berasal dari venue evidence jika tersedia. Limit touch bukan bukti fill. Partial fills tetap event terpisah.
