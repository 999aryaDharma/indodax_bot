# research-workbench roadmap

Classification: PLANNED. Status/DAG authority: [manifest](../../sprints/sprint-manifest.json).

- [RW0 — Domain contracts](RW0-domain-contracts.md)
- [RW1 — Dataset registry](RW1-dataset-registry.md)
- [RW2 — Component and pipeline registries](RW2-component-and-pipeline-registries.md)
- [RW3 — Experiment and backtest orchestration](RW3-experiment-and-backtest-orchestration.md)
- [RW4 — Candidate packaging](RW4-candidate-packaging.md)
- [RW5 — Tournament runtime](RW5-tournament-runtime.md)
- [RW6 — Portfolio Shadow](RW6-portfolio-shadow.md)
- [RW7 — QuantOps MCP](RW7-quantops-mcp.md)
- [RW8 — Dashboard](RW8-dashboard.md)
- [RW9 — Production bridge](RW9-production-bridge.md)

Every task requires dependencies DONE and independent exact-SHA review. Real data, model environment, licenses, venue behavior and host gates are separately recorded. Existing implementation is reused; REVIEW prerequisites are reviewed, not automatically rebuilt.

## Product workflow amendment

[Program contract](../BOT-TRADE-PROGRAM.md): DATA-07 reuses collection and registry primitives, RW2 adds YAML/form/MCP parity, RW3 produces independent per-pair batches, RW5 supplies Top 10, RW6 qualifies shared Production allocation, and RW7/RW8 expose the same services. Preserve existing dependency/review gates.
