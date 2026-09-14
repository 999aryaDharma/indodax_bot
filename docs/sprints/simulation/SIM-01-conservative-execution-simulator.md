# SIM-01 — Conservative execution simulator

## Metadata

Status: PLANNED

Priority: P0 | Type: feature | Domain: simulation | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/sim-01-conservative-execution-simulator`

Requirements: FR-06 | Legacy tasks: 18

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Order intent menghasilkan fill paling awal di event yang eligible berikutnya dengan biaya realistis.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `SIM-01` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: SignalIntent + market + schedule -> REJECTED/PARTIAL/FILLED; next-open, precision, SL_FIRST, latency.

Direct consumers: SIM-02, LABEL-01, ML-02

## Depends On

- COST-01 — Time-valid exchange cost schedules
- BAR-01 — Causal time and event bars

## Unlocks

SIM-02, LABEL-01, ML-02

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/08-costs-ledger-and-execution.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency COST-01 supplies: market, side, role, event_ts -> service/tax/exchange components and min notional with sources; [valid_from,valid_to).
- Dependency BAR-01 supplies: PASS trades + continuity + fixed/train-only threshold -> separate bar_type datasets, end-exclusive windows.

## In Scope

- Order intent menghasilkan fill paling awal di event yang eligible berikutnya dengan biaya realistis.
- Same-close execution ditolak.
- Insufficient depth dan min-size menghasilkan reject atau partial.
- Limit touch tidak otomatis maker fill.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: SIM-02, LABEL-01, ML-02.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `SIM-01` dan dependency evidence yang valid, when owning component dijalankan, then order intent menghasilkan fill paling awal di event yang eligible berikutnya dengan biaya realistis.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **SIM-01-FR0:** Order intent menghasilkan fill paling awal di event yang eligible berikutnya dengan biaya realistis.
1. **SIM-01-FR1:** Same-close execution ditolak.
2. **SIM-01-FR2:** Insufficient depth dan min-size menghasilkan reject atau partial.
3. **SIM-01-FR3:** Limit touch tidak otomatis maker fill.

## Domain Rules / Invariants

SignalIntent + market + schedule -> REJECTED/PARTIAL/FILLED; next-open, precision, SL_FIRST, latency.

Decimal valued double-entry journal; separate asset units from IDR valuation; exact fees, partial fills and market rules.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/backtest`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

SignalIntent + market + schedule -> REJECTED/PARTIAL/FILLED; next-open, precision, SL_FIRST, latency.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/backtest/events.py`
- `src/indodax_lab/backtest/execution.py`
- `tests/unit/lab/backtest/test_execution.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/08-costs-ledger-and-execution.md`; exact table schemas use the Required Reading dataset contract.

SignalIntent + market + schedule -> REJECTED/PARTIAL/FILLED; next-open, precision, SL_FIRST, latency.

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

First establish SIM-01-AC0: Order intent menghasilkan fill paling awal di event yang eligible berikutnya dengan biaya realistis. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `SIM-01-AC1`, build minimal fixture proving: Same-close execution ditolak. Write `test_sim_01_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `SIM-01-AC2`, build minimal fixture proving: Insufficient depth dan min-size menghasilkan reject atau partial. Write `test_sim_01_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `SIM-01-AC3`, build minimal fixture proving: Limit touch tidak otomatis maker fill. Write `test_sim_01_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **SIM-01-AC0**, `test_sim_01_valid_contract` — Order intent menghasilkan fill paling awal di event yang eligible berikutnya dengan biaya realistis. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| SIM-01-AC1 | `test_sim_01_contract_1` | Same-close execution ditolak |
| SIM-01-AC2 | `test_sim_01_contract_2` | Insufficient depth dan min-size menghasilkan reject atau partial |
| SIM-01-AC3 | `test_sim_01_contract_3` | Limit touch tidak otomatis maker fill |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Same-close execution ditolak. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Insufficient depth dan min-size menghasilkan reject atau partial. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Limit touch tidak otomatis maker fill. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
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

Emit `SIM-01` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Ledger mismatch invalidates run; restore last complete checkpoint and replay, never patch PnL in reports.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **SIM-01-AC0** Order intent menghasilkan fill paling awal di event yang eligible berikutnya dengan biaya realistis. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **SIM-01-AC1** Same-close execution ditolak. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **SIM-01-AC2** Insufficient depth dan min-size menghasilkan reject atau partial. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **SIM-01-AC3** Limit touch tidak otomatis maker fill. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Same-close execution ditolak. Inspect fixture and actual production path.
- Attempt to disprove: Insufficient depth dan min-size menghasilkan reject atau partial. Inspect fixture and actual production path.
- Attempt to disprove: Limit touch tidak otomatis maker fill. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/sim-01-conservative-execution-simulator`. Commit: `feat(sim-01): conservative execution simulator` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/SIM-01-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: SIM-02, LABEL-01, ML-02. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement SIM-01 only: Conservative execution simulator.
Read AGENTS.md, docs/sprints/simulation/SIM-01-conservative-execution-simulator.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Order intent menghasilkan fill paling awal di event yang eligible berikutnya dengan biaya realistis.
Contract: SignalIntent + market + schedule -> REJECTED/PARTIAL/FILLED; next-open, precision, SL_FIRST, latency.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
