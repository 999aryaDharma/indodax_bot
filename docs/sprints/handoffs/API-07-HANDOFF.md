# API-07 Handoff

## Implementation

- Sprint: API-07 — Tailscale-authenticated Production read composition.
- Source SHA after review fixes: `3d59484fc2f5d6a7e9d27916b052f01eaa3f534e` (includes API composition commit `995a8b8` and review-fix commit `3d59484`).
- Owner: `/root`.
- Scope: allow-listed Tailscale Serve identity maps to `production.read` only; environment composition uses the existing `IndodaxReadOnlyClient` through a Production-marked account provider; namespace must be `production`; frontend never receives credentials.
- Composition lives in `src/indodax_lab/runtimes/production/control_plane.py`. It wires shared API/client components without duplicating trading rules. No shared engine logic, credentials outside runtime composition, or running state was moved.
- No live environment values, Indodax endpoint, ASUS host, Tailscale config, orders, ledger or runtime database were accessed or changed.

## Verification

- `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/api/test_tailscale_operator_auth.py tests/integration/lab/api/test_production_runtime_composition.py tests/unit/lab/api/test_capability_policy.py tests/integration/lab/api/test_production_routes.py -q` — PASS, 22 tests on FastAPI 0.115.0 / Starlette 0.38.6.
- `C:/Users/User/miniconda3/envs/ML/python.exe -m ruff check src/indodax_lab/api/auth.py src/indodax_lab/runtimes/production tests/unit/lab/api/test_tailscale_operator_auth.py tests/integration/lab/api/test_production_runtime_composition.py` — PASS.
- `git diff --check` — PASS.
- Identity tests cover exact allowlist match, case normalization, missing/disallowed identity, non-loopback source, Research/legacy namespace, no venue call on invalid configuration, and a compatible end-to-end ASGI test with Uvicorn proxy rewriting disabled.

## Review and External Gates

- Independent review on `b09249dd7f88ca79656518352d8d40b2f47fc254`: CHANGES_REQUESTED for missing runnable ASGI/dependency declaration, proxy-header rewriting compatibility, TestClient compatibility across supported versions, and stale ADR sprint IDs. Fixes are in `3d59484fc2f5d6a7e9d27916b052f01eaa3f534e`.
- Re-review on `8e7c21431483f8a5149d24415dba954d431ad5ab`: PASS for prior Critical/Important findings; one Minor spec wording inconsistency (“no new dependencies”) is corrected in the current docs commit. Final exact-SHA confirmation is PENDING.
- Reviewer: `/root/api03_security`.
- Tailscale Serve only; no Funnel or tagged-device operator sessions. API listener must be loopback-only and reachable only through Serve.
- Because Research shares ASUS, activation requires verified process/network isolation preventing Research from directly reaching the listener and spoofing proxy headers. Loopback alone does not provide this isolation.
- Run from the source checkout with the package on `PYTHONPATH` using `python -m indodax_lab.runtimes.production.control_plane`; configure protected env (`INDODAX_VIEW_API_KEY`, `INDODAX_VIEW_SECRET_KEY`, `PRODUCTION_NAMESPACE=production`, absolute `PRODUCTION_STATE_ROOT`, and `PRODUCTION_OPERATOR_ALLOWLIST`). Optional `PRODUCTION_API_PORT` defaults to 8000. No OS service/host configuration was changed here.
- No deployment or live account request was performed.
