# UI-09 Handoff

## Implementation

- Sprint: UI-09 — same-origin Production API access.
- Source SHA: `7a7ff2b4a30e5664fbc23c01617e42a1b0bcb353`.
- Owner: `/root`.
- Scope: typed browser client defaults to relative `/api/v1`; Vite development server proxies `/api/v1` to `http://127.0.0.1:8000`; browser continues using `credentials: omit` and sends no Indodax credentials.
- No UI visuals or design prototype were changed.

## Verification

- `npm test -- --run` (from `frontend/`) — PASS, 19 tests across 4 files.
- `npm run typecheck` (from `frontend/`) — PASS.
- `npm run build` (from `frontend/`) — PASS; Vite transformed 4,772 modules.
- Impeccable detector on `frontend/src/api/client.ts`, `frontend/src/api/client.test.ts`, and `frontend/vite.config.ts` — PASS, no findings (`[]`).
- `git diff --check` — PASS.

## Review and External Gates

- Independent review: exact batch SHA `51cc55d1eb4720c318bd0594fc02c2b0bad4fff5` PASS; no UI code findings. Reviewer environment could not start `npm test -- --run` (`esbuild spawn EPERM`); owner run recorded 19 passing tests on unchanged UI source SHA `7a7ff2b4a30e5664fbc23c01617e42a1b0bcb353`. Reviewer independently confirmed typecheck and production build pass.
- Production reverse proxy must serve the static dashboard and route `/api/v1` through Tailscale Serve to the API listener. This is not configured or deployed by this sprint.
- Vite proxy applies only to local development.
