# OPS-02 — Snapshot transfer and restore

## Metadata

Status: REVIEW

Priority: P0 | Type: safety | Domain: operations | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/ops-02-snapshot-transfer-and-restore`

Requirements: FR-15 | Legacy tasks: Catalog extension / operational gap identified in audit

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Dataset antar-host ditransfer dan dipulihkan melalui staging yang diverifikasi.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `OPS-02` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: manifest + checksums + SQLite consistent backup -> staged copy -> verify -> atomic publish.

Direct consumers: OPS-03, QA-02

## Depends On

- DATA-06 — Provider-derived reproducible snapshot
- JOB-01 — Durable leased jobs

## Unlocks

OPS-03, QA-02

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/17-operations-security-and-recovery.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency DATA-06 supplies: Typed loaders -> recomputed sentry decisions -> fixed cutoff -> immutable snapshot with 45 source references.
- Dependency JOB-01 supplies: SQLite WAL local queue: PENDING/RUNNING/SUCCESS/FAILED_RETRYABLE/FAILED_FINAL/BLOCKED_DATA/BLOCKED_POLICY/CANCELLED/STALE.

## In Scope

- Dataset antar-host ditransfer dan dipulihkan melalui staging yang diverifikasi.
- Partial transfer tidak mengganti aktif snapshot.
- Backup SQLite memakai consistent API bukan copy WAL mentah.
- Restore run di root baru mempertahankan IDs.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: OPS-03, QA-02.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `OPS-02` dan dependency evidence yang valid, when owning component dijalankan, then dataset antar-host ditransfer dan dipulihkan melalui staging yang diverifikasi.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **OPS-02-FR0:** Dataset antar-host ditransfer dan dipulihkan melalui staging yang diverifikasi.
1. **OPS-02-FR1:** Partial transfer tidak mengganti aktif snapshot.
2. **OPS-02-FR2:** Backup SQLite memakai consistent API bukan copy WAL mentah.
3. **OPS-02-FR3:** Restore run di root baru mempertahankan IDs.

## Domain Rules / Invariants

manifest + checksums + SQLite consistent backup -> staged copy -> verify -> atomic publish.

Artifacts outside Git; host-neutral logical paths, local service profile; consistent DB backup; verified transfer staging.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `deploy, configs/schedules`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

manifest + checksums + SQLite consistent backup -> staged copy -> verify -> atomic publish.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `deploy/backup-lab.sh`
- `deploy/restore-lab.sh`
- `tests/integration/lab/test_backup_restore.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/17-operations-security-and-recovery.md`; exact table schemas use the Required Reading dataset contract.

manifest + checksums + SQLite consistent backup -> staged copy -> verify -> atomic publish.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Artifacts outside Git; host-neutral logical paths, local service profile; consistent DB backup; verified transfer staging.

Schema-changing capability: sebelum perubahan, buat consistent backup/copy dan test upgrade, second-run idempotency, rollback serta referential integrity.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish OPS-02-AC0: Dataset antar-host ditransfer dan dipulihkan melalui staging yang diverifikasi. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `OPS-02-AC1`, build minimal fixture proving: Partial transfer tidak mengganti aktif snapshot. Write `test_ops_02_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `OPS-02-AC2`, build minimal fixture proving: Backup SQLite memakai consistent API bukan copy WAL mentah. Write `test_ops_02_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `OPS-02-AC3`, build minimal fixture proving: Restore run di root baru mempertahankan IDs. Write `test_ops_02_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **OPS-02-AC0**, `test_ops_02_valid_contract` — Dataset antar-host ditransfer dan dipulihkan melalui staging yang diverifikasi. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| OPS-02-AC1 | `test_ops_02_contract_1` | Partial transfer tidak mengganti aktif snapshot |
| OPS-02-AC2 | `test_ops_02_contract_2` | Backup SQLite memakai consistent API bukan copy WAL mentah |
| OPS-02-AC3 | `test_ops_02_contract_3` | Restore run di root baru mempertahankan IDs |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Partial transfer tidak mengganti aktif snapshot. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Backup SQLite memakai consistent API bukan copy WAL mentah. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Restore run di root baru mempertahankan IDs. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Least-privilege service user; private env file; no public dashboard implied; secrets redacted; destructive cleanup dry-run first.

Trust boundary assessment: untrusted provider/artifact input or privileged state mutation exists; require negative tests and redacted diagnostics.

## Concurrency / Idempotency

Single active writer host; transfer immutable artifacts only; local locks; never shared SQLite WAL via SMB/NFS.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `OPS-02` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Verified restore rehearsal in alternate root; measure RPO/RTO; pin last working compatible artifact and environment lock.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Restore verified pre-migration copy on a stopped writer, replay from known checkpoint, and compare identities/row counts before reactivation. Keep failed migration evidence; never delete sole backup.

## Acceptance Criteria

- [ ] **OPS-02-AC0** Dataset antar-host ditransfer dan dipulihkan melalui staging yang diverifikasi. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **OPS-02-AC1** Partial transfer tidak mengganti aktif snapshot. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **OPS-02-AC2** Backup SQLite memakai consistent API bukan copy WAL mentah. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **OPS-02-AC3** Restore run di root baru mempertahankan IDs. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Partial transfer tidak mengganti aktif snapshot. Inspect fixture and actual production path.
- Attempt to disprove: Backup SQLite memakai consistent API bukan copy WAL mentah. Inspect fixture and actual production path.
- Attempt to disprove: Restore run di root baru mempertahankan IDs. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/ops-02-snapshot-transfer-and-restore`. Commit: `feat(ops-02): snapshot transfer and restore` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/OPS-02-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: OPS-03, QA-02. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement OPS-02 only: Snapshot transfer and restore.
Read AGENTS.md, docs/sprints/operations/OPS-02-snapshot-transfer-and-restore.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Dataset antar-host ditransfer dan dipulihkan melalui staging yang diverifikasi.
Contract: manifest + checksums + SQLite consistent backup -> staged copy -> verify -> atomic publish.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
