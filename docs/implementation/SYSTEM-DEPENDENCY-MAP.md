# System dependency map

Classification: PLANNED. The [manifest](../sprints/sprint-manifest.json) is sole status/DAG authority; this is the architectural view.

## Critical ordering

DOC-01 review → RP-01 shared decision ownership → RW0-01 immutable contracts.

RW0 → datasets and component registries; components → typed pipelines → candidate evaluator. RW0 also feeds portfolio/risk and atomic execution-state work. Candidate evaluator + portfolio/risk + execution state → historical/shadow adapters → parity tests.

Datasets + pipelines + historical adapter + existing reviewed queue/registry → experiments → candidate packaging → isolated agents → tournament/qualification. Portfolio Shadow is a separate namespace after agent/kernel infrastructure, never the tournament wallet.

Read-only MCP follows implemented registry/query services. Mutation MCP follows the corresponding completed mutation services, agents and promotion-request bridge. Dashboard views follow service contracts; form/graph editing follows pipeline validation and experiment services. Production bridge follows qualified evidence and reviewed production release schema.

Production safety can run independently where dependencies allow: PM-01 authority, PM-02 financial transaction, then PM-03 recovery/control; PM-04 venue semantics consumes authority/financial contracts. PM-05 binds release identity; PM-06 verifies CI/operations. No production activation is included.

## New executable units

| Task | Direct prerequisites | Deliverable |
|---|---|---|
| [DOC-01](../../docs/sprints/planning/DOC-01-frozen-architecture-audit-and-delivery-program.md) | None | Frozen architecture audit and delivery program |
| [RP-01](../../docs/sprints/runtime-parity/RP-01-shared-signalintent-ownership-with-compatibility.md) | DOC-01, BASE-01 | Shared SignalIntent ownership with compatibility |
| [RW0-01](../../docs/sprints/research-workbench/RW0-01-immutable-workbench-domain-manifests.md) | RP-01, DATA-01 | Immutable Workbench domain manifests |
| [RW1-01](../../docs/sprints/research-workbench/RW1-01-reusable-immutable-dataset-registry.md) | RW0-01, DATA-06 | Reusable immutable dataset registry |
| [RW2-01](../../docs/sprints/research-workbench/RW2-01-durable-versioned-strategy-registry.md) | RW0-01, STRAT-01 | Durable versioned strategy registry |
| [RW2-02](../../docs/sprints/research-workbench/RW2-02-model-registry-and-offline-training-services.md) | RW0-01, ML-04, JOB-01 | Model registry and offline training services |
| [RW2-03](../../docs/sprints/research-workbench/RW2-03-typed-declarative-pipeline-composer.md) | RW2-01, RW2-02 | Typed declarative pipeline composer |
| [RP-02](../../docs/sprints/runtime-parity/RP-02-shared-candidate-feature-and-exit-evaluation.md) | RW2-03, FEAT-02 | Shared candidate feature and exit evaluation |
| [RP-03](../../docs/sprints/runtime-parity/RP-03-shared-portfolio-sizing-and-risk-semantics.md) | RW0-01, SIM-02 | Shared portfolio sizing and risk semantics |
| [PM-01](../../docs/sprints/production-main/PM-01-authoritative-fail-closed-pre-write-gate.md) | RW0-01 | Authoritative fail-closed pre-write gate |
| [PM-02](../../docs/sprints/production-main/PM-02-atomic-financial-execution-state-and-recovery.md) | RW0-01, LED-01 | Atomic financial execution state and recovery |
| [PM-03](../../docs/sprints/production-main/PM-03-recovery-mode-and-durable-operator-risk-governance.md) | PM-01, PM-02 | Recovery mode and durable operator risk governance |
| [PM-04](../../docs/sprints/production-main/PM-04-venue-parser-cancellation-and-supported-order-semantics.md) | PM-01, PM-02 | Venue parser cancellation and supported order semantics |
| [RP-04](../../docs/sprints/runtime-parity/RP-04-canonical-feed-and-environment-runtime-adapters.md) | RP-02, RP-03, PM-02 | Canonical feed and environment runtime adapters |
| [RP-05](../../docs/sprints/runtime-parity/RP-05-runtime-parity-qualification-fixtures.md) | RP-04, PM-04 | Runtime parity qualification fixtures |
| [RW3-01](../../docs/sprints/research-workbench/RW3-01-experiment-lifecycle-and-backtest-orchestration.md) | RW1-01, RW2-03, RP-04, EVAL-01, JOB-01 | Experiment lifecycle and backtest orchestration |
| [RW4-01](../../docs/sprints/research-workbench/RW4-01-immutable-candidate-packaging-and-lifecycle.md) | RW3-01, ML-04 | Immutable candidate packaging and lifecycle |
| [RW5-01](../../docs/sprints/research-workbench/RW5-01-isolated-durable-forward-shadow-agents.md) | RW4-01, RP-05 | Isolated durable forward-shadow agents |
| [RW5-02](../../docs/sprints/research-workbench/RW5-02-tournament-cohorts-leaderboard-and-qualification.md) | RW5-01, SHADOW-03 | Tournament cohorts leaderboard and qualification |
| [RW6-01](../../docs/sprints/research-workbench/RW6-01-separate-shared-capital-portfolio-shadow.md) | RW5-01, RP-03 | Separate shared-capital Portfolio Shadow |
| [RW7-01](../../docs/sprints/research-workbench/RW7-01-read-only-quantops-mcp-boundary.md) | RW1-01, RW2-03, RW4-01 | Read-only QuantOps MCP boundary |
| [RW7-02](../../docs/sprints/research-workbench/RW7-02-audited-quantops-research-mutations.md) | RW7-01, RW5-02, RW6-01, RW9-01 | Audited QuantOps research mutations |
| [RW8-01](../../docs/sprints/research-workbench/RW8-01-research-read-models-and-dashboard-navigation.md) | RW5-02, RW6-01 | Research read models and dashboard navigation |
| [RW8-02](../../docs/sprints/research-workbench/RW8-02-workbench-form-and-graph-editors.md) | RW8-01, RW2-03, RW3-01 | Workbench form and graph editors |
| [PM-05](../../docs/sprints/production-main/PM-05-candidate-bound-release-provenance.md) | RW4-01, PM-03 | Candidate-bound release provenance |
| [PM-06](../../docs/sprints/production-main/PM-06-ci-security-and-operational-release-evidence.md) | PM-05, RW5-01 | CI security and operational release evidence |
| [RW9-01](../../docs/sprints/research-workbench/RW9-01-promotion-request-and-production-export-bridge.md) | RW4-01, RW5-02, PM-05 | Promotion request and production export bridge |

## Scheduling and gates

Legacy REVIEW nodes are real prerequisites: review their existing code and handoffs on exact SHA before DONE; do not reimplement them or drop edges to unlock new work. DOC-01 owns shared manifest/projection files during this delivery. After review, RP-01 is the first LUNA task; dependencies do not imply real-data availability. No dashboard, MCP mutation or tournament implementation may leapfrog its declared service/kernel prerequisites. External activation constraints stay blocked even when offline fixture implementation becomes READY.
