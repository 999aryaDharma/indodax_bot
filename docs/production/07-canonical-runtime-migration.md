# Canonical runtime migration

Status: ACTIVE MIGRATION CONTRACT

## Shared public-market migration — 2026-09-23

[Shared Market Runtime](research-workbench/SHARED-MARKET-RUNTIME.md) is the detailed implementation design for public WebSocket ownership, ASUS hardware/resource qualification and shared features/inference. [ADR-008](../decisions/ADR-008-shared-market-runtime-and-asus-edge.md) records the topology/identity amendment. Implementation phases there refine the market/shadow portion of the migration below; they do not replace the sprint manifest as status/DAG authority.

At audited `dev` `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`, `run_shadow_bot.py` still calls `LiveShadowEngine.fetch_live_market_data` for REST tickers/history, `compute_features` for Pandas recomputation and pair-specific model/rule branches. Separately, `PublicMarketCollector` already supports public trade/book WebSocket collection, durable channel offsets and book recovery. Integrate these existing owners rather than build another exchange adapter.

Sequence: characterize/approve contracts → durable canonical envelope/journal → multi-channel WebSocket owner → bounded fan-out/gateway → shared causal features → verified shared serving/triggers → isolated candidate-driven tournament → separate Portfolio Shadow → service/restore cutover → ASUS capacity/thermal/24h+ qualification and legacy decommission. Each phase specifies affected paths, tests, failure behavior, observability and rollback in the detailed design.

Legacy polling and its artifacts remain readable until behavioral parity or intentional source/semantic differences are recorded. Source/feature/model changes create new runtime/candidate versions and evidence namespaces. Do not merge old forward history into newly qualified runtime evidence. REST remains centralized for bootstrap/history/metadata/repair/sanity/fallback, never normal per-strategy acquisition.

Service drift at that SHA: `lab-shadow.service` names absent `indodax_lab.cli.shadow`; `lab-collector.service` names absent `indodax_lab.cli.collector`; actual collector CLI is `indodax_lab.cli.collect_market_stream`. Host config uses `asus_zenbook` and does not describe an integrated local feed. These are implementation gaps; no deploy/config mutation is performed by this document update.

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

## Historical hardening snapshot

Pada hardening 2026-09-21:

- shadow risk authority telah memakai canonical `PortfolioRiskManager`;
- shadow financial state telah memakai canonical balanced `ResearchLedger`;
- canonical package dilarang mengimpor legacy flat modules;
- canonical private read-only venue adapter dan reconciler telah diimplementasikan;
- durable OMS state machine/store telah diimplementasikan tanpa order-write capability;
- real order-write venue adapter, production fill ingestion/cursoring, dan venue-proven
  operational evidence tetap menjadi blocker.

Migration status tidak mengubah project menjadi live-ready.

The dated snapshot above is provenance, not a current absence claim for later execution modules. Use the [current implementation audit](../implementation/CURRENT-STATE.md) and exact code SHA for Production Main parser/adapter/ledger status. This market-runtime design does not certify private execution readiness.
