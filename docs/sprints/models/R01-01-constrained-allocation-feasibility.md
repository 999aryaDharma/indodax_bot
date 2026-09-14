# R01-01 — Constrained allocation feasibility

## Metadata

Status: REVIEW

Priority: P2 | Type: spike | Domain: models | Portfolio: EXPERIMENTAL

Implementation Owner: Antigravity | Independent Reviewer: UNASSIGNED (pending independent review)

Recommended Branch: `feat/r01-01-constrained-allocation-feasibility`

Requirements: FR-10 | Legacy tasks: Catalog extension / operational gap identified in audit

External gates: Portfolio backlog activation by owner; not in default scheduler

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Spike menilai apakah RL layak diteruskan dengan reward bersih biaya dan constraints modal.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `R01-01` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: Offline simulator + fixed allocation baselines -> feasibility report, no scheduler default and no promotion.

Direct consumers: Release or owner-reviewed research comparison; no required downstream implementation.

## Depends On

- QA-01 — Wave 1 tournament checkpoint
- SHADOW-02 — Shared capital reconciliation

## Unlocks

No mandatory dependent sprint.

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/12-tabular-models-and-training.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`
- `docs/research/dataset-feature-contracts.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency QA-01 supplies: tiny offline tournament -> all lifecycle outcomes + identical snapshot/folds/costs comparison.
- Dependency SHADOW-02 supplies: durable event IDs + risk policy -> reconciled postings, independent vs shared reports.

## In Scope

- Spike menilai apakah RL layak diteruskan dengan reward bersih biaya dan constraints modal.
- Reward hack diuji melalui turnover dan cash.
- Same budget versus inverse-vol baseline.
- Tidak ada order live atau policy export otomatis.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: track riset atau release lain.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `R01-01` dan dependency evidence yang valid, when owning component dijalankan, then spike menilai apakah RL layak diteruskan dengan reward bersih biaya dan constraints modal.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **R01-01-FR0:** Spike menilai apakah RL layak diteruskan dengan reward bersih biaya dan constraints modal.
1. **R01-01-FR1:** Reward hack diuji melalui turnover dan cash.
2. **R01-01-FR2:** Same budget versus inverse-vol baseline.
3. **R01-01-FR3:** Tidak ada order live atau policy export otomatis.

## Domain Rules / Invariants

Offline simulator + fixed allocation baselines -> feasibility report, no scheduler default and no promotion.

Train-only preprocessing; held-out calibration; bundle all fitted transforms, features, hashes and thresholds.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/models`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

Offline simulator + fixed allocation baselines -> feasibility report, no scheduler default and no promotion.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `docs/research/rl-feasibility.md`
- `tests/research/test_rl_reward_contract.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/12-tabular-models-and-training.md`; exact table schemas use the Required Reading dataset contract.

Offline simulator + fixed allocation baselines -> feasibility report, no scheduler default and no promotion.

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

First establish R01-01-AC0: Spike menilai apakah RL layak diteruskan dengan reward bersih biaya dan constraints modal. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `R01-01-AC1`, build minimal fixture proving: Reward hack diuji melalui turnover dan cash. Write `test_r01_01_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `R01-01-AC2`, build minimal fixture proving: Same budget versus inverse-vol baseline. Write `test_r01_01_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `R01-01-AC3`, build minimal fixture proving: Tidak ada order live atau policy export otomatis. Write `test_r01_01_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **R01-01-AC0**, `test_r01_01_valid_contract` — Spike menilai apakah RL layak diteruskan dengan reward bersih biaya dan constraints modal. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| R01-01-AC1 | `test_r01_01_contract_1` | Reward hack diuji melalui turnover dan cash |
| R01-01-AC2 | `test_r01_01_contract_2` | Same budget versus inverse-vol baseline |
| R01-01-AC3 | `test_r01_01_contract_3` | Tidak ada order live atau policy export otomatis |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Reward hack diuji melalui turnover dan cash. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Same budget versus inverse-vol baseline. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Tidak ada order live atau policy export otomatis. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
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

Emit `R01-01` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Resume only identical recipe/data hashes; best validation checkpoint, never best test seed.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [x] **R01-01-AC0** Spike menilai apakah RL layak diteruskan dengan reward bersih biaya dan constraints modal. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [x] **R01-01-AC1** Reward hack diuji melalui turnover dan cash. Evidence: mapped test, exact command/exit and target SHA.
- [x] **R01-01-AC2** Same budget versus inverse-vol baseline. Evidence: mapped test, exact command/exit and target SHA.
- [x] **R01-01-AC3** Tidak ada order live atau policy export otomatis. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Reward hack diuji melalui turnover dan cash. Inspect fixture and actual production path.
- Attempt to disprove: Same budget versus inverse-vol baseline. Inspect fixture and actual production path.
- Attempt to disprove: Tidak ada order live atau policy export otomatis. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/r01-01-constrained-allocation-feasibility`. Commit: `feat(r01-01): constrained allocation feasibility` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/R01-01-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: none required. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement R01-01 only: Constrained allocation feasibility.
Read AGENTS.md, docs/sprints/models/R01-01-constrained-allocation-feasibility.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Spike menilai apakah RL layak diteruskan dengan reward bersih biaya dan constraints modal.
Contract: Offline simulator + fixed allocation baselines -> feasibility report, no scheduler default and no promotion.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
