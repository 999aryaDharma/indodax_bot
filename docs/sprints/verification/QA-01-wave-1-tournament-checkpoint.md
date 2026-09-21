# QA-01 — Wave 1 tournament checkpoint

## Metadata

Status: REVIEW

Priority: P0 | Type: quality | Domain: verification | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/qa-01-wave-1-tournament-checkpoint`

Requirements: FR-18 | Legacy tasks: 27

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Turnamen kecil menyatukan baseline classical ML dan follow-up jobs dengan hasil deterministik.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `QA-01` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: tiny offline tournament -> all lifecycle outcomes + identical snapshot/folds/costs comparison.

Direct consumers: DL-01, R01-01, QA-03, REL-01

## Depends On

- JOB-03 — Evaluator-controlled research DAG
- SHADOW-02 — Shared capital reconciliation
- C01-01 — Donchian breakout
- C02-01 — EMA pullback
- C03-01 — Time series momentum
- C04-01 — Cross sectional momentum
- C07-01 — Bollinger RSI reversion
- C10-01 — Regime ensemble
- S01-01 — Liquidity screened breakout
- S02-01 — Squeeze expansion
- ML-04 — Portable model bundles and replay

## Unlocks

DL-01, R01-01, QA-03, REL-01

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency JOB-03 supplies: cadence window + snapshot + recipe -> idempotent DAG jobs with dependency states.
- Dependency SHADOW-02 supplies: durable event IDs + risk policy -> reconciled postings, independent vs shared reports.
- Dependency C01-01 supplies: Previous N-bar high breakout with volume gate; ATR stop -> versioned LONG/FLAT intent, never direct orders.
- Dependency C02-01 supplies: Long EMA regime plus short EMA pullback and recovery -> versioned LONG/FLAT intent, never direct orders.
- Dependency C03-01 supplies: Positive lookback return with volatility target and cash fallback -> versioned LONG/FLAT intent, never direct orders.
- Dependency C04-01 supplies: PIT rank return top-K with liquidity and stable tie break -> versioned LONG/FLAT intent, never direct orders.
- Dependency C07-01 supplies: Extreme BB and RSI deviation only under available sideways regime -> versioned LONG/FLAT intent, never direct orders.
- Dependency C10-01 supplies: Deterministic trend/reversion switch using available regime and frozen members -> versioned LONG/FLAT intent, never direct orders.
- Dependency S01-01 supplies: Breakout with spread/depth gate relative to simulated size -> versioned LONG/FLAT intent, never direct orders.
- Dependency S02-01 supplies: BB/Keltner squeeze followed by volume expansion and no-chase cap -> versioned LONG/FLAT intent, never direct orders.
- Dependency ML-04 supplies: model + preprocessor + calibrator + thresholds + hashes + feature order -> verified bundle, replay forecast.

## In Scope

- Turnamen kecil menyatukan baseline classical ML dan follow-up jobs dengan hasil deterministik.
- Fixture mencakup INVALID_RUN HARD_FAIL NEAR_MISS PASS.
- Jadwal tindak lanjut sesuai outcome.
- Tiny CI bukan bukti real-market profitability.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: DL-01, R01-01, QA-03, REL-01.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `QA-01` dan dependency evidence yang valid, when owning component dijalankan, then turnamen kecil menyatukan baseline classical ML dan follow-up jobs dengan hasil deterministik.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **QA-01-FR0:** Turnamen kecil menyatukan baseline classical ML dan follow-up jobs dengan hasil deterministik.
1. **QA-01-FR1:** Fixture mencakup INVALID_RUN HARD_FAIL NEAR_MISS PASS.
2. **QA-01-FR2:** Jadwal tindak lanjut sesuai outcome.
3. **QA-01-FR3:** Tiny CI bukan bukti real-market profitability.

## Domain Rules / Invariants

tiny offline tournament -> all lifecycle outcomes + identical snapshot/folds/costs comparison.

Feature tests embedded in every sprint; checkpoint is integration of production interfaces not synthetic ID matching.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `tests, docs/quality`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

tiny offline tournament -> all lifecycle outcomes + identical snapshot/folds/costs comparison.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `tests/regression/test_wave1_tournament.py`
- `docs/research/phase2-tournament-verification.md`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/20-testing-strategy.md`; exact table schemas use the Required Reading dataset contract.

tiny offline tournament -> all lifecycle outcomes + identical snapshot/folds/costs comparison.

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

First establish QA-01-AC0: Turnamen kecil menyatukan baseline classical ML dan follow-up jobs dengan hasil deterministik. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `QA-01-AC1`, build minimal fixture proving: Fixture mencakup INVALID_RUN HARD_FAIL NEAR_MISS PASS. Write `test_qa_01_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `QA-01-AC2`, build minimal fixture proving: Jadwal tindak lanjut sesuai outcome. Write `test_qa_01_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `QA-01-AC3`, build minimal fixture proving: Tiny CI bukan bukti real-market profitability. Write `test_qa_01_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **QA-01-AC0**, `test_qa_01_valid_contract` — Turnamen kecil menyatukan baseline classical ML dan follow-up jobs dengan hasil deterministik. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| QA-01-AC1 | `test_qa_01_contract_1` | Fixture mencakup INVALID_RUN HARD_FAIL NEAR_MISS PASS |
| QA-01-AC2 | `test_qa_01_contract_2` | Jadwal tindak lanjut sesuai outcome |
| QA-01-AC3 | `test_qa_01_contract_3` | Tiny CI bukan bukti real-market profitability |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Fixture mencakup INVALID_RUN HARD_FAIL NEAR_MISS PASS. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Jadwal tindak lanjut sesuai outcome. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Tiny CI bukan bukti real-market profitability. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
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

Emit `QA-01` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Failure preserves artifacts/logs and exact SHA; release rollback proven before activation; no unstated skipped gate.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **QA-01-AC0** Turnamen kecil menyatukan baseline classical ML dan follow-up jobs dengan hasil deterministik. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **QA-01-AC1** Fixture mencakup INVALID_RUN HARD_FAIL NEAR_MISS PASS. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **QA-01-AC2** Jadwal tindak lanjut sesuai outcome. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **QA-01-AC3** Tiny CI bukan bukti real-market profitability. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Fixture mencakup INVALID_RUN HARD_FAIL NEAR_MISS PASS. Inspect fixture and actual production path.
- Attempt to disprove: Jadwal tindak lanjut sesuai outcome. Inspect fixture and actual production path.
- Attempt to disprove: Tiny CI bukan bukti real-market profitability. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/qa-01-wave-1-tournament-checkpoint`. Commit: `feat(qa-01): wave 1 tournament checkpoint` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/QA-01-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: DL-01, R01-01, QA-03, REL-01. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement QA-01 only: Wave 1 tournament checkpoint.
Read AGENTS.md, docs/sprints/verification/QA-01-wave-1-tournament-checkpoint.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Turnamen kecil menyatukan baseline classical ML dan follow-up jobs dengan hasil deterministik.
Contract: tiny offline tournament -> all lifecycle outcomes + identical snapshot/folds/costs comparison.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
