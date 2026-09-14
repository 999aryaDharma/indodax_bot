# ADR-001 — Paper scope and documentation precedence

Status: ACCEPTED planning baseline (preserves existing paper-only design). Date: 2026-09-14.

Context: repository has an existing bot, implemented research data pipeline and a 35-task plan. A request for complete large-project planning must not silently authorize live order execution.

Decision: evolve adjacent lab package and preserve legacy modules. Master + ADR and subsystem docs are planning authority; data contract remains exact detailed source except targeted overrides below. Old plan is historical execution crosswalk, not current dependency authority. Include all catalog hypotheses but activate extension/experimental tracks explicitly. Live orders, public SaaS and unrestricted LLM decisions remain excluded.

Alternatives: rewrite as distributed microservices (rejected: no demonstrated scale need); ignore baseline and start all sprints PLANNED (rejected: destroys useful provenance); execute the old numbered list unchanged (rejected: labels depend on later cost/execution interfaces).

Consequences: documentation branch contains only documentation and its validator. Existing WIP is retained in original worktree. Root AGENTS guides future agents; does not change runtime behavior.
