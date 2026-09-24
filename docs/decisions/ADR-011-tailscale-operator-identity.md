# ADR-011 — Tailscale identity for the Production dashboard

Status: Accepted by owner in this task, 2026-09-24. Applies to the read-only dashboard/API boundary.

## Context

Production API capability policy already fails closed without a principal. Indodax view-only credentials authenticate server-to-exchange requests; they do not identify the human using the dashboard. The operator selected Tailscale/reverse proxy for dashboard access.

## Decision

- Use Tailscale Serve identity headers (`Tailscale-User-Login`, `Tailscale-User-Name`) as the operator identity source and map only an explicitly configured login allowlist to `production.read`. Tagged devices are not supported for this operator flow because Serve does not populate those identity headers for tagged-node requests.
- Trust these headers only when the API is bound to loopback and reachable through Tailscale Serve. Do not use Funnel or accept browser-supplied API tokens/Indodax credentials.
- Missing, malformed, or non-allow-listed identity denies access. Do not grant `production.control` in this read-only scope.
- Serve and API must be deployed with network/process isolation so the co-resident Research runtime cannot directly reach the listener and forge proxy headers. This is a hard activation gate, not something loopback binding alone satisfies on a shared host.
- Browser uses same-origin `/api/v1`; local development uses Vite proxy. Indodax keys remain backend-only.

## Consequences

API-07 owns server authentication, runnable Production read composition and provider wiring. UI-09 owns the browser API origin. ASUS proxy, host isolation and real credentials are not changed or verified in these code sprints. Tailscale documents header injection/removal and recommends a localhost backend; exact ASUS isolation still requires deployment evidence.
