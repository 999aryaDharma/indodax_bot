# Leak-free ML predictions and portable artifacts

## Purpose and responsibilities

Leak-free ML predictions and portable artifacts. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `src/indodax_lab/models`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| ML-01 | Preprocessor menyimpan fitted statistics dan feature order tanpa mengakses test. | `docs/sprints/models/ML-01-train-only-preprocessing.md` |
| ML-02 | Forecast terkalibrasi hanya menjadi intent ketika net edge melampaui margin. | `docs/sprints/models/ML-02-held-out-calibration-and-cost-mapper.md` |
| ML-03 | Search mencatat trial budget dan tidak memakai sealed test sebagai objective. | `docs/sprints/models/ML-03-bounded-trial-search.md` |
| M01-01 | M01 memberi probabilitas net-positive dengan recipe linear teratur yang reproducible. | `docs/sprints/models/M01-01-calibrated-logistic-baseline.md` |
| M02-01 | M02 dibandingkan secara fair dengan linear dan classical pada outer folds yang sama. | `docs/sprints/models/M02-01-xgboost-challenger.md` |
| ML-04 | Trainer mempublikasikan bundle lengkap yang bisa diload ulang dan diuji inference identik. | `docs/sprints/models/ML-04-portable-model-bundles-and-replay.md` |
| M03-01 | Kandidat M03-01 menambah hipotesis risk/forecast yang terukur setelah Wave 1. | `docs/sprints/models/M03-01-random-forest-regime-gate.md` |
| M04-01 | Kandidat M04-01 menambah hipotesis risk/forecast yang terukur setelah Wave 1. | `docs/sprints/models/M04-01-quantile-risk-regression.md` |
| M05-01 | Kandidat M05-01 menambah hipotesis risk/forecast yang terukur setelah Wave 1. | `docs/sprints/models/M05-01-meta-label-signal-filter.md` |
| M06-01 | Kandidat M06-01 menambah hipotesis risk/forecast yang terukur setelah Wave 1. | `docs/sprints/models/M06-01-market-anomaly-risk-gate.md` |
| R01-01 | Spike menilai apakah RL layak diteruskan dengan reward bersih biaya dan constraints modal. | `docs/sprints/models/R01-01-constrained-allocation-feasibility.md` |

## Inputs, outputs and public interfaces

### ML-01 — Train-only preprocessing

train features -> imputer/scaler/pruner artifact; validation transform only.

Acceptance boundary:
- Test extreme value tidak memengaruhi train median.
- Missing extra reordered feature ditolak.
- Transform tidak menjalankan fit.

### ML-02 — Held-out calibration and cost mapper

forecast(kind=NET_RETURN/GROSS_RETURN/PROBABILITY) + payoff/cost basis -> abstain or intent; net costs applied once.

Acceptance boundary:
- Calibrator memakai inner held-out segment.
- Dataset calibration terlalu kecil memblokir.
- Gross dan net equivalent forecast menghasilkan keputusan sama.

### ML-03 — Bounded trial search

versioned search space + inner folds + family budget -> frozen winning recipe, all trial outcomes.

Acceptance boundary:
- Trial gagal tetap menghabiskan budget.
- Resume config mismatch ditolak.
- Maksimum 30 trial dan satu near-miss revision per model.

### M01-01 — Calibrated logistic baseline

Logistic elastic-net solver-compatible config -> fitted preprocessor/model/calibrator bundle.

Acceptance boundary:
- Invalid solver penalty ditolak.
- Tiny class imbalance diproses atau blocked dengan reason.
- Output dinilai net utility bersama cash dan naive baseline.

### M02-01 — XGBoost challenger

Versioned tree search + early stopping -> best iteration and frozen artifact.

Acceptance boundary:
- Early stop tidak melihat sealed labels.
- Finalist median dan worst tiga seed dicatat.
- Tree pipeline tetap menjaga feature order.

### ML-04 — Portable model bundles and replay

model + preprocessor + calibrator + thresholds + hashes + feature order -> verified bundle, replay forecast.

Acceptance boundary:
- Checksum weights mismatch menolak load.
- Missing calibration metadata memblokir.
- Reload memberi prediksi ekuivalen pada fixture.

### M03-01 — Random forest regime gate

Train-only regime labels -> calibrated risk classification

Acceptance boundary:
- Test regime tidak melatih model.
- Abstain untuk unknown class.
- Report downside dan net utility.

### M04-01 — Quantile risk regression

Registered return volatility or tail quantile target -> interval forecast

Acceptance boundary:
- Quantile crossing ditangani eksplisit.
- Coverage out-of-sample tercatat.
- Tail target tidak masuk input.

### M05-01 — Meta-label signal filter

Automatic base-strategy decisions and outcomes -> TAKE/SKIP probability

Acceptance boundary:
- Manual click tidak menjadi label.
- Meta split purge base label overlap.
- Compare base vs filtered pada same candidates.

### M06-01 — Market anomaly risk gate

Train-only liquidity distribution -> anomaly score and abstain threshold

Acceptance boundary:
- Threshold tidak fit future.
- No anomaly target mengklaim arah return.
- Missing data berbeda dari anomaly market.

### R01-01 — Constrained allocation feasibility

Offline simulator + fixed allocation baselines -> feasibility report, no scheduler default and no promotion.

Acceptance boundary:
- Reward hack diuji melalui turnover dan cash.
- Same budget versus inverse-vol baseline.
- Tidak ada order live atau policy export otomatis.

## Data model, persistence and lifecycle

Train-only preprocessing; held-out calibration; bundle all fitted transforms, features, hashes and thresholds.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

Per-run isolated output and seed; no shared mutable fitted transformer; budget consumed even by failed trials.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

Load verified local artifacts only; pickle is executable input, never deserialize arbitrary uploads. No sealed tuning.

## Failure, retry, migration and recovery

Resume only identical recipe/data hashes; best validation checkpoint, never best test seed.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)

## Fit, calibration and artifact details

`fit_preprocessor(train_table, feature_schema)` returns fitted train statistics and ordered names; impute median only on train, optional robust scaler/correlation pruning fit only there. `transform` rejects missing/extra/reordered input unless a declared adapter restores exact verified schema. Missing optional fields use registered masks, never fabricated observed values.

M01 logistic/elastic-net checks solver/penalty compatibility; M02 XGBoost uses bounded depth, learning rate, estimators/early-stop, subsample, column fraction and regularization from versioned config. Their actual search ranges are a registered research recipe established before trial execution. Search <=30 trials including failed trials; resume uses study+config/data identity. Calibration uses dedicated held-out inner data, with Brier/log-loss/reliability diagnostics; too-small set yields BLOCKED_DATA.

`map_forecast(kind,value,payoff,cost,margin)` handles NET_RETURN, GROSS_RETURN and calibrated PROBABILITY explicitly (ADR-002). The mapper also requires risk/universe eligibility; probability above0.5 alone never authorizes a trade. A frozen finalist bundle records feature order, preprocessor, model, calibrator, threshold, best iteration, environment lock, data/label/split/cost/execution/Git IDs. Stochastic finalist reports median and worst of3 fixed seeds; never select the lucky seed. Verify reload equality through common execution mapper and evaluator, not accuracy alone.
