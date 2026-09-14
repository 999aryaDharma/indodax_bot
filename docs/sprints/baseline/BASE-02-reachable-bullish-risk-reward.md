# BASE-02 — Reachable bullish risk reward

## Metadata

Status: DONE

Priority: P0 | Type: safety | Domain: baseline | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/base-02-reachable-bullish-risk-reward`

Requirements: FR-01 | Legacy tasks: 2

External gates: No additional portfolio activation gate; data/policy validity still applies.

Historical import; no fresh runtime test claim.

## Goal

Rencana bullish yang memenuhi minimum RR dapat melewati risk gate.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `BASE-02` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: ATR stop/target configuration -> TradingPlan or explicit reject.

Direct consumers: BASE-05

## Depends On

- BASE-01 — Offline verification harness

## Unlocks

BASE-05

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/03-baseline-and-paper-compatibility.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

Existing committed implementation; preserve and reverify only when affected.

- Dependency BASE-01 supplies: pytest + injected transports -> reproducible result; no credentials required.

## In Scope

- Rencana bullish yang memenuhi minimum RR dapat melewati risk gate.
- RR dihitung dari jarak entry-stop dan target-entry.
- ATR nol ditolak.
- Perubahan multiplier tidak menyisakan gate mustahil.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: BASE-05.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `BASE-02` dan dependency evidence yang valid, when owning component dijalankan, then rencana bullish yang memenuhi minimum RR dapat melewati risk gate.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **BASE-02-FR0:** Rencana bullish yang memenuhi minimum RR dapat melewati risk gate.
1. **BASE-02-FR1:** RR dihitung dari jarak entry-stop dan target-entry.
2. **BASE-02-FR2:** ATR nol ditolak.
3. **BASE-02-FR3:** Perubahan multiplier tidak menyisakan gate mustahil.

## Domain Rules / Invariants

ATR stop/target configuration -> TradingPlan or explicit reject.

SQLite backup-first; exact accounting TEXT; preserve triggers, FK children and high-water mark. No production DB touched by tests.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/main.py, src/paper_trader.py, src/signal_observer.py`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

ATR stop/target configuration -> TradingPlan or explicit reject.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/config.py`
- `src/risk_manager.py`
- `tests/unit/test_risk_config.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/03-baseline-and-paper-compatibility.md`; exact table schemas use the Required Reading dataset contract.

ATR stop/target configuration -> TradingPlan or explicit reject.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

SQLite backup-first; exact accounting TEXT; preserve triggers, FK children and high-water mark. No production DB touched by tests.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface delivery: Telegram read-only or observation-bound callback as specified; no exchange trading mutation. Validate allowlist, payload size and retry behavior.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Pengguna harus dapat membedakan success, blocked/no-data dan transport error. Format Markdown aman, ringkas, dengan as_of dan provenance. No extra dashboard.

## Implementation Steps

First establish BASE-02-AC0: Rencana bullish yang memenuhi minimum RR dapat melewati risk gate. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `BASE-02-AC1`, build minimal fixture proving: RR dihitung dari jarak entry-stop dan target-entry. Write `test_base_02_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `BASE-02-AC2`, build minimal fixture proving: ATR nol ditolak. Write `test_base_02_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `BASE-02-AC3`, build minimal fixture proving: Perubahan multiplier tidak menyisakan gate mustahil. Write `test_base_02_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **BASE-02-AC0**, `test_base_02_valid_contract` — Rencana bullish yang memenuhi minimum RR dapat melewati risk gate. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| BASE-02-AC1 | `test_base_02_contract_1` | RR dihitung dari jarak entry-stop dan target-entry |
| BASE-02-AC2 | `test_base_02_contract_2` | ATR nol ditolak |
| BASE-02-AC3 | `test_base_02_contract_3` | Perubahan multiplier tidak menyisakan gate mustahil |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

Historical DONE: these names describe required behavior mapping, not newly executed test functions. Find actual tests in the listed baseline files and evidence before reopening.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: RR dihitung dari jarak entry-stop dan target-entry. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: ATR nol ditolak. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Perubahan multiplier tidak menyisakan gate mustahil. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Callbacks are untrusted; validate observation identity and allowlisted chat. No real order executor.

Trust boundary assessment: untrusted provider/artifact input or privileged state mutation exists; require negative tests and redacted diagnostics.

## Concurrency / Idempotency

Two connections exercise atomic close; decisions have immutable unique key. Replays retain monotonic checkpoints.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `BASE-02` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Protect existing flat modules; migration on copy only; abort/rollback on failure and retain verified backup.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **BASE-02-AC0** Rencana bullish yang memenuhi minimum RR dapat melewati risk gate. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **BASE-02-AC1** RR dihitung dari jarak entry-stop dan target-entry. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **BASE-02-AC2** ATR nol ditolak. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **BASE-02-AC3** Perubahan multiplier tidak menyisakan gate mustahil. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: RR dihitung dari jarak entry-stop dan target-entry. Inspect fixture and actual production path.
- Attempt to disprove: ATR nol ditolak. Inspect fixture and actual production path.
- Attempt to disprove: Perubahan multiplier tidak menyisakan gate mustahil. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/base-02-reachable-bullish-risk-reward`. Commit: `fix(base-02): reachable bullish risk reward` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/BASE-02-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: BASE-05. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement BASE-02 only: Reachable bullish risk reward.
Read AGENTS.md, docs/sprints/baseline/BASE-02-reachable-bullish-risk-reward.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Rencana bullish yang memenuhi minimum RR dapat melewati risk gate.
Contract: ATR stop/target configuration -> TradingPlan or explicit reject.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
