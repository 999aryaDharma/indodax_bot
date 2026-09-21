# ADR-005 — Shared runtime kernel with separate execution authority

Status: ACCEPTED planning decision, 2026-09-21. Authority: explicit user runtime-parity requirements and approved documentation plan. Implementation remains PLANNED.

Context: research replay and live shadow reuse accounting/risk primitives but bypass the production-shaped portfolio/OMS lifecycle. Frozen production roadmap says durable production ledger is separate from research/paper in-memory ledger. This is authority/storage separation, not a demand for different financial algorithms.

Decision: reuse the existing Decimal accounting and risk primitives; extract environment-neutral decision ownership; unify candidate/features, portfolio/risk, OMS, fill normalization, accounting and audit contracts. Inject clock, market, venue, fill model, namespace and reconciliation authority. Production alone resolves the real venue writer; research has no dependency path that can resolve it. Source modules may retain compatibility aliases while the owning implementation moves. No broad rewrite is required merely to rename packages.

Alternatives: independent paper financial engine rejected because qualification would not exercise production semantics; immediate wholesale rewrite rejected because it discards working primitives and historical compatibility. Incremental extraction with characterization and parity tests is selected.

Consequences: preserve old evidence/runtime identities; do not count pre-migration shadow as new-runtime parity proof. Production and each agent have separate durable namespaces and one writer. Different fill outcomes are justified only by versioned adapters. No frozen G0–G7 gate changes. See implementation/RUNTIME-PARITY and RP task series.
