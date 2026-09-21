# EVAL-02 — Hard gates and selection diagnostics

## Metadata

Status: REVIEW

Priority: P0 | Type: research | Domain: evaluation | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/eval-02-hard-gates-and-selection-diagnostics`

Requirements: FR-09 | Legacy tasks: 21

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Evaluator memisahkan validitas run dari kualitas strategi dengan gate versioned.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `EVAL-02` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: metrics + policy + trial family -> INVALID_RUN/HARD_FAIL/NEAR_MISS/REGIME_EDGE/PASS, DSR/PBO when eligible.

Direct consumers: EVAL-03

## Depends On

- EVAL-01 — Immutable experiment registry

## Unlocks

EVAL-03

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/11-evaluation-and-experiment-lifecycle.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency EVAL-01 supplies: run_id + parent + git SHA + environment/data/config/cost/execution hashes -> immutable run record.

## In Scope

- Evaluator memisahkan validitas run dari kualitas strategi dengan gate versioned.
- Score tinggi tidak menutupi cost unknown.
- Sample kecil menghasilkan insufficient evidence.
- Best seed tidak dipilih sebagai hasil finalist.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: EVAL-03.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `EVAL-02` dan dependency evidence yang valid, when owning component dijalankan, then evaluator memisahkan validitas run dari kualitas strategi dengan gate versioned.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **EVAL-02-FR0:** Evaluator memisahkan validitas run dari kualitas strategi dengan gate versioned.
1. **EVAL-02-FR1:** Score tinggi tidak menutupi cost unknown.
2. **EVAL-02-FR2:** Sample kecil menghasilkan insufficient evidence.
3. **EVAL-02-FR3:** Best seed tidak dipilih sebagai hasil finalist.

## Domain Rules / Invariants

metrics + policy + trial family -> INVALID_RUN/HARD_FAIL/NEAR_MISS/REGIME_EDGE/PASS, DSR/PBO when eligible.

Record all trials, invalid runs, holdout exposures, policy decisions and parent versions; gate before leaderboard score.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/evaluation`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

metrics + policy + trial family -> INVALID_RUN/HARD_FAIL/NEAR_MISS/REGIME_EDGE/PASS, DSR/PBO when eligible.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/evaluation/gates.py`
- `src/indodax_lab/evaluation/statistics.py`
- `tests/unit/lab/evaluation/test_gates.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/11-evaluation-and-experiment-lifecycle.md`; exact table schemas use the Required Reading dataset contract.

metrics + policy + trial family -> INVALID_RUN/HARD_FAIL/NEAR_MISS/REGIME_EDGE/PASS, DSR/PBO when eligible.

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

First establish EVAL-02-AC0: Evaluator memisahkan validitas run dari kualitas strategi dengan gate versioned. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `EVAL-02-AC1`, build minimal fixture proving: Score tinggi tidak menutupi cost unknown. Write `test_eval_02_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `EVAL-02-AC2`, build minimal fixture proving: Sample kecil menghasilkan insufficient evidence. Write `test_eval_02_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `EVAL-02-AC3`, build minimal fixture proving: Best seed tidak dipilih sebagai hasil finalist. Write `test_eval_02_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **EVAL-02-AC0**, `test_eval_02_valid_contract` — Evaluator memisahkan validitas run dari kualitas strategi dengan gate versioned. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| EVAL-02-AC1 | `test_eval_02_contract_1` | Score tinggi tidak menutupi cost unknown |
| EVAL-02-AC2 | `test_eval_02_contract_2` | Sample kecil menghasilkan insufficient evidence |
| EVAL-02-AC3 | `test_eval_02_contract_3` | Best seed tidak dipilih sebagai hasil finalist |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Score tinggi tidak menutupi cost unknown. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Sample kecil menghasilkan insufficient evidence. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Best seed tidak dipilih sebagai hasil finalist. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
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

Emit `EVAL-02` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Technical invalidity can retry after root fix with cap; HARD_FAIL archive; tuning creates new challenger.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **EVAL-02-AC0** Evaluator memisahkan validitas run dari kualitas strategi dengan gate versioned. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **EVAL-02-AC1** Score tinggi tidak menutupi cost unknown. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **EVAL-02-AC2** Sample kecil menghasilkan insufficient evidence. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **EVAL-02-AC3** Best seed tidak dipilih sebagai hasil finalist. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Score tinggi tidak menutupi cost unknown. Inspect fixture and actual production path.
- Attempt to disprove: Sample kecil menghasilkan insufficient evidence. Inspect fixture and actual production path.
- Attempt to disprove: Best seed tidak dipilih sebagai hasil finalist. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/eval-02-hard-gates-and-selection-diagnostics`. Commit: `feat(eval-02): hard gates and selection diagnostics` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/EVAL-02-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: EVAL-03. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement EVAL-02 only: Hard gates and selection diagnostics.
Read AGENTS.md, docs/sprints/evaluation/EVAL-02-hard-gates-and-selection-diagnostics.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Evaluator memisahkan validitas run dari kualitas strategi dengan gate versioned.
Contract: metrics + policy + trial family -> INVALID_RUN/HARD_FAIL/NEAR_MISS/REGIME_EDGE/PASS, DSR/PBO when eligible.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
