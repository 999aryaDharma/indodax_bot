# CR-20260924-PDA — Production dashboard operator access

Status: Accepted by owner in this task on 2026-09-24 for read-only implementation planning. No ASUS or live runtime change is authorized.

## Request

Complete the Production dashboard connection to the real Production-owned read-only Indodax account provider and authenticate dashboard operators through Tailscale Serve/reverse proxy identity. This operator identity is separate from the Indodax view-only API key already held in server environment variables.

## Impact

Admit API-07 and UI-09. API-07 composes the existing read-only client and server-side environment credentials into API-02's provider contract, resolves only allow-listed Tailscale Serve operator identity to `production.read`, and fails closed when trusted identity/configuration is absent. It grants no write capability. UI-09 changes the browser API default to same-origin `/api/v1` and uses a local Vite proxy for development; browser requests never receive Indodax credentials.

Tailscale Serve must be used (not Funnel); its identity headers are trusted only on a backend listener reachable exclusively through the trusted proxy, with an interactive user identity (tagged devices do not populate these headers). Since Research shares ASUS, network/process isolation preventing Research from directly reaching or spoofing requests to the Production API is a deployment gate. Do not change ASUS or deploy as part of these sprints.

## Boundaries

No live keys are read during development; code may read `INDODAX_VIEW_API_KEY` and `INDODAX_VIEW_SECRET_KEY` at runtime only. No order, ledger, runtime DB, venue writer, Research provider, Tailscale configuration, host or deployment mutation. Missing credentials, namespace, state root, operator allowlist, proxy identity, or isolation evidence prevents activation.

## Validation

Use fake account providers/network and temporary stores. Test forged/missing/disallowed identity denial, read-only client construction, secret redaction, absence of write routes, same-origin browser URL, and no credentials in browser fetch. Independent review must pass exact implementation SHA before sprint completion. ASUS isolation and Tailscale configuration remain external gates.
