# LABEL-02 — Triple barrier outcomes

## Metadata

Status: REVIEW

Priority: P0 | Type: data | Domain: labels | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/label-02-triple-barrier-outcomes`

Requirements: FR-07 | Legacy tasks: 16

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Outcome upper/lower/vertical barrier mulai dari entry dan menyimpan akhir overlap.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `LABEL-02` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: entry + decision-time volatility + barrier config -> first_touch, label_end_ts, MAE/MFE, concurrency weight.

Direct consumers: SPLIT-01, D03-01

## Depends On

- LABEL-01 — Execution-aligned net return labels

## Unlocks

D03-01, SPLIT-01

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/09-labels-splits-and-training-data.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`
- `docs/research/dataset-feature-contracts.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency LABEL-01 supplies: sample + horizon + fill model -> entry/exit, gross/net return, costs and label_available_at.

## In Scope

- Outcome upper/lower/vertical barrier mulai dari entry dan menyimpan akhir overlap.
- Dua barrier dalam candle sama memilih lower.
- Volatilitas masa depan tidak menggeser barrier.
- Missing exit data menghasilkan censored/excluded status.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: SPLIT-01, D03-01.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `LABEL-02` dan dependency evidence yang valid, when owning component dijalankan, then outcome upper/lower/vertical barrier mulai dari entry dan menyimpan akhir overlap.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **LABEL-02-FR0:** Outcome upper/lower/vertical barrier mulai dari entry dan menyimpan akhir overlap.
1. **LABEL-02-FR1:** Dua barrier dalam candle sama memilih lower.
2. **LABEL-02-FR2:** Volatilitas masa depan tidak menggeser barrier.
3. **LABEL-02-FR3:** Missing exit data menghasilkan censored/excluded status.

## Domain Rules / Invariants

entry + decision-time volatility + barrier config -> first_touch, label_end_ts, MAE/MFE, concurrency weight.

Store label_end_ts, entry/exit, cost/execution IDs; assignment table per sample; purge overlaps and embargo.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/labels, cli/build_training_dataset.py`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

entry + decision-time volatility + barrier config -> first_touch, label_end_ts, MAE/MFE, concurrency weight.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/labels/triple_barrier.py`
- `configs/labels/triple_barrier_v1.yaml`
- `tests/unit/lab/labels/test_triple_barrier.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/09-labels-splits-and-training-data.md`; exact table schemas use the Required Reading dataset contract.

entry + decision-time volatility + barrier config -> first_touch, label_end_ts, MAE/MFE, concurrency weight.

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

First establish LABEL-02-AC0: Outcome upper/lower/vertical barrier mulai dari entry dan menyimpan akhir overlap. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `LABEL-02-AC1`, build minimal fixture proving: Dua barrier dalam candle sama memilih lower. Write `test_label_02_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `LABEL-02-AC2`, build minimal fixture proving: Volatilitas masa depan tidak menggeser barrier. Write `test_label_02_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `LABEL-02-AC3`, build minimal fixture proving: Missing exit data menghasilkan censored/excluded status. Write `test_label_02_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **LABEL-02-AC0**, `test_label_02_valid_contract` — Outcome upper/lower/vertical barrier mulai dari entry dan menyimpan akhir overlap. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| LABEL-02-AC1 | `test_label_02_contract_1` | Dua barrier dalam candle sama memilih lower |
| LABEL-02-AC2 | `test_label_02_contract_2` | Volatilitas masa depan tidak menggeser barrier |
| LABEL-02-AC3 | `test_label_02_contract_3` | Missing exit data menghasilkan censored/excluded status |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Dua barrier dalam candle sama memilih lower. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Volatilitas masa depan tidak menggeser barrier. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Missing exit data menghasilkan censored/excluded status. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
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

Emit `LABEL-02` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Changed horizon/target/cost creates new materialization; exposed holdout cannot become sealed again.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **LABEL-02-AC0** Outcome upper/lower/vertical barrier mulai dari entry dan menyimpan akhir overlap. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **LABEL-02-AC1** Dua barrier dalam candle sama memilih lower. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **LABEL-02-AC2** Volatilitas masa depan tidak menggeser barrier. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **LABEL-02-AC3** Missing exit data menghasilkan censored/excluded status. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Dua barrier dalam candle sama memilih lower. Inspect fixture and actual production path.
- Attempt to disprove: Volatilitas masa depan tidak menggeser barrier. Inspect fixture and actual production path.
- Attempt to disprove: Missing exit data menghasilkan censored/excluded status. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/label-02-triple-barrier-outcomes`. Commit: `feat(label-02): triple barrier outcomes` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/LABEL-02-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: SPLIT-01, D03-01. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement LABEL-02 only: Triple barrier outcomes.
Read AGENTS.md, docs/sprints/labels/LABEL-02-triple-barrier-outcomes.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Outcome upper/lower/vertical barrier mulai dari entry dan menyimpan akhir overlap.
Contract: entry + decision-time volatility + barrier config -> first_touch, label_end_ts, MAE/MFE, concurrency weight.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
