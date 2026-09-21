# DATA-06 — Provider-derived reproducible snapshot

## Metadata

Status: DONE

Priority: P0 | Type: quality | Domain: market-data | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/data-06-provider-derived-reproducible-snapshot`

Requirements: FR-02 | Legacy tasks: 14

External gates: No additional portfolio activation gate; data/policy validity still applies.

Historical import; no fresh runtime test claim.

## Goal

Pipeline offline benar-benar menghubungkan wire sampai final snapshot melalui artifact yang diverifikasi.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `DATA-06` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: Typed loaders -> recomputed sentry decisions -> fixed cutoff -> immutable snapshot with 45 source references.

Direct consumers: FEAT-01, SIM-03, LOB-01, OPS-02

## Depends On

- BASE-06 — Baseline trust checkpoint
- UNIV-01 — Point-in-time investable universe
- BAR-01 — Causal time and event bars

## Unlocks

FEAT-01, LOB-01, OPS-02, SIM-03, RW1-01

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/04-market-data-and-provenance.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

Existing committed implementation; preserve and reverify only when affected.

- Dependency BASE-06 supplies: Committed source SHA + command exits -> phase0 evidence.
- Dependency UNIV-01 supplies: as_of + availability cutoff + provider response -> BIG_CAP/SMALL_CAP/LIQUIDITY_ONLY and exclusion reasons.
- Dependency BAR-01 supplies: PASS trades + continuity + fixed/train-only threshold -> separate bar_type datasets, end-exclusive windows.

## In Scope

- Pipeline offline benar-benar menghubungkan wire sampai final snapshot melalui artifact yang diverifikasi.
- Wire garbage atau event berbeda dari parse ditolak.
- Cap observation direkonstruksi dari body provider.
- Dua root berbeda memberi snapshot dan global decision ID identik.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: FEAT-01, SIM-03, LOB-01, OPS-02.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `DATA-06` dan dependency evidence yang valid, when owning component dijalankan, then pipeline offline benar-benar menghubungkan wire sampai final snapshot melalui artifact yang diverifikasi.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **DATA-06-FR0:** Pipeline offline benar-benar menghubungkan wire sampai final snapshot melalui artifact yang diverifikasi.
1. **DATA-06-FR1:** Wire garbage atau event berbeda dari parse ditolak.
2. **DATA-06-FR2:** Cap observation direkonstruksi dari body provider.
3. **DATA-06-FR3:** Dua root berbeda memberi snapshot dan global decision ID identik.

## Domain Rules / Invariants

Typed loaders -> recomputed sentry decisions -> fixed cutoff -> immutable snapshot with 45 source references.

Raw bytes before parse; canonical typed schemas; immutable Parquet/manifest; partial never means success.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/data, src/indodax_lab/cli`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

Typed loaders -> recomputed sentry decisions -> fixed cutoff -> immutable snapshot with 45 source references.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/universe/lineage.py`
- `src/indodax_lab/universe/materializer.py`
- `tests/integration/lab/test_raw_to_silver_pipeline.py`
- `tests/regression/test_phase1_snapshot.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/04-market-data-and-provenance.md`; exact table schemas use the Required Reading dataset contract.

Typed loaders -> recomputed sentry decisions -> fixed cutoff -> immutable snapshot with 45 source references.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Raw bytes before parse; canonical typed schemas; immutable Parquet/manifest; partial never means success.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

Public provider contract must be checked against official documentation before active acquisition; offline fixture verification does not prove endpoint availability.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish DATA-06-AC0: Pipeline offline benar-benar menghubungkan wire sampai final snapshot melalui artifact yang diverifikasi. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `DATA-06-AC1`, build minimal fixture proving: Wire garbage atau event berbeda dari parse ditolak. Write `test_data_06_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `DATA-06-AC2`, build minimal fixture proving: Cap observation direkonstruksi dari body provider. Write `test_data_06_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `DATA-06-AC3`, build minimal fixture proving: Dua root berbeda memberi snapshot dan global decision ID identik. Write `test_data_06_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **DATA-06-AC0**, `test_data_06_valid_contract` — Pipeline offline benar-benar menghubungkan wire sampai final snapshot melalui artifact yang diverifikasi. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| DATA-06-AC1 | `test_data_06_contract_1` | Wire garbage atau event berbeda dari parse ditolak |
| DATA-06-AC2 | `test_data_06_contract_2` | Cap observation direkonstruksi dari body provider |
| DATA-06-AC3 | `test_data_06_contract_3` | Dua root berbeda memberi snapshot dan global decision ID identik |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

Historical DONE: these names describe required behavior mapping, not newly executed test functions. Find actual tests in the listed baseline files and evidence before reopening.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Wire garbage atau event berbeda dari parse ditolak. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Cap observation direkonstruksi dari body provider. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Dua root berbeda memberi snapshot dan global decision ID identik. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Treat JSON and paths as untrusted. Bounded payloads, reject symlink escape, never persist secret request headers.

Trust boundary assessment: untrusted provider/artifact input or privileged state mutation exists; require negative tests and redacted diagnostics.

## Concurrency / Idempotency

One writer per partition; only checkpoint durable data. Verify bytes on retry; conflicting hash fails closed.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `DATA-06` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Quarantine failed content; recover from verified wire; never repair prices with zero or overwrite existing partition.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **DATA-06-AC0** Pipeline offline benar-benar menghubungkan wire sampai final snapshot melalui artifact yang diverifikasi. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **DATA-06-AC1** Wire garbage atau event berbeda dari parse ditolak. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **DATA-06-AC2** Cap observation direkonstruksi dari body provider. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **DATA-06-AC3** Dua root berbeda memberi snapshot dan global decision ID identik. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Wire garbage atau event berbeda dari parse ditolak. Inspect fixture and actual production path.
- Attempt to disprove: Cap observation direkonstruksi dari body provider. Inspect fixture and actual production path.
- Attempt to disprove: Dua root berbeda memberi snapshot dan global decision ID identik. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/data-06-provider-derived-reproducible-snapshot`. Commit: `fix(data-06): provider-derived reproducible snapshot` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/DATA-06-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: FEAT-01, SIM-03, LOB-01, OPS-02. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement DATA-06 only: Provider-derived reproducible snapshot.
Read AGENTS.md, docs/sprints/market-data/DATA-06-provider-derived-reproducible-snapshot.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Pipeline offline benar-benar menghubungkan wire sampai final snapshot melalui artifact yang diverifikasi.
Contract: Typed loaders -> recomputed sentry decisions -> fixed cutoff -> immutable snapshot with 45 source references.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
