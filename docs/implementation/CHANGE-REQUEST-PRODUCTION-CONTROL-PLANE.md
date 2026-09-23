# CR-2026-09-23 — Admit Production Read API and Read-Only Dashboard

Status: ACCEPTED by the repository owner for scoped implementation planning and paper/shadow-only development. This does not authorize real-money operation, Production deployment, credential use, or any deployment to ASUS.

## Request

Admit a governed Production Main read API and read-only desktop/smartphone dashboard, with dependencies represented in the sprint manifest and all generated projections. Work Production before Research UI/API. Use Cloudflare Kumo UI components with Vercel Geist Sans/Mono, styled to the existing `DESIGN.md` tokens and behavior. API-00 and UI-00 may proceed in parallel on disjoint paths: UI-00 implements only against the frozen TypeScript-facing schema/route contract already written in the Production API plan and does not depend on backend code. Run one independent reviewer after both implementation packets are complete; do not mark either sprint DONE until the reviewer has checked its exact SHA.

## Scope and impact

- Add API-00 shared contracts; API-01 Production read models; API-03 capability/audit boundary; API-02 read-only Production routes; UI-00 shell and typed client; UI-01 context/capability navigation; UI-02 Production operational views.
- The implementation order is dependency-driven: API-00 and UI-00 may run in parallel; after API-00 is independently reviewed and DONE, API-01 and API-03 may run in parallel; then API-02; then UI-01; then UI-02. Every parallel pair owns disjoint files.
- Read endpoints expose only backend-derived state. Unknown/unavailable stays explicit; financial values remain Decimal strings; each snapshot carries UTC `as_of`, source revision, request identity and provenance.
- API-03 fails closed without an explicit principal/capability. Test/development principals are injected, never inferred as Production operators. No public or remote deployment is part of this CR.
- UI-00/UI-01/UI-02 use `@cloudflare/kumo` 2.14.0 components and self-hosted Vercel Geist Sans/Mono WOFF2 assets under the upstream SIL Open Font License. Product colors, density, type scale, radii and spacing come from `DESIGN.md`; Kumo defaults must be overridden where they diverge. Use desktop and smartphone layouts only. References: [Kumo component library](https://github.com/cloudflare/kumo), [Geist font source](https://github.com/vercel/geist-font).
- No order/withdrawal/production-command endpoints, live credentials, ledger repair, candidate mutation, Research UI/API, Docker deployment, or runtime host changes are admitted here.
- PM-01 through PM-04 are currently DONE in the manifest. PM-05/PM-06 remain PLANNED; release evidence must display unavailable/incomplete until its backend source exists. Research and runtime-parity tasks are not prerequisites for this read-only Production MVP.

## Host, market-feed, and UI transport boundaries

- The three compute planes remain distinct: Lenovo Research Compute, ASUS Research Runtime/shadow edge, and a future separate Production Main host. ASUS hardware figures are owner-reported planning inputs; live inventory, capacity and qualification are unknown. Do not invent host capacity or deploy Production Main there.
- Research owns one centrally admitted Indodax public WebSocket subscription runtime on ASUS (union subscriptions, validated/recovered events, durable local journal, bounded fan-out). Research strategies do not own exchange sockets. REST is centrally rate-budgeted for metadata/bootstrap/history/recovery; a detected WS gap pauses affected evaluation rather than being silently bridged by REST.
- Production Main owns and independently verifies its market gateway/feed health, account truth, release and write authority. Its API/UI must never source Production status through ASUS or label the ASUS Research feed as Production market truth. Production may reuse reviewed software/artifact formats only.
- Browser updates are a separate observability transport from the Indodax market WebSocket. If a future dashboard event stream is admitted, it is backend-to-browser, bounded/coalesced, read-only and non-authoritative; the browser never connects to the exchange feed. No live stream is required by this MVP.
- The read-only API exposes distinct `/api/v1/production/*`, `/api/v1/research/*`, and `/api/v1/system/*` namespaces as those domains are admitted. UI health views label the authority/host explicitly; future infrastructure views show the Production host as unprovisioned until specified.
- ASUS co-tenant inventory, free storage/network limits, safe CPU/RAM/queue/model budgets and sustained throughput are unverified. Qualification requires realistic-host benchmarks, thermal soak and 24h+ evidence under a separate Research Runtime sprint. This is not a Production API/UI dependency.

## Canonical IDs and dependencies

| Sprint | Direct dependencies | Deliverable |
|---|---|---|
| API-00 | none | Common API envelope, errors, UTC/Decimal/provenance and capability vocabulary |
| API-01 | API-00, PM-01, PM-02, PM-03, PM-04 | Production service-derived read models |
| API-03 | API-00 | Fail-closed read capability policy and request/audit context |
| API-02 | API-01, API-03 | FastAPI app and read-only Production routes |
| UI-00 | none | Kumo/Geist shell foundation and typed API client against the frozen route contract |
| UI-01 | UI-00, API-03 | Production/Research context namespace and capability presentation boundary |
| UI-02 | UI-01, API-02 | Read-only Production operational pages |

The API-03 security boundary intentionally precedes API-02. UI-00 follows the stable envelope, errors, capability names and routes already specified in the Production API plan; it does not wait for API-00 source or server routes. Collect the API-00/UI-00 implementation packets before one independent review pass; neither sprint is DONE until its exact SHA passes. API-01 may expose an explicit UNAVAILABLE release view; it does not depend on PM-05 or imply verification. API-02 exposes no write-capable route or venue adapter.

## Canonical planning changes

- Production API IDs follow `docs/superpowers/plans/2026-09-22-production-api-plan.md`: API-00 contracts, API-01 read models, API-02 read routes, API-03 capability/audit, API-04 guarded commands, API-05 event stream, API-06 qualification.
- Dashboard IDs follow `docs/superpowers/plans/2026-09-22-unified-dashboard-plan.md`: UI-00 shell/client, UI-01 context/capability guard, UI-02 Production views; later UI-03 commands, UI-04/UI-05 Research views, UI-06 editor, UI-07 event stream, UI-08 qualification.
- Research API keeps the `RW-API-*` prefix used by its child plan. It does not consume Production API IDs.
- Update the roadmap, program plan, child plans, sprint files, manifest, sprint index, dependency graph, execution waves, feature map, status summary and FR-23 traceability together.

## Compatibility, safety, and rollback

The frozen Production Main / Research Workbench authority boundary is unchanged. `DESIGN.md` controls visual behavior; Kumo and Geist are implementation inputs, not a replacement theme. UI capabilities never authorize backend access. Development remains DISABLED/RECOVERY/READ_ONLY/SHADOW and the server does not instantiate the production writer. ASUS remains Research Runtime/shadow edge; a separate Production host and deployment contract are required before any Production deployment. The Research WebSocket runtime and dashboard observability stream have separate owners, transports and authority. Rollback is a scoped revert of this CR and its generated planning files; preserve all unrelated design WIP and runtime evidence.

## Validation

Use `python docs/quality/validate_planning.py --refresh --self-test` and `git diff --check`. These are documentation validators only; they do not qualify product behavior or authorize release. Each implementation sprint still requires its own task-scope tests, exact SHA handoff, and independent review evidence.
