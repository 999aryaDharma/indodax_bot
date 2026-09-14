# JOB-01 — Durable leased jobs

## Metadata

Status: PLANNED

Priority: P0 | Type: feature | Domain: orchestration | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/job-01-durable-leased-jobs`

Requirements: FR-11 | Legacy tasks: 24

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Dua worker tidak dapat mengeksekusi claim yang sama dan crash dapat dipulihkan tanpa duplicate result.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `JOB-01` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: SQLite WAL local queue: PENDING/RUNNING/SUCCESS/FAILED_RETRYABLE/FAILED_FINAL/BLOCKED_DATA/BLOCKED_POLICY/CANCELLED/STALE.

Direct consumers: JOB-02, OPS-02

## Depends On

- EVAL-01 — Immutable experiment registry

## Unlocks

JOB-02, OPS-02

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/13-jobs-resource-policy-and-repeats.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency EVAL-01 supplies: run_id + parent + git SHA + environment/data/config/cost/execution hashes -> immutable run record.

## In Scope

- Dua worker tidak dapat mengeksekusi claim yang sama dan crash dapat dipulihkan tanpa duplicate result.
- Claim atomik dua koneksi hanya satu menang.
- Stale lease fencing menolak publish worker lama.
- Partial artifact tidak menandai SUCCESS.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: JOB-02, OPS-02.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `JOB-01` dan dependency evidence yang valid, when owning component dijalankan, then dua worker tidak dapat mengeksekusi claim yang sama dan crash dapat dipulihkan tanpa duplicate result.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **JOB-01-FR0:** Dua worker tidak dapat mengeksekusi claim yang sama dan crash dapat dipulihkan tanpa duplicate result.
1. **JOB-01-FR1:** Claim atomik dua koneksi hanya satu menang.
2. **JOB-01-FR2:** Stale lease fencing menolak publish worker lama.
3. **JOB-01-FR3:** Partial artifact tidak menandai SUCCESS.

## Domain Rules / Invariants

SQLite WAL local queue: PENDING/RUNNING/SUCCESS/FAILED_RETRYABLE/FAILED_FINAL/BLOCKED_DATA/BLOCKED_POLICY/CANCELLED/STALE.

Local SQLite WAL queue with lease generation fencing, heartbeat, attempts and immutable outputs.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/orchestration`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

SQLite WAL local queue: PENDING/RUNNING/SUCCESS/FAILED_RETRYABLE/FAILED_FINAL/BLOCKED_DATA/BLOCKED_POLICY/CANCELLED/STALE.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/orchestration/jobs.py`
- `src/indodax_lab/orchestration/queue.py`
- `tests/unit/lab/orchestration/test_queue.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/13-jobs-resource-policy-and-repeats.md`; exact table schemas use the Required Reading dataset contract.

SQLite WAL local queue: PENDING/RUNNING/SUCCESS/FAILED_RETRYABLE/FAILED_FINAL/BLOCKED_DATA/BLOCKED_POLICY/CANCELLED/STALE.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Local SQLite WAL queue with lease generation fencing, heartbeat, attempts and immutable outputs.

Schema-changing capability: sebelum perubahan, buat consistent backup/copy dan test upgrade, second-run idempotency, rollback serta referential integrity.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish JOB-01-AC0: Dua worker tidak dapat mengeksekusi claim yang sama dan crash dapat dipulihkan tanpa duplicate result. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `JOB-01-AC1`, build minimal fixture proving: Claim atomik dua koneksi hanya satu menang. Write `test_job_01_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `JOB-01-AC2`, build minimal fixture proving: Stale lease fencing menolak publish worker lama. Write `test_job_01_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `JOB-01-AC3`, build minimal fixture proving: Partial artifact tidak menandai SUCCESS. Write `test_job_01_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **JOB-01-AC0**, `test_job_01_valid_contract` — Dua worker tidak dapat mengeksekusi claim yang sama dan crash dapat dipulihkan tanpa duplicate result. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| JOB-01-AC1 | `test_job_01_contract_1` | Claim atomik dua koneksi hanya satu menang |
| JOB-01-AC2 | `test_job_01_contract_2` | Stale lease fencing menolak publish worker lama |
| JOB-01-AC3 | `test_job_01_contract_3` | Partial artifact tidak menandai SUCCESS |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Claim atomik dua koneksi hanya satu menang. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Stale lease fencing menolak publish worker lama. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Partial artifact tidak menandai SUCCESS. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Worker commands from allowlisted job types; reports cannot inject shell commands; credentials scoped to collection only.

Trust boundary assessment: no new public authentication surface; verified local input remains mandatory and existing secret/PII controls apply.

## Concurrency / Idempotency

One HIGH/GPU or two MEDIUM by default on capable Lenovo; stale worker fenced before requeue. No cross-host shared SQLite.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `JOB-01` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

SIGTERM checkpoint at trial/fold boundary; lease expiry does not imply successful publish; bounded retry by reason.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Restore verified pre-migration copy on a stopped writer, replay from known checkpoint, and compare identities/row counts before reactivation. Keep failed migration evidence; never delete sole backup.

## Acceptance Criteria

- [ ] **JOB-01-AC0** Dua worker tidak dapat mengeksekusi claim yang sama dan crash dapat dipulihkan tanpa duplicate result. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **JOB-01-AC1** Claim atomik dua koneksi hanya satu menang. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **JOB-01-AC2** Stale lease fencing menolak publish worker lama. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **JOB-01-AC3** Partial artifact tidak menandai SUCCESS. Evidence: mapped test, exact command/exit and target SHA.
- [ ] Public contract matches this sprint and downstream can consume its actual verified output.
- [ ] Failure diagnostics are explicit and no forbidden side effect exists.

## Definition of Done

- [ ] All acceptance criteria mapped to evidence; no required tests skipped silently.
- [ ] Focused and affected integration/regression checks pass; full suite where required by scope.
- [ ] No unrelated capability or policy relaxation introduced.
- [ ] Contracts/docs updated if implementation reveals an approved deviation.
- [ ] Self-reviewed diff and handoff record contain exact source SHA, environment, commands and risks.
- [ ] Independent reviewer verifies spec and quality on that same SHA; no unresolved Critical/Important findings.
- [ ] Coordinator updates manifest and regenerates status/waves only after review PASS.

Historical import note: unchecked boxes describe the gate for future work/reverification; they do not replace imported DONE evidence.

## Reviewer Checklist

- Attempt to disprove: Claim atomik dua koneksi hanya satu menang. Inspect fixture and actual production path.
- Attempt to disprove: Stale lease fencing menolak publish worker lama. Inspect fixture and actual production path.
- Attempt to disprove: Partial artifact tidak menandai SUCCESS. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/job-01-durable-leased-jobs`. Commit: `feat(job-01): durable leased jobs` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/JOB-01-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: JOB-02, OPS-02. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement JOB-01 only: Durable leased jobs.
Read AGENTS.md, docs/sprints/orchestration/JOB-01-durable-leased-jobs.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Dua worker tidak dapat mengeksekusi claim yang sama dan crash dapat dipulihkan tanpa duplicate result.
Contract: SQLite WAL local queue: PENDING/RUNNING/SUCCESS/FAILED_RETRYABLE/FAILED_FINAL/BLOCKED_DATA/BLOCKED_POLICY/CANCELLED/STALE.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
