# DL-02 — Causal sequence datasets

## Metadata

Status: PLANNED

Priority: P1 | Type: data | Domain: deep-learning | Portfolio: EXTENSION

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/dl-02-causal-sequence-datasets`

Requirements: FR-13 | Legacy tasks: 28

External gates: Portfolio backlog activation by owner; not in default scheduler; Measured Lenovo resource admission; actual data eligibility evidence for research runs

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Window sequence tidak menyeberangi pair, gap, split atau target.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `DL-02` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: chronological feature windows + mask + sample ID -> sequence tensor with target outside input.

Direct consumers: D02-01

## Depends On

- DL-01 — Isolated resumable neural training

## Unlocks

D02-01

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/15-deep-learning-and-provenance.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`
- `docs/research/dataset-feature-contracts.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency DL-01 supplies: optional torch environment + recipe -> model/optimizer/scheduler/RNG checkpoint; non-DL import isolation.

## In Scope

- Window sequence tidak menyeberangi pair, gap, split atau target.
- Padding tidak menjadi harga nol nyata.
- Session gap memutus window.
- Target/future token tidak masuk input.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: D02-01.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `DL-02` dan dependency evidence yang valid, when owning component dijalankan, then window sequence tidak menyeberangi pair, gap, split atau target.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **DL-02-FR0:** Window sequence tidak menyeberangi pair, gap, split atau target.
1. **DL-02-FR1:** Padding tidak menjadi harga nol nyata.
2. **DL-02-FR2:** Session gap memutus window.
3. **DL-02-FR3:** Target/future token tidak masuk input.

## Domain Rules / Invariants

chronological feature windows + mask + sample ID -> sequence tensor with target outside input.

Sequence masks/session boundaries; <=12 configs, 50 epochs, patience 7; graph <=8; checkpoints include RNG.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/models/dl, graph, foundation`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

chronological feature windows + mask + sample ID -> sequence tensor with target outside input.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/models/dl/dataset.py`
- `tests/unit/lab/models/dl/test_sequence_dataset.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/15-deep-learning-and-provenance.md`; exact table schemas use the Required Reading dataset contract.

chronological feature windows + mask + sample ID -> sequence tensor with target outside input.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Sequence masks/session boundaries; <=12 configs, 50 epochs, patience 7; graph <=8; checkpoints include RNG.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish DL-02-AC0: Window sequence tidak menyeberangi pair, gap, split atau target. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `DL-02-AC1`, build minimal fixture proving: Padding tidak menjadi harga nol nyata. Write `test_dl_02_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `DL-02-AC2`, build minimal fixture proving: Session gap memutus window. Write `test_dl_02_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `DL-02-AC3`, build minimal fixture proving: Target/future token tidak masuk input. Write `test_dl_02_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **DL-02-AC0**, `test_dl_02_valid_contract` — Window sequence tidak menyeberangi pair, gap, split atau target. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| DL-02-AC1 | `test_dl_02_contract_1` | Padding tidak menjadi harga nol nyata |
| DL-02-AC2 | `test_dl_02_contract_2` | Session gap memutus window |
| DL-02-AC3 | `test_dl_02_contract_3` | Target/future token tidak masuk input |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Padding tidak menjadi harga nol nyata. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Session gap memutus window. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Target/future token tidak masuk input. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

External weights need checksum/license/cutoff. Unknown cutoff EXPLORATORY; no remote executable model code by default.

Trust boundary assessment: no new public authentication surface; verified local input remains mandatory and existing secret/PII controls apply.

## Concurrency / Idempotency

Separate optional environment; one GPU job; checkpoint resources on interruption; no torch imports in core path.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `DL-02` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Fail run on nonfinite loss; restore verified best validation checkpoint; no extra epochs to rescue HARD_FAIL.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **DL-02-AC0** Window sequence tidak menyeberangi pair, gap, split atau target. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **DL-02-AC1** Padding tidak menjadi harga nol nyata. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **DL-02-AC2** Session gap memutus window. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **DL-02-AC3** Target/future token tidak masuk input. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Padding tidak menjadi harga nol nyata. Inspect fixture and actual production path.
- Attempt to disprove: Session gap memutus window. Inspect fixture and actual production path.
- Attempt to disprove: Target/future token tidak masuk input. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/dl-02-causal-sequence-datasets`. Commit: `feat(dl-02): causal sequence datasets` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/DL-02-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: D02-01. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement DL-02 only: Causal sequence datasets.
Read AGENTS.md, docs/sprints/deep-learning/DL-02-causal-sequence-datasets.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Window sequence tidak menyeberangi pair, gap, split atau target.
Contract: chronological feature windows + mask + sample ID -> sequence tensor with target outside input.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
