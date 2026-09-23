# UI-00 Handoff

## Implementation

- Sprint: UI-00
- Commit: `438edbfda7b590167c355466362410c8a6bc868d`
- Scope: Kumo/Geist control-plane shell, DESIGN.md tokens, typed read client, context-aware navigation, semantic status hierarchy and desktop/smartphone layout foundation.
- Production operational pages and API routes remain later sprint work.

## Verification

- `npm test` — PASS, 1 file / 4 tests, including malformed envelope rejection and explicit EMPTY status.
- `npm run typecheck` — PASS.
- `npm run build` — PASS, Vite production build.
- Browser visual inspection: desktop, 390×844 and minimum supported 320×740. Smartphone layout fits without horizontal overflow; WITA (Asia/Makassar, UTC+8) is visible. Selecting Workbench changes the header and page context to Research Workbench.
- On refresh failure the previous snapshot is cleared; an explicit EMPTY envelope renders a distinct empty state, and malformed 2xx responses are rejected.
- Detailed `dashboard.pen` inspection was unavailable because Pencil MCP returned `Transport closed`; layout decisions follow `DESIGN.md` and the previously observed Production frame names. The `.pen` file was not read from disk.
- `python docs/quality/validate_planning.py --refresh --self-test` — PASS, 126 nodes, 226 edges, 0 cycles; seven invalid mutations rejected.
- Independent review: FAIL on prior commit `7315cc1`; fixes for all Important findings are in `438edbf` and re-review is pending.

## Gates

- The browser calls only the read-only control-plane HTTP client and does not connect to Indodax sockets.
- API outage/unavailability is shown explicitly; no fake portfolio or health data is seeded.
- No Production host is selected or deployed. ASUS remains Research Runtime only.
- No secrets are persisted in browser storage. No live credentials or Docker deployment were used.
- API/persisted timestamps remain UTC; only operator display converts to WITA.
