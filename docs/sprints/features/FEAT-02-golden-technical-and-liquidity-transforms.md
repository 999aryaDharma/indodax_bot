# FEAT-02 — Golden technical and liquidity transforms

## Metadata

Status: PLANNED

Priority: P0 | Type: data | Domain: features | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/feat-02-golden-technical-and-liquidity-transforms`

Requirements: FR-05 | Legacy tasks: 15

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Indikator continuous dan volume transforms menghasilkan nilai serta warmup yang dapat diaudit.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `FEAT-02` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: closed OHLCV -> normalized EMA RSI StochRSI MACD ATR ADX BB Donchian VWAP returns and liquidity features.

Direct consumers: FEAT-04

## Depends On

- FEAT-01 — Versioned feature registry

## Unlocks

FEAT-04

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/07-feature-engineering.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`
- `docs/research/dataset-feature-contracts.md`

## Current Context

Legacy Task 15 contains uncommitted WIP in original worktree; inspect registry/technical/liquidity and tests before reuse. No WIP has been imported into this docs branch; do not claim it verified.

- Dependency FEAT-01 supplies: registry YAML -> feature definitions and source hash; exact contracted names after expansion.

## In Scope

- Indikator continuous dan volume transforms menghasilkan nilai serta warmup yang dapat diaudit.
- Golden expected dihitung independen dengan toleransi eksplisit.
- Flat price atau zero-volume tidak menghasilkan infinity.
- Ubah future bar tidak mengubah fitur masa lalu.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: FEAT-04.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `FEAT-02` dan dependency evidence yang valid, when owning component dijalankan, then indikator continuous dan volume transforms menghasilkan nilai serta warmup yang dapat diaudit.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **FEAT-02-FR0:** Indikator continuous dan volume transforms menghasilkan nilai serta warmup yang dapat diaudit.
1. **FEAT-02-FR1:** Golden expected dihitung independen dengan toleransi eksplisit.
2. **FEAT-02-FR2:** Flat price atau zero-volume tidak menghasilkan infinity.
3. **FEAT-02-FR3:** Ubah future bar tidak mengubah fitur masa lalu.

## Domain Rules / Invariants

closed OHLCV -> normalized EMA RSI StochRSI MACD ATR ADX BB Donchian VWAP returns and liquidity features.

41 scalar Wave 1 names after expanding families; float64 features, Decimal source money; label tables separate.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/features, cli/build_features.py`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

closed OHLCV -> normalized EMA RSI StochRSI MACD ATR ADX BB Donchian VWAP returns and liquidity features.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/features/technical.py`
- `src/indodax_lab/features/liquidity.py`
- `tests/fixtures/features/golden_ohlcv.csv`
- `tests/unit/lab/features/test_technical.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/07-feature-engineering.md`; exact table schemas use the Required Reading dataset contract.

closed OHLCV -> normalized EMA RSI StochRSI MACD ATR ADX BB Donchian VWAP returns and liquidity features.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

41 scalar Wave 1 names after expanding families; float64 features, Decimal source money; label tables separate.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish FEAT-02-AC0: Indikator continuous dan volume transforms menghasilkan nilai serta warmup yang dapat diaudit. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `FEAT-02-AC1`, build minimal fixture proving: Golden expected dihitung independen dengan toleransi eksplisit. Write `test_feat_02_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `FEAT-02-AC2`, build minimal fixture proving: Flat price atau zero-volume tidak menghasilkan infinity. Write `test_feat_02_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `FEAT-02-AC3`, build minimal fixture proving: Ubah future bar tidak mengubah fitur masa lalu. Write `test_feat_02_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **FEAT-02-AC0**, `test_feat_02_valid_contract` — Indikator continuous dan volume transforms menghasilkan nilai serta warmup yang dapat diaudit. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| FEAT-02-AC1 | `test_feat_02_contract_1` | Golden expected dihitung independen dengan toleransi eksplisit |
| FEAT-02-AC2 | `test_feat_02_contract_2` | Flat price atau zero-volume tidak menghasilkan infinity |
| FEAT-02-AC3 | `test_feat_02_contract_3` | Ubah future bar tidak mengubah fitur masa lalu |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Golden expected dihitung independen dengan toleransi eksplisit. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Flat price atau zero-volume tidak menghasilkan infinity. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Ubah future bar tidak mengubah fitur masa lalu. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

No future rows or labels in inference view; public registry config validated; reject arbitrary callable import from user input.

Trust boundary assessment: no new public authentication surface; verified local input remains mandatory and existing secret/PII controls apply.

## Concurrency / Idempotency

Compute partition by pair/time with sufficient overlap context; publish once. Cross-sectional joins use same decision timestamp.

## Performance Constraints

Pure/rolling feature workloads: process sorted pair partitions with bounded context, avoid full cross product of timestamps × all raw events. Measure scaling against row/window count and validate chunk-boundary equality.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `FEAT-02` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Version every semantic change; retain old features for reproducibility; no bfill or silent zero imputation.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **FEAT-02-AC0** Indikator continuous dan volume transforms menghasilkan nilai serta warmup yang dapat diaudit. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **FEAT-02-AC1** Golden expected dihitung independen dengan toleransi eksplisit. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **FEAT-02-AC2** Flat price atau zero-volume tidak menghasilkan infinity. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **FEAT-02-AC3** Ubah future bar tidak mengubah fitur masa lalu. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Golden expected dihitung independen dengan toleransi eksplisit. Inspect fixture and actual production path.
- Attempt to disprove: Flat price atau zero-volume tidak menghasilkan infinity. Inspect fixture and actual production path.
- Attempt to disprove: Ubah future bar tidak mengubah fitur masa lalu. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/feat-02-golden-technical-and-liquidity-transforms`. Commit: `feat(feat-02): golden technical and liquidity transforms` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/FEAT-02-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: FEAT-04. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement FEAT-02 only: Golden technical and liquidity transforms.
Read AGENTS.md, docs/sprints/features/FEAT-02-golden-technical-and-liquidity-transforms.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Indikator continuous dan volume transforms menghasilkan nilai serta warmup yang dapat diaudit.
Contract: closed OHLCV -> normalized EMA RSI StochRSI MACD ATR ADX BB Donchian VWAP returns and liquidity features.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
