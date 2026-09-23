# API-01 Handoff

## Identity

- Sprint: API-01 — Production service-derived read models
- Base SHA: `3bb7e0a89fb268c06de279f140e9004455a526b1`
- Implementation SHA: `fc40bca766b918191f3748241bb84edd544a04dd`
- Reviewer: `/root/prod_mvp_final_reviewer` — PASS, exact SHA reviewed
- Environment: Windows, Python 3.12.13
- Host/network: no ASUS/Indodax connection; no credentials loaded; tests use in-memory fake providers

## Implementation

- Added immutable typed views and `ProductionReadService.snapshot()` for overview, mode, portfolio, positions, orders, fills, reconciliation, risk, release and audit.
- The portfolio uses an explicitly injected read-only `VenueAccountProvider` compatible with `IndodaxReadOnlyClient.get_account_snapshot()` and marked `production.indodax.account`. Research/shadow providers are rejected before their snapshot method is called. It exposes raw per-currency available/held/total balances, quote-currency available/held amounts, Indodax `server_time`, local observation time, provenance and a normalized snapshot fingerprint. Service construction loads no credentials and makes no network call; fetching occurs only when `snapshot()` invokes the injected provider.
- Freshness uses the injected/default `ReconciliationPolicy.max_snapshot_age` (default 30 seconds). Stale account data returns `UNAVAILABLE`/`STALE` and no balances. Missing quote balances remain `None`, never fabricated zero. Equity remains unavailable because no authoritative mark valuation is wired into API-01.
- Internal ledger positions/orders come only from an explicitly injected `ExecutionStateStore` whose configured namespace matches `production_namespace` and whose resolved database path stays under the explicitly configured Production state root. Missing root, mismatched namespace, `prod_paper`, known Research/shadow/tournament namespaces and databases outside the Production root fail closed. These views remain `PARTIAL` and financially non-authoritative without reconciliation/freshness evidence. Database-root and provider authority markers are composition boundary checks; the API does not open arbitrary paths or create venue clients.
- Market health, venue health, latest reconciliation, quantitative risk, current verified release, fill history and audit remain explicitly unavailable/unknown because no authoritative read snapshot interface exists for them yet. Research feed health is never used as Production status.
- No writes, credentials, writer adapter, migration, host, deployment or manifest changes.

## Verification

- RED: focused pytest initially failed because the API-01 service did not exist; after adding an importable stub, all three acceptance tests failed on missing snapshot behavior.
- RED: `test_api_01_4_research_account_provider_cannot_satisfy_production_portfolio` failed as expected while the account provider authority was unchecked.
- RED: `test_api_01_5_research_database_cannot_satisfy_production_positions_or_orders` failed as expected while the database root was unchecked.
- GREEN: `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/api/test_production_read_models.py tests/unit/lab/api/test_capability_policy.py tests/integration/lab/api/test_api_audit.py tests/unit/lab/api/test_common_contracts.py -q -p no:cacheprovider` — PASS, 19 tests, exit 0.
- `rtk ruff check src/indodax_lab/api tests/unit/lab/api` — PASS, exit 0.
- Research account-provider and Research database path negative tests were added after independent review; both were observed RED before the authority checks were implemented.
- `C:\Users\User\miniconda3\envs\ML\python.exe -m ruff check src/indodax_lab/api tests/unit/lab/api tests/integration/lab/api` — PASS, exit 0.
- `rtk git diff --check` — PASS, exit 0.

## Review and gates

- Independent review: PASS on exact committed SHA `fc40bca766b918191f3748241bb84edd544a04dd`; no Critical/Important findings.
- Real Indodax account reads require the API-02 composition root to inject a Production-owned view-only provider and appropriately scoped credentials. That composition is outside API-01 and was not exercised here.
- ASUS resource qualification, capacity, service isolation and deployment remain separate gates; this sprint did not connect to or change ASUS. API-02 must bind the Production authority marker and database root to the actual Production-owned provider/storage at composition.
