# STRAT-01 — Declarative strategy protocol

## Metadata

Status: REVIEW

Priority: P0 | Type: feature | Domain: strategies | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/strat-01-declarative-strategy-protocol`

Requirements: FR-08 | Legacy tasks: 19

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Strategi terdaftar hanya menghasilkan intent dan tidak memiliki otoritas fill atau ledger.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `STRAT-01` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: StrategySpecification + DecisionFrame -> list[SignalIntent]; ID/version/family/timeframes/risk/split required.

Direct consumers: C01-01, C07-01, C02-01, C03-01, C04-01, S01-01, S02-01, C05-01, C06-01, C08-01, C09-01, C11-01, S03-01, S04-01, S05-01, S06-01, S08-01, S09-01

## Depends On

- SIM-03 — Deterministic replay judge
- FEAT-04 — Immutable feature materialization

## Unlocks

C01-01, C02-01, C03-01, C04-01, C05-01, C06-01, C07-01, C08-01, C09-01, C11-01, S01-01, S02-01, S03-01, S04-01, S05-01, S06-01, S08-01, S09-01, RW2-01

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/10-strategy-catalog-and-protocol.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency SIM-03 supplies: market -> pending fills -> barriers -> decision -> risk -> orders -> mark; stable event/pair/order sort.
- Dependency FEAT-04 supplies: snapshot IDs + registry hash -> features manifest, ordered columns, row_ready_at, eligibility.

## In Scope

- Strategi terdaftar hanya menghasilkan intent dan tidak memiliki otoritas fill atau ledger.
- Unknown config ditolak.
- Future atau ineligible row tidak masuk DecisionFrame.
- Parameter atau logic change memerlukan versi baru.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: C01-01, C07-01, C02-01, C03-01, C04-01, S01-01, S02-01, C05-01, C06-01, C08-01, C09-01, C11-01, S03-01, S04-01, S05-01, S06-01, S08-01, S09-01.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `STRAT-01` dan dependency evidence yang valid, when owning component dijalankan, then strategi terdaftar hanya menghasilkan intent dan tidak memiliki otoritas fill atau ledger.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **STRAT-01-FR0:** Strategi terdaftar hanya menghasilkan intent dan tidak memiliki otoritas fill atau ledger.
1. **STRAT-01-FR1:** Unknown config ditolak.
2. **STRAT-01-FR2:** Future atau ineligible row tidak masuk DecisionFrame.
3. **STRAT-01-FR3:** Parameter atau logic change memerlukan versi baru.

## Domain Rules / Invariants

StrategySpecification + DecisionFrame -> list[SignalIntent]; ID/version/family/timeframes/risk/split required.

Stateless decision functions over approved frame; only LONG/FLAT intents; registry version and fixed risk profile.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/strategies, configs/strategies`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

StrategySpecification + DecisionFrame -> list[SignalIntent]; ID/version/family/timeframes/risk/split required.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/strategies/base.py`
- `src/indodax_lab/strategies/registry.py`
- `tests/unit/lab/strategies/test_registry.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/10-strategy-catalog-and-protocol.md`; exact table schemas use the Required Reading dataset contract.

StrategySpecification + DecisionFrame -> list[SignalIntent]; ID/version/family/timeframes/risk/split required.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Stateless decision functions over approved frame; only LONG/FLAT intents; registry version and fixed risk profile.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish STRAT-01-AC0: Strategi terdaftar hanya menghasilkan intent dan tidak memiliki otoritas fill atau ledger. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `STRAT-01-AC1`, build minimal fixture proving: Unknown config ditolak. Write `test_strat_01_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `STRAT-01-AC2`, build minimal fixture proving: Future atau ineligible row tidak masuk DecisionFrame. Write `test_strat_01_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `STRAT-01-AC3`, build minimal fixture proving: Parameter atau logic change memerlukan versi baru. Write `test_strat_01_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **STRAT-01-AC0**, `test_strat_01_valid_contract` — Strategi terdaftar hanya menghasilkan intent dan tidak memiliki otoritas fill atau ledger. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| STRAT-01-AC1 | `test_strat_01_contract_1` | Unknown config ditolak |
| STRAT-01-AC2 | `test_strat_01_contract_2` | Future atau ineligible row tidak masuk DecisionFrame |
| STRAT-01-AC3 | `test_strat_01_contract_3` | Parameter atau logic change memerlukan versi baru |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Unknown config ditolak. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Future atau ineligible row tidak masuk DecisionFrame. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Parameter atau logic change memerlukan versi baru. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Strategies cannot mutate ledger, bypass risk or import live order API. Config implementation allowlist only.

Trust boundary assessment: no new public authentication surface; verified local input remains mandatory and existing secret/PII controls apply.

## Concurrency / Idempotency

Pure deterministic decisions; universe ties use canonical pair order; capital conflicts resolved by judge not strategy.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `STRAT-01` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Freeze strategy versions; archive failed hypothesis; never silently retune historical winner.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **STRAT-01-AC0** Strategi terdaftar hanya menghasilkan intent dan tidak memiliki otoritas fill atau ledger. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **STRAT-01-AC1** Unknown config ditolak. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **STRAT-01-AC2** Future atau ineligible row tidak masuk DecisionFrame. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **STRAT-01-AC3** Parameter atau logic change memerlukan versi baru. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Unknown config ditolak. Inspect fixture and actual production path.
- Attempt to disprove: Future atau ineligible row tidak masuk DecisionFrame. Inspect fixture and actual production path.
- Attempt to disprove: Parameter atau logic change memerlukan versi baru. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/strat-01-declarative-strategy-protocol`. Commit: `feat(strat-01): declarative strategy protocol` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/STRAT-01-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: C01-01, C07-01, C02-01, C03-01, C04-01, S01-01, S02-01, C05-01, C06-01, C08-01, C09-01, C11-01, S03-01, S04-01, S05-01, S06-01, S08-01, S09-01. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement STRAT-01 only: Declarative strategy protocol.
Read AGENTS.md, docs/sprints/strategies/STRAT-01-declarative-strategy-protocol.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Strategi terdaftar hanya menghasilkan intent dan tidak memiliki otoritas fill atau ledger.
Contract: StrategySpecification + DecisionFrame -> list[SignalIntent]; ID/version/family/timeframes/risk/split required.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
