# S10-01 — Microprice continuation benchmark

## Metadata

ID: S10-01
Status: PLANNED
Tier: EXTENSION
Owner: UNASSIGNED
Reviewer: UNASSIGNED
Alias in design: EXP-H03

## Goal

Microprice continuation benchmark dengan causal input, frozen recipe dan shared judge.

## Why This Sprint Exists

Menguji hipotesis atau komponen pada kartu berikut, tanpa menggandakan keluarga canonical. Semua hasil penelitian belum diketahui.

## Depends On

- S04-01 — Order flow imbalance
- LOB-01 — Forward book dataset eligibility
- SIM-01 — Conservative execution simulator
- SIM-03 — Deterministic replay judge
- COST-01 — Time-valid exchange cost schedules
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

### EXP-H03 — Microprice continuation benchmark

Hipotesis: harga berbobot best-quote depth memberi sinyal continuation jangka pendek setelah biaya; ini benchmark L2, bukan janji HFT layak.

Dependency: S04-01, LOB-01, SIM-01/03, COST-01, EVAL-01. Collector continuity RELIABLE; quote age <=2 detik pada decision; satu decision per 5 detik. Queue simulation tidak diwajibkan karena baseline taker; taker fill tetap depth/latency-aware.

Rumus: `mid=(ask+bid)/2`, `micro=(ask*bid_qty + bid*ask_qty)/(bid_qty+ask_qty)`, `edge_bps=10000*(micro-mid)/mid`.

Entry hanya `edge_bps > estimated_roundtrip_cost_bps + 2`, spread <=20 bps, ask>bid>0 dan kedua qty positif. Cost estimate wajib tersedia dari public cost/execution quote pada decision; jangan membuat fee konstan. Target <=0.05 equity, <=1% visible ask notional pada best ask; minimum order diperiksa judge.

Exit saat edge<=0 atau 60 detik sejak first fill atau stop 0.5% fill price, whichever first. Order latency default simulasi 500ms, stress 1000ms. Crossing signal threshold tidak menjamin execution edge. GAP/RECOVERING menghasilkan abstain; existing position tetap ditangani risk/time exit pada market sehat berikutnya sesuai SIM policy, tidak diisi harga lama.

Golden bid=99, ask=101, bid_qty=3, ask_qty=1 -> micro=100.5 dan edge=50 bps; spread=200 bps sehingga entry ditolak. Fixture accepted: bid=99.95, ask=100.05, qty 3 dan1 -> micro=100.025, edge=2.5 bps, spread=10 bps; mock public cost quote=0.4 bps memberi threshold=2.4 -> eligible. Biaya kecil ini hanya fixture matematika, bukan fee Indodax.

Acceptance H03-A: dua golden di atas dengan toleransi absolute 1e-8 bps; H03-B: equality edge threshold tidak entry; H03-C: stale/crossed/zero depth/GAP abstain; H03-D: delayed fill menggunakan depth sesudah latency; H03-E: restart tidak menggandakan intent/time horizon; H03-F: no historical L2 fabricated from candles.

## Out of Scope

Live trading, short selling, futures, new data providers, unlimited tuning, direct ledger writes, replacing existing canonical strategies.

## User / Actor Behavior

Research worker consumes frozen recipe and eligible data, produces auditable intent/reason/result. Reviewer can reproduce the same decision with identical inputs.

## Functional Requirements

- S10-01-AC0: H03-A: dua golden di atas dengan toleransi absolute 1e-8 bps
- S10-01-AC1: H03-B: equality edge threshold tidak entry
- S10-01-AC2: H03-C: stale/crossed/zero depth/GAP abstain
- S10-01-AC3: H03-D: delayed fill menggunakan depth sesudah latency
- S10-01-AC4: H03-E: restart tidak menggandakan intent/time horizon
- S10-01-AC5: H03-F: no historical L2 fabricated from candles

## Domain Rules / Invariants

All numeric rules, threshold equality, stop/holding horizon and invalid data behavior are normative in In Scope. Shared contract: docs/research/catalog-expansion/02-experiment-contract.md. No available_at after decision; no same-close fill.

## Architecture / Design Contract

EXP-H03 canonical frame/artifact -> intent atau allocation/filter; bukan fill. Map semantic fields to STRAT-01 existing public types before coding. ABSTAIN leaves positions unchanged; TARGET_ZERO requests exit. If current types conflate these, resolve in STRAT-01 with regression before implementing candidate.

## Planned Files / Artifacts

- `src/indodax_lab/strategies/microprice.py`
- `configs/strategies/s10-01.yaml`
- `tests/unit/lab/strategies/test_microprice.py`

## Interfaces & Contracts

EXP-H03 canonical frame/artifact -> intent atau allocation/filter; bukan fill. Public cost quote is required for S10; missing quote blocks entry. Allocation uses target weights, never order placement. Lineage includes family ancestry, code/config/data/feature/split/cost/execution identities.

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

- `test_s10_01_0`: H03-A: dua golden di atas dengan toleransi absolute 1e-8 bps
- `test_s10_01_1`: H03-B: equality edge threshold tidak entry
- `test_s10_01_2`: H03-C: stale/crossed/zero depth/GAP abstain
- `test_s10_01_3`: H03-D: delayed fill menggunakan depth sesudah latency
- `test_s10_01_4`: H03-E: restart tidak menggandakan intent/time horizon
- `test_s10_01_5`: H03-F: no historical L2 fabricated from candles

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

- [ ] **S10-01-AC0** H03-A: dua golden di atas dengan toleransi absolute 1e-8 bps
- [ ] **S10-01-AC1** H03-B: equality edge threshold tidak entry
- [ ] **S10-01-AC2** H03-C: stale/crossed/zero depth/GAP abstain
- [ ] **S10-01-AC3** H03-D: delayed fill menggunakan depth sesudah latency
- [ ] **S10-01-AC4** H03-E: restart tidak menggandakan intent/time horizon
- [ ] **S10-01-AC5** H03-F: no historical L2 fabricated from candles

## Definition of Done

All AC backed by fresh evidence; focused/affected checks pass, no unresolved Critical/Important findings, independent spec and quality PASS. Coordinator updates manifest. Backtest performance is a separate gate.

## Reviewer Checklist

Recompute golden independently; attempt future perturbation, missing data, threshold equality, fee double count and same-close fill. Inspect public replay rather than mock counts. Confirm no family budget reset.

## Commit Guidance

Use `feat/s10-01-microprice`. Stage only mapped files; no automatic main merge or live activation.

## Handoff Requirements

Create docs/sprints/handoffs/S10-01-HANDOFF.md with code SHA, environment, command/exit, all AC evidence, budget ancestry, exclusions, reviewer verdict and next consumer. REVIEW remains pending if independent reviewer unavailable.

## Ready-to-Run Implementation Prompt

```text
Implement only S10-01. Read this entire sprint and Required Reading. Verify manifest prerequisites and data gates. Follow Implementation Steps. Do not run parameter search or activate scheduler. Commit scoped work with fresh evidence; stop at REVIEW until independent PASS.
```
