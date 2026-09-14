# UNIV-01 — Point-in-time investable universe

## Metadata

Status: DONE

Priority: P0 | Type: data | Domain: universe | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/univ-01-point-in-time-investable-universe`

Requirements: FR-03 | Legacy tasks: 12

External gates: No additional portfolio activation gate; data/policy validity still applies.

Historical import; no fresh runtime test claim.

## Goal

Universe pada tanggal tertentu memakai hanya listing, cap dan likuiditas yang tersedia saat itu.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `UNIV-01` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: as_of + availability cutoff + provider response -> BIG_CAP/SMALL_CAP/LIQUIDITY_ONLY and exclusion reasons.

Direct consumers: DATA-06

## Depends On

- DATA-04 — Snapshot quality decisions
- DATA-05 — Reliable forward market collection

## Unlocks

DATA-06

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/05-point-in-time-universe.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`
- `docs/research/dataset-feature-contracts.md`

## Current Context

Existing committed implementation; preserve and reverify only when affected.

- Dependency DATA-04 supplies: validate_snapshot(snapshot, coverage, as_of) -> canonical quality report, CLI exit 0/3/4.
- Dependency DATA-05 supplies: DISCONNECTED -> SYNCING -> RELIABLE; gap -> GAP -> RECOVERING; bounded durable writer.

## In Scope

- Universe pada tanggal tertentu memakai hanya listing, cap dan likuiditas yang tersedia saat itu.
- Current-only cap tidak menjadi historical cap.
- Delisting tidak menghapus histori.
- TTL memakai timestamp konsisten dan future payload ditolak.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: DATA-06.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `UNIV-01` dan dependency evidence yang valid, when owning component dijalankan, then universe pada tanggal tertentu memakai hanya listing, cap dan likuiditas yang tersedia saat itu.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **UNIV-01-FR0:** Universe pada tanggal tertentu memakai hanya listing, cap dan likuiditas yang tersedia saat itu.
1. **UNIV-01-FR1:** Current-only cap tidak menjadi historical cap.
2. **UNIV-01-FR2:** Delisting tidak menghapus histori.
3. **UNIV-01-FR3:** TTL memakai timestamp konsisten dan future payload ditolak.

## Domain Rules / Invariants

as_of + availability cutoff + provider response -> BIG_CAP/SMALL_CAP/LIQUIDITY_ONLY and exclusion reasons.

Listing/provider identity and availability join; unknown historical cap yields LIQUIDITY_ONLY. Delisted history retained.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/universe`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

as_of + availability cutoff + provider response -> BIG_CAP/SMALL_CAP/LIQUIDITY_ONLY and exclusion reasons.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/indodax_lab/universe/coingecko_adapter.py`
- `src/indodax_lab/universe/eligibility.py`
- `src/indodax_lab/universe/snapshot.py`
- `tests/integration/lab/test_universe_snapshot.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/05-point-in-time-universe.md`; exact table schemas use the Required Reading dataset contract.

as_of + availability cutoff + provider response -> BIG_CAP/SMALL_CAP/LIQUIDITY_ONLY and exclusion reasons.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Listing/provider identity and availability join; unknown historical cap yields LIQUIDITY_ONLY. Delisted history retained.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

Public provider contract must be checked against official documentation before active acquisition; offline fixture verification does not prove endpoint availability.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

First establish UNIV-01-AC0: Universe pada tanggal tertentu memakai hanya listing, cap dan likuiditas yang tersedia saat itu. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `UNIV-01-AC1`, build minimal fixture proving: Current-only cap tidak menjadi historical cap. Write `test_univ_01_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `UNIV-01-AC2`, build minimal fixture proving: Delisting tidak menghapus histori. Write `test_univ_01_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `UNIV-01-AC3`, build minimal fixture proving: TTL memakai timestamp konsisten dan future payload ditolak. Write `test_univ_01_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **UNIV-01-AC0**, `test_univ_01_valid_contract` — Universe pada tanggal tertentu memakai hanya listing, cap dan likuiditas yang tersedia saat itu. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| UNIV-01-AC1 | `test_univ_01_contract_1` | Current-only cap tidak menjadi historical cap |
| UNIV-01-AC2 | `test_univ_01_contract_2` | Delisting tidak menghapus histori |
| UNIV-01-AC3 | `test_univ_01_contract_3` | TTL memakai timestamp konsisten dan future payload ditolak |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

Historical DONE: these names describe required behavior mapping, not newly executed test functions. Find actual tests in the listed baseline files and evidence before reopening.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Current-only cap tidak menjadi historical cap. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Delisting tidak menghapus histori. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: TTL memakai timestamp konsisten dan future payload ditolak. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

External metadata untrusted; verify response and provider ID. Source time cannot substitute available time.

Trust boundary assessment: no new public authentication surface; verified local input remains mandatory and existing secret/PII controls apply.

## Concurrency / Idempotency

Snapshots immutable and content addressed. Retry same snapshot must reproduce same ID.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `UNIV-01` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Keep old snapshots referenced by runs; corrections become new version; never relabel historical tier silently.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **UNIV-01-AC0** Universe pada tanggal tertentu memakai hanya listing, cap dan likuiditas yang tersedia saat itu. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [ ] **UNIV-01-AC1** Current-only cap tidak menjadi historical cap. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **UNIV-01-AC2** Delisting tidak menghapus histori. Evidence: mapped test, exact command/exit and target SHA.
- [ ] **UNIV-01-AC3** TTL memakai timestamp konsisten dan future payload ditolak. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Current-only cap tidak menjadi historical cap. Inspect fixture and actual production path.
- Attempt to disprove: Delisting tidak menghapus histori. Inspect fixture and actual production path.
- Attempt to disprove: TTL memakai timestamp konsisten dan future payload ditolak. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/univ-01-point-in-time-investable-universe`. Commit: `fix(univ-01): point-in-time investable universe` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/UNIV-01-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: DATA-06. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement UNIV-01 only: Point-in-time investable universe.
Read AGENTS.md, docs/sprints/universe/UNIV-01-point-in-time-investable-universe.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Universe pada tanggal tertentu memakai hanya listing, cap dan likuiditas yang tersedia saat itu.
Contract: as_of + availability cutoff + provider response -> BIG_CAP/SMALL_CAP/LIQUIDITY_ONLY and exclusion reasons.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
