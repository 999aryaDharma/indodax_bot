# Live release gates and current blockers

Passing CI adalah syarat perlu, bukan cukup. Gate bersifat kumulatif.

## G0 Repository truth

Fresh checkout reproducible, required CI green, no critical security finding, protected release refs, dependency/environment identity recorded.

## G1 Data and trusted judge

Causal data replay passes, point-in-time fee/tax coverage tersedia, unknown historical cost blocks promotion, simulator menangani reject/partial-fill/latency/conservative fills, ledger deterministic replay reconciles.

## G2 Candidate evidence

Sealed historical evaluation passes, failed trials preserved, cost stress dan parameter stability acceptable, tidak ada test-period retuning.

## G3 Forward shadow

Minimum: >=90 calendar days AND >=100 closed forward trades, no unresolved risk breach, no unresolved ledger/reconciliation incident, restart/recovery invariants demonstrated. Trade count bukan proof tunggal; uncertainty dan regime coverage tetap dilaporkan.

## G4 Operational readiness

Target host benchmarked, backup/restore drill passes, RPO/RTO measured, clock/network failure drill, telemetry/alerts tested, secret rotation rehearsed, current venue API/fee/minimum-order verified.

## G5 Private read-only integration

Balances/orders/trades reconcile, belum ada order-write permission, auth/rate-limit/nonce behavior tested, private payload redaction verified.

## G6 Manual micro-live

Tightly bounded capital, satu reviewed candidate, small universe, explicit human approval per order, reconciliation setelah fills, hard loss/drawdown guards.

## G7 Autonomous limited

Bounded capital + universe, immutable candidate, no online learning, no automatic model promotion, central risk authority, auto-halt on stale data/model mismatch/reconciliation breach.

## Current blockers (Strict Taxonomy: BLOCKED_EXTERNAL)

The following items are strictly external and cannot be satisfied by code alone without physical hardware allocation or live production credentials:

- **Live Venue Access:** Private API credentials (`INDODAX_VIEW_API_KEY`, `INDODAX_VIEW_SECRET_KEY`, `INDODAX_TRADE_API_KEY`, `INDODAX_TRADE_SECRET_KEY`) have not yet been provisioned for real-account smoke verification (`BLOCKED_EXTERNAL`);
- **Live Account Operational Evidence:** Real-account operational run history has not yet accumulated on real production exchange balances (`BLOCKED_EXTERNAL`);
- **Hardware & HA Benchmarks:** Real physical host / HA hardware failover latency and restore RPO/RTO have not been measured on dedicated production metal (`BLOCKED_EXTERNAL`);
- **Live Shadow Soak Time:** Minimum forward shadow requirement (>=90 calendar days AND >=100 closed forward trades without unresolved incidents) requires real-time forward accumulation (`BLOCKED_EXTERNAL`);
- **Branch Protection:** Remote repository branch protection rules on `dev` and `main` require GitHub repository administrator privileges (`BLOCKED_EXTERNAL`).

## Recently hardened on dev

- **Canonical MarketGateway:** Implemented with `ClockGuard` (detecting time regressions and system clock skew) and `DataQualityGuard` (enforcing valid crossed-book detection, monotonic sequence numbers, and max age staleness checks);
- **Write-Capable Venue Adapter & OrderRouter:** Added `IndodaxTradingClient` and `OrderRouter` enforcing fail-closed `UNKNOWN` order recovery without blind retries, backed by deterministic `FakeVenueAdapter`;
- **Automated Fill Ingestion & Durable Reconciliation:** Implemented `VenueFillIngester` and integrated fill-history cursoring into `DurableReconciliationCoordinator` for automatic double-entry ledger posting;
- **Centralized Risk & Portfolio Authority:** Implemented `PortfolioConstructor` and `RiskEngine` with rate limits, notional limits, daily loss halts, and immediate kill switch triggers;
- **Control Modes & Manual Approval Store:** Implemented full runtime mode gating (`DISABLED`, `READ_ONLY`, `SHADOW`, `SEMI_AUTOMATED`, `FULL_AUTOMATION`) and persistent `ManualApprovalStore` with strict TTL;
- **Operator CLI Suite:** Implemented canonical operator CLI tools (`approval.py`, `reconcile.py`, `kill_switch.py`) with explicit `BLOCKED_EXTERNAL` exit handling;
- **Comprehensive Operator Runbooks:** Created step-by-step procedures in `docs/production/runbooks/` for routine reconciliation, uncertain-write recovery, emergency kill switch, and operator approval workflow;
- **Failure Injection Disaster Drills:** Verified network dropouts, clock skews, unknown-order crash recovery, and cancel-fill race conditions via end-to-end integration tests;
- **Secret Redaction & Metrics Telemetry:** Added zero-dependency regex-based secret scrubber (`redact_secrets`) and thread-safe in-memory Prometheus-compatible metrics registry;
- **Cryptographic Release Verification:** Added `verify_release_bundle` validating git commit SHA, signed tag, sha256 checksums, and clean working tree.

These fixes establish full institutional engineering discipline on `dev`; real financial capital remains blocked until external gates G4-G7 are formally signed off.
