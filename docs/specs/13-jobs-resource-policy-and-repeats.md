# Durable bounded background research

## Purpose and responsibilities

Durable bounded background research. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `src/indodax_lab/orchestration`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| JOB-01 | Dua worker tidak dapat mengeksekusi claim yang sama dan crash dapat dipulihkan tanpa duplicate result. | `docs/sprints/orchestration/JOB-01-durable-leased-jobs.md` |
| JOB-02 | Pekerjaan berat hanya masuk saat profil host, daya, RAM, idle dan thermal memenuhi policy. | `docs/sprints/orchestration/JOB-02-resource-aware-idle-admission.md` |
| JOB-03 | Scheduler hanya mengulang eksperimen yang diizinkan evaluator pada input immutable. | `docs/sprints/orchestration/JOB-03-evaluator-controlled-research-dag.md` |

## Inputs, outputs and public interfaces

### JOB-01 — Durable leased jobs

SQLite WAL local queue: PENDING/RUNNING/SUCCESS/FAILED_RETRYABLE/FAILED_FINAL/BLOCKED_DATA/BLOCKED_POLICY/CANCELLED/STALE.

Acceptance boundary:
- Claim atomik dua koneksi hanya satu menang.
- Stale lease fencing menolak publish worker lama.
- Partial artifact tidak menandai SUCCESS.

### JOB-02 — Resource-aware idle admission

Injected resource probes + LOW/MEDIUM/HIGH/GPU profile -> admit/defer with reasons.

Acceptance boundary:
- Sensor UNKNOWN tidak dianggap aman.
- AC terputus memicu checkpoint pause.
- ASUS profile tidak mengimpor atau menjalankan training.

### JOB-03 — Evaluator-controlled research DAG

cadence window + snapshot + recipe -> idempotent DAG jobs with dependency states.

Acceptance boundary:
- HARD_FAIL tidak dibuka karena komputer idle.
- INVALID_RUN retry terbatas memakai config sama.
- NEAR_MISS perlu hipotesis dan budget serta versi baru.

## Data model, persistence and lifecycle

Local SQLite WAL queue with lease generation fencing, heartbeat, attempts and immutable outputs.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

One HIGH/GPU or two MEDIUM by default on capable Lenovo; stale worker fenced before requeue. No cross-host shared SQLite.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

Worker commands from allowlisted job types; reports cannot inject shell commands; credentials scoped to collection only.

## Failure, retry, migration and recovery

SIGTERM checkpoint at trial/fold boundary; lease expiry does not imply successful publish; bounded retry by reason.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)

## Lease and retry contract

Job identity includes type, recipe version/hash, input IDs and cadence window. Claim transaction updates PENDING -> RUNNING with owner, generation and expiration under SQLite WAL; heartbeat extends only matching owner/generation. Result publication checks same generation before committing SUCCESS; stale worker output cannot overwrite successor. External immutable artifact may exist before DB success after crash, so retry verifies and reuses identical complete output rather than duplicating it.

FAILED_RETRYABLE has attempt cap/backoff and stable config. FAILED_FINAL, CANCELLED and exhausted retries do not auto-reschedule. BLOCKED_DATA/BLOCKED_POLICY only clear when new dependency evidence satisfies the recorded reason. SIGTERM persists checkpoint at safe trial/fold boundary. Event-time and wall-clock heartbeat serve different purposes; injected clocks cover expiry tests.

Admission defaults: Lenovo at most1 HIGH/GPU or2 MEDIUM, DL AC-connected, idle>=10min, freeRAM>=4GB, explicit thermal/GPU policy. These are inherited policy inputs, not proof the machine can sustain the workload. Probe missing thermal is UNKNOWN; GPU/AC absence has explicit defer behavior. No training on ASUS-light profile. A stopped collector or stale quality stream can block paper entries independent of compute idleness.
