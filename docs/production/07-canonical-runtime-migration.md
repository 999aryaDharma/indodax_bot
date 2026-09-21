# Canonical runtime migration

Status: ACTIVE MIGRATION CONTRACT

## Canonical authority

Semua development production baru berada di `src/indodax_lab/`.

Flat modules di `src/*.py` adalah legacy compatibility surface. Mereka boleh tetap digunakan untuk
workflow lama selama migrasi, tetapi tidak boleh menjadi dependency baru bagi `indodax_lab`.
Architecture test di `tests/architecture/test_canonical_runtime_boundary.py` menegakkan aturan ini.

## Legacy freeze policy

Dilarang menambahkan ke legacy flat runtime:

- venue order-write capability baru;
- risk policy baru;
- accounting authority baru;
- model promotion logic baru;
- production persistence baru;
- autonomous control state baru.

Bug keamanan kritis pada legacy boleh diperbaiki sampai decommission, tetapi fitur baru harus masuk
canonical package.

## Responsibility migration map

| Legacy module | Canonical destination |
|---|---|
| `risk_manager.py` | `indodax_lab.backtest.risk` / future `indodax_lab.risk` |
| `paper_accounting.py` | `indodax_lab.backtest.ledger` |
| `paper_trader.py` | `indodax_lab.paper` + canonical execution kernel |
| `position_tracker.py` | ledger + portfolio + reconciliation |
| `signal_logic.py` | `indodax_lab.strategies` |
| `ta_processor.py` | canonical feature pipeline |
| `indodax_api.py` | future `execution/indodax_venue.py` adapter |
| `telegram_bot.py` | operations/notification adapter |
| `signal_cache.py` | canonical decision/event store |
| `signal_observer.py` | operations/observability |
| `main.py` | supervised canonical entrypoint/control plane |

## Production dependency direction

~~~text
data -> features -> strategy/model -> portfolio -> risk -> OMS -> venue
                                              \-> ledger <- fills
                                                   |
                                                   -> reconciliation
~~~

UI/Telegram may read control-plane state and request authorized state transitions. Mereka tidak boleh
memanggil venue adapter atau memodifikasi ledger secara langsung.

## Decommission gate per legacy module

Sebuah legacy module hanya boleh dihapus ketika:

1. responsibility canonical replacement selesai;
2. behavioral parity atau intentional-difference evidence tersedia;
3. relevant tests hijau;
4. tidak ada import/runtime reference aktif;
5. runbook/operator entrypoint telah dialihkan;
6. rollback plan tidak membutuhkan module tersebut.

## Migration order

1. financial accounting and risk authority;
2. paper/shadow execution;
3. market/exchange adapter;
4. position/reconciliation state;
5. signal/feature path;
6. notifications/observer;
7. top-level entrypoint;
8. delete legacy only after repository-wide reference audit.

## Current state

Pada hardening 2026-09-21:

- shadow risk authority telah memakai canonical `PortfolioRiskManager`;
- shadow financial state telah memakai canonical balanced `ResearchLedger`;
- canonical package dilarang mengimpor legacy flat modules;
- real-money venue adapter/reconciler masih belum diimplementasikan dan tetap production blocker.

Migration status tidak mengubah project menjadi live-ready.
