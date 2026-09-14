# EVAL-03 — Sealed candidate lifecycle

## Metadata

Status: PLANNED

Priority: P0 | Type: safety | Domain: evaluation | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/eval-03-sealed-candidate-lifecycle`

Requirements: FR-09 | Legacy tasks: 21

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Promosi mengikuti freeze dan exposure audit sebelum gate berikutnya dibuka.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `EVAL-03` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: IDEA -> IMPLEMENTED -> BACKTESTED -> VALIDATED -> SEALED_PASS -> SHADOW -> CHAMPION; immutable transitions.

Direct consumers: ML-04, JOB-03, SHADOW-01, SHADOW-03, REPORT-01

## Depends On

- EVAL-02 — Hard gates and selection diagnostics
- SPLIT-01 — Sealed purged chronological folds

## Unlocks

ML-04, JOB-03, SHADOW-01, SHADOW-03, REPORT-01

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/11-evaluation-and-experiment-lifecycle.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency EVAL-02 supplies: metrics + policy + trial family -> INVALID_RUN/HARD_FAIL/NEAR_MISS/REGIME_EDGE/PASS, DSR/PBO when eligible.
- Dependency SPLIT-01 supplies: sample IDs + label_end_ts + declared exposure history -> versioned roles, purge and embargo manifest.

## In Scope

- Promosi mengikuti freeze dan exposure audit sebelum gate berikutnya dibuka.
- Config berubah setelah sealed menjadi challenger baru.
- Gate dibuka sekali dan dicatat.
- Invalid run tidak masuk ranking.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: ML-04, JOB-03, SHADOW-01, SHADOW-03, REPORT-01.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `EVAL-03` dan dependency evidence yang valid, when owning component dijalankan, then promosi mengikuti freeze dan exposure audit sebelum gate berikutnya dibuka.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **EVAL-03-FR0:** Promosi mengikuti freeze dan exposure audit sebelum gate berikutnya dibuka.
1. **EVAL-03-FR1:** Config berubah setelah sealed menjadi challenger baru.
2. **EVAL-03-FR2:** Gate dibuka sekali dan dicatat.
3. **EVAL-03-FR3:** Invalid run tidak masuk ranking.

## Domain Rules / Invariants

IDEA -> IMPLEMENTED -> BACKTESTED -> VALIDATED -> SEALED_PASS -> SHADOW -> CHAMPION; immutable transitions.

Record all trials, invalid runs, holdout exposures, policy decisions and parent versions; gate before leaderboard score.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/evaluation`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

IDEA -> IMPLEMENTED -> BACKTESTED -> VALIDATED -> SEALED_PASS -> SHADOW -> CHAMPION; immutable transitions.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/evaluation/lifecycle.py`
- `tests/unit/lab/evaluation/test_lifecycle.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/11-evaluation-and-experiment-lifecycle.md`; exact table schemas use the Required Reading dataset contract.

IDEA -> IMPLEMENTED -> BACKTESTED -> VALIDATED -> SEALED_PASS -> SHADOW -> CHAMPION; immutable transitions.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Record all trials, invalid runs, holdout exposures, policy decisions and parent versions; gate before leaderboard score.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish EVAL-03-AC0: Promosi mengikuti freeze dan exposure audit sebelum gate berikutnya dibuka. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `EVAL-03-AC1`, build minimal fixture proving: Config berubah setelah sealed menjadi challenger baru. Write `test_eval_03_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `EVAL-03-AC2`, build minimal fixture proving: Gate dibuka sekali dan dicatat. Write `test_eval_03_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `EVAL-03-AC3`, build minimal fixture proving: Invalid run tidak masuk ranking. Write `test_eval_03_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **EVAL-03-AC0**, `test_eval_03_valid_contract` — Promosi mengikuti freeze dan exposure audit sebelum gate berikutnya dibuka. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| EVAL-03-AC1 | `test_eval_03_contract_1` | Config berubah setelah sealed menjadi challenger baru |
| EVAL-03-AC2 | `test_eval_03_contract_2` | Gate dibuka sekali dan dicatat |
| EVAL-03-AC3 | `test_eval_03_contract_3` | Invalid run tidak masuk ranking |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Config berubah setelah sealed menjadi challenger baru. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Gate dibuka sekali dan dicatat. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Invalid run tidak masuk ranking. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Evaluator changes require independent policy review; agent cannot lower gate to pass its candidate.

Trust boundary assessment: untrusted provider/artifact input or privileged state mutation exists; require negative tests and redacted diagnostics.

## Concurrency / Idempotency

SQLite local transactions append lifecycle; unique run IDs and transitions; do not share WAL across network hosts.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `EVAL-03` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Technical invalidity can retry after root fix with cap; HARD_FAIL archive; tuning creates new challenger.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **EVAL-03-AC0** Promosi mengikuti freeze dan exposure audit sebelum gate berikutnya dibuka. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **EVAL-03-AC1** Config berubah setelah sealed menjadi challenger baru. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **EVAL-03-AC2** Gate dibuka sekali dan dicatat. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **EVAL-03-AC3** Invalid run tidak masuk ranking. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Config berubah setelah sealed menjadi challenger baru. Inspect fixture and actual production path.
- Attempt to disprove: Gate dibuka sekali dan dicatat. Inspect fixture and actual production path.
- Attempt to disprove: Invalid run tidak masuk ranking. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/eval-03-sealed-candidate-lifecycle`. Commit: `feat(eval-03): sealed candidate lifecycle` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/EVAL-03-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: ML-04, JOB-03, SHADOW-01, SHADOW-03, REPORT-01. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement EVAL-03 only: Sealed candidate lifecycle.
Read AGENTS.md, docs/sprints/evaluation/EVAL-03-sealed-candidate-lifecycle.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Promosi mengikuti freeze dan exposure audit sebelum gate berikutnya dibuka.
Contract: IDEA -> IMPLEMENTED -> BACKTESTED -> VALIDATED -> SEALED_PASS -> SHADOW -> CHAMPION; immutable transitions.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
