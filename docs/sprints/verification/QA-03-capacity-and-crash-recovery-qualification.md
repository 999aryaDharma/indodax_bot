# QA-03 — Capacity and crash recovery qualification

## Metadata

Status: REVIEW

Priority: P0 | Type: performance | Domain: verification | Portfolio: CORE

Implementation Owner: Antigravity | Independent Reviewer: UNASSIGNED (pending independent review)

Recommended Branch: `feat/qa-03-capacity-and-crash-recovery-qualification`

Requirements: FR-18 | Legacy tasks: 35

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

ASUS punya bukti capacity, isolation, workload co-residency dan recovery untuk Production Main + Research Runtime sebelum release/deployment.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `QA-03` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: current ASUS inventory + representative co-resident Production/Research workloads -> CPU/RAM/disk/latency/thermal/isolation/recovery evidence; Lenovo training remains outside the ASUS load profile.

Direct consumers: REL-01

## Depends On

- OPS-01 — Host profiles and service lifecycle
- OPS-03 — Storage retention and integrity maintenance
- QA-01 — Wave 1 tournament checkpoint

## Unlocks

REL-01, PM-06

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`
- `docs/decisions/ADR-009-asus-production-and-research-runtime.md`
- `docs/production/research-workbench/SHARED-MARKET-RUNTIME.md`
- `docs/implementation/ASUS-BOT-CAPACITY-CROSSCHECK.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency OPS-01 supplies: systemd service/timer or equivalent local host supervisor -> start/stop/restart with explicit roots and env.
- Dependency OPS-03 supplies: registry reachability + retention policy -> deletion candidates, approved apply report.
- Dependency QA-01 supplies: tiny offline tournament -> all lifecycle outcomes + identical snapshot/folds/costs comparison.

## In Scope

2026-09-24 capacity extension: follow `docs/implementation/ASUS-BOT-CAPACITY-CROSSCHECK.md`; additional cases remain unverified, including for REVIEW tasks.

- ASUS punya bukti capacity, isolation, workload co-residency dan recovery untuk Production Main + Research Runtime sebelum release/deployment.
- Disk-full tidak mengakui sukses.
- Worker kill tidak duplicate metrics.
- Resource ceiling ditetapkan dari measured co-resident ASUS Production + Research baseline, bukan spesifikasi CPU semata.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: REL-01.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `QA-03` dan dependency evidence yang valid, when owning component dijalankan, then host yang dipilih punya bukti workload dan recovery sebelum release.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **QA-03-FR0:** ASUS punya bukti capacity, isolation, workload co-residency and recovery untuk Production Main + Research Runtime sebelum release/deployment.
1. **QA-03-FR1:** Disk-full tidak mengakui sukses.
2. **QA-03-FR2:** Worker kill tidak duplicate metrics.
3. **QA-03-FR3:** Resource ceiling ditetapkan dari measured co-resident ASUS Production + Research baseline, bukan spesifikasi CPU semata.

## Domain Rules / Invariants

current ASUS inventory + representative co-resident Production/Research workload -> CPU/RAM/disk/latency/thermal/isolation/recovery evidence.

Feature tests embedded in every sprint; checkpoint is integration of production interfaces not synthetic ID matching.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `tests, docs/quality`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

current ASUS inventory + representative co-resident Production/Research workload -> CPU/RAM/disk/latency/thermal/isolation/recovery evidence.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `tests/integration/lab/test_operational_recovery.py`
- `docs/quality/capacity-evidence.md`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/20-testing-strategy.md`; exact table schemas use the Required Reading dataset contract.

current ASUS inventory + representative co-resident Production/Research workload -> CPU/RAM/disk/latency/thermal/isolation/recovery evidence.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Feature tests embedded in every sprint; checkpoint is integration of production interfaces not synthetic ID matching.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish QA-03-AC0: ASUS punya bukti capacity, isolation, workload co-residency dan recovery untuk Production Main + Research Runtime sebelum release/deployment. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `QA-03-AC1`, build minimal fixture proving: Disk-full tidak mengakui sukses. Write `test_qa_03_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `QA-03-AC2`, build minimal fixture proving: Worker kill tidak duplicate metrics. Write `test_qa_03_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `QA-03-AC3`, build minimal fixture proving: Resource ceiling ditetapkan dari measured co-resident ASUS Production + Research baseline, bukan spesifikasi CPU semata. Write `test_qa_03_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **QA-03-AC0**, `test_qa_03_valid_contract` — ASUS punya bukti capacity, isolation, workload co-residency dan recovery untuk Production Main + Research Runtime sebelum release/deployment. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| QA-03-AC1 | `test_qa_03_contract_1` | Disk-full tidak mengakui sukses |
| QA-03-AC2 | `test_qa_03_contract_2` | Worker kill tidak duplicate metrics |
| QA-03-AC3 | `test_qa_03_contract_3` | Resource ceiling ditetapkan dari measured co-resident ASUS Production + Research baseline, bukan spesifikasi CPU semata |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Disk-full tidak mengakui sukses. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Worker kill tidak duplicate metrics. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Resource ceiling ditetapkan dari measured co-resident ASUS Production + Research baseline, bukan spesifikasi CPU semata. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Network forbidden in ordinary tests; fake Telegram; temp DB only; explicit operator-owned integration environments.

Trust boundary assessment: no new public authentication surface; verified local input remains mandatory and existing secret/PII controls apply.

## Concurrency / Idempotency

Isolated test roots, injected clocks/seeds/probes; no cross-test singletons or shared real DB.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `QA-03` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Failure preserves artifacts/logs and exact SHA; release rollback proven before activation; no unstated skipped gate.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **QA-03-AC5** Capacity guards resolve each configured path to its actual mount and account for shared physical disk contention. Evidence: `test_qa_03_mount_capacity` and measured mount inventory; pending.

- [ ] **QA-03-AC4** Recorded ASUS mixed-load qualification includes stepped pair agent model counts and 24h soak with preregistered budgets. Evidence: `test_qa_03_capacity_4` plus applicable measured host artifact; not established by historical tests.

- [x] **QA-03-AC0** ASUS punya bukti capacity, isolation, workload co-residency dan recovery untuk Production Main + Research Runtime sebelum release/deployment. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [x] **QA-03-AC1** Disk-full tidak mengakui sukses. Evidence: mapped test, exact command/exit and target SHA.
- [x] **QA-03-AC2** Worker kill tidak duplicate metrics. Evidence: mapped test, exact command/exit and target SHA.
- [x] **QA-03-AC3** Resource ceiling ditetapkan dari measured co-resident ASUS Production + Research baseline, bukan spesifikasi CPU semata. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Disk-full tidak mengakui sukses. Inspect fixture and actual production path.
- Attempt to disprove: Worker kill tidak duplicate metrics. Inspect fixture and actual production path.
- Attempt to disprove: Resource ceiling ditetapkan dari measured co-resident ASUS Production + Research baseline, bukan spesifikasi CPU semata. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/qa-03-capacity-and-crash-recovery-qualification`. Commit: `feat(qa-03): capacity and crash recovery qualification` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/QA-03-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: REL-01. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement QA-03 only: Capacity and crash recovery qualification.
Read AGENTS.md, docs/sprints/verification/QA-03-capacity-and-crash-recovery-qualification.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: ASUS punya bukti capacity, isolation, workload co-residency dan recovery untuk Production Main + Research Runtime sebelum release/deployment.
Contract: current ASUS inventory + representative co-resident Production/Research workloads -> CPU/RAM/disk/latency/thermal/isolation/recovery evidence.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
