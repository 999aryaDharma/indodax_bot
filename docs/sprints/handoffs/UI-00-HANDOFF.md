# UI-00 Handoff

## Implementation

- Sprint: UI-00
- Source commit: `3bb7e0a89fb268c06de279f140e9004455a526b1`
- Scope: Kumo/Geist control-plane shell, DESIGN.md tokens, typed read client, context-aware navigation, semantic status hierarchy and desktop/smartphone layout foundation.
- Production operational pages and API routes remain later sprint work.

## Verification

- `npm test` — PASS, 2 files / 7 tests, including an `EMPTY` snapshot with conflicting operational values.
- `npm run typecheck` — PASS.
- `npm run build` — PASS, Vite production build.
- Browser visual inspection: desktop, 390×844 and minimum supported 320×740. Smartphone layout fits without horizontal overflow; WITA (Asia/Makassar, UTC+8) is visible. Selecting Workbench changes the header and page context to Research Workbench.
- On refresh failure the previous snapshot is cleared; an `EMPTY` envelope hides all operational values; malformed 2xx responses are rejected. WITA time ticks once per second with interval cleanup, and snapshot evidence includes local date/time and updating age.
- Detailed `dashboard.pen` inspection was unavailable because Pencil MCP returned `Transport closed`; layout decisions follow `DESIGN.md` and the previously observed Production frame names. The `.pen` file was not read from disk.
- `python docs/quality/validate_planning.py --refresh --self-test` — PASS, 126 nodes, 226 edges, 0 cycles; seven invalid mutations rejected.
- Independent review: PASS on exact source SHA `3bb7e0a89fb268c06de279f140e9004455a526b1`, no Critical/Important findings. Reviewer could not reopen the existing browser session; independent visual capture is not claimed.

## Gates

- The browser calls only the read-only control-plane HTTP client and does not connect to Indodax sockets.
- API outage/unavailability is shown explicitly; no fake portfolio or health data is seeded.
- ASUS is the selected Production Main host and remains the Research Runtime host under ADR-009; this sprint did not deploy or modify either runtime.
- No secrets are persisted in browser storage. No live credentials or Docker deployment were used.
- API/persisted timestamps remain UTC; only operator display converts to WITA.
