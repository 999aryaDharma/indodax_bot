# UI-00 Handoff

## Implementation

- Sprint: UI-00
- Commit: `7315cc173b6da257fcdd95cc3a4f69661e17a64a`
- Scope: Kumo/Geist control-plane shell, DESIGN.md tokens, typed read client, and desktop/smartphone layout foundation.
- Production operational pages and API routes remain later sprint work.

## Verification

- `npm test` — PASS, 1 file / 3 tests.
- `npm run typecheck` — PASS.
- `npm run build` — PASS, Vite production build.
- Desktop shell was visually inspected in the browser. Smartphone layout is implemented in CSS, but a smartphone-sized browser capture was not available in this run.
- Detailed `dashboard.pen` inspection was unavailable because Pencil MCP returned `Transport closed`; layout decisions follow `DESIGN.md` and the previously observed Production frame names. The `.pen` file was not read from disk.
- `python docs/quality/validate_planning.py --refresh --self-test` — PASS, 126 nodes, 226 edges, 0 cycles; seven invalid mutations rejected.
- Independent review: PENDING for the exact implementation commit above.

## Gates

- The browser calls only the read-only control-plane HTTP client and does not connect to Indodax sockets.
- API outage/unavailability is shown explicitly; no fake portfolio or health data is seeded.
- No Production host is selected or deployed. ASUS remains Research Runtime only.
- No secrets are persisted in browser storage. No live credentials or Docker deployment were used.
