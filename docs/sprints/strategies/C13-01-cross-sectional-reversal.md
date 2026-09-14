# C13-01 — Cross-sectional reversal

## Metadata

ID: C13-01
Status: PLANNED
Tier: EXTENSION
Owner: UNASSIGNED
Reviewer: UNASSIGNED
Alias in design: EXP-H01

## Goal

Cross-sectional reversal dengan causal input, frozen recipe dan shared judge.

## Why This Sprint Exists

Menguji hipotesis atau komponen pada kartu berikut, tanpa menggandakan keluarga canonical. Semua hasil penelitian belum diketahui.

## Depends On

- STRAT-01 — Declarative strategy protocol
- FEAT-04 — Immutable feature materialization
- C04-01 — Cross sectional momentum
- C07-01 — Bollinger RSI reversion
- SIM-03 — Deterministic replay judge
- SPLIT-01 — Sealed purged chronological folds
- EVAL-01 — Immutable experiment registry

## Unlocks

C14-01

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

### EXP-H01 — Cross-sectional reversal spot

Hipotesis: aset liquid yang relatif tertinggal satu hari dapat pulih pada regime pasar mendukung. Berbeda dari oversold RSI per aset.

Dependency: STRAT-01, FEAT-04, C04-01, C07-01, SIM-03, SPLIT-01, EVAL-01. Input 1h OHLCV PIT universe; minimal 20 aset eligible dan BTC benchmark tersedia. Baseline rebalance setiap 24 jam pada 00:00 UTC memakai bar terakhir berakhir pada boundary itu.

Aturan:
- `r24 = close_t / close_(t-24) - 1` dengan 24 interval berurutan, bukan sekadar 24 row.
- Regime gate BTC close > SMA 168 jam tertutup. Equality gagal gate dan menghasilkan TARGET_ZERO saat rebalance.
- Rank ascending r24; pilih tepat 5 aset terendah dengan `r24 < 0`, tie pair ascending. Jika hanya 3 memenuhi, pilih 3.
- Alokasi per aset 10% equity, total <=50%; jika hanya 3, total 30% dan sisanya cash. Minimum universe gagal: abstain, posisi lama diserahkan time exit/risk judge.
- Stop awal 2 ATR14 di bawah reference entry; reference fill aktual milik judge, tidak menaikkan ukuran akibat stop sempit. Exit paling lambat 24 jam sejak fill pertama. Tidak pyramiding. Re-entry sesudah close diperbolehkan hanya pada rebalance berikutnya.

Golden: universe 20 aset dengan lima r24 terendah -0.08,-0.06,-0.04,-0.02,-0.01 serta gate BTC true -> lima bobot 0.10. Return nol tidak dipilih. Pertukaran urutan input tidak mengubah rank.

Acceptance H01-A: golden tepat; H01-B: benchmark future tidak memengaruhi keputusan; H01-C: 19 aset abstain; H01-D: stop dan time exit judge dengan partial fills tidak mereset horizon; H01-E: satu modal bersama tidak overspend saat rotasi; H01-F: no fill pada signal close.

Ablation: r24 rank tanpa regime dibanding recipe utama pada universe sama; dihitung trial terpisah. Invalid jika gap waktu disamakan contiguous atau rank memakai survivors masa kini.

## Out of Scope

Live trading, short selling, futures, new data providers, unlimited tuning, direct ledger writes, replacing existing canonical strategies.

## User / Actor Behavior

Research worker consumes frozen recipe and eligible data, produces auditable intent/reason/result. Reviewer can reproduce the same decision with identical inputs.

## Functional Requirements

- C13-01-AC0: H01-A: golden tepat
- C13-01-AC1: H01-B: benchmark future tidak memengaruhi keputusan
- C13-01-AC2: H01-C: 19 aset abstain
- C13-01-AC3: H01-D: stop dan time exit judge dengan partial fills tidak mereset horizon
- C13-01-AC4: H01-E: satu modal bersama tidak overspend saat rotasi
- C13-01-AC5: H01-F: no fill pada signal close

## Domain Rules / Invariants

All numeric rules, threshold equality, stop/holding horizon and invalid data behavior are normative in In Scope. Shared contract: docs/research/catalog-expansion/02-experiment-contract.md. No available_at after decision; no same-close fill.

## Architecture / Design Contract

EXP-H01 canonical frame/artifact -> intent atau allocation/filter; bukan fill. Map semantic fields to STRAT-01 existing public types before coding. ABSTAIN leaves positions unchanged; TARGET_ZERO requests exit. If current types conflate these, resolve in STRAT-01 with regression before implementing candidate.

## Planned Files / Artifacts

- `src/indodax_lab/strategies/cross_sectional_reversal.py`
- `configs/strategies/c13-01.yaml`
- `tests/unit/lab/strategies/test_cross_sectional_reversal.py`

## Interfaces & Contracts

EXP-H01 canonical frame/artifact -> intent atau allocation/filter; bukan fill. Public cost quote is required for S10; missing quote blocks entry. Allocation uses target weights, never order placement. Lineage includes family ancestry, code/config/data/feature/split/cost/execution identities.

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

- `test_c13_01_0`: H01-A: golden tepat
- `test_c13_01_1`: H01-B: benchmark future tidak memengaruhi keputusan
- `test_c13_01_2`: H01-C: 19 aset abstain
- `test_c13_01_3`: H01-D: stop dan time exit judge dengan partial fills tidak mereset horizon
- `test_c13_01_4`: H01-E: satu modal bersama tidak overspend saat rotasi
- `test_c13_01_5`: H01-F: no fill pada signal close

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

- [ ] **C13-01-AC0** H01-A: golden tepat
- [ ] **C13-01-AC1** H01-B: benchmark future tidak memengaruhi keputusan
- [ ] **C13-01-AC2** H01-C: 19 aset abstain
- [ ] **C13-01-AC3** H01-D: stop dan time exit judge dengan partial fills tidak mereset horizon
- [ ] **C13-01-AC4** H01-E: satu modal bersama tidak overspend saat rotasi
- [ ] **C13-01-AC5** H01-F: no fill pada signal close

## Definition of Done

All AC backed by fresh evidence; focused/affected checks pass, no unresolved Critical/Important findings, independent spec and quality PASS. Coordinator updates manifest. Backtest performance is a separate gate.

## Reviewer Checklist

Recompute golden independently; attempt future perturbation, missing data, threshold equality, fee double count and same-close fill. Inspect public replay rather than mock counts. Confirm no family budget reset.

## Commit Guidance

Use `feat/c13-01-cross-sectional-reversal`. Stage only mapped files; no automatic main merge or live activation.

## Handoff Requirements

Create docs/sprints/handoffs/C13-01-HANDOFF.md with code SHA, environment, command/exit, all AC evidence, budget ancestry, exclusions, reviewer verdict and next consumer. REVIEW remains pending if independent reviewer unavailable.

## Ready-to-Run Implementation Prompt

```text
Implement only C13-01. Read this entire sprint and Required Reading. Verify manifest prerequisites and data gates. Follow Implementation Steps. Do not run parameter search or activate scheduler. Commit scoped work with fresh evidence; stop at REVIEW until independent PASS.
```
