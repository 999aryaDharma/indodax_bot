# Host lifecycle, backup, transfer and retention

## Purpose and responsibilities

Host lifecycle, backup, transfer and retention. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `deploy, configs/schedules`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

Production Main is a live real-trading system. Operational/control-plane read surfaces must consume authoritative live Production state and never silently mutate upstream artifacts or financial state. Research/experiment subsystems do not receive Production trading credentials or write authority. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| OPS-01 | Production Main and Research Runtime run as separate ASUS services with measured Production resource headroom; Lenovo handles ML/DL training and tuning. | `docs/sprints/operations/OPS-01-host-profiles-and-service-lifecycle.md` |
| OPS-02 | Dataset antar-host ditransfer dan dipulihkan melalui staging yang diverifikasi. | `docs/sprints/operations/OPS-02-snapshot-transfer-and-restore.md` |
| OPS-03 | Cleanup hanya menghapus artifact tidak direferensikan setelah retention dan dry-run audit. | `docs/sprints/operations/OPS-03-storage-retention-and-integrity-maintenance.md` |

## Inputs, outputs and public interfaces

### OPS-01 — Host profiles and service lifecycle

systemd service/timer or equivalent local host supervisor -> start/stop/restart with explicit roots and env.

Acceptance boundary:
- Cold boot tidak menjalankan dua writer.
- SIGTERM flush dan lease release.
- Missing secret fail tanpa mencetak secret.

### OPS-02 — Snapshot transfer and restore

manifest + checksums + SQLite consistent backup -> staged copy -> verify -> atomic publish.

Acceptance boundary:
- Partial transfer tidak mengganti aktif snapshot.
- Backup SQLite memakai consistent API bukan copy WAL mentah.
- Restore run di root baru mempertahankan IDs.

### OPS-03 — Storage retention and integrity maintenance

registry reachability + retention policy -> deletion candidates, approved apply report.

Acceptance boundary:
- Champion dan sealed inputs tidak terhapus.
- Symlink escape ditolak.
- Interrupted cleanup dapat rerun tanpa menghapus live data.

## Data model, persistence and lifecycle

Artifacts outside Git; host-neutral logical paths, local service profile; consistent DB backup; verified transfer staging.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

Single active writer host; transfer immutable artifacts only; local locks; never shared SQLite WAL via SMB/NFS.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

Least-privilege service user; private env file; no public dashboard implied; secrets redacted; destructive cleanup dry-run first.

## Failure, retry, migration and recovery

Verified restore rehearsal in alternate root; measure RPO/RTO; pin last working compatible artifact and environment lock.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)
