# Forward unbiased paper trading and champion control

## Purpose and responsibilities

Forward unbiased paper trading and champion control. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `src/indodax_lab/paper`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| SHADOW-01 | Forecast forward dan keputusan risiko tersimpan sebelum outcome tanpa callback selection bias. | `docs/sprints/shadow/SHADOW-01-auditable-forward-paper-decisions.md` |
| SHADOW-02 | Satu ledger bersama Rp500k menyelesaikan konflik kas dan restart secara konsisten. | `docs/sprints/shadow/SHADOW-02-shared-capital-reconciliation.md` |
| SHADOW-03 | Challenger menggantikan champion hanya setelah historical dan forward evidence cukup. | `docs/sprints/shadow/SHADOW-03-champion-replacement-gate.md` |

## Inputs, outputs and public interfaces

### SHADOW-01 — Auditable forward paper decisions

frozen candidate + live available features -> immutable prediction/decision with paper intent only.

Acceptance boundary:
- Telegram gagal tidak menghapus decision.
- Stale data atau model mismatch menolak entry.
- Manual intent bukan ground truth.

### SHADOW-02 — Shared capital reconciliation

durable event IDs + risk policy -> reconciled postings, independent vs shared reports.

Acceptance boundary:
- Duplicate event tidak membuat entry kedua.
- Maksimum dua posisi shared.
- Restart menghasilkan equity dan checkpoint sama.

### SHADOW-03 — Champion replacement gate

sealed pass + >=90 days AND >=100 pooled closed forward trades + no policy breach -> versioned promotion.

Acceptance boundary:
- 100 trade dalam 10 hari belum lolos.
- 90 hari tanpa cukup trade belum lolos.
- Training challenger tidak mengubah champion aktif.

## Data model, persistence and lifecycle

Immutable decisions before outcome; shared Rp500k vs independent Rp500k; reconcile event IDs and balances.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

Atomic cash reservations and processed-event checkpoint; risk cap across all candidates in shared portfolio.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

Paper only; authorized operator may pause/reset hard halt via audited control, never through untrusted callback.

## Failure, retry, migration and recovery

Champion pointer changes atomically only after gates; preserve prior compatible artifact and ledger checkpoints.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)

## Forward and shared ledger contract

Prediction record contains frozen model/strategy version, sample/feature IDs, decision timestamp, raw forecast basis/value, calibration version, estimated cost, margin, risk decision and planned paper order. Save before outcome resolution. User clicks reference existing observation; no ID or stale legacy callback is rejected explicitly.

Each independent ledger starts virtual IDR500000; shared ledger starts IDR500000 once. Shared conflict resolution uses stable priority/tie policy fixed before run, atomically reserves cash and respects max2 positions plus aggregate exposure. Event ID checkpoint and ledger mutation commit together. Reconciliation compares cash, quantity, valued postings and processed event IDs after restart.

Champion replacement is a separate decision: frozen historical-qualified candidate plus at least90 days observed forward AND100 pooled closed trades, with no policy breach and sufficient quality. Unknown fees/data/model mismatch block new entry. Training does not overwrite champion pointer. Promotion stores previous/current bundle IDs and can roll back only to compatible verified model/schema; never erase failed forward outcomes.
