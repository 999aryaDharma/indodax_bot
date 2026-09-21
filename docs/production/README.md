# Production infrastructure — controlled future target

Status: **DESIGN / NOT LIVE-READY**. Dokumen ini mendefinisikan kontrak yang wajib dipenuhi sebelum real-money execution. Tidak ada bagian di sini yang mengotorisasi API write credentials, deployment live, atau autonomous trading.

Targetnya adalah systematic trading platform dengan disiplin institusional: deterministic decision path, satu risk authority, durable accounting, exchange reconciliation, reproducible artifacts, fail-closed state transitions, dan evidence yang dapat direview independen.

## Non-negotiable boundaries

- Research, model training, hyperparameter search dan notebook tidak berjalan di production execution process.
- Strategy/model hanya menghasilkan intent; tidak boleh mengubah kas atau memanggil exchange.
- PortfolioRiskManager atau penerusnya yang direview adalah satu-satunya pre-trade risk authority.
- Hanya OMS venue adapter yang boleh memiliki order-write capability.
- Withdrawal credentials tidak pernah berada pada trading host.
- HALT_NEW_ORDERS dan EMERGENCY_FLATTEN adalah dua kontrol berbeda.
- Missing/corrupt model, market data, ledger, risk state atau reconciliation evidence memblokir exposure baru.
- Shadow, manual-live dan autonomous-live memakai domain/execution/accounting contract yang sama; venue adapter yang berubah.
- ASUS X441U boleh menjadi watchdog/observer/collector setelah benchmark, tetapi bukan satu-satunya production execution authority.
- Software release bukan bukti edge; champion qualification tetap gate terpisah.

## Dokumen

1. 01-target-architecture.md
2. 02-security-deployment.md
3. 03-ledger-reconciliation.md
4. 04-slo-disaster-recovery.md
5. 05-live-release-gates-and-blockers.md
6. 06-production-node-build-sheet.md

Master specification dan quality release gates tetap authoritative jika dokumen ini tidak memperketatnya.
