# Unified Production and Research Dashboard Implementation Plan

> **For agentic workers:** Build the frontend against API contracts and fixtures. Do not invent backend state, call SQLite directly, or add UI actions whose backend command is not defined.

**Goal:** Deliver one control-plane dashboard with a shared shell and two visibly separate contexts: Production Main for operations and Research Workbench for evidence creation.

**Architecture:** React/TypeScript/Vite frontend with route namespaces `/production/*` and `/research/*`. Shared navigation, authentication context, request client, status strip, audit drawer, and error presentation are reused. Production and Research pages use separate API clients and capability guards.

**Tech Stack:** React, TypeScript, Vite, Cloudflare `@cloudflare/kumo` 2.14.0 components, locally hosted Vercel Geist Sans/Mono, existing design input in `DESIGN.md`, API schemas from the Production and Research API plans, Playwright or the repository's approved browser test tool only if already available.

**Spec:** `DESIGN.md` as the design-system and behavior input, `dashboard.pen` as the visual prototype reference for corresponding frames, frozen Production Main/Research Workbench documents as authority, and the three control-plane plans. UI implementers must inspect the relevant Pencil frames before building their pages and preserve the prototype's intended hierarchy while applying the DESIGN.md tokens.

## Route map

Kumo supplies accessible React controls and interaction primitives. Apply the graphite colors, density, typography scale, radii, borders and spacing from `DESIGN.md` over Kumo defaults; do not reproduce Cloudflare product branding. Load Geist Sans/Mono as self-hosted WOFF2 assets with the upstream SIL Open Font License. Responsive targets in this phase are desktop and smartphone.

```text
/                         redirect to /overview
/overview                 combined health summary; no write controls
/production/overview      operational truth
/production/portfolio
/production/positions
/production/orders
/production/reconciliation
/production/risk
/production/approvals
/production/releases
/production/audit
/research/workbench
/research/datasets
/research/strategies
/research/models
/research/pipelines
/research/experiments
/research/backtests
/research/candidates
/research/tournament
/research/portfolio-shadow
/research/promotion-requests
```

The shared shell must always display current context (`PRODUCTION` or `RESEARCH`), execution mode if available, UTC time, API health, and current actor capability. A route guard must prevent accidental navigation from becoming a capability escalation.

## Tasks

### UI-00 — Frontend shell and typed API client

**Dependencies:** None. The route paths and response types are frozen in the Production API plan, so shell/client work can proceed in parallel with API-00.

**Files:** Create `frontend/package.json`, `frontend/package-lock.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/src/main.tsx`, `frontend/src/app/App.tsx`, `frontend/src/api/client.ts`, `frontend/src/api/types.ts`, `frontend/src/styles/tokens.css`, `frontend/src/assets/fonts/`; test `frontend/src/api/client.test.ts`.

Use one typed request client with:

- `requestId` generation;
- `Idempotency-Key` for commands;
- decimal values retained as strings;
- stable error rendering from `ApiError`;
- no token or secret persistence in local storage;
- explicit environment base URL.
- Kumo 2.14.0 components use product CSS tokens from `DESIGN.md`; Geist fonts are bundled locally, not fetched at runtime.

### UI-01 — Context navigation and capability guards

**Files:** Create `frontend/src/app/Shell.tsx`, `frontend/src/app/ContextSwitcher.tsx`, `frontend/src/app/CapabilityBoundary.tsx`, `frontend/src/components/StatusStrip.tsx`; test `frontend/src/app/CapabilityBoundary.test.tsx`.

Production and Research remain visually distinct but share typography, spacing, and status components. A Research actor must not see production command controls. A Production viewer must see read-only views only. `CapabilityBoundary` renders a safe blocked state, never a disabled button that falsely implies authority.

### UI-02 — Production operational views

**Dependencies:** API-01/API-02.

The Production view sprint also depends on UI-01 so route namespace and capability presentation are already present.

**Files:** Create `frontend/src/features/production/OverviewPage.tsx`, `PortfolioPage.tsx`, `OrdersPage.tsx`, `ReconciliationPage.tsx`, `RiskPage.tsx`, `ApprovalsPage.tsx`, `ReleasesPage.tsx`, `AuditPage.tsx`; tests under `frontend/src/features/production/*.test.tsx`.

Implement:

- safety banner for HALTED, RECOVERY, stale data, reconciliation mismatch, UNKNOWN OMS, and unavailable risk authority;
- status strip for mode, venue, market, reconciliation, unknown orders, risk, release, backup;
- authoritative-vs-unavailable labels;
- order/fill tables with OMS state and venue identity;
- reconciliation differences without “fix balance” actions;
- risk limit utilization, kill-switch status, and approval evidence;
- release provenance and gate progress without “deploy live”.

### UI-03 — Production command workflows

**Dependencies:** API-04.

**Files:** Create `frontend/src/features/production/ModeTransitionDialog.tsx`, `KillSwitchDialog.tsx`, `ApprovalDecisionDrawer.tsx`, `ReconciliationRunButton.tsx`; tests for stale revision, duplicate click, forbidden command, and expired approval.

Every command shows current revision, actor, reason, expiry, and backend result. Repeated clicks reuse the same idempotency key. The UI never asks for exchange credentials and never offers generic order entry.

### UI-04 — Research Workbench and registry views

**Dependencies:** RW-API-01 and RW-API-02.

**Files:** Create `frontend/src/features/research/WorkbenchPage.tsx`, `DatasetsPage.tsx`, `ExperimentsPage.tsx`, `BacktestsPage.tsx`, `CandidatesPage.tsx`; tests under `frontend/src/features/research/*.test.tsx`.

Show immutable identities, quality reports, pipeline graph summary, experiment lifecycle, clone action, result provenance, artifact hashes, and qualification status. A completed experiment has no edit action; the only configuration action is clone.

### UI-05 — Tournament and Portfolio Shadow views

**Dependencies:** RW-API-03 and RW-API-04.

**Files:** Create `frontend/src/features/research/TournamentPage.tsx`, `AgentDetailPage.tsx`, `PortfolioShadowPage.tsx`; tests for isolated agent values and shared Portfolio Shadow values.

Clearly label virtual cash, isolated ledger, forward age, closed trades, metrics, rank, and production eligibility. Never show leaderboard rank as authorization.

### UI-06 — Form/graph pipeline editor

**Dependencies:** RW2-03, RW3-01, RW-API-02.

**Files:** Create `frontend/src/features/research/PipelineEditorPage.tsx`, `PipelineForm.tsx`, `PipelineGraph.tsx`, `pipelineValidation.ts`; tests for synchronized form/graph round trip, invalid schema edge, missing component, and clone-before-edit.

Both modes edit one declarative manifest. The frontend displays backend validation errors and does not run arbitrary code from graph nodes.

### UI-07 — Status stream, audit drawer, and failure states

**Dependencies:** API-05 and RW API audit routes.

**Files:** Create `frontend/src/hooks/useEventStream.ts`, `frontend/src/components/AuditDrawer.tsx`, `frontend/src/components/FailureState.tsx`; tests for reconnect, replay-unavailable, stale snapshot, API outage, and permission denial.

Use SSE with last event ID. All critical states are conveyed by text/icon plus color. Loading, empty, blocked, stale, and unavailable are distinct states.

### UI-08 — Dashboard qualification

**Dependencies:** UI-00 through UI-07.

**Files:** Create `frontend/tests/e2e/context-isolation.spec.ts`, `frontend/tests/e2e/production-safety.spec.ts`, `frontend/tests/e2e/research-immutability.spec.ts`.

Verify:

- navigation never crosses capability boundary;
- Production mismatch blocks new-order controls;
- Research cannot see or call live-write actions;
- completed experiment cannot be edited;
- Tournament and Portfolio Shadow display different semantics;
- refresh/reconnect preserves context and does not duplicate commands;
- mock production state is visibly marked as mock/fixture in development.

## Definition of done

- One dashboard shell serves both systems without merging their authority or persistence.
- Production is operationally useful in read-only mode before live activation.
- Research is usable for evidence navigation and, when services exist, controlled mutation.
- UI renders API provenance and qualification status rather than inventing it.
- All command actions are backend guarded, audited, idempotent, and unavailable in unsafe environments.

## 2026-09-24 operator-workflow amendment

Canonical UI-03 depends on API-04 and UI-02 and follows `docs/implementation/BOT-TRADE-PROGRAM.md`. Use existing pages.tsx and route.tsx equivalents rather than recreating the older proposed file inventory. Add reviewed adoption/allocation and draining presentation alongside guarded lifecycle controls; backend owns all financial decisions. YAML is the selected companion to the component form for Workbench.
