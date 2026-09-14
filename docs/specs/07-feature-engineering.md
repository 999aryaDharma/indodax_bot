# Deterministic available-at-time feature rows

## Purpose and responsibilities

Deterministic available-at-time feature rows. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `src/indodax_lab/features, cli/build_features.py`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| FEAT-01 | Definisi fitur Wave 1 dapat dimuat dengan identitas versi dan metadata lengkap. | `docs/sprints/features/FEAT-01-versioned-feature-registry.md` |
| FEAT-02 | Indikator continuous dan volume transforms menghasilkan nilai serta warmup yang dapat diaudit. | `docs/sprints/features/FEAT-02-golden-technical-and-liquidity-transforms.md` |
| FEAT-03 | Fitur BTC, rank dan breadth hanya memakai universe dan closed bars yang tersedia saat keputusan. | `docs/sprints/features/FEAT-03-as-of-market-context.md` |
| FEAT-04 | CLI membangun feature matrix dengan sample identity, warmup mask dan lineage penuh. | `docs/sprints/features/FEAT-04-immutable-feature-materialization.md` |

## Inputs, outputs and public interfaces

### FEAT-01 — Versioned feature registry

registry YAML -> feature definitions and source hash; exact contracted names after expansion.

Acceptance boundary:
- Nama duplikat dan bfill ditolak.
- Lookback kurang dari kebutuhan rumus ditolak.
- Perubahan konten tanpa version bump ditolak.

### FEAT-02 — Golden technical and liquidity transforms

closed OHLCV -> normalized EMA RSI StochRSI MACD ATR ADX BB Donchian VWAP returns and liquidity features.

Acceptance boundary:
- Golden expected dihitung independen dengan toleransi eksplisit.
- Flat price atau zero-volume tidak menghasilkan infinity.
- Ubah future bar tidak mengubah fitur masa lalu.

### FEAT-03 — As-of market context

decision_ts + PIT universe + context series -> availability-safe aligned context with missing reasons.

Acceptance boundary:
- Daily atau 4h partial bar dikecualikan.
- Future listing dan future cap tidak mengubah rank historis.
- Missing BTC history menghasilkan null bukan backfill.

### FEAT-04 — Immutable feature materialization

snapshot IDs + registry hash -> features manifest, ordered columns, row_ready_at, eligibility.

Acceptance boundary:
- Required feature null membuat row ineligible.
- Label atau future column tidak masuk feature schema.
- Dua root menghasilkan value-equivalent features dengan tolerance terdaftar.

## Data model, persistence and lifecycle

41 scalar Wave 1 names after expanding families; float64 features, Decimal source money; label tables separate.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

Compute partition by pair/time with sufficient overlap context; publish once. Cross-sectional joins use same decision timestamp.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

No future rows or labels in inference view; public registry config validated; reject arbitrary callable import from user input.

## Failure, retry, migration and recovery

Version every semantic change; retain old features for reproducibility; no bfill or silent zero imputation.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)

## Registry and calculation contract details

Registry keys: feature_set_id=`tabular_bar`, version semantic string, decision_interval=`1h`, features[]. Each definition requires name, family, source_columns, formula, allowlisted implementation identifier, params, lookback_bars, availability, lag_bars, dtype=float64, missing_policy, normalization and monotonicity. The expanded canonical set has 41 names; count alone is insufficient, compare exact names from dataset §7.3. Same-version semantic change is rejected; freeze registry source hash in dataset manifest.

FEAT-01 valid fixture loads all definitions and returns deterministic registry/source identity. Unknown implementation cannot execute arbitrary Python import. FEAT-02 uses the registry formula to compute normalized scalars; include independent literal golden values at warmup boundary, first eligible row and later row. Explicitly choose EMA seed/min_periods, Wilder ATR/RSI/ADX initialization, rolling ddof, StochRSI zero-range behavior and MACD parameterization in YAML before implementation; do not inherit undocumented library defaults. Warmup is null with INSUFFICIENT_LOOKBACK; masks do not backfill. Feature snapshot records those formula versions.

`build_context(decision_ts, universe_ref, closed_bars_by_pair)` returns only information with available_at<=decision_ts. Ties in cross-sectional ranks use registered policy; denominator is eligible observed pairs, with exclusion counts. Listing age uses available listing metadata, never earliest row guessed as listing date. `build_features(snapshot_ref, universe_ref, registry_ref, output_root)` produces features plus manifest with source IDs, column order, schema version, eligibility and row_ready_at=max(input availability). Chunk overlap must reproduce uninterrupted rolling computation. Training normalization remains ML-01, not this deterministic feature builder.
