# JOB-02 — Resource-aware idle admission

## Metadata

Status: REVIEW

Priority: P0 | Type: safety | Domain: orchestration | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/job-02-resource-aware-idle-admission`

Requirements: FR-11 | Legacy tasks: 24

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Pekerjaan berat hanya masuk saat profil host, daya, RAM, idle dan thermal memenuhi policy.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `JOB-02` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: Injected resource probes + LOW/MEDIUM/HIGH/GPU profile -> admit/defer with reasons.

Direct consumers: JOB-03, DL-01, OPS-01

## Depends On

- JOB-01 — Durable leased jobs

## Unlocks

DL-01, OPS-01, JOB-03, DATA-07

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/13-jobs-resource-policy-and-repeats.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`
- `docs/implementation/ASUS-BOT-CAPACITY-CROSSCHECK.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency JOB-01 supplies: SQLite WAL local queue: PENDING/RUNNING/SUCCESS/FAILED_RETRYABLE/FAILED_FINAL/BLOCKED_DATA/BLOCKED_POLICY/CANCELLED/STALE.

## In Scope

2026-09-24 capacity extension: follow `docs/implementation/ASUS-BOT-CAPACITY-CROSSCHECK.md`; additional cases remain unverified, including for REVIEW tasks.

- Pekerjaan berat hanya masuk saat profil host, daya, RAM, idle dan thermal memenuhi policy.
- Sensor UNKNOWN tidak dianggap aman.
- AC terputus memicu checkpoint pause.
- ASUS profile tidak mengimpor atau menjalankan training.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: JOB-03, DL-01, OPS-01.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `JOB-02` dan dependency evidence yang valid, when owning component dijalankan, then pekerjaan berat hanya masuk saat profil host, daya, RAM, idle dan thermal memenuhi policy.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **JOB-02-FR0:** Pekerjaan berat hanya masuk saat profil host, daya, RAM, idle dan thermal memenuhi policy.
1. **JOB-02-FR1:** Sensor UNKNOWN tidak dianggap aman.
2. **JOB-02-FR2:** AC terputus memicu checkpoint pause.
3. **JOB-02-FR3:** ASUS profile tidak mengimpor atau menjalankan training.

## Domain Rules / Invariants

Injected resource probes + LOW/MEDIUM/HIGH/GPU profile -> admit/defer with reasons.

Local SQLite WAL queue with lease generation fencing, heartbeat, attempts and immutable outputs.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/orchestration`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

Injected resource probes + LOW/MEDIUM/HIGH/GPU profile -> admit/defer with reasons.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/orchestration/resources.py`
- `src/indodax_lab/orchestration/worker.py`
- `tests/unit/lab/orchestration/test_resources.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/13-jobs-resource-policy-and-repeats.md`; exact table schemas use the Required Reading dataset contract.

Injected resource probes + LOW/MEDIUM/HIGH/GPU profile -> admit/defer with reasons.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Local SQLite WAL queue with lease generation fencing, heartbeat, attempts and immutable outputs.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish JOB-02-AC0: Pekerjaan berat hanya masuk saat profil host, daya, RAM, idle dan thermal memenuhi policy. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `JOB-02-AC1`, build minimal fixture proving: Sensor UNKNOWN tidak dianggap aman. Write `test_job_02_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `JOB-02-AC2`, build minimal fixture proving: AC terputus memicu checkpoint pause. Write `test_job_02_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `JOB-02-AC3`, build minimal fixture proving: ASUS profile tidak mengimpor atau menjalankan training. Write `test_job_02_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **JOB-02-AC0**, `test_job_02_valid_contract` — Pekerjaan berat hanya masuk saat profil host, daya, RAM, idle dan thermal memenuhi policy. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| JOB-02-AC1 | `test_job_02_contract_1` | Sensor UNKNOWN tidak dianggap aman |
| JOB-02-AC2 | `test_job_02_contract_2` | AC terputus memicu checkpoint pause |
| JOB-02-AC3 | `test_job_02_contract_3` | ASUS profile tidak mengimpor atau menjalankan training |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Sensor UNKNOWN tidak dianggap aman. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: AC terputus memicu checkpoint pause. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: ASUS profile tidak mengimpor atau menjalankan training. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
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

Emit `JOB-02` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

SIGTERM checkpoint at trial/fold boundary; lease expiry does not imply successful publish; bounded retry by reason.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **JOB-02-AC5** Capacity guards resolve each configured path to its actual mount and account for shared physical disk contention. Evidence: `test_job_02_mount_capacity` and measured mount inventory; pending.

- [ ] **JOB-02-AC4** Unknown or stale required resource sensors reject admission and optional Research load sheds before Production deadlines fail. Evidence: `test_job_02_capacity_4` plus applicable measured host artifact; not established by historical tests.

- [ ] **JOB-02-AC0** Pekerjaan berat hanya masuk saat profil host, daya, RAM, idle dan thermal memenuhi policy. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **JOB-02-AC1** Sensor UNKNOWN tidak dianggap aman. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **JOB-02-AC2** AC terputus memicu checkpoint pause. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **JOB-02-AC3** ASUS profile tidak mengimpor atau menjalankan training. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Sensor UNKNOWN tidak dianggap aman. Inspect fixture and actual production path.
- Attempt to disprove: AC terputus memicu checkpoint pause. Inspect fixture and actual production path.
- Attempt to disprove: ASUS profile tidak mengimpor atau menjalankan training. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/job-02-resource-aware-idle-admission`. Commit: `feat(job-02): resource-aware idle admission` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/JOB-02-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: JOB-03, DL-01, OPS-01. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement JOB-02 only: Resource-aware idle admission.
Read AGENTS.md, docs/sprints/orchestration/JOB-02-resource-aware-idle-admission.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Pekerjaan berat hanya masuk saat profil host, daya, RAM, idle dan thermal memenuhi policy.
Contract: Injected resource probes + LOW/MEDIUM/HIGH/GPU profile -> admit/defer with reasons.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
