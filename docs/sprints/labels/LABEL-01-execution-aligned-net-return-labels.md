# LABEL-01 — Execution-aligned net return labels

## Metadata

Status: PLANNED

Priority: P0 | Type: data | Domain: labels | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/label-01-execution-aligned-net-return-labels`

Requirements: FR-07 | Legacy tasks: 16

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Target return mengukur net proceeds relatif terhadap gross cash debit dari execution model yang sama.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `LABEL-01` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: sample + horizon + fill model -> entry/exit, gross/net return, costs and label_available_at.

Direct consumers: LABEL-02

## Depends On

- FEAT-04 — Immutable feature materialization
- SIM-01 — Conservative execution simulator

## Unlocks

LABEL-02

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/09-labels-splits-and-training-data.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`
- `docs/research/dataset-feature-contracts.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency FEAT-04 supplies: snapshot IDs + registry hash -> features manifest, ordered columns, row_ready_at, eligibility.
- Dependency SIM-01 supplies: SignalIntent + market + schedule -> REJECTED/PARTIAL/FILLED; next-open, precision, SL_FIRST, latency.

## In Scope

- Target return mengukur net proceeds relatif terhadap gross cash debit dari execution model yang sama.
- Entry sebelum decision ditolak.
- Horizon tidak lengkap tidak menjadi label nol.
- Cost schedule atau fill unavailable menghasilkan excluded sample.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: LABEL-02.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `LABEL-01` dan dependency evidence yang valid, when owning component dijalankan, then target return mengukur net proceeds relatif terhadap gross cash debit dari execution model yang sama.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **LABEL-01-FR0:** Target return mengukur net proceeds relatif terhadap gross cash debit dari execution model yang sama.
1. **LABEL-01-FR1:** Entry sebelum decision ditolak.
2. **LABEL-01-FR2:** Horizon tidak lengkap tidak menjadi label nol.
3. **LABEL-01-FR3:** Cost schedule atau fill unavailable menghasilkan excluded sample.

## Domain Rules / Invariants

sample + horizon + fill model -> entry/exit, gross/net return, costs and label_available_at.

Store label_end_ts, entry/exit, cost/execution IDs; assignment table per sample; purge overlaps and embargo.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/labels, cli/build_training_dataset.py`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

sample + horizon + fill model -> entry/exit, gross/net return, costs and label_available_at.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/labels/returns.py`
- `configs/labels/net_return_v1.yaml`
- `tests/unit/lab/labels/test_returns.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/09-labels-splits-and-training-data.md`; exact table schemas use the Required Reading dataset contract.

sample + horizon + fill model -> entry/exit, gross/net return, costs and label_available_at.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Store label_end_ts, entry/exit, cost/execution IDs; assignment table per sample; purge overlaps and embargo.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish LABEL-01-AC0: Target return mengukur net proceeds relatif terhadap gross cash debit dari execution model yang sama. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `LABEL-01-AC1`, build minimal fixture proving: Entry sebelum decision ditolak. Write `test_label_01_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `LABEL-01-AC2`, build minimal fixture proving: Horizon tidak lengkap tidak menjadi label nol. Write `test_label_01_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `LABEL-01-AC3`, build minimal fixture proving: Cost schedule atau fill unavailable menghasilkan excluded sample. Write `test_label_01_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **LABEL-01-AC0**, `test_label_01_valid_contract` — Target return mengukur net proceeds relatif terhadap gross cash debit dari execution model yang sama. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| LABEL-01-AC1 | `test_label_01_contract_1` | Entry sebelum decision ditolak |
| LABEL-01-AC2 | `test_label_01_contract_2` | Horizon tidak lengkap tidak menjadi label nol |
| LABEL-01-AC3 | `test_label_01_contract_3` | Cost schedule atau fill unavailable menghasilkan excluded sample |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Entry sebelum decision ditolak. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Horizon tidak lengkap tidak menjadi label nol. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Cost schedule atau fill unavailable menghasilkan excluded sample. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Sealed data access logged; user-facing report must not expose sealed metrics before approved gate.

Trust boundary assessment: untrusted provider/artifact input or privileged state mutation exists; require negative tests and redacted diagnostics.

## Concurrency / Idempotency

Immutable sample IDs; duplicate joins rejected; split table created once for registered version.

## Performance Constraints

Pure/rolling feature workloads: process sorted pair partitions with bounded context, avoid full cross product of timestamps × all raw events. Measure scaling against row/window count and validate chunk-boundary equality.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `LABEL-01` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Changed horizon/target/cost creates new materialization; exposed holdout cannot become sealed again.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **LABEL-01-AC0** Target return mengukur net proceeds relatif terhadap gross cash debit dari execution model yang sama. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **LABEL-01-AC1** Entry sebelum decision ditolak. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **LABEL-01-AC2** Horizon tidak lengkap tidak menjadi label nol. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **LABEL-01-AC3** Cost schedule atau fill unavailable menghasilkan excluded sample. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Entry sebelum decision ditolak. Inspect fixture and actual production path.
- Attempt to disprove: Horizon tidak lengkap tidak menjadi label nol. Inspect fixture and actual production path.
- Attempt to disprove: Cost schedule atau fill unavailable menghasilkan excluded sample. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/label-01-execution-aligned-net-return-labels`. Commit: `feat(label-01): execution-aligned net return labels` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/LABEL-01-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: LABEL-02. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement LABEL-01 only: Execution-aligned net return labels.
Read AGENTS.md, docs/sprints/labels/LABEL-01-execution-aligned-net-return-labels.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Target return mengukur net proceeds relatif terhadap gross cash debit dari execution model yang sama.
Contract: sample + horizon + fill model -> entry/exit, gross/net return, costs and label_available_at.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
