# C15-01 — Equal risk contribution overlay

## Metadata

ID: C15-01
Status: PLANNED
Tier: EXTENSION
Owner: UNASSIGNED
Reviewer: UNASSIGNED
Alias in design: EXP-O01

## Goal

Equal risk contribution overlay dengan causal input, frozen recipe dan shared judge.

## Why This Sprint Exists

Menguji hipotesis atau komponen pada kartu berikut, tanpa menggandakan keluarga canonical. Semua hasil penelitian belum diketahui.

## Depends On

- C11-01 — Volatility allocation
- SIM-02 — Portfolio risk and circuit breakers
- SIM-03 — Deterministic replay judge
- FEAT-04 — Immutable feature materialization
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

### EXP-O01 — Equal risk contribution overlay

Tujuan: bandingkan alokasi covariance penuh dengan C11 inverse-vol pada sinyal aset yang sama. Bukan entry generator.

Dependency: C11-01, SIM-02/03, FEAT-04, EVAL-01. Input eligible held/selected assets dari kandidat beku, daily simple returns 60 interval berurutan; minimal 2 aset. Covariance sample ddof=1 dengan shrinkage tetap `S=0.9*sample_cov +0.1*diag(sample_cov)`. Tolak non-finite, zero variance atau matrix tidak positive definite; failure -> abstain, tidak fallback optimizer diam-diam.

Cari bobot positif sum=1 sehingga normalized risk contribution `w_i*(S*w)_i / (w.T*S*w)` dekat 1/n; max absolute residual <=1e-4, max iterations 1000. Initial equal weights, solver/version/tolerance tercatat. Jika tidak converged, abstain. Scale ke exposure 0.5, lalu cap per aset 0.2 tanpa redistribusi sisa; cash menampung selisih. Laporkan residual sesudah cap sebagai realised allocation; tidak klaim cap tetap equal-risk.

Golden dua aset covariance diagonal [0.04,0.16] -> unconstrained w=[2/3,1/3]; exposure scaled [1/3,1/6], capped [0.2,1/6], cash=19/30. Acceptance O01-A golden tolerance 1e-4; O01-B future return perturbation invariant; O01-C covariance singular/zero variance rejection; O01-D nonconvergence diagnostic; O01-E exposure/turnover/fees dibanding C11 dengan input sinyal identik.

## Out of Scope

Live trading, short selling, futures, new data providers, unlimited tuning, direct ledger writes, replacing existing canonical strategies.

## User / Actor Behavior

Research worker consumes frozen recipe and eligible data, produces auditable intent/reason/result. Reviewer can reproduce the same decision with identical inputs.

## Functional Requirements

- [ ] C15-01-AC0: O01-A golden tolerance 1e-4 (`test_c15_01_0`)
- [ ] C15-01-AC1: O01-B future return perturbation invariant (`test_c15_01_1`)
- [ ] C15-01-AC2: O01-C covariance singular/zero variance rejection (`test_c15_01_2`)
- [ ] C15-01-AC3: O01-D nonconvergence diagnostic (`test_c15_01_3`)
- [ ] C15-01-AC4: O01-E exposure/turnover/fees dibanding C11 dengan input sinyal identik (`test_c15_01_4`)

## Domain Rules / Invariants

All numeric rules, threshold equality, stop/holding horizon and invalid data behavior are normative in In Scope. Shared contract: docs/research/catalog-expansion/02-experiment-contract.md. No available_at after decision; no same-close fill.

## Architecture / Design Contract

EXP-O01 canonical frame/artifact -> intent atau allocation/filter; bukan fill. Map semantic fields to STRAT-01 existing public types before coding. ABSTAIN leaves positions unchanged; TARGET_ZERO requests exit. If current types conflate these, resolve in STRAT-01 with regression before implementing candidate.

## Planned Files / Artifacts

- `src/indodax_lab/strategies/risk_contribution.py`
- `configs/strategies/c15-01.yaml`
- `tests/unit/lab/strategies/test_risk_contribution.py`

## Interfaces & Contracts

EXP-O01 canonical frame/artifact -> intent atau allocation/filter; bukan fill. Public cost quote is required for S10; missing quote blocks entry. Allocation uses target weights, never order placement. Lineage includes family ancestry, code/config/data/feature/split/cost/execution identities.

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

- [ ] C15-01-AC0: O01-A golden tolerance 1e-4 (`test_c15_01_0`)
- [ ] C15-01-AC1: O01-B future return perturbation invariant (`test_c15_01_1`)
- [ ] C15-01-AC2: O01-C covariance singular/zero variance rejection (`test_c15_01_2`)
- [ ] C15-01-AC3: O01-D nonconvergence diagnostic (`test_c15_01_3`)
- [ ] C15-01-AC4: O01-E exposure/turnover/fees dibanding C11 dengan input sinyal identik (`test_c15_01_4`)

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

- [ ] C15-01-AC0: O01-A golden tolerance 1e-4 (`test_c15_01_0`)
- [ ] C15-01-AC1: O01-B future return perturbation invariant (`test_c15_01_1`)
- [ ] C15-01-AC2: O01-C covariance singular/zero variance rejection (`test_c15_01_2`)
- [ ] C15-01-AC3: O01-D nonconvergence diagnostic (`test_c15_01_3`)
- [ ] C15-01-AC4: O01-E exposure/turnover/fees dibanding C11 dengan input sinyal identik (`test_c15_01_4`)

## Definition of Done

All AC backed by fresh evidence; focused/affected checks pass, no unresolved Critical/Important findings, independent spec and quality PASS. Coordinator updates manifest. Backtest performance is a separate gate.

## Reviewer Checklist

Recompute golden independently; attempt future perturbation, missing data, threshold equality, fee double count and same-close fill. Inspect public replay rather than mock counts. Confirm no family budget reset.

## Commit Guidance

Use `feat/c15-01-risk-contribution`. Stage only mapped files; no automatic main merge or live activation.

## Handoff Requirements

Create docs/sprints/handoffs/C15-01-HANDOFF.md with code SHA, environment, command/exit, all AC evidence, budget ancestry, exclusions, reviewer verdict and next consumer. REVIEW remains pending if independent reviewer unavailable.

## Ready-to-Run Implementation Prompt

```text
Implement only C15-01. Read this entire sprint and Required Reading. Verify manifest prerequisites and data gates. Follow Implementation Steps. Do not run parameter search or activate scheduler. Commit scoped work with fresh evidence; stop at REVIEW until independent PASS.
```
