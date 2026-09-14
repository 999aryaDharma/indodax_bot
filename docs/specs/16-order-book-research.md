# Forward LOB quality and spread-aware experiments

## Purpose and responsibilities

Forward LOB quality and spread-aware experiments. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `src/indodax_lab/models/lob, features/lob.py`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| LOB-01 | LOB dataset hanya mengizinkan sesi PASS yang punya coverage dan event efektif cukup. | `docs/sprints/microstructure/LOB-01-forward-book-dataset-eligibility.md` |
| L01-01 | DeepLOB mengukur short-horizon edge setelah spread dan latency melalui book dataset terverifikasi. | `docs/sprints/microstructure/L01-01-deeplob-baseline.md` |
| L02-01 | Attention LOB challenger dibandingkan dengan DeepLOB pada biaya dan budget yang sama. | `docs/sprints/microstructure/L02-01-tlob-style-challenger.md` |

## Inputs, outputs and public interfaces

### LOB-01 — Forward book dataset eligibility

continuous raw books -> depth/imbalance tensors with >=90 day coverage gate plus sample/regime report.

Acceptance boundary:
- Candle tidak dapat menjadi book fixture pengganti.
- Gap memutus sequence window.
- Banyak row dalam sedikit hari belum memenuhi gate.

### L01-01 — DeepLOB baseline

LOB tensor + spread-aware label -> forecast and common execution mapper.

Acceptance boundary:
- Mid-price accuracy tinggi belum berarti net profitable.
- Gapped book blocks run.
- Baseline MLP memakai sample identik.

### L02-01 — TLOB style challenger

same LOB snapshot/folds + <=8 configs -> challenger artifact with latency/compute evidence.

Acceptance boundary:
- No perfect queue fill assumption.
- Batas budget menghentikan search.
- Poor valid result diarsipkan.

## Data model, persistence and lifecycle

>=90 days PASS coverage plus effective samples/regimes; full book/trade inputs, not candles; latency labels.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

Bounded tensor windows never cross gap; immutable session IDs and event ordering.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

Reject corrupted/unreliable session; acquired data and model license validated; no guarantee of maker fill.

## Failure, retry, migration and recovery

Gap invalidates affected window; restart from verified book snapshot; model outputs remain blocked until data gate.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)

## Data eligibility versus implementation eligibility

LOB-01 implementation can test with synthetic genuine book/trade fixtures; real research execution remains blocked until >=90 days PASS forward coverage, enough effective samples and multiple observed regimes are documented. Count disjoint valid sessions, missing intervals, depth consistency and effective label overlap; total row count cannot substitute for coverage. No historical books are reconstructed from OHLCV.

Tensor identity includes session, snapshot, level ordering, timestamp/offset, feature version, mask and target horizon. Validate monotonic offset, non-crossed prices under the source contract and nonnegative quantity. Sequence gap resets rolling context; sample never crosses session boundary. Spread-aware targets and latency budget feed common execution mapper; report quote validity, fill assumptions and rejected orders.

L01 establishes DeepLOB versus simple MLP baseline before L02 attention challenger. S04/S08 can consume the verified LOB dataset capability independently of neural model adoption; quality does not require DL to be useful. Actual maker queue modeling must document its uncertainty and avoid guaranteed fills.
