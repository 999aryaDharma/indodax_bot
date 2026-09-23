# LED-01 — Balanced research postings

## Metadata

Status: DONE

Priority: P0 | Type: safety | Domain: simulation | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/led-01-balanced-research-postings`

Requirements: FR-06 | Legacy tasks: 17

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Simulasi kas dan posisi memakai posting balance dengan cost basis exact.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `LED-01` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: Fill -> cash/asset/fee/PnL postings in one valuation currency; quantity tracked separately; Decimal.

Direct consumers: SIM-02

## Depends On

- COST-01 — Time-valid exchange cost schedules
- BASE-04 — Exact paper accounting migration

## Unlocks

SIM-02, PM-02

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/08-costs-ledger-and-execution.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency COST-01 supplies: market, side, role, event_ts -> service/tax/exchange components and min notional with sources; [valid_from,valid_to).
- Dependency BASE-04 supplies: Decimal buy/sell -> canonical TEXT, gross cash cost basis, LEGACY_ESTIMATE or EXACT accounting status.

## In Scope

- Simulasi kas dan posisi memakai posting balance dengan cost basis exact.
- Buy partial sell final sell menjaga quantity nonnegative.
- Fee lebih tinggi tidak meningkatkan fixed-path PnL.
- Duplicate fill ID tidak menggandakan posting.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: SIM-02.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `LED-01` dan dependency evidence yang valid, when owning component dijalankan, then simulasi kas dan posisi memakai posting balance dengan cost basis exact.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **LED-01-FR0:** Simulasi kas dan posisi memakai posting balance dengan cost basis exact.
1. **LED-01-FR1:** Buy partial sell final sell menjaga quantity nonnegative.
2. **LED-01-FR2:** Fee lebih tinggi tidak meningkatkan fixed-path PnL.
3. **LED-01-FR3:** Duplicate fill ID tidak menggandakan posting.

## Domain Rules / Invariants

Fill -> cash/asset/fee/PnL postings in one valuation currency; quantity tracked separately; Decimal.

Decimal valued double-entry journal; separate asset units from IDR valuation; exact fees, partial fills and market rules.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/backtest`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

Fill -> cash/asset/fee/PnL postings in one valuation currency; quantity tracked separately; Decimal.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/backtest/ledger.py`
- `src/indodax_lab/backtest/orders.py`
- `tests/property/lab/test_ledger_invariants.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/08-costs-ledger-and-execution.md`; exact table schemas use the Required Reading dataset contract.

Fill -> cash/asset/fee/PnL postings in one valuation currency; quantity tracked separately; Decimal.

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

First establish LED-01-AC0: Simulasi kas dan posisi memakai posting balance dengan cost basis exact. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `LED-01-AC1`, build minimal fixture proving: Buy partial sell final sell menjaga quantity nonnegative. Write `test_led_01_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `LED-01-AC2`, build minimal fixture proving: Fee lebih tinggi tidak meningkatkan fixed-path PnL. Write `test_led_01_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `LED-01-AC3`, build minimal fixture proving: Duplicate fill ID tidak menggandakan posting. Write `test_led_01_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **LED-01-AC0**, `test_led_01_valid_contract` — Simulasi kas dan posisi memakai posting balance dengan cost basis exact. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| LED-01-AC1 | `test_led_01_contract_1` | Buy partial sell final sell menjaga quantity nonnegative |
| LED-01-AC2 | `test_led_01_contract_2` | Fee lebih tinggi tidak meningkatkan fixed-path PnL |
| LED-01-AC3 | `test_led_01_contract_3` | Duplicate fill ID tidak menggandakan posting |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Buy partial sell final sell menjaga quantity nonnegative. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Fee lebih tinggi tidak meningkatkan fixed-path PnL. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Duplicate fill ID tidak menggandakan posting. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
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

Emit `LED-01` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Ledger mismatch invalidates run; restore last complete checkpoint and replay, never patch PnL in reports.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **LED-01-AC0** Simulasi kas dan posisi memakai posting balance dengan cost basis exact. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **LED-01-AC1** Buy partial sell final sell menjaga quantity nonnegative. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **LED-01-AC2** Fee lebih tinggi tidak meningkatkan fixed-path PnL. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **LED-01-AC3** Duplicate fill ID tidak menggandakan posting. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Buy partial sell final sell menjaga quantity nonnegative. Inspect fixture and actual production path.
- Attempt to disprove: Fee lebih tinggi tidak meningkatkan fixed-path PnL. Inspect fixture and actual production path.
- Attempt to disprove: Duplicate fill ID tidak menggandakan posting. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/led-01-balanced-research-postings`. Commit: `feat(led-01): balanced research postings` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/LED-01-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: SIM-02. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement LED-01 only: Balanced research postings.
Read AGENTS.md, docs/sprints/simulation/LED-01-balanced-research-postings.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Simulasi kas dan posisi memakai posting balance dengan cost basis exact.
Contract: Fill -> cash/asset/fee/PnL postings in one valuation currency; quantity tracked separately; Decimal.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
