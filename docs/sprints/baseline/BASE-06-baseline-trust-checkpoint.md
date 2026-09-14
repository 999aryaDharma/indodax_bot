# BASE-06 — Baseline trust checkpoint

## Metadata

Status: DONE

Priority: P0 | Type: quality | Domain: baseline | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/base-06-baseline-trust-checkpoint`

Requirements: FR-01 | Legacy tasks: 6

External gates: No additional portfolio activation gate; data/policy validity still applies.

Historical import; no fresh runtime test claim.

## Goal

Perilaku API, risk, accounting dan observasi terbukti bersama melalui regression checkpoint.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `BASE-06` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: Committed source SHA + command exits -> phase0 evidence.

Direct consumers: DATA-06

## Depends On

- BASE-05 — Unbiased signal observations

## Unlocks

DATA-06

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/03-baseline-and-paper-compatibility.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

Existing committed implementation; preserve and reverify only when affected.

- Dependency BASE-05 supplies: Decision key -> observation; exec/skip/paper:<id> -> separate intent; closed bar -> SL_FIRST outcome.

## In Scope

- Perilaku API, risk, accounting dan observasi terbukti bersama melalui regression checkpoint.
- Semua field v2 termasuk maker flag fee dan unit diverifikasi.
- Mutation kontrak membuat checkpoint merah.
- Evidence membedakan SHA kode dari SHA dokumen.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: DATA-06.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `BASE-06` dan dependency evidence yang valid, when owning component dijalankan, then perilaku API, risk, accounting dan observasi terbukti bersama melalui regression checkpoint.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **BASE-06-FR0:** Perilaku API, risk, accounting dan observasi terbukti bersama melalui regression checkpoint.
1. **BASE-06-FR1:** Semua field v2 termasuk maker flag fee dan unit diverifikasi.
2. **BASE-06-FR2:** Mutation kontrak membuat checkpoint merah.
3. **BASE-06-FR3:** Evidence membedakan SHA kode dari SHA dokumen.

## Domain Rules / Invariants

Committed source SHA + command exits -> phase0 evidence.

SQLite backup-first; exact accounting TEXT; preserve triggers, FK children and high-water mark. No production DB touched by tests.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/main.py, src/paper_trader.py, src/signal_observer.py`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

Committed source SHA + command exits -> phase0 evidence.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `tests/regression/test_phase0_invariants.py`
- `docs/research/phase0-verification.md`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/03-baseline-and-paper-compatibility.md`; exact table schemas use the Required Reading dataset contract.

Committed source SHA + command exits -> phase0 evidence.

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

First establish BASE-06-AC0: Perilaku API, risk, accounting dan observasi terbukti bersama melalui regression checkpoint. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `BASE-06-AC1`, build minimal fixture proving: Semua field v2 termasuk maker flag fee dan unit diverifikasi. Write `test_base_06_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `BASE-06-AC2`, build minimal fixture proving: Mutation kontrak membuat checkpoint merah. Write `test_base_06_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `BASE-06-AC3`, build minimal fixture proving: Evidence membedakan SHA kode dari SHA dokumen. Write `test_base_06_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **BASE-06-AC0**, `test_base_06_valid_contract` — Perilaku API, risk, accounting dan observasi terbukti bersama melalui regression checkpoint. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| BASE-06-AC1 | `test_base_06_contract_1` | Semua field v2 termasuk maker flag fee dan unit diverifikasi |
| BASE-06-AC2 | `test_base_06_contract_2` | Mutation kontrak membuat checkpoint merah |
| BASE-06-AC3 | `test_base_06_contract_3` | Evidence membedakan SHA kode dari SHA dokumen |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

Historical DONE: these names describe required behavior mapping, not newly executed test functions. Find actual tests in the listed baseline files and evidence before reopening.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Semua field v2 termasuk maker flag fee dan unit diverifikasi. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Mutation kontrak membuat checkpoint merah. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Evidence membedakan SHA kode dari SHA dokumen. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
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

Emit `BASE-06` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Protect existing flat modules; migration on copy only; abort/rollback on failure and retain verified backup.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **BASE-06-AC0** Perilaku API, risk, accounting dan observasi terbukti bersama melalui regression checkpoint. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **BASE-06-AC1** Semua field v2 termasuk maker flag fee dan unit diverifikasi. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **BASE-06-AC2** Mutation kontrak membuat checkpoint merah. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **BASE-06-AC3** Evidence membedakan SHA kode dari SHA dokumen. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Semua field v2 termasuk maker flag fee dan unit diverifikasi. Inspect fixture and actual production path.
- Attempt to disprove: Mutation kontrak membuat checkpoint merah. Inspect fixture and actual production path.
- Attempt to disprove: Evidence membedakan SHA kode dari SHA dokumen. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/base-06-baseline-trust-checkpoint`. Commit: `fix(base-06): baseline trust checkpoint` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/BASE-06-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: DATA-06. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement BASE-06 only: Baseline trust checkpoint.
Read AGENTS.md, docs/sprints/baseline/BASE-06-baseline-trust-checkpoint.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Perilaku API, risk, accounting dan observasi terbukti bersama melalui regression checkpoint.
Contract: Committed source SHA + command exits -> phase0 evidence.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
