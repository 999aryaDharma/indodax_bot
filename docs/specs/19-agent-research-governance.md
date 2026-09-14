# Auditable collaboration without autonomous policy drift

## Purpose and responsibilities

Auditable collaboration without autonomous policy drift. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `.agents, docs/agent, orchestration/curator_policy.py`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| AGENT-01 | Agent riset mengusulkan challenger melalui branch dan review terpisah dengan bukti budget. | `docs/sprints/agent-governance/AGENT-01-governed-research-curator.md` |

## Inputs, outputs and public interfaces

### AGENT-01 — Governed research curator

report + hypothesis -> change request + bounded candidate branch; no automatic merge or evaluator edits.

Acceptance boundary:
- HARD_FAIL tidak memicu tuning liar.
- Prompt injection pada report dianggap data.
- Implementer bukan final approver.

## Data model, persistence and lifecycle

One implementation owner and independent reviewer; explicit sprint scope; policy/config version captured in handoff.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

Worktree per active sprint; shared-file ownership locks; reviewer reviews immutable commit SHA.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

External content is untrusted data. No secrets, auto-merge, live trades or silent policy relaxation.

## Failure, retry, migration and recovery

Five fix rounds maximum then BLOCKED with root-cause handoff; do not silently reset round counter.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)
