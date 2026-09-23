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
- ASUS X441U/X441UV adalah Research Runtime / Shadow Edge: shared public WebSocket feed, fitur bersama, inferensi CPU terpilih, Tournament/Portfolio Shadow dan evidence. Training tetap di Lenovo; Production Main memiliki host/otoritas terpisah. Kapasitas ASUS harus dikualifikasi.
- Software release bukan bukti edge; champion qualification tetap gate terpisah.

## Dokumen

Mulai dari [Frozen Systems](FROZEN-SYSTEMS.md), [Production Main](main/README.md), dan [Research Workbench](research-workbench/README.md). [Shared Market Runtime](research-workbench/SHARED-MARKET-RUNTIME.md) memuat desain lengkap migrasi WebSocket, profil ASUS, recovery, resource budgets, benchmark dan rollout. [ADR-008](../decisions/ADR-008-shared-market-runtime-and-asus-edge.md) mencatat amendment host/runtime; target belum berarti implemented atau activated.

1. 01-target-architecture.md
2. 02-security-deployment.md
3. 03-ledger-reconciliation.md
4. 04-slo-disaster-recovery.md
5. 05-live-release-gates-and-blockers.md
6. 06-production-node-build-sheet.md
7. 07-canonical-runtime-migration.md
8. 08-private-readonly-integration.md

Ikuti precedence Frozen Systems dan explicit accepted ADR overrides; dokumen target lama yang ditandai superseded hanya konteks historis. Current operation tetap paper/shadow.
