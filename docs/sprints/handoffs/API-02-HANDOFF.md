# API-02 Handoff

## Identity

- Sprint: API-02 — Read-only Production API application and routes.
- Base SHA: `5d1594a5b780f4fd7027058df4b9a929e574ca52` (API-01/API-03 dependency baseline in the shared workspace).
- Implementation SHA: `603f72fa6feb5a8cf348e61a47a4e29dc35252e6`.
- Reviewer: `/root/prod_mvp_final_reviewer` — PASS on exact SHA.
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
- RED: `test_api_02_6_orders_page_reaches_records_past_the_first_500_and_keeps_total` first returned total 500 for 505 orders at offset 500; `test_api_01_7_account_freshness_uses_observation_time_after_provider_read` first treated a fresh post-request Indodax timestamp as unavailable.
- GREEN: `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/integration/lab/api/test_production_routes.py tests/unit/lab/api/test_production_read_models.py tests/unit/lab/api/test_capability_policy.py tests/integration/lab/api/test_api_audit.py tests/unit/lab/api/test_common_contracts.py -q -p no:cacheprovider` — PASS, 27 tests, exit 0.
- `rtk ruff check src/indodax_lab/api tests/integration/lab/api/test_production_routes.py` — PASS, exit 0.
- `rtk git diff --check` — PASS, exit 0.
- Coordinator integration checks fixed: overview field names now match API-01; FastAPI `detail.code` authorization errors are parsed and rendered as denied; account freshness compares against observation time after the provider responds; order pages select beyond 500 and preserve the true total. RED tests reproduced malformed overview parsing, denied-code parsing, timestamp race and page-500 truncation before fixes.
- Reviewer pass 1 on parent commit `38096b651f3ae32eaf9ed98f398c3cbae4c39b8c` returned four Important findings; regression tests reproduced each and integration-fix changes address all four. Final independent review on `603f72fa6feb5a8cf348e61a47a4e29dc35252e6`: PASS, no Critical/Important findings.

## Review and gates

- Independent review: PASS on exact source SHA `603f72fa6feb5a8cf348e61a47a4e29dc35252e6` by `/root/prod_mvp_final_reviewer`.
- Real Indodax account freshness was not exercised; the route test uses a fake provider with a server timestamp. No live service, credential, or account state was accessed.
- The `/portfolio` API route returns the real-account read model, but this sprint does not build the portfolio page. UI-02 owns the operator-facing account/balance view.
- Production startup still needs trusted auth middleware and the existing Production-owned view-only account provider plus the exact Production state root/namespace. No API deployment or ASUS host change was performed.

## CI defect record - Linux runner failure 2026-09-29 (needs CR, DONE sprint untouched)

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | External audit reports CI dev red: 6 failures in tests/integration/lab/api/test_production_routes.py, all `ValueError: PRODUCTION_STATE_ROOT_MUST_BE_ABSOLUTE`.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | Root cause verified by stdlib semantics at dev HEAD: fixture `production_state_root="D:/var/lib/indodax"` is absolute on Windows (PureWindowsPath.is_absolute True) but NOT on POSIX (PurePosixPath.is_absolute False), so Linux CI trips the intentional fail-closed guard in src/indodax_lab/api/app.py:42-43. Production-code guard is correct; the DONE test fixture is non-portable. No code changed (DONE sprint - fix needs defect/CR + owner).
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | Proposed minimal fix for CR scoping: test-only, replace the `D:/...` literal with a platform-absolute path (e.g. tmp_path fixture); intent `valid absolute root` preserved, zero production behavior change.
