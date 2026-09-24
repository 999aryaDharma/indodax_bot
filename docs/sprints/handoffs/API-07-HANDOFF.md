# API-07 Handoff

## Implementation

- Sprint: API-07 — Tailscale-authenticated Production read composition.
- Source SHA: `13fa3f4009310795a3721099a2b976880ecac851` (includes API composition commit `995a8b8`).
- Owner: `/root`.
- Scope: allow-listed Tailscale Serve identity maps to `production.read` only; environment composition uses the existing `IndodaxReadOnlyClient` through a Production-marked account provider; namespace must be `production`; frontend never receives credentials.
- Composition lives in `src/indodax_lab/runtimes/production/control_plane.py`. It wires shared API/client components without duplicating trading rules. No shared engine logic, credentials outside runtime composition, or running state was moved.
- No live environment values, Indodax endpoint, ASUS host, Tailscale config, orders, ledger or runtime database were accessed or changed.

## Verification

- `python -m pytest tests/unit/lab/api/test_tailscale_operator_auth.py tests/integration/lab/api/test_production_runtime_composition.py tests/unit/lab/api/test_capability_policy.py tests/integration/lab/api/test_production_routes.py -q` — PASS, 21 tests.
- `rtk ruff check src/indodax_lab/api/auth.py src/indodax_lab/runtimes/production/control_plane.py tests/unit/lab/api/test_tailscale_operator_auth.py tests/integration/lab/api/test_production_runtime_composition.py` — PASS.
- `git diff --check` — PASS.
- Identity tests cover exact allowlist match, case normalization, missing/disallowed identity, non-loopback source, Research namespace, legacy `production_main` namespace, and no venue call on invalid configuration.

## Review and External Gates

- Independent review: PENDING on the final batch SHA.
- Tailscale Serve only; no Funnel or tagged-device operator sessions. API listener must be loopback-only and reachable only through Serve.
- Because Research shares ASUS, activation requires verified process/network isolation preventing Research from directly reaching the listener and spoofing proxy headers. Loopback alone does not provide this isolation.
- The ASUS service must explicitly call the composition with protected env configuration (`INDODAX_VIEW_API_KEY`, `INDODAX_VIEW_SECRET_KEY`, `PRODUCTION_NAMESPACE=production`, absolute `PRODUCTION_STATE_ROOT`, and `PRODUCTION_OPERATOR_ALLOWLIST`). No host/service entrypoint was changed here.
- No deployment or live account request was performed.
