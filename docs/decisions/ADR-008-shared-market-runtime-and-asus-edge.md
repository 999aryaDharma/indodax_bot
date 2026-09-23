# ADR-008 — Shared WebSocket market runtime and ASUS Research Edge

Status: ACCEPTED planning decision, 2026-09-23. Authority: explicit owner architecture/hardware requirements and approved documentation plan. Implementation remains PLANNED. Change request: [CR-20260923](CR-20260923-shared-market-runtime.md).

## Context and precise override

Frozen v1.0 requires one canonical validated market feed for research agents but leaves its transport/runtime topology unspecified. Production Main section 7 describes ASUS primarily as an observer/backup target. This ADR explicitly supersedes that limited host-role description: ASUS is the always-on Research Workbench runtime/shadow edge; optional production observation remains separately qualified. It does not supersede Production Main execution authority, its pre-write gate, G0–G7 or isolated tournament accounting.

ASUS is owner-reported X441U/X441UV, Ubuntu Server 22.04.5, i3-6006U (2 physical cores/4 threads), 4 GB RAM, CPU-only, shared with other services. Storage/free space and network details are historical observations to remeasure.

## Decision

1. Extend the existing public collector/protocol/recovery and MarketGateway. One connection normally multiplexes the union of admitted channel subscriptions; bounded extra connections require provider/measurement justification. No strategy owns exchange polling or a socket.
2. Use a durable feed journal plus bounded in-process fan-out. Provider channel epoch/offset and trade sequence remain distinct from the existing planned `CanonicalMarketEvent.sequence`, which is a local durable feed position. Recovery preserves source identity and never fabricates provider continuity or timestamps.
3. Reuse existing typed payloads and the planned RuntimePlan/CandidateManifest/ModelManifest contracts. Add versioned runtime input/trigger/eligibility policy references, shared feature identities and prediction identities under their existing owners. Extend, never replace, ADR-006 identity rules.
4. Share feature state by semantic calculation identity; share model instances and single-flight deterministic predictions. One bounded inference subprocess isolates native-library stalls and permits model-memory reclamation; it is shared across candidates, with one active inference by default. No per-candidate processes or training imports.
5. Retain local SQLite WAL and immutable market/artifact files. Feed durability and consumer financial ACK are different checkpoints; consumer state follows ADR-007, without a second cursor transaction protocol.
6. Reuse `orchestration/resources.py` resource classes and admission authority. Model budgets, queue bounds and soft/hard thresholds are host qualification inputs. Missing required sensors blocks new workload admission. Persisted financial/feed evidence takes precedence over optional research work.
7. Training, sweeps, historical processing and packaging stay on Lenovo. ASUS serves only selected qualified CPU artifacts. Research can request promotion; only the separate Production Main release process grants execution authority.

## Consequences

REST remains centrally owned for bootstrap, metadata, history, recovery and bounded sanity/fallback reads. REST fallback does not turn an unreliable stream into a reliable one or substitute missing trades/order-book history. Transport/source or feature-semantic changes create new runtime/evidence versions.

Current public contracts remain readable; new envelope/manifest versions and explicit migration reports handle extensions. Existing historical evidence keeps original identity. Registered/LIVE model catalog state is never activation permission. Broker/PostgreSQL/hardware migration is justified only by measured bottlenecks after work sharing and bounds.

Details, tests, qualification and phased rollback: [Shared Market Runtime](../production/research-workbench/SHARED-MARKET-RUNTIME.md). This ADR documents a target, not successful deployment.
