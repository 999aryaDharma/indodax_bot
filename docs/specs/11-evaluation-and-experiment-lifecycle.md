# Versioned gates and honest experiment accounting

## Purpose and responsibilities

Versioned gates and honest experiment accounting. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `src/indodax_lab/evaluation`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| EVAL-01 | Setiap percobaan termasuk gagal tersimpan dengan konfigurasi dan ancestry yang dapat diaudit. | `docs/sprints/evaluation/EVAL-01-immutable-experiment-registry.md` |
| EVAL-02 | Evaluator memisahkan validitas run dari kualitas strategi dengan gate versioned. | `docs/sprints/evaluation/EVAL-02-hard-gates-and-selection-diagnostics.md` |
| EVAL-03 | Promosi mengikuti freeze dan exposure audit sebelum gate berikutnya dibuka. | `docs/sprints/evaluation/EVAL-03-sealed-candidate-lifecycle.md` |

## Inputs, outputs and public interfaces

### EVAL-01 — Immutable experiment registry

run_id + parent + git SHA + environment/data/config/cost/execution hashes -> immutable run record.

Acceptance boundary:
- Dirty worktree tidak memenuhi promotable run.
- Failed trial ikut trial count.
- Duplicate run key tidak menimpa hasil berbeda.

### EVAL-02 — Hard gates and selection diagnostics

metrics + policy + trial family -> INVALID_RUN/HARD_FAIL/NEAR_MISS/REGIME_EDGE/PASS, DSR/PBO when eligible.

Acceptance boundary:
- Score tinggi tidak menutupi cost unknown.
- Sample kecil menghasilkan insufficient evidence.
- Best seed tidak dipilih sebagai hasil finalist.

### EVAL-03 — Sealed candidate lifecycle

IDEA -> IMPLEMENTED -> BACKTESTED -> VALIDATED -> SEALED_PASS -> SHADOW -> CHAMPION; immutable transitions.

Acceptance boundary:
- Config berubah setelah sealed menjadi challenger baru.
- Gate dibuka sekali dan dicatat.
- Invalid run tidak masuk ranking.

## Data model, persistence and lifecycle

Record all trials, invalid runs, holdout exposures, policy decisions and parent versions; gate before leaderboard score.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

SQLite local transactions append lifecycle; unique run IDs and transitions; do not share WAL across network hosts.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

Evaluator changes require independent policy review; agent cannot lower gate to pass its candidate.

## Failure, retry, migration and recovery

Technical invalidity can retry after root fix with cap; HARD_FAIL archive; tuning creates new challenger.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)

## Gate inputs and outcomes

Run validity: missing provenance, corrupt data, ledger mismatch or interrupted output => INVALID_RUN, excluded from ranking but retained in registry. Candidate quality: valid negative net edge/risk breach => HARD_FAIL; stable positive safety-compliant near soft boundary => NEAR_MISS with diagnostic hypothesis; causal conditional edge => REGIME_EDGE; all required hard/evidence gates => PASS. Thresholds belong to versioned policy. No evaluator metric can override invalidity.

Store metrics by year/regime/tier/asset; no-trade expectancy/Sharpe/PF may be undefined with reason, not favorable zero/infinity. Annualized metrics require adequate duration and documented annualization convention. Confidence intervals/resampling must preserve temporal dependence (e.g. registered block bootstrap); random row shuffle cannot justify a time-series claim. DSR and PBO/CSCV report NOT_ESTIMABLE when trials/time blocks inadequate; account for all tested variants.

Promotion defaults: net-positive and PF>1 after base cost, sample evidence100 pooled and20 per relevant regime,1.5x stress not materially negative, concentration and parameter plateau checks. Terms such as materially negative and stable plateau must become numeric versioned evaluator policy before a promotion run; until then evaluator emits BLOCKED_POLICY, not arbitrary human interpretation. Owner/reviewer freeze that policy before viewing candidate sealed metrics.

Candidate transitions and sealed exposure are append-only. Automated algorithm selects next gate only after frozen version and authorized exposure record. Sorting score is advisory; hard gate failure visible. Current annual holdouts cannot be reused unknowingly by merely changing model name.
