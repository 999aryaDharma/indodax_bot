# SHADOW-01 — Auditable forward paper decisions

## Metadata

Status: REVIEW

Priority: P0 | Type: feature | Domain: shadow | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/shadow-01-auditable-forward-paper-decisions`

Requirements: FR-12 | Legacy tasks: 26

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Forecast forward dan keputusan risiko tersimpan sebelum outcome tanpa callback selection bias.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `SHADOW-01` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: frozen candidate + live available features -> immutable prediction/decision with paper intent only.

Direct consumers: SHADOW-02

## Depends On

- EVAL-03 — Sealed candidate lifecycle
- ML-04 — Portable model bundles and replay
- DATA-05 — Reliable forward market collection

## Unlocks

SHADOW-02

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/14-shadow-portfolios-and-promotion.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency EVAL-03 supplies: IDEA -> IMPLEMENTED -> BACKTESTED -> VALIDATED -> SEALED_PASS -> SHADOW -> CHAMPION; immutable transitions.
- Dependency ML-04 supplies: model + preprocessor + calibrator + thresholds + hashes + feature order -> verified bundle, replay forecast.
- Dependency DATA-05 supplies: DISCONNECTED -> SYNCING -> RELIABLE; gap -> GAP -> RECOVERING; bounded durable writer.

## In Scope

- Forecast forward dan keputusan risiko tersimpan sebelum outcome tanpa callback selection bias.
- Telegram gagal tidak menghapus decision.
- Stale data atau model mismatch menolak entry.
- Manual intent bukan ground truth.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: SHADOW-02.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `SHADOW-01` dan dependency evidence yang valid, when owning component dijalankan, then forecast forward dan keputusan risiko tersimpan sebelum outcome tanpa callback selection bias.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **SHADOW-01-FR0:** Forecast forward dan keputusan risiko tersimpan sebelum outcome tanpa callback selection bias.
1. **SHADOW-01-FR1:** Telegram gagal tidak menghapus decision.
2. **SHADOW-01-FR2:** Stale data atau model mismatch menolak entry.
3. **SHADOW-01-FR3:** Manual intent bukan ground truth.

## Domain Rules / Invariants

frozen candidate + live available features -> immutable prediction/decision with paper intent only.

Immutable decisions before outcome; shared Rp500k vs independent Rp500k; reconcile event IDs and balances.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/paper`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

frozen candidate + live available features -> immutable prediction/decision with paper intent only.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/paper/contracts.py`
- `src/indodax_lab/paper/runner.py`
- `tests/integration/lab/test_shadow_replay.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/14-shadow-portfolios-and-promotion.md`; exact table schemas use the Required Reading dataset contract.

frozen candidate + live available features -> immutable prediction/decision with paper intent only.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Immutable decisions before outcome; shared Rp500k vs independent Rp500k; reconcile event IDs and balances.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish SHADOW-01-AC0: Forecast forward dan keputusan risiko tersimpan sebelum outcome tanpa callback selection bias. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `SHADOW-01-AC1`, build minimal fixture proving: Telegram gagal tidak menghapus decision. Write `test_shadow_01_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `SHADOW-01-AC2`, build minimal fixture proving: Stale data atau model mismatch menolak entry. Write `test_shadow_01_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `SHADOW-01-AC3`, build minimal fixture proving: Manual intent bukan ground truth. Write `test_shadow_01_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **SHADOW-01-AC0**, `test_shadow_01_valid_contract` — Forecast forward dan keputusan risiko tersimpan sebelum outcome tanpa callback selection bias. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| SHADOW-01-AC1 | `test_shadow_01_contract_1` | Telegram gagal tidak menghapus decision |
| SHADOW-01-AC2 | `test_shadow_01_contract_2` | Stale data atau model mismatch menolak entry |
| SHADOW-01-AC3 | `test_shadow_01_contract_3` | Manual intent bukan ground truth |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Telegram gagal tidak menghapus decision. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Stale data atau model mismatch menolak entry. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Manual intent bukan ground truth. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Paper only; authorized operator may pause/reset hard halt via audited control, never through untrusted callback.

Trust boundary assessment: untrusted provider/artifact input or privileged state mutation exists; require negative tests and redacted diagnostics.

## Concurrency / Idempotency

Atomic cash reservations and processed-event checkpoint; risk cap across all candidates in shared portfolio.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `SHADOW-01` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Champion pointer changes atomically only after gates; preserve prior compatible artifact and ledger checkpoints.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **SHADOW-01-AC0** Forecast forward dan keputusan risiko tersimpan sebelum outcome tanpa callback selection bias. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **SHADOW-01-AC1** Telegram gagal tidak menghapus decision. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **SHADOW-01-AC2** Stale data atau model mismatch menolak entry. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **SHADOW-01-AC3** Manual intent bukan ground truth. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Telegram gagal tidak menghapus decision. Inspect fixture and actual production path.
- Attempt to disprove: Stale data atau model mismatch menolak entry. Inspect fixture and actual production path.
- Attempt to disprove: Manual intent bukan ground truth. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/shadow-01-auditable-forward-paper-decisions`. Commit: `feat(shadow-01): auditable forward paper decisions` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/SHADOW-01-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: SHADOW-02. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement SHADOW-01 only: Auditable forward paper decisions.
Read AGENTS.md, docs/sprints/shadow/SHADOW-01-auditable-forward-paper-decisions.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Forecast forward dan keputusan risiko tersimpan sebelum outcome tanpa callback selection bias.
Contract: frozen candidate + live available features -> immutable prediction/decision with paper intent only.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
