# API-02 Handoff

## Identity

- Sprint: API-02 — Read-only Production API application and routes.
- Base SHA: `5d1594a5b780f4fd7027058df4b9a929e574ca52` (API-01/API-03 dependency baseline in the shared workspace).
- Implementation SHA: pending coordinator commit; this owner was instructed not to commit.
- Reviewer: pending independent review.
- Environment: Windows, Python 3.12.13.
- Host/network: no ASUS or Indodax access; no credentials loaded; tests use a fake Production-marked provider.

## Implementation

- Added `create_app` with explicit absolute Production namespace/state-root configuration and injected `production.indodax.account` provider. Research/shadow/tournament namespace and provider authority are rejected. Missing provider is represented as safe unavailable by API-01; missing/invalid Production namespace or root fails app construction.
- The application does not read environment credentials, create an exchange client, import/resolve `IndodaxTradingVenue`, or modify live authority. Existing Production runtime remains responsible for trusted auth, its server-side read-only provider, and supplying the Production-owned namespace/root.
- Added capability-protected GET routes for snapshot, overview, mode, portfolio, positions, orders, fills, reconciliation, risk, release and audit, plus bounded offset/limit list routes. No write routes are registered. The default auth resolver is absent, so requests fail closed until trusted Production middleware is injected.
- All routes use API-01 read models and API-03 `production.read` policy/audit context. Account values retain API-01 Decimal, Indodax server timestamp, freshness and source provenance behavior.

## Verification

- RED: `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/integration/lab/api/test_production_routes.py -q -p no:cacheprovider` — failed collection because `indodax_lab.api.app` did not exist.
- RED: added a regression for `/overview` and `/mode`; `/overview` initially raised `AttributeError` because the root `ProductionOverview` model has no per-resource `evidence` field.
- GREEN: `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/integration/lab/api/test_production_routes.py tests/unit/lab/api/test_production_read_models.py tests/unit/lab/api/test_capability_policy.py tests/integration/lab/api/test_api_audit.py tests/unit/lab/api/test_common_contracts.py -q -p no:cacheprovider` — PASS, 25 tests, exit 0.
- `rtk ruff check src/indodax_lab/api tests/integration/lab/api/test_production_routes.py` — PASS, exit 0.
- `rtk git diff --check` — PASS, exit 0.
- Coordinator integration check found the UI-00 overview parser expected different field names from the API-01 `ProductionOverview` contract. The frontend types/parser were aligned to `mode`, `venue_health`, `market_health`, `reconciliation_status`, `unknown_orders_count`, and `risk_status`; Vitest first reproduced three rejected valid-envelope cases, then passed after the fix. Frontend typecheck and production build pass.

## Review and gates

- Independent review: pending.
- Real Indodax account freshness was not exercised; the route test uses a fake provider with a server timestamp. No live service, credential, or account state was accessed.
- The `/portfolio` API route returns the real-account read model, but this sprint does not build the portfolio page. UI-02 owns the operator-facing account/balance view.
- Production startup still needs trusted auth middleware and the existing Production-owned view-only account provider plus the exact Production state root/namespace. No API deployment or ASUS host change was performed.
