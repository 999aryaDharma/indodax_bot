# SIM-04 — Net-cost risk and capacity metrics

## Metadata

Status: REVIEW

Priority: P0 | Type: feature | Domain: simulation | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/sim-04-net-cost-risk-and-capacity-metrics`

Requirements: FR-06 | Legacy tasks: 18

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Report menghitung performa dari ledger dan menunjukkan batas data serta kapasitas.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `SIM-04` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: postings + equity + rejected orders -> metrics by year/regime/tier/asset and 1.5x/2x stress.

Direct consumers: EVAL-01, REPORT-01

## Depends On

- SIM-03 — Deterministic replay judge

## Unlocks

EVAL-01, REPORT-01

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/08-costs-ledger-and-execution.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency SIM-03 supplies: market -> pending fills -> barriers -> decision -> risk -> orders -> mark; stable event/pair/order sort.

## In Scope

- Report menghitung performa dari ledger dan menunjukkan batas data serta kapasitas.
- No-trade dan zero-loss PF menghasilkan undefined beralasan.
- Fee tidak dikurangi dua kali dari net cash equity.
- Missing spread tidak dilaporkan sebagai biaya nol.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: EVAL-01, REPORT-01.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `SIM-04` dan dependency evidence yang valid, when owning component dijalankan, then report menghitung performa dari ledger dan menunjukkan batas data serta kapasitas.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **SIM-04-FR0:** Report menghitung performa dari ledger dan menunjukkan batas data serta kapasitas.
1. **SIM-04-FR1:** No-trade dan zero-loss PF menghasilkan undefined beralasan.
2. **SIM-04-FR2:** Fee tidak dikurangi dua kali dari net cash equity.
3. **SIM-04-FR3:** Missing spread tidak dilaporkan sebagai biaya nol.

## Domain Rules / Invariants

postings + equity + rejected orders -> metrics by year/regime/tier/asset and 1.5x/2x stress.

Decimal valued double-entry journal; separate asset units from IDR valuation; exact fees, partial fills and market rules.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/backtest`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

postings + equity + rejected orders -> metrics by year/regime/tier/asset and 1.5x/2x stress.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/backtest/metrics.py`
- `tests/unit/lab/backtest/test_metrics.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/08-costs-ledger-and-execution.md`; exact table schemas use the Required Reading dataset contract.

postings + equity + rejected orders -> metrics by year/regime/tier/asset and 1.5x/2x stress.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Decimal valued double-entry journal; separate asset units from IDR valuation; exact fees, partial fills and market rules.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish SIM-04-AC0: Report menghitung performa dari ledger dan menunjukkan batas data serta kapasitas. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `SIM-04-AC1`, build minimal fixture proving: No-trade dan zero-loss PF menghasilkan undefined beralasan. Write `test_sim_04_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `SIM-04-AC2`, build minimal fixture proving: Fee tidak dikurangi dua kali dari net cash equity. Write `test_sim_04_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `SIM-04-AC3`, build minimal fixture proving: Missing spread tidak dilaporkan sebagai biaya nol. Write `test_sim_04_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **SIM-04-AC0**, `test_sim_04_valid_contract` — Report menghitung performa dari ledger dan menunjukkan batas data serta kapasitas. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| SIM-04-AC1 | `test_sim_04_contract_1` | No-trade dan zero-loss PF menghasilkan undefined beralasan |
| SIM-04-AC2 | `test_sim_04_contract_2` | Fee tidak dikurangi dua kali dari net cash equity |
| SIM-04-AC3 | `test_sim_04_contract_3` | Missing spread tidak dilaporkan sebagai biaya nol |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: No-trade dan zero-loss PF menghasilkan undefined beralasan. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Fee tidak dikurangi dua kali dari net cash equity. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Missing spread tidak dilaporkan sebagai biaya nol. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

No order-routing/network write capability. Unknown historical cost blocks promotion; signed or locally reviewed schedules.

Trust boundary assessment: untrusted provider/artifact input or privileged state mutation exists; require negative tests and redacted diagnostics.

## Concurrency / Idempotency

Stable market event ordering; posting keyed by fill; risk/cash reservation atomically shared across candidates.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `SIM-04` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Ledger mismatch invalidates run; restore last complete checkpoint and replay, never patch PnL in reports.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **SIM-04-AC0** Report menghitung performa dari ledger dan menunjukkan batas data serta kapasitas. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **SIM-04-AC1** No-trade dan zero-loss PF menghasilkan undefined beralasan. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **SIM-04-AC2** Fee tidak dikurangi dua kali dari net cash equity. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **SIM-04-AC3** Missing spread tidak dilaporkan sebagai biaya nol. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: No-trade dan zero-loss PF menghasilkan undefined beralasan. Inspect fixture and actual production path.
- Attempt to disprove: Fee tidak dikurangi dua kali dari net cash equity. Inspect fixture and actual production path.
- Attempt to disprove: Missing spread tidak dilaporkan sebagai biaya nol. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/sim-04-net-cost-risk-and-capacity-metrics`. Commit: `feat(sim-04): net-cost risk and capacity metrics` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/SIM-04-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: EVAL-01, REPORT-01. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement SIM-04 only: Net-cost risk and capacity metrics.
Read AGENTS.md, docs/sprints/simulation/SIM-04-net-cost-risk-and-capacity-metrics.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Report menghitung performa dari ledger dan menunjukkan batas data serta kapasitas.
Contract: postings + equity + rejected orders -> metrics by year/regime/tier/asset and 1.5x/2x stress.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
