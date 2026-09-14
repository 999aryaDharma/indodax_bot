# DATA-05 — Reliable forward market collection

## Metadata

Status: DONE

Priority: P0 | Type: integration | Domain: market-data | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/data-05-reliable-forward-market-collection`

Requirements: FR-02 | Legacy tasks: 11

External gates: No additional portfolio activation gate; data/policy validity still applies.

Historical import; no fresh runtime test claim.

## Goal

Collector mempertahankan bukti sequence gap dan reconnect tanpa menganggap event hilang sebagai normal.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `DATA-05` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: DISCONNECTED -> SYNCING -> RELIABLE; gap -> GAP -> RECOVERING; bounded durable writer.

Direct consumers: UNIV-01, BAR-01, SHADOW-01

## Depends On

- DATA-02 — Durable immutable publication

## Unlocks

UNIV-01, BAR-01, SHADOW-01

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/04-market-data-and-provenance.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

Existing committed implementation; preserve and reverify only when affected.

- Dependency DATA-02 supplies: Arrow explicit schema + ZSTD + partial/fsync/rename + canonical checksum manifest.

## In Scope

- Collector mempertahankan bukti sequence gap dan reconnect tanpa menganggap event hilang sebagai normal.
- Normal close memicu reconnect dengan stream identity benar.
- Pending gap dipertahankan sampai quarantine durable.
- SIGTERM menutup transport dan flush dengan checkpoint setelah durable write.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: UNIV-01, BAR-01, SHADOW-01.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `DATA-05` dan dependency evidence yang valid, when owning component dijalankan, then collector mempertahankan bukti sequence gap dan reconnect tanpa menganggap event hilang sebagai normal.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **DATA-05-FR0:** Collector mempertahankan bukti sequence gap dan reconnect tanpa menganggap event hilang sebagai normal.
1. **DATA-05-FR1:** Normal close memicu reconnect dengan stream identity benar.
2. **DATA-05-FR2:** Pending gap dipertahankan sampai quarantine durable.
3. **DATA-05-FR3:** SIGTERM menutup transport dan flush dengan checkpoint setelah durable write.

## Domain Rules / Invariants

DISCONNECTED -> SYNCING -> RELIABLE; gap -> GAP -> RECOVERING; bounded durable writer.

Raw bytes before parse; canonical typed schemas; immutable Parquet/manifest; partial never means success.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/data, src/indodax_lab/cli`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

DISCONNECTED -> SYNCING -> RELIABLE; gap -> GAP -> RECOVERING; bounded durable writer.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/data/indodax_stream.py`
- `src/indodax_lab/data/book_recovery.py`
- `src/indodax_lab/cli/collect_market_stream.py`
- `tests/unit/lab/data/test_book_recovery.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/04-market-data-and-provenance.md`; exact table schemas use the Required Reading dataset contract.

DISCONNECTED -> SYNCING -> RELIABLE; gap -> GAP -> RECOVERING; bounded durable writer.

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

First establish DATA-05-AC0: Collector mempertahankan bukti sequence gap dan reconnect tanpa menganggap event hilang sebagai normal. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `DATA-05-AC1`, build minimal fixture proving: Normal close memicu reconnect dengan stream identity benar. Write `test_data_05_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `DATA-05-AC2`, build minimal fixture proving: Pending gap dipertahankan sampai quarantine durable. Write `test_data_05_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `DATA-05-AC3`, build minimal fixture proving: SIGTERM menutup transport dan flush dengan checkpoint setelah durable write. Write `test_data_05_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **DATA-05-AC0**, `test_data_05_valid_contract` — Collector mempertahankan bukti sequence gap dan reconnect tanpa menganggap event hilang sebagai normal. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| DATA-05-AC1 | `test_data_05_contract_1` | Normal close memicu reconnect dengan stream identity benar |
| DATA-05-AC2 | `test_data_05_contract_2` | Pending gap dipertahankan sampai quarantine durable |
| DATA-05-AC3 | `test_data_05_contract_3` | SIGTERM menutup transport dan flush dengan checkpoint setelah durable write |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

Historical DONE: these names describe required behavior mapping, not newly executed test functions. Find actual tests in the listed baseline files and evidence before reopening.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Normal close memicu reconnect dengan stream identity benar. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Pending gap dipertahankan sampai quarantine durable. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: SIGTERM menutup transport dan flush dengan checkpoint setelah durable write. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
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

Emit `DATA-05` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Quarantine failed content; recover from verified wire; never repair prices with zero or overwrite existing partition.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **DATA-05-AC0** Collector mempertahankan bukti sequence gap dan reconnect tanpa menganggap event hilang sebagai normal. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **DATA-05-AC1** Normal close memicu reconnect dengan stream identity benar. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **DATA-05-AC2** Pending gap dipertahankan sampai quarantine durable. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **DATA-05-AC3** SIGTERM menutup transport dan flush dengan checkpoint setelah durable write. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Normal close memicu reconnect dengan stream identity benar. Inspect fixture and actual production path.
- Attempt to disprove: Pending gap dipertahankan sampai quarantine durable. Inspect fixture and actual production path.
- Attempt to disprove: SIGTERM menutup transport dan flush dengan checkpoint setelah durable write. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/data-05-reliable-forward-market-collection`. Commit: `fix(data-05): reliable forward market collection` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/DATA-05-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: UNIV-01, BAR-01, SHADOW-01. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement DATA-05 only: Reliable forward market collection.
Read AGENTS.md, docs/sprints/market-data/DATA-05-reliable-forward-market-collection.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Collector mempertahankan bukti sequence gap dan reconnect tanpa menganggap event hilang sebagai normal.
Contract: DISCONNECTED -> SYNCING -> RELIABLE; gap -> GAP -> RECOVERING; bounded durable writer.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
