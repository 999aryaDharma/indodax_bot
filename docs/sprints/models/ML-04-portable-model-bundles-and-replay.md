# ML-04 — Portable model bundles and replay

## Metadata

Status: PLANNED

Priority: P0 | Type: integration | Domain: models | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/ml-04-portable-model-bundles-and-replay`

Requirements: FR-10 | Legacy tasks: 23

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Trainer mempublikasikan bundle lengkap yang bisa diload ulang dan diuji inference identik.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `ML-04` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: model + preprocessor + calibrator + thresholds + hashes + feature order -> verified bundle, replay forecast.

Direct consumers: JOB-03, SHADOW-01, QA-01, M03-01, M04-01, M05-01, M06-01

## Depends On

- M01-01 — Calibrated logistic baseline
- M02-01 — XGBoost challenger
- EVAL-03 — Sealed candidate lifecycle

## Unlocks

JOB-03, SHADOW-01, QA-01, M03-01, M04-01, M05-01, M06-01, M07-01

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/12-tabular-models-and-training.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`
- `docs/research/dataset-feature-contracts.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency M01-01 supplies: Logistic elastic-net solver-compatible config -> fitted preprocessor/model/calibrator bundle.
- Dependency M02-01 supplies: Versioned tree search + early stopping -> best iteration and frozen artifact.
- Dependency EVAL-03 supplies: IDEA -> IMPLEMENTED -> BACKTESTED -> VALIDATED -> SEALED_PASS -> SHADOW -> CHAMPION; immutable transitions.

## In Scope

- Trainer mempublikasikan bundle lengkap yang bisa diload ulang dan diuji inference identik.
- Checksum weights mismatch menolak load.
- Missing calibration metadata memblokir.
- Reload memberi prediksi ekuivalen pada fixture.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: JOB-03, SHADOW-01, QA-01, M03-01, M04-01, M05-01, M06-01.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `ML-04` dan dependency evidence yang valid, when owning component dijalankan, then trainer mempublikasikan bundle lengkap yang bisa diload ulang dan diuji inference identik.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **ML-04-FR0:** Trainer mempublikasikan bundle lengkap yang bisa diload ulang dan diuji inference identik.
1. **ML-04-FR1:** Checksum weights mismatch menolak load.
2. **ML-04-FR2:** Missing calibration metadata memblokir.
3. **ML-04-FR3:** Reload memberi prediksi ekuivalen pada fixture.

## Domain Rules / Invariants

model + preprocessor + calibrator + thresholds + hashes + feature order -> verified bundle, replay forecast.

Train-only preprocessing; held-out calibration; bundle all fitted transforms, features, hashes and thresholds.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/models`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

model + preprocessor + calibrator + thresholds + hashes + feature order -> verified bundle, replay forecast.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/models/artifacts.py`
- `src/indodax_lab/models/trainer.py`
- `src/indodax_lab/cli/train_model.py`
- `tests/integration/lab/test_ml_walk_forward.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/12-tabular-models-and-training.md`; exact table schemas use the Required Reading dataset contract.

model + preprocessor + calibrator + thresholds + hashes + feature order -> verified bundle, replay forecast.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Train-only preprocessing; held-out calibration; bundle all fitted transforms, features, hashes and thresholds.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish ML-04-AC0: Trainer mempublikasikan bundle lengkap yang bisa diload ulang dan diuji inference identik. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `ML-04-AC1`, build minimal fixture proving: Checksum weights mismatch menolak load. Write `test_ml_04_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `ML-04-AC2`, build minimal fixture proving: Missing calibration metadata memblokir. Write `test_ml_04_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `ML-04-AC3`, build minimal fixture proving: Reload memberi prediksi ekuivalen pada fixture. Write `test_ml_04_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **ML-04-AC0**, `test_ml_04_valid_contract` — Trainer mempublikasikan bundle lengkap yang bisa diload ulang dan diuji inference identik. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| ML-04-AC1 | `test_ml_04_contract_1` | Checksum weights mismatch menolak load |
| ML-04-AC2 | `test_ml_04_contract_2` | Missing calibration metadata memblokir |
| ML-04-AC3 | `test_ml_04_contract_3` | Reload memberi prediksi ekuivalen pada fixture |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Checksum weights mismatch menolak load. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Missing calibration metadata memblokir. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Reload memberi prediksi ekuivalen pada fixture. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Load verified local artifacts only; pickle is executable input, never deserialize arbitrary uploads. No sealed tuning.

Trust boundary assessment: no new public authentication surface; verified local input remains mandatory and existing secret/PII controls apply.

## Concurrency / Idempotency

Per-run isolated output and seed; no shared mutable fitted transformer; budget consumed even by failed trials.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `ML-04` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Resume only identical recipe/data hashes; best validation checkpoint, never best test seed.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **ML-04-AC0** Trainer mempublikasikan bundle lengkap yang bisa diload ulang dan diuji inference identik. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **ML-04-AC1** Checksum weights mismatch menolak load. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **ML-04-AC2** Missing calibration metadata memblokir. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **ML-04-AC3** Reload memberi prediksi ekuivalen pada fixture. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Checksum weights mismatch menolak load. Inspect fixture and actual production path.
- Attempt to disprove: Missing calibration metadata memblokir. Inspect fixture and actual production path.
- Attempt to disprove: Reload memberi prediksi ekuivalen pada fixture. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/ml-04-portable-model-bundles-and-replay`. Commit: `feat(ml-04): portable model bundles and replay` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/ML-04-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: JOB-03, SHADOW-01, QA-01, M03-01, M04-01, M05-01, M06-01. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement ML-04 only: Portable model bundles and replay.
Read AGENTS.md, docs/sprints/models/ML-04-portable-model-bundles-and-replay.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Trainer mempublikasikan bundle lengkap yang bisa diload ulang dan diuji inference identik.
Contract: model + preprocessor + calibrator + thresholds + hashes + feature order -> verified bundle, replay forecast.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
