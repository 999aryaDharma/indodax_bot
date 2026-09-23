# UI-01 Handoff

## Implementation

- Sprint: UI-01 — Production and Research context navigation with capability boundary.
- Implementation base: `fc40bca766b918191f3748241bb84edd544a04dd`.
- Final source SHA: pending coordinator integration commit; implementation was left uncommitted by request.
- Owned paths: `frontend/src/app/App.tsx`, `frontend/src/app/context.ts`, `frontend/src/app/context.test.ts`, `frontend/src/styles/tokens.css`.
- Route namespaces are explicit: `/production/*`, `/research/*`, `/system/*`. Browser history navigation and deep links select the matching context.
- Only `/production/overview` requests the Production overview read model. Research and System routes render their own service-unavailable/unfinished states and never display Production snapshot values.
- Research labels the isolated environment and explicitly says Production account data is unavailable there. Shadow and tournament remain Research-owned.
- A Production capability/identity denial renders a blocked state without a retry/action control. This is presentational; API-03 remains the authorization boundary.
- Mobile quick navigation exposes every route in the active context through horizontal scrolling; targets are at least 48px. Existing graphite/Kumo/Geist styling and DESIGN.md tokens remain in place.

## Verification

- `npm test -- --run` (from `frontend/`) — PASS, 3 files / 12 tests.
- `npm run typecheck` (from `frontend/`) — PASS.
- `npm run build` (from `frontend/`) — PASS, Vite production build.
- Browser desktop inspection at `/research/workbench` — PASS: isolated Research heading and unavailable Research API are visible; no Production snapshot fields appear.
- Local desktop preview at `/research/workbench` confirmed the same Research-only copy and route context. The preview API returned 404 because the Production API server was not running; no live account state was accessed.
- Coordinator integration check found UI-00 expected a different Production overview data shape than API-01/API-02 provide. The typed client and overview mapping were aligned and its new-contract tests passed. This is a shared client integration correction, not portfolio page work.
- Independent review pass 1 on `38096b651f3ae32eaf9ed98f398c3cbae4c39b8c` found the FastAPI denial shape was not shown as blocked and smartphone navigation omitted context routes. Both findings are fixed with regression coverage; re-review of the final integration-fix SHA is pending.
- Smartphone screenshot inspection — not completed; Chrome DevTools viewport controls were unavailable through the active browser surface. Responsive CSS retains the existing <=600px layout and the quick-navigation controls have a 48px minimum hit area.
- Smartphone behavior is therefore verified only by CSS/code inspection; no rendered mobile screenshot is claimed.
- Pencil references were inspected through Pencil MCP for the Production Overview, Research Workbench and Production Main Flow frames. The `.pen` file was not read from disk or modified.
- No live account, key, order, ledger, host, Docker, or deployment access was used.

## Review and gates

- Independent review: pending.
- Planning manifest remains coordinator-owned and was not changed by this implementation.
- No API-02 page/data, Research API, or live-write capability is included.
- `/production/portfolio` remains a placeholder in UI-01; UI-02 must render the API-02 live Indodax portfolio read model with explicit freshness and unavailable states.
