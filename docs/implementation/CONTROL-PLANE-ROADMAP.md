# Production API and Unified Dashboard Roadmap

Classification: TARGET PLANNING. `docs/sprints/sprint-manifest.json` is the sole status and dependency authority. API/UI units become claimable only when admitted by [CR-2026-09-23](CHANGE-REQUEST-PRODUCTION-CONTROL-PLANE.md) and represented by canonical sprint specs.

## Current implementation boundary

Production Main domain primitives PM-01 through PM-04 are DONE and independently reviewed in the manifest. PM-05 and PM-06 remain PLANNED. Research Workbench RW0-01 and RW1-01 are DONE; later registry/orchestration and dashboard work remains PLANNED. CR-2026-09-23 admits API-00..03/API-02 and UI-00..02; their current status is shown only in the sprint manifest and generated projections. Existing `DESIGN.md` and `dashboard.pen` are design inputs, not backend authority.

API-00 contracts and the UI-00 shell are implemented and independently reviewed; read models/routes and operational pages remain on the sprint DAG. The target stays a read-only Production API and desktop/smartphone dashboard with paper/shadow-safe defaults. The UI cannot own authoritative state. ASUS is the selected Production Main host and continues to host a separate Research Runtime for shadow/tournaments; Lenovo performs ML/DL training and tuning. Host inventory, service isolation and co-resident capacity remain unqualified, so implementation does not imply deployment readiness.

## Canonical MVP sprint DAG

| Sprint | Dependencies | Deliverable | Unlocks |
|---|---|---|---|
| API-00 | — | Shared response/error/provenance/capability contracts | API-01, API-03 |
| API-01 | API-00, PM-01, PM-02, PM-03, PM-04 | Service-derived Production read models | API-02 |
| API-03 | API-00 | Fail-closed read capability policy and audit context | API-02, UI-01 |
| API-02 | API-01, API-03 | FastAPI read-only Production route boundary | UI-00, UI-02 |
| UI-00 | — | React/Vite shell foundation, Kumo components, Geist fonts, typed API client using the frozen documented route contract | UI-01 |
| UI-01 | UI-00, API-03 | Context navigation and capability presentation boundary | UI-02 |
| UI-02 | UI-01, API-02 | Production operations, portfolio, orders, reconciliation, risk, releases and audit views | UI-03, UI-08 |

API-00 and UI-00 may run in parallel because UI-00 consumes the stable endpoint/type contract already frozen in the Production API plan, not API-00 source code. After API-00 is independently reviewed and DONE, API-01 and API-03 may run in parallel. Each sprint has one owner and disjoint scoped files. Review exact parallel SHAs after both implementation packets are complete; neither sprint is marked DONE before findings are resolved.

Release evidence remains explicitly unavailable until the relevant source exists. API/UI must not imply PM-05 release verification, readiness-gate passage, or production authorization. The MVP has no command endpoints, order submission, withdrawals, automatic repairs, or model replacement.

## Visual implementation contract

Use `@cloudflare/kumo` 2.14.0 React components for shared controls and tables; use locally bundled Vercel Geist Sans and Geist Mono WOFF2 assets under their SIL Open Font License. Keep Kumo's accessible interaction behavior while overriding visual tokens to match `DESIGN.md`: graphite canvas/surfaces, restrained semantic colors, compact density, 4–8px radii, borders before shadows, and tabular financial numbers. Do not adopt Cloudflare branding or Kumo defaults wholesale. Build only desktop and smartphone responsive layouts in this phase.

## Later dependencies outside this MVP

- Production commands: API-04 depends on the required PM safety/governance tasks and API-02; UI-03 depends on API-04 and UI-02.
- Production event stream: API-05 depends on API-01/API-02; UI-07 consumes it.
- Research API: RW-API-00..06 keep their Research domain dependencies (RW0/RW1/RW2/RW3/RW4/RW5/RW6/RW9 and PM-05 where required). They do not gate the Production MVP.
- Research UI: UI-04/UI-05/UI-06 depend on the corresponding RW APIs and research services.
- Cross-context/browser qualification: API-06 and UI-08 follow their API, UI and PM/RP security dependencies.
- Docker, remote host setup and deployment require an implemented runtime contract and OPS-01/QA-03 evidence on ASUS under realistic co-resident Production + Research load. Production and Research keep separate processes, local state, credentials and resource budgets. Never share SQLite WAL across hosts or domains.

## Admission rule

Until canonical sprint specs are admitted to the manifest and all projections validate, these IDs are planning only. A sprint is claimable only when the manifest marks it READY and every declared dependency is DONE. Structural READY does not qualify data, a release, a host, or real-money activation.

## Guarded commands admission

[ADR-010](../decisions/ADR-010-multi-strategy-production-and-guarded-controls.md) admits API-04/UI-03 planning for the exact adoption, allocation, pause-entry, resume, halt and draining commands in [BOT-TRADE-PROGRAM](BOT-TRADE-PROGRAM.md). Existing read-only task evidence stays unchanged. Backend approval and release gates remain authoritative.
