# Targets and chronological datasets without leakage

## Purpose and responsibilities

Targets and chronological datasets without leakage. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `src/indodax_lab/labels, cli/build_training_dataset.py`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| LABEL-01 | Target return mengukur net proceeds relatif terhadap gross cash debit dari execution model yang sama. | `docs/sprints/labels/LABEL-01-execution-aligned-net-return-labels.md` |
| LABEL-02 | Outcome upper/lower/vertical barrier mulai dari entry dan menyimpan akhir overlap. | `docs/sprints/labels/LABEL-02-triple-barrier-outcomes.md` |
| SPLIT-01 | Fold assignment memisahkan train validation dan sealed test tanpa overlap label. | `docs/sprints/labels/SPLIT-01-sealed-purged-chronological-folds.md` |
| TRAIN-01 | Materializer menggabungkan fitur label dan fold hanya melalui ID yang telah diverifikasi. | `docs/sprints/labels/TRAIN-01-verified-training-dataset-assembly.md` |

## Inputs, outputs and public interfaces

### LABEL-01 — Execution-aligned net return labels

sample + horizon + fill model -> entry/exit, gross/net return, costs and label_available_at.

Acceptance boundary:
- Entry sebelum decision ditolak.
- Horizon tidak lengkap tidak menjadi label nol.
- Cost schedule atau fill unavailable menghasilkan excluded sample.

### LABEL-02 — Triple barrier outcomes

entry + decision-time volatility + barrier config -> first_touch, label_end_ts, MAE/MFE, concurrency weight.

Acceptance boundary:
- Dua barrier dalam candle sama memilih lower.
- Volatilitas masa depan tidak menggeser barrier.
- Missing exit data menghasilkan censored/excluded status.

### SPLIT-01 — Sealed purged chronological folds

sample IDs + label_end_ts + declared exposure history -> versioned roles, purge and embargo manifest.

Acceptance boundary:
- Sample melewati boundary dipurge.
- Embargo minimal max horizon.
- Tahun yang pernah dilihat tidak diklaim sealed kembali.

### TRAIN-01 — Verified training dataset assembly

dataset/feature/label/split/universe/cost IDs -> training manifest and role-restricted tables.

Acceptance boundary:
- Duplicate sample join ditolak.
- Target kolom tidak boleh berada dalam inference feature list.
- Checksum atau availability mismatch memblokir output.

## Data model, persistence and lifecycle

Store label_end_ts, entry/exit, cost/execution IDs; assignment table per sample; purge overlaps and embargo.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

Immutable sample IDs; duplicate joins rejected; split table created once for registered version.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

Sealed data access logged; user-facing report must not expose sealed metrics before approved gate.

## Failure, retry, migration and recovery

Changed horizon/target/cost creates new materialization; exposed holdout cannot become sealed again.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)

## Target interface details

`build_net_return(sample, horizon, execution_model, cost_schedule)` uses the first eligible execution event after decision. `net_return = net_sell_proceeds / total_buy_cash_debit - 1`; store gross_return, buy_cost, sell_cost and slippage separately without charging twice. Missing terminal market event produces censored/excluded label; sample remains auditable. `label_available_at` must include upstream data availability, not merely simulated exit time.

`build_barrier_label(entry, decision_volatility, pt_multiplier, sl_multiplier, vertical_horizon)` computes bounds after entry and never refits volatility on the outcome interval. Store +1/-1/0, first_touch_ts, label_end_ts, MAE/MFE and concurrency weight. Overlap count based only on overlapping target intervals; labels and masks remain outside feature arrays.

`assign_folds(samples, split_policy, exposure_log)` writes immutable sample/fold/role table. Old annual_v1 (through2022 discovery,2023 validation,2024 gate,2025 confirmation,2026 forward) is a proposed protocol subject to actual exposure history and data coverage. Inner default expanding12-month train,3-month validation,1-month step where history permits; shorter history must produce explicit alternative version or blocked evidence, never move future to train. Calibration is a distinct held-out inner segment. Purge label overlap at boundaries and embargo >= maximum registered horizon. Known label availability must be <= fit cutoff.

`materialize_training(feature_ref,label_ref,split_ref,universe_ref,cost_ref)` requires unique sample join, verified bytes and explicit authorized columns. Output includes training_dataset_id, parent IDs, fold counts/exclusions and feature order. Trainer cannot regenerate a more convenient split silently.
