# L01-01 — DeepLOB baseline

## Metadata

Status: REVIEW

Priority: P2 | Type: research | Domain: microstructure | Portfolio: EXPERIMENTAL

Implementation Owner: Antigravity | Independent Reviewer: PENDING

Recommended Branch: `feat/l01-01-deeplob-baseline`

Requirements: FR-14 | Legacy tasks: 31

External gates: Portfolio backlog activation by owner; not in default scheduler; Measured Lenovo resource admission; actual data eligibility evidence for research runs

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

DeepLOB mengukur short-horizon edge setelah spread dan latency melalui book dataset terverifikasi.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `L01-01` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: LOB tensor + spread-aware label -> forecast and common execution mapper.

Direct consumers: L02-01

## Depends On

- LOB-01 — Forward book dataset eligibility
- D01-01 — Tabular MLP baseline

## Unlocks

L02-01

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/16-order-book-research.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`
- `docs/research/dataset-feature-contracts.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency LOB-01 supplies: continuous raw books -> depth/imbalance tensors with >=90 day coverage gate plus sample/regime report.
- Dependency D01-01 supplies: same feature rows + <=12 configs -> nonlinear baseline forecast via common mapper.

## In Scope

- DeepLOB mengukur short-horizon edge setelah spread dan latency melalui book dataset terverifikasi.
- Mid-price accuracy tinggi belum berarti net profitable.
- Gapped book blocks run.
- Baseline MLP memakai sample identik.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: L02-01.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `L01-01` dan dependency evidence yang valid, when owning component dijalankan, then deepLOB mengukur short-horizon edge setelah spread dan latency melalui book dataset terverifikasi.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **L01-01-FR0:** DeepLOB mengukur short-horizon edge setelah spread dan latency melalui book dataset terverifikasi.
1. **L01-01-FR1:** Mid-price accuracy tinggi belum berarti net profitable.
2. **L01-01-FR2:** Gapped book blocks run.
3. **L01-01-FR3:** Baseline MLP memakai sample identik.

## Domain Rules / Invariants

LOB tensor + spread-aware label -> forecast and common execution mapper.

>=90 days PASS coverage plus effective samples/regimes; full book/trade inputs, not candles; latency labels.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/models/lob, features/lob.py`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

LOB tensor + spread-aware label -> forecast and common execution mapper.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/models/lob/l01_deeplob.py`
- `tests/integration/lab/test_deeplob_smoke.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/16-order-book-research.md`; exact table schemas use the Required Reading dataset contract.

LOB tensor + spread-aware label -> forecast and common execution mapper.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

>=90 days PASS coverage plus effective samples/regimes; full book/trade inputs, not candles; latency labels.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish L01-01-AC0: DeepLOB mengukur short-horizon edge setelah spread dan latency melalui book dataset terverifikasi. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `L01-01-AC1`, build minimal fixture proving: Mid-price accuracy tinggi belum berarti net profitable. Write `test_l01_01_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `L01-01-AC2`, build minimal fixture proving: Gapped book blocks run. Write `test_l01_01_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `L01-01-AC3`, build minimal fixture proving: Baseline MLP memakai sample identik. Write `test_l01_01_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **L01-01-AC0**, `test_l01_01_valid_contract` — DeepLOB mengukur short-horizon edge setelah spread dan latency melalui book dataset terverifikasi. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| L01-01-AC1 | `test_l01_01_contract_1` | Mid-price accuracy tinggi belum berarti net profitable |
| L01-01-AC2 | `test_l01_01_contract_2` | Gapped book blocks run |
| L01-01-AC3 | `test_l01_01_contract_3` | Baseline MLP memakai sample identik |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Mid-price accuracy tinggi belum berarti net profitable. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Gapped book blocks run. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Baseline MLP memakai sample identik. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Reject corrupted/unreliable session; acquired data and model license validated; no guarantee of maker fill.

Trust boundary assessment: no new public authentication surface; verified local input remains mandatory and existing secret/PII controls apply.

## Concurrency / Idempotency

Bounded tensor windows never cross gap; immutable session IDs and event ordering.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `L01-01` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Gap invalidates affected window; restart from verified book snapshot; model outputs remain blocked until data gate.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **L01-01-AC0** DeepLOB mengukur short-horizon edge setelah spread dan latency melalui book dataset terverifikasi. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **L01-01-AC1** Mid-price accuracy tinggi belum berarti net profitable. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **L01-01-AC2** Gapped book blocks run. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **L01-01-AC3** Baseline MLP memakai sample identik. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Mid-price accuracy tinggi belum berarti net profitable. Inspect fixture and actual production path.
- Attempt to disprove: Gapped book blocks run. Inspect fixture and actual production path.
- Attempt to disprove: Baseline MLP memakai sample identik. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/l01-01-deeplob-baseline`. Commit: `feat(l01-01): deeplob baseline` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/L01-01-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: L02-01. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement L01-01 only: DeepLOB baseline.
Read AGENTS.md, docs/sprints/microstructure/L01-01-deeplob-baseline.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: DeepLOB mengukur short-horizon edge setelah spread dan latency melalui book dataset terverifikasi.
Contract: LOB tensor + spread-aware label -> forecast and common execution mapper.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
