# LABEL-01 — Execution-aligned net return labels

## Metadata

Status: CHANGES_REQUESTED

Priority: P0 | Type: data | Domain: labels | Portfolio: CORE

Implementation Owner: `Antigravity` | Independent Reviewer: `/root/docs_review`

Recommended Branch: `feat/label-01-execution-aligned-net-return-labels`

Requirements: FR-07 | Legacy tasks: 16

External gates: Unknown/unverified historical tariff intervals remain excluded and block affected net-performance claims/promotion. This sprint does not qualify full strategy PnL or production fills.

Implementation artifacts named below are implemented on the current review candidate; independent exact-SHA review is pending. Sprint status remains CHANGES_REQUESTED until reviewer PASS is recorded in the manifest.

## Goal

Candidate-sized fixed-horizon outcome derives from shared simulator fills and costs; it is not full SL/TP strategy PnL.

## Why This Sprint Exists

Without this capability, downstream cannot rely on verified execution-aligned labels. Contract: candidate bundle + sample-specific `SignalIntent` + horizon -> actual simulator entry/exit fills, costs and label availability.

Direct consumers: LABEL-02. New labels bind candidate bundle, sample-specific candidate sizing intent and a fixed horizon outcome using the shared simulator.

## Depends On

- FEAT-04 — Immutable feature materialization
- SIM-01 — Conservative execution simulator

## Unlocks

LABEL-02

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/09-labels-splits-and-training-data.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`
- `docs/research/dataset-feature-contracts.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency FEAT-04 supplies: snapshot IDs + registry hash -> features manifest, ordered columns, row_ready_at, eligibility.
- Dependency SIM-01 supplies: SignalIntent + market + schedule -> REJECTED/PARTIAL/FILLED; next-open, precision, SL_FIRST, latency.

## In Scope

- New materialization `net_return_candidate_horizon_v2` measures candidate-specific net proceeds relative to gross cash debit from the shared execution model.
- Every sample carries immutable `candidate_bundle_id` and candidate-generated `SignalIntent`; `desired_qty` is candidate strategy sizing for that sample.
- The target sells actual entry-filled quantity at the configured horizon; it is not full strategy PnL and ignores candidate SL/TP triggers.
- Candidate, intent and sample lineage must match; entry before decision is rejected.
- Horizon tidak lengkap tidak menjadi label nol.
- Cost schedule atau fill unavailable menghasilkan excluded sample.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: LABEL-02.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `LABEL-01` dan dependency evidence yang valid, when owning component dijalankan, then target return mengukur net proceeds relatif terhadap gross cash debit dari execution model yang sama.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **LABEL-01-FR0:** Candidate-sized fixed-horizon net outcome derives from actual shared simulator fills and costs.
1. **LABEL-01-FR1:** Candidate, intent and sample lineage match; entry before decision is rejected.
2. **LABEL-01-FR2:** Horizon tidak lengkap tidak menjadi label nol.
3. **LABEL-01-FR3:** Cost schedule atau fill unavailable menghasilkan excluded sample.

## Domain Rules / Invariants

sample + candidate bundle + candidate `SignalIntent` + horizon + shared fill model -> entry/exit fills, gross/net return, costs and label_available_at.

Reuse `ConservativeExecutionSimulator` for BUY entry and SELL at horizon. No fixed-size/proxy fallback and no silent rescaling. Bind candidate, strategy, pair, decision timestamp and sample lineage. No entry fill, no exit fill, or incomplete exit is `EXCLUDED` with a stable reason. Partial entry uses actual filled quantity only when the horizon SELL closes it fully. Candidate SL/TP are not executed for this fixed-horizon target. Existing `net_return_v1` artifacts remain immutable; v2 has distinct config/materialization identity. Pin v2 to the simulator's supported execution version (`causal-bar-proxy-v2`, verify at implementation). Unknown tariff provenance remains excluded.

Store label_end_ts, candidate bundle ID, intent ID, actual entry/exit fills, costs/execution IDs and exclusion reason; assignment table per sample; purge overlaps and embargo. V2 materialization never overwrites v1.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/labels, cli/build_training_dataset.py`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

candidate bundle + sample-specific `SignalIntent` + horizon -> shared simulator fills, gross/net return, costs and label_available_at.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/labels/returns.py`
- `configs/labels/net_return_candidate_horizon_v2.yaml`
- `tests/unit/lab/labels/test_returns.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/09-labels-splits-and-training-data.md`; exact table schemas use the Required Reading dataset contract.

sample + horizon + fill model -> entry/exit, gross/net return, costs and label_available_at.

Input harus membawa sample, candidate bundle ID, frozen candidate `SignalIntent`, horizon, cost schedule dan versi eksekusi yang didukung. Output memisahkan hasil valid, excluded dengan reason code, blocked, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Store label_end_ts, candidate bundle ID, intent ID, actual entry/exit fills, costs/execution IDs and exclusion reason; assignment table per sample; purge overlaps and embargo. New output is versioned `net_return_candidate_horizon_v2`; do not overwrite or reinterpret v1 artifacts.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

LABEL-01-AC0 is implemented: candidate-specific `SignalIntent` is priced through the shared simulator at entry and fixed horizon exit, and net return derives from actual fills/costs. Baseline review reproduced zero-depth bars yielding VALID while the simulator rejected the fill; regression coverage now exercises missing liquidity against the shared simulator.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `LABEL-01-AC1`, prove candidate bundle/intent/sample lineage and decision-time match; reject mismatches. Write a mapped test and observe behavioral RED, then GREEN.
3. For `LABEL-01-AC2`, build minimal fixture proving: Horizon tidak lengkap tidak menjadi label nol. Write `test_label_01_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `LABEL-01-AC3`, prove unavailable cost, no entry fill, no exit fill, and partially unclosed horizon exit all produce explicit EXCLUDED outcomes; partial entry is valid only when actual filled quantity is fully exited. Observe behavioral RED, then GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **LABEL-01-AC0**, `test_label_01_valid_contract` — candidate-sized fixed-horizon net outcome derives from actual shared simulator fills/costs and is separate from SL/TP PnL. Prove valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| LABEL-01-AC1 | candidate lineage/causality contract test | Candidate bundle, strategy, pair, decision time and intent match; entry before decision is rejected |
| LABEL-01-AC2 | `test_label_01_contract_2` | Horizon tidak lengkap tidak menjadi label nol |
| LABEL-01-AC3 | simulator fill exclusion contract tests | Unknown cost, no entry/exit fill or incomplete exit is EXCLUDED; no silent rescaling |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Entry sebelum decision ditolak. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Horizon tidak lengkap tidak menjadi label nol. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Unknown cost, no entry/exit fill or incomplete exit yields excluded sample. Expected behavior is this assertion; never fall through to success.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Sealed data access logged; user-facing report must not expose sealed metrics before approved gate.

Trust boundary assessment: untrusted provider/artifact input or privileged state mutation exists; require negative tests and redacted diagnostics.

## Concurrency / Idempotency

Immutable sample IDs; duplicate joins rejected; split table created once for registered version.

## Performance Constraints

Pure/rolling feature workloads: process sorted pair partitions with bounded context, avoid full cross product of timestamps × all raw events. Measure scaling against row/window count and validate chunk-boundary equality.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `LABEL-01` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Changed horizon/target/cost creates new materialization; exposed holdout cannot become sealed again.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **LABEL-01-AC0** `net_return_candidate_horizon_v2` binds candidate-specific sizing/identity and measures horizon outcome from actual shared BUY/SELL fills and fees; not full SL/TP strategy PnL. Evidence: `test_candidate_horizon_v2_uses_actual_candidate_size_and_shared_fills`.
- [ ] **LABEL-01-AC1** Candidate bundle, intent, pair, strategy, sample and decision-time lineage match; mismatches reject/exclude before output. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **LABEL-01-AC2** Horizon tidak lengkap tidak menjadi label nol. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **LABEL-01-AC3** Unknown cost, no entry/exit fill, or an exit that fails to close the actual entry quantity yields EXCLUDED with reason. Partial entry may be included only if actual filled quantity is fully exited. Evidence: v2 missing/unverified-cost, missing-liquidity, partial-entry, partial-exit and incomplete-horizon tests.
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

- Attempt to disprove: Entry sebelum decision ditolak. Inspect fixture and actual production path.
- Attempt to disprove: Horizon tidak lengkap tidak menjadi label nol. Inspect fixture and actual production path.
- Attempt to disprove: Missing cost/fill or incomplete exit is excluded. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/label-01-execution-aligned-net-return-labels`. Commit: `feat(label-01): execution-aligned net return labels` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/LABEL-01-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: LABEL-02. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement LABEL-01 only: Execution-aligned net return labels.
Read AGENTS.md, docs/sprints/labels/LABEL-01-execution-aligned-net-return-labels.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Candidate-sized fixed-horizon outcome from shared simulator fills/costs, distinct from full SL/TP PnL.
Contract: candidate bundle + sample-specific `SignalIntent` + horizon -> entry/exit fills, gross/net return, costs and label_available_at.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
