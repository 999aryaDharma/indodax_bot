# M07-01 — Conformal abstention filter

## Metadata

ID: M07-01
Status: PLANNED
Tier: EXTENSION
Owner: UNASSIGNED
Reviewer: UNASSIGNED
Alias in design: EXP-O02

## Goal

Conformal abstention filter dengan causal input, frozen recipe dan shared judge.

## Why This Sprint Exists

Menguji hipotesis atau komponen pada kartu berikut, tanpa menggandakan keluarga canonical. Semua hasil penelitian belum diketahui.

## Depends On

- M04-01 — Quantile risk regression
- ML-01 — Train-only preprocessing
- ML-04 — Portable model bundles and replay
- SPLIT-01 — Sealed purged chronological folds
- LABEL-01 — Execution-aligned net return labels
- EVAL-01 — Immutable experiment registry
- EVAL-02 — Hard gates and selection diagnostics

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

### EXP-O02 — Conformal abstention filter pilot

Tujuan: filter ketidakpastian atas prediktor net-return yang sudah beku. Tidak memberi jaminan coverage teoretis pada time-series non-exchangeable.

Dependency: M04-01, ML-01/04, SPLIT-01, LABEL-01, EVAL-01/02. Predictor median return fit train-only; calibration terpisah kronologis dengan 200 residual berlabel matang sesudah train dan sebelum evaluation. Target return net-cost sama dengan label contract; jangan mengurangi fee dua kali.

Residual `abs(y_net - prediction)`; alpha=0.10; k=ceil((n+1)*(1-alpha)), quantile residual sorted posisi k (1-based). k>n atau n<200 -> abstain. Interval prediction +/-q. Entry dasar hanya diteruskan bila lower bound >0; equality -> abstain. Filter tidak membuat entry baru, tidak memblokir exit, tidak mengubah sizing. Calibration artifact beku untuk satu evaluation fold; refit bukan online memakai label belum matang.

Golden n=200, residual sorted i/1000 untuk i=1..200 -> k=181,q=0.181. Prediksi 0.20 -> lower=0.019 lolos; prediksi 0.181 -> lower=0 ditolak. Angka fixture tidak merepresentasikan return realistis.

Acceptance O02-A golden exact quantile; O02-B overlap calibration/evaluation ditolak; O02-C label unavailable ditolak; O02-D basic strategy no-entry tetap no-entry; O02-E exits tetap diteruskan; O02-F coverage/width/trade retention dilaporkan per fold tanpa janji coverage 90% pasti.

## Out of Scope

Live trading, short selling, futures, new data providers, unlimited tuning, direct ledger writes, replacing existing canonical strategies.

## User / Actor Behavior

Research worker consumes frozen recipe and eligible data, produces auditable intent/reason/result. Reviewer can reproduce the same decision with identical inputs.

## Functional Requirements

- [ ] M07-01-AC0: O02-A golden exact quantile (`test_m07_01_0`)
- [ ] M07-01-AC1: O02-B overlap calibration/evaluation ditolak (`test_m07_01_1`)
- [ ] M07-01-AC2: O02-C label unavailable ditolak (`test_m07_01_2`)
- [ ] M07-01-AC3: O02-D basic strategy no-entry tetap no-entry (`test_m07_01_3`)
- [ ] M07-01-AC4: O02-E exits tetap diteruskan (`test_m07_01_4`)
- [ ] M07-01-AC5: O02-F coverage/width/trade retention dilaporkan per fold tanpa janji coverage 90% pasti (`test_m07_01_5`)

## Domain Rules / Invariants

All numeric rules, threshold equality, stop/holding horizon and invalid data behavior are normative in In Scope. Shared contract: docs/research/catalog-expansion/02-experiment-contract.md. No available_at after decision; no same-close fill.

## Architecture / Design Contract

EXP-O02 canonical frame/artifact -> intent atau allocation/filter; bukan fill. Map semantic fields to STRAT-01 existing public types before coding. ABSTAIN leaves positions unchanged; TARGET_ZERO requests exit. If current types conflate these, resolve in STRAT-01 with regression before implementing candidate.

## Planned Files / Artifacts

- `src/indodax_lab/models/conformal_filter.py`
- `configs/strategies/m07-01.yaml`
- `tests/unit/lab/models/test_conformal_filter.py`

## Interfaces & Contracts

EXP-O02 canonical frame/artifact -> intent atau allocation/filter; bukan fill. Public cost quote is required for S10; missing quote blocks entry. Allocation uses target weights, never order placement. Lineage includes family ancestry, code/config/data/feature/split/cost/execution identities.

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

- [ ] M07-01-AC0: O02-A golden exact quantile (`test_m07_01_0`)
- [ ] M07-01-AC1: O02-B overlap calibration/evaluation ditolak (`test_m07_01_1`)
- [ ] M07-01-AC2: O02-C label unavailable ditolak (`test_m07_01_2`)
- [ ] M07-01-AC3: O02-D basic strategy no-entry tetap no-entry (`test_m07_01_3`)
- [ ] M07-01-AC4: O02-E exits tetap diteruskan (`test_m07_01_4`)
- [ ] M07-01-AC5: O02-F coverage/width/trade retention dilaporkan per fold tanpa janji coverage 90% pasti (`test_m07_01_5`)

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

- [ ] M07-01-AC0: O02-A golden exact quantile (`test_m07_01_0`)
- [ ] M07-01-AC1: O02-B overlap calibration/evaluation ditolak (`test_m07_01_1`)
- [ ] M07-01-AC2: O02-C label unavailable ditolak (`test_m07_01_2`)
- [ ] M07-01-AC3: O02-D basic strategy no-entry tetap no-entry (`test_m07_01_3`)
- [ ] M07-01-AC4: O02-E exits tetap diteruskan (`test_m07_01_4`)
- [ ] M07-01-AC5: O02-F coverage/width/trade retention dilaporkan per fold tanpa janji coverage 90% pasti (`test_m07_01_5`)

## Definition of Done

All AC backed by fresh evidence; focused/affected checks pass, no unresolved Critical/Important findings, independent spec and quality PASS. Coordinator updates manifest. Backtest performance is a separate gate.

## Reviewer Checklist

Recompute golden independently; attempt future perturbation, missing data, threshold equality, fee double count and same-close fill. Inspect public replay rather than mock counts. Confirm no family budget reset.

## Commit Guidance

Use `feat/m07-01-conformal-filter`. Stage only mapped files; no automatic main merge or live activation.

## Handoff Requirements

Create docs/sprints/handoffs/M07-01-HANDOFF.md with code SHA, environment, command/exit, all AC evidence, budget ancestry, exclusions, reviewer verdict and next consumer. REVIEW remains pending if independent reviewer unavailable.

## Ready-to-Run Implementation Prompt

```text
Implement only M07-01. Read this entire sprint and Required Reading. Verify manifest prerequisites and data gates. Follow Implementation Steps. Do not run parameter search or activate scheduler. Commit scoped work with fresh evidence; stop at REVIEW until independent PASS.
```
