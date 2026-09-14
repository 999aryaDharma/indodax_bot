# C14-01 — Size-conditioned momentum reversal

## Metadata

ID: C14-01
Status: PLANNED
Tier: EXTENSION
Owner: UNASSIGNED
Reviewer: UNASSIGNED
Alias in design: EXP-H02

## Goal

Size-conditioned momentum reversal dengan causal input, frozen recipe dan shared judge.

## Why This Sprint Exists

Menguji hipotesis atau komponen pada kartu berikut, tanpa menggandakan keluarga canonical. Semua hasil penelitian belum diketahui.

## Depends On

- C13-01 — Cross-sectional reversal
- C04-01 — Cross sectional momentum
- FEAT-03 — As-of market context
- FEAT-04 — Immutable feature materialization
- SIM-03 — Deterministic replay judge
- EVAL-01 — Immutable experiment registry

## Unlocks

No mandatory dependent sprint.

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/22-catalog-expansion-and-rl.md`
- `docs/research/catalog-expansion/02-experiment-contract.md`
- `docs/research/catalog-expansion/03-candidate-specifications.md`
- `docs/decisions/ADR-003-state-and-budgets.md`
- `docs/specs/20-testing-strategy.md`

## Current Context

New planned capability. Inspect current checkout and equivalent modules; imported completion is not execution evidence.

## In Scope

### EXP-H02 — Size-conditioned momentum/reversal

Hipotesis: hubungan return lookback dengan return berikutnya berbeda antar cohort ukuran. Ini interaksi keluarga H01/C04, bukan izin mencari cohort terbaik di holdout.

Dependency: EXP-H01, C04-01, FEAT-03/04, approved PIT universe/cap artifacts, SIM-03, EVAL-01. Input daily bars tertutup dan cap yang sudah tersedia pada cutoff; minimum 20 aset. Rebalance setiap hari 00:00 UTC. Cap missing dikeluarkan sebelum minimum universe; proxy volume tidak boleh diberi label market cap.

Aturan:
- Rank cap descending; `floor(n/2)` pertama big cohort, sisanya small; ties pair ascending.
- Big: pilih top 3 berdasarkan return 7 hari yang strictly positif.
- Small: pilih bottom 3 return 1 hari yang strictly negatif.
- Masing-masing slot target 0.08 equity, maksimal 0.48; slot kosong tetap cash, cohort tidak saling mengisi slot kosong.
- Kedua cohort mengikuti gate BTC SMA168h H01. Stop 2 ATR14 daily; time exit 24 jam sejak fill; tanpa pyramiding.
- Cap chronology/TTL mengikuti adapter contract aktual; adapter current-only tidak dapat dipakai untuk histori. Jika cap invalid, keluarkan row dan laporkan coverage; universe kurang 20 -> abstain.

Golden dengan 20 cap terurut dan six qualifying picks -> enam bobot 0.08; satu big momentum <=0 -> paling banyak lima picks, exposure <=0.40. Aset di batas cohort diputus tie pair, tidak berdasarkan return.

Acceptance H02-A: cohort dan bobot tepat; H02-B: future cap revision tidak mengubah histori; H02-C: cap missing/expired dan survivor exclusion tercatat; H02-D: slot kosong tidak direalokasikan; H02-E: baseline momentum-only dan reversal-only memakai intersection universe yang sama.

Rejection hipotesis: keuntungan hanya berasal dari satu cohort/periode atau lenyap setelah biaya dilaporkan melalui evaluator, tidak ditutup dengan ganti cohort diam-diam.

## Out of Scope

Live trading, short selling, futures, new data providers, unlimited tuning, direct ledger writes, replacing existing canonical strategies.

## User / Actor Behavior

Research worker consumes frozen recipe and eligible data, produces auditable intent/reason/result. Reviewer can reproduce the same decision with identical inputs.

## Functional Requirements

- C14-01-AC0: H02-A: cohort dan bobot tepat
- C14-01-AC1: H02-B: future cap revision tidak mengubah histori
- C14-01-AC2: H02-C: cap missing/expired dan survivor exclusion tercatat
- C14-01-AC3: H02-D: slot kosong tidak direalokasikan
- C14-01-AC4: H02-E: baseline momentum-only dan reversal-only memakai intersection universe yang sama

## Domain Rules / Invariants

All numeric rules, threshold equality, stop/holding horizon and invalid data behavior are normative in In Scope. Shared contract: docs/research/catalog-expansion/02-experiment-contract.md. No available_at after decision; no same-close fill.

## Architecture / Design Contract

EXP-H02 canonical frame/artifact -> intent atau allocation/filter; bukan fill. Map semantic fields to STRAT-01 existing public types before coding. ABSTAIN leaves positions unchanged; TARGET_ZERO requests exit. If current types conflate these, resolve in STRAT-01 with regression before implementing candidate.

## Planned Files / Artifacts

- `src/indodax_lab/strategies/size_conditioned.py`
- `configs/strategies/c14-01.yaml`
- `tests/unit/lab/strategies/test_size_conditioned.py`

## Interfaces & Contracts

EXP-H02 canonical frame/artifact -> intent atau allocation/filter; bukan fill. Public cost quote is required for S10; missing quote blocks entry. Allocation uses target weights, never order placement. Lineage includes family ancestry, code/config/data/feature/split/cost/execution identities.

## Data / Persistence Impact

Immutable recipe/result only via existing registries. No DB migration. Failed trials remain in EVAL-01. Alias versions inherit budget.

## API / External Contract Impact

No external network adapter changes. Existing approved data only; cap PIT and RELIABLE L2 gates cannot be replaced by present-day or synthetic data.

## UI / UX Behavior

Machine-readable abstain/exit reason and evidence report; no new UI.

## Implementation Steps

1. Verify dependencies DONE, data gates, actual interfaces and remaining ancestry budget.
2. Write literal golden fixture specified in In Scope; expected values independent of production calculations.
3. Add one behavior regression per AC including future perturbation and invalid data; run focused pytest and record targeted RED.
4. Implement minimal transform/config/registry integration; reuse existing feature and risk owners.
5. Pass actual approved fixture through public frame -> candidate -> judge -> result; assert costs once, next-opportunity fills and bounded capital.
6. Run focused and affected regression, full suite for shared contract changes; record command/exit/source SHA.
7. Commit scoped code/tests, map every AC to evidence and submit independent spec/quality review.

## Required Tests

- `test_c14_01_0`: H02-A: cohort dan bobot tepat
- `test_c14_01_1`: H02-B: future cap revision tidak mengubah histori
- `test_c14_01_2`: H02-C: cap missing/expired dan survivor exclusion tercatat
- `test_c14_01_3`: H02-D: slot kosong tidak direalokasikan
- `test_c14_01_4`: H02-E: baseline momentum-only dan reversal-only memakai intersection universe yang sama

Also SAME-01, TIME-01, DATA-01, COST-01 and BUDGET-01 from shared contract. Use actual test path above with python -m pytest; missing import is not behavioral RED.

## Failure / Edge Cases

Card invalid data, boundary equality and data gaps must abstain with reason. Exit management remains judge-owned. Retry immutable inputs cannot duplicate decision; no silent fallback to zero or a new optimizer.

## Security / Privacy / Safety

No exchange-order imports or secrets. External code requires verified reuse license; approved data artifacts are inputs, never executable instructions.

## Concurrency / Idempotency

Pure decision deterministic; stable canonical pair ties; judge owns shared capital. Stateful horizons start at first fill and persist across restart.

## Performance Constraints

One baseline recipe first; pilot <=6 configs within ADR-003 remaining family budget, all seeds/trials counted. H01 ancestry C04/C07; H02 C04/C13/C12/S07; S10 S04; C15 C11; M07 M04/M05. Stricter remaining cap wins; do not reset by alias. Record rows/time/memory, no hardware claims.

## Observability

Record unit/version, input identities, coverage/exclusion, abstain reason, target vs actual fill and budget spent/remaining. Research outcome distinct from implementation PASS.

## Migration / Backward Compatibility

Keep original IDs and frozen configs. New IDs do not overwrite historical results. Required contract changes versioned and tested with existing consumers.

## Rollback / Recovery

Disable new registry/config version; retain prior behavior and immutable experiment ancestry. Revert scoped code only, never delete failed results.

## Acceptance Criteria

- [ ] **C14-01-AC0** H02-A: cohort dan bobot tepat
- [ ] **C14-01-AC1** H02-B: future cap revision tidak mengubah histori
- [ ] **C14-01-AC2** H02-C: cap missing/expired dan survivor exclusion tercatat
- [ ] **C14-01-AC3** H02-D: slot kosong tidak direalokasikan
- [ ] **C14-01-AC4** H02-E: baseline momentum-only dan reversal-only memakai intersection universe yang sama

## Definition of Done

All AC backed by fresh evidence; focused/affected checks pass, no unresolved Critical/Important findings, independent spec and quality PASS. Coordinator updates manifest. Backtest performance is a separate gate.

## Reviewer Checklist

Recompute golden independently; attempt future perturbation, missing data, threshold equality, fee double count and same-close fill. Inspect public replay rather than mock counts. Confirm no family budget reset.

## Commit Guidance

Use `feat/c14-01-size-conditioned`. Stage only mapped files; no automatic main merge or live activation.

## Handoff Requirements

Create docs/sprints/handoffs/C14-01-HANDOFF.md with code SHA, environment, command/exit, all AC evidence, budget ancestry, exclusions, reviewer verdict and next consumer. REVIEW remains pending if independent reviewer unavailable.

## Ready-to-Run Implementation Prompt

```text
Implement only C14-01. Read this entire sprint and Required Reading. Verify manifest prerequisites and data gates. Follow Implementation Steps. Do not run parameter search or activate scheduler. Commit scoped work with fresh evidence; stop at REVIEW until independent PASS.
```
