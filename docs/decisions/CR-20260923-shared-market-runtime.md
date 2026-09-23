# CR-20260923 — Shared market runtime and ASUS research edge

Status: ACCEPTED documentation/design scope, 2026-09-23. Authority: owner's shared-WebSocket architecture brief, ASUS hardware profile, and approval to update production documentation. Runtime implementation and deployment are not authorized by this documentation change.

Owner: Codex documentation author. Worktree: `D:/bot-trading`, existing `docs/architecture-runtime-plan` branch, based on `dev`. Code evidence baseline: `dev` at `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Preserve unrelated local work, including `dashboard.pen`. Independent review is required before treating this document change as reviewed.

## Problem and outcome

The public WebSocket collector already exists, but `run_shadow_bot.py` still calls the REST-polling `LiveShadowEngine`. Frozen documents require a shared feed and isolated tournament agents. ASUS host descriptions still emphasize observer duties without describing its Research Workbench runtime role. The owner supplied a constrained 4 GB, two-core, CPU-only, shared-host profile.

Outcome: one detailed [runtime design](../production/research-workbench/SHARED-MARKET-RUNTIME.md), referenced by existing production documents, with explicit current-versus-target evidence and a staged implementation plan. [ADR-008](ADR-008-shared-market-runtime-and-asus-edge.md) records the material topology and identity decisions.

## Impact and alternatives

- Requirements: FR-02/05/10/11/12/15/18; causality, durability, security, bounded resources and recovery NFRs. No cost/search/promotion budget change or new sealed-data exposure.
- Reuse DATA-05 collector/recovery, FEAT registry/materializer, ML artifact loaders, JOB-02 admission, RP shared kernel, RW immutable manifests, and PM-02 execution transaction semantics. No second registry or financial authority.
- Affected future work: DATA-05 extensions, FEAT live equivalence, ML runtime serving, JOB-02 resource extensions, RP-02/04, RW0/2/4/5/6, OPS-01 and QA-03. Existing sprint statuses are unchanged. Before code starts, map the design phases into the manifest/DAG and feature map under reviewed owning tasks; do not manufacture READY or DONE from this document.
- Selected: bounded in-process fan-out with one shared inference subprocess when models are admitted. Rejected for now: per-candidate processes, broker infrastructure and unconditional database replacement; they increase memory/operational cost without measured need.
- Persistence: new versioned feed journal/cursors and isolated execution namespaces require explicit schema migration. Keep legacy evidence read-only; no automatic live DB conversion.
- Provider: public market data only; current limits, replay behavior and storage/retention permissions need activation evidence. No private market/account key is required for this design.
- Host facts supplied by owner are planning inputs, not a fresh remote hardware audit or throughput evidence. Capacity remains unqualified until ASUS measurements.

## Acceptance and rollback

Documentation must preserve Production Main authority and G0–G7, distinguish tournament/portfolio modes, specify bounded failure behavior, expose CLI/service drift, and link all implementation phases to tests, observability and rollback. Run the planning validator, Markdown link checks and diff-check. No product-test or host qualification claim comes from these checks.

Rollback of documentation restores the prior documentation revision without deleting evidence. Runtime rollback is a separate, namespace-aware procedure in the design; no financial history is rewound.

## Documentation verification and review — 2026-09-23

Reviewed design SHA: `624ceadb30a708176d59554886f6d44332f0f521`; cumulative base: `b8b4dc5d88c098e395585cd3d2c8bf724f1dee1b`. This section is a subsequent evidence-only amendment, not an assertion that the design's future implementation has passed.

- `python docs/quality/validate_planning.py`: exit 0, PASS; 119 nodes, 214 edges, zero cycles. Manifest/status files were not changed.
- `git diff b8b4dc5 HEAD --check -- docs` at reviewed SHA: exit 0. Local Markdown file targets and heading anchors checked across all 15 changed/new documents: PASS.
- Independent reviewer `/root/shared_runtime_docs_review`: initial review requested one Important correction for periodic-trigger identity; fix adds durable trigger envelopes, original-input binding, deadline/recovery semantics and prescribed regression cases. Re-review of exact design SHA above: PASS, no remaining Critical/Important findings.
- Review scope: documentation requirements, architecture consistency, recovery/identity/resource/authority boundaries. Product tests, live provider behavior, ASUS measurements and deployment readiness were not certified or claimed. Runtime/config/service files and unrelated `dashboard.pen` were not changed by this task.
- Output remains on the existing `docs/architecture-runtime-plan` worktree branch; no merge, push, service activation or live execution occurred.
