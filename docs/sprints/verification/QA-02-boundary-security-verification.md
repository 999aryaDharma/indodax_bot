# QA-02 — Boundary security verification

## Metadata

Status: REVIEW

Priority: P0 | Type: security | Domain: verification | Portfolio: CORE

Implementation Owner: Antigravity | Independent Reviewer: UNASSIGNED (pending independent review)

Recommended Branch: `feat/qa-02-boundary-security-verification`

Requirements: FR-18 | Legacy tasks: 35

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Audit membuktikan akses secret, artifact loader dan destructive paths tertutup pada release candidate.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `QA-02` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: threat model + attack fixtures -> findings with severity and reproducible evidence.

Direct consumers: REL-01

## Depends On

- REPORT-02 — Read-only Telegram research status
- AGENT-01 — Governed research curator
- OPS-02 — Snapshot transfer and restore

## Unlocks

REL-01

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency REPORT-02 supplies: allowlisted chat -> status/history/report; bounded messages and deterministic error states.
- Dependency AGENT-01 supplies: report + hypothesis -> change request + bounded candidate branch; no automatic merge or evaluator edits.
- Dependency OPS-02 supplies: manifest + checksums + SQLite consistent backup -> staged copy -> verify -> atomic publish.

## In Scope

- Audit membuktikan akses secret, artifact loader dan destructive paths tertutup pada release candidate.
- Traversal dan malicious artifact ditolak.
- Tidak ada trade-withdraw credentials.
- Allowlist Telegram ditegakkan.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: REL-01.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `QA-02` dan dependency evidence yang valid, when owning component dijalankan, then audit membuktikan akses secret, artifact loader dan destructive paths tertutup pada release candidate.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **QA-02-FR0:** Audit membuktikan akses secret, artifact loader dan destructive paths tertutup pada release candidate.
1. **QA-02-FR1:** Traversal dan malicious artifact ditolak.
2. **QA-02-FR2:** Tidak ada trade-withdraw credentials.
3. **QA-02-FR3:** Allowlist Telegram ditegakkan.

## Domain Rules / Invariants

threat model + attack fixtures -> findings with severity and reproducible evidence.

Feature tests embedded in every sprint; checkpoint is integration of production interfaces not synthetic ID matching.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `tests, docs/quality`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

threat model + attack fixtures -> findings with severity and reproducible evidence.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `tests/security/test_lab_boundaries.py`
- `docs/quality/security-evidence.md`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/20-testing-strategy.md`; exact table schemas use the Required Reading dataset contract.

threat model + attack fixtures -> findings with severity and reproducible evidence.

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

First establish QA-02-AC0: Audit membuktikan akses secret, artifact loader dan destructive paths tertutup pada release candidate. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `QA-02-AC1`, build minimal fixture proving: Traversal dan malicious artifact ditolak. Write `test_qa_02_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `QA-02-AC2`, build minimal fixture proving: Tidak ada trade-withdraw credentials. Write `test_qa_02_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `QA-02-AC3`, build minimal fixture proving: Allowlist Telegram ditegakkan. Write `test_qa_02_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **QA-02-AC0**, `test_qa_02_valid_contract` — Audit membuktikan akses secret, artifact loader dan destructive paths tertutup pada release candidate. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| QA-02-AC1 | `test_qa_02_contract_1` | Traversal dan malicious artifact ditolak |
| QA-02-AC2 | `test_qa_02_contract_2` | Tidak ada trade-withdraw credentials |
| QA-02-AC3 | `test_qa_02_contract_3` | Allowlist Telegram ditegakkan |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Traversal dan malicious artifact ditolak. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Tidak ada trade-withdraw credentials. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Allowlist Telegram ditegakkan. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
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

Emit `QA-02` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Failure preserves artifacts/logs and exact SHA; release rollback proven before activation; no unstated skipped gate.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [x] **QA-02-AC0** Audit membuktikan akses secret, artifact loader dan destructive paths tertutup pada release candidate. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [x] **QA-02-AC1** Traversal dan malicious artifact ditolak. Evidence: mapped test, exact command/exit and target SHA.
- [x] **QA-02-AC2** Tidak ada trade-withdraw credentials. Evidence: mapped test, exact command/exit and target SHA.
- [x] **QA-02-AC3** Allowlist Telegram ditegakkan. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Traversal dan malicious artifact ditolak. Inspect fixture and actual production path.
- Attempt to disprove: Tidak ada trade-withdraw credentials. Inspect fixture and actual production path.
- Attempt to disprove: Allowlist Telegram ditegakkan. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/qa-02-boundary-security-verification`. Commit: `feat(qa-02): boundary security verification` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/QA-02-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: REL-01. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement QA-02 only: Boundary security verification.
Read AGENTS.md, docs/sprints/verification/QA-02-boundary-security-verification.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Audit membuktikan akses secret, artifact loader dan destructive paths tertutup pada release candidate.
Contract: threat model + attack fixtures -> findings with severity and reproducible evidence.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
