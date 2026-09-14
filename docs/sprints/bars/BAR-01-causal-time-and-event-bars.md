# BAR-01 — Causal time and event bars

## Metadata

Status: DONE

Priority: P0 | Type: data | Domain: bars | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/bar-01-causal-time-and-event-bars`

Requirements: FR-04 | Legacy tasks: 13

External gates: No additional portfolio activation gate; data/policy validity still applies.

Historical import; no fresh runtime test claim.

## Goal

Time bar dan event bar mempertahankan session, threshold, boundary dan availability lineage.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `BAR-01` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: PASS trades + continuity + fixed/train-only threshold -> separate bar_type datasets, end-exclusive windows.

Direct consumers: DATA-06, SIM-01

## Depends On

- DATA-04 — Snapshot quality decisions
- DATA-05 — Reliable forward market collection

## Unlocks

DATA-06, SIM-01

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/06-bars-and-session-continuity.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`
- `docs/research/dataset-feature-contracts.md`

## Current Context

Existing committed implementation; preserve and reverify only when affected.

- Dependency DATA-04 supplies: validate_snapshot(snapshot, coverage, as_of) -> canonical quality report, CLI exit 0/3/4.
- Dependency DATA-05 supplies: DISCONNECTED -> SYNCING -> RELIABLE; gap -> GAP -> RECOVERING; bounded durable writer.

## In Scope

- Time bar dan event bar mempertahankan session, threshold, boundary dan availability lineage.
- Threshold available setelah event ditolak.
- Session gap tidak boleh disebrangi event bar.
- Seluruh official file divalidasi sebelum filter interval.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: DATA-06, SIM-01.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `BAR-01` dan dependency evidence yang valid, when owning component dijalankan, then time bar dan event bar mempertahankan session, threshold, boundary dan availability lineage.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **BAR-01-FR0:** Time bar dan event bar mempertahankan session, threshold, boundary dan availability lineage.
1. **BAR-01-FR1:** Threshold available setelah event ditolak.
2. **BAR-01-FR2:** Session gap tidak boleh disebrangi event bar.
3. **BAR-01-FR3:** Seluruh official file divalidasi sebelum filter interval.

## Domain Rules / Invariants

PASS trades + continuity + fixed/train-only threshold -> separate bar_type datasets, end-exclusive windows.

End-exclusive windows, session continuity, threshold and artifact lineage, official anchor validates whole input.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/data/bars.py, event_bars.py, cli/build_bars.py`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

PASS trades + continuity + fixed/train-only threshold -> separate bar_type datasets, end-exclusive windows.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/data/bars.py`
- `src/indodax_lab/data/event_bars.py`
- `src/indodax_lab/cli/build_bars.py`
- `tests/unit/lab/data/test_event_bars.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/06-bars-and-session-continuity.md`; exact table schemas use the Required Reading dataset contract.

PASS trades + continuity + fixed/train-only threshold -> separate bar_type datasets, end-exclusive windows.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

End-exclusive windows, session continuity, threshold and artifact lineage, official anchor validates whole input.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish BAR-01-AC0: Time bar dan event bar mempertahankan session, threshold, boundary dan availability lineage. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `BAR-01-AC1`, build minimal fixture proving: Threshold available setelah event ditolak. Write `test_bar_01_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `BAR-01-AC2`, build minimal fixture proving: Session gap tidak boleh disebrangi event bar. Write `test_bar_01_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `BAR-01-AC3`, build minimal fixture proving: Seluruh official file divalidasi sebelum filter interval. Write `test_bar_01_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **BAR-01-AC0**, `test_bar_01_valid_contract` — Time bar dan event bar mempertahankan session, threshold, boundary dan availability lineage. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| BAR-01-AC1 | `test_bar_01_contract_1` | Threshold available setelah event ditolak |
| BAR-01-AC2 | `test_bar_01_contract_2` | Session gap tidak boleh disebrangi event bar |
| BAR-01-AC3 | `test_bar_01_contract_3` | Seluruh official file divalidasi sebelum filter interval |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

Historical DONE: these names describe required behavior mapping, not newly executed test functions. Find actual tests in the listed baseline files and evidence before reopening.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Threshold available setelah event ditolak. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Session gap tidak boleh disebrangi event bar. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Seluruh official file divalidasi sebelum filter interval. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Normal mode consumes existing verified quality decision; it must not manufacture approval.

Trust boundary assessment: no new public authentication surface; verified local input remains mandatory and existing secret/PII controls apply.

## Concurrency / Idempotency

Deterministic sort; reject duplicate/conflicting events at batch gate. Output only after full source validation.

## Performance Constraints

Pure/rolling feature workloads: process sorted pair partitions with bounded context, avoid full cross product of timestamps × all raw events. Measure scaling against row/window count and validate chunk-boundary equality.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `BAR-01` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Rebuild new snapshot from durable events; no interpolation across gaps; fitted threshold cannot travel backward in time.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **BAR-01-AC0** Time bar dan event bar mempertahankan session, threshold, boundary dan availability lineage. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **BAR-01-AC1** Threshold available setelah event ditolak. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **BAR-01-AC2** Session gap tidak boleh disebrangi event bar. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **BAR-01-AC3** Seluruh official file divalidasi sebelum filter interval. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Threshold available setelah event ditolak. Inspect fixture and actual production path.
- Attempt to disprove: Session gap tidak boleh disebrangi event bar. Inspect fixture and actual production path.
- Attempt to disprove: Seluruh official file divalidasi sebelum filter interval. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/bar-01-causal-time-and-event-bars`. Commit: `fix(bar-01): causal time and event bars` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/BAR-01-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: DATA-06, SIM-01. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement BAR-01 only: Causal time and event bars.
Read AGENTS.md, docs/sprints/bars/BAR-01-causal-time-and-event-bars.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Time bar dan event bar mempertahankan session, threshold, boundary dan availability lineage.
Contract: PASS trades + continuity + fixed/train-only threshold -> separate bar_type datasets, end-exclusive windows.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
