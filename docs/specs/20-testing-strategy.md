# Evidence-based release and cross-cutting qualification

## Purpose and responsibilities

Evidence-based release and cross-cutting qualification. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `tests, docs/quality`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| QA-01 | Turnamen kecil menyatukan baseline classical ML dan follow-up jobs dengan hasil deterministik. | `docs/sprints/verification/QA-01-wave-1-tournament-checkpoint.md` |
| QA-02 | Audit membuktikan akses secret, artifact loader dan destructive paths tertutup pada release candidate. | `docs/sprints/verification/QA-02-boundary-security-verification.md` |
| QA-03 | ASUS has capacity, isolation, co-resident workload and recovery evidence for Production Main + Research Runtime before release/deployment. | `docs/sprints/verification/QA-03-capacity-and-crash-recovery-qualification.md` |
| REL-01 | Release paper/research terpaket dengan lock, runbook dan rollback yang diverifikasi. | `docs/sprints/verification/REL-01-paper-research-release-candidate.md` |

## Inputs, outputs and public interfaces

### QA-01 — Wave 1 tournament checkpoint

tiny offline tournament -> all lifecycle outcomes + identical snapshot/folds/costs comparison.

Acceptance boundary:
- Fixture mencakup INVALID_RUN HARD_FAIL NEAR_MISS PASS.
- Jadwal tindak lanjut sesuai outcome.
- Tiny CI bukan bukti real-market profitability.

### QA-02 — Boundary security verification

threat model + attack fixtures -> findings with severity and reproducible evidence.

Acceptance boundary:
- Traversal dan malicious artifact ditolak.
- Tidak ada trade-withdraw credentials.
- Allowlist Telegram ditegakkan.

### QA-03 — Capacity and crash recovery qualification

current ASUS inventory + representative co-resident Production/Research workload -> CPU/RAM/disk/latency/thermal/isolation/recovery evidence.

Acceptance boundary:
- Disk-full tidak mengakui sukses.
- Worker kill tidak duplicate metrics.
- Resource ceiling ditetapkan dari measured co-resident ASUS Production + Research baseline, bukan spesifikasi CPU semata.

### REL-01 — Paper research release candidate

frozen SHA + tested artifacts + release checklist -> candidate tag and reviewable release record.

Acceptance boundary:
- Restore previous compatible artifact terbukti.
- Optional experimental work tidak diam-diam dipromosikan.
- Unmet forward gate terlihat jelas sebagai pending champion qualification.

## Data model, persistence and lifecycle

Feature tests embedded in every sprint; checkpoint is integration of production interfaces not synthetic ID matching.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

Isolated test roots, injected clocks/seeds/probes; no cross-test singletons or shared real DB.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

Network forbidden in ordinary tests; fake Telegram; temp DB only; explicit operator-owned integration environments.

## Failure, retry, migration and recovery

Failure preserves artifacts/logs and exact SHA; release rollback proven before activation; no unstated skipped gate.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)

## Verification commands and evidence limits

Existing test environment installation is described by `requirements-dev.txt` and `requirements-research.txt`; select isolated environment before execution. Current baseline CI runs `python -m pytest -q` and `python -m ruff check src tests`. Later optional DL sprint must register `dl` and split non-DL and DL jobs; do not run an unregistered selector today and call it proof.

Per sprint: run its focused tests, affected integration/regression gates, and lint/diff checks. A full suite is required for shared contracts, migrations, judge, checkpoint and release changes; otherwise justify selection by changed behavior. Record command, exit, exact result, environment identity and target SHA. A test not installed is not a failing product test and is not passing evidence. Previously recorded counts are historical only.

Documentation-only changes run `python docs/quality/validate_planning.py` and `git diff --check`; do not install trading dependencies or claim product tests were rerun. Validation script has deliberate mutation checks documented in quality evidence.
