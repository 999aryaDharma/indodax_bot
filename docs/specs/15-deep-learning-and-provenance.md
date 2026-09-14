# Optional staged complex-model research

## Purpose and responsibilities

Optional staged complex-model research. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `src/indodax_lab/models/dl, graph, foundation`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| DL-01 | Optional DL worker membuat checkpoint lengkap dan tidak membebani core runtime. | `docs/sprints/deep-learning/DL-01-isolated-resumable-neural-training.md` |
| D01-01 | MLP menguji manfaat nonlinearitas dengan fitur tabular yang sama seperti M01/M02. | `docs/sprints/deep-learning/D01-01-tabular-mlp-baseline.md` |
| DL-02 | Window sequence tidak menyeberangi pair, gap, split atau target. | `docs/sprints/deep-learning/DL-02-causal-sequence-datasets.md` |
| D02-01 | Eksperimen D02-01 menghasilkan forecast yang tunduk pada evaluator bersama. | `docs/sprints/deep-learning/D02-01-causal-tcn-baseline.md` |
| D03-01 | Eksperimen D03-01 menghasilkan forecast yang tunduk pada evaluator bersama. | `docs/sprints/deep-learning/D03-01-resnet-lstm-challenger.md` |
| D04-01 | Eksperimen D04-01 menghasilkan forecast yang tunduk pada evaluator bersama. | `docs/sprints/deep-learning/D04-01-compact-itransformer-challenger.md` |
| G01-01 | Eksperimen G01-01 menghasilkan forecast yang tunduk pada evaluator bersama. | `docs/sprints/deep-learning/G01-01-point-in-time-graph-challenger.md` |
| F01-01 | Loader memverifikasi asal, lisensi, checksum dan cutoff external model sebelum artifact boleh digunakan atau diberi status EXPLORATORY. | `docs/sprints/deep-learning/F01-01-foundation-provenance-gate.md` |
| F01-02 | Eksperimen F01-02 menghasilkan forecast yang tunduk pada evaluator bersama. | `docs/sprints/deep-learning/F01-02-staged-foundation-adaptation.md` |

## Inputs, outputs and public interfaces

### DL-01 — Isolated resumable neural training

optional torch environment + recipe -> model/optimizer/scheduler/RNG checkpoint; non-DL import isolation.

Acceptance boundary:
- Missing torch tidak mematahkan core CI.
- Resume input hash mismatch ditolak.
- Epoch cap 50 patience 7 memakai validation terbaik.

### D01-01 — Tabular MLP baseline

same feature rows + <=12 configs -> nonlinear baseline forecast via common mapper.

Acceptance boundary:
- Same sample comparator dijaga.
- Tiga finalist seed tidak cherry-pick.
- Training interrupted dapat resume pada best checkpoint.

### DL-02 — Causal sequence datasets

chronological feature windows + mask + sample ID -> sequence tensor with target outside input.

Acceptance boundary:
- Padding tidak menjadi harga nol nyata.
- Session gap memutus window.
- Target/future token tidak masuk input.

### D02-01 — Causal TCN baseline

Causal dilated convolutions + mask-safe pooling -> multi-horizon forecast

Acceptance boundary:
- Future token perturbation tidak mengubah output historis.
- Finite loss pada tiny fixture.
- Parameter dan compute budget tercatat.

### D03-01 — ResNet LSTM challenger

Residual temporal blocks + recurrent head -> registered triple-barrier target

Acceptance boundary:
- No bidirectional future leakage.
- Mask menjaga padded sequence.
- Common evaluation cost dan folds digunakan.

### D04-01 — Compact iTransformer challenger

Variates as tokens with available input window -> panel forecast

Acceptance boundary:
- Shape time-feature tidak tertukar.
- Missing variate masking diuji.
- Tidak memakai future universe.

### G01-01 — Point-in-time graph challenger

Eligible nodes + train-only rolling edges -> cross-asset rank; <=8 configurations

Acceptance boundary:
- Full sample adjacency ditolak.
- New listing tidak masuk graph lama.
- Dibandingkan no-edge MLP dan panel regression.

### F01-01 — Foundation provenance gate

revision checksum license release and cutoff -> verified external artifact or EXPLORATORY

Acceptance boundary:
- Unknown cutoff blocks promotion.
- Unverified bytes tidak diload.
- CI memakai fake adapter tanpa unduh weights.

### F01-02 — Staged foundation adaptation

Zero-shot then frozen probe then bounded adapter tuning -> comparable post-cutoff results

Acceptance boundary:
- Stage sebelumnya harus terdokumentasi.
- Full fine tune bukan default.
- Contaminated dates tidak menjadi sealed claim.

## Data model, persistence and lifecycle

Sequence masks/session boundaries; <=12 configs, 50 epochs, patience 7; graph <=8; checkpoints include RNG.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

Separate optional environment; one GPU job; checkpoint resources on interruption; no torch imports in core path.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

External weights need checksum/license/cutoff. Unknown cutoff EXPLORATORY; no remote executable model code by default.

## Failure, retry, migration and recovery

Fail run on nonfinite loss; restore verified best validation checkpoint; no extra epochs to rescue HARD_FAIL.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)

## Optional implementation controls

D01 uses same tabular feature order as M01/M02; DL-02 then adds session-safe sequences before D02 causal TCN, D03 residual recurrent head and D04 variates-token attention. Each model produces forecasts through common calibration/mapper; none implements independent trading execution. Sequence length, target horizons, hidden sizes, dropout and optimizer must be bounded in versioned configuration before search; maximum12 configs,50 epochs,patience7, min_delta1e-4, gradient_clip1.0 default inherited recipe. Record actual batch size and parameter count against measured RAM/GPU.

G01 nodes reflect current eligible universe; rolling correlation/economic edges available at decision only. Compare no-edge MLP, regularized panel and C04/M02 on identical samples. <=8 configurations and3-seed finalist. Graph metadata binds edge method/window/train cutoff and availability.

F01 provenance fields: model_name, immutable revision, sha256, license_id, released_at, declared_pretraining_cutoff, declared_sources and contamination_risk. Missing revision/hash/license rejects load. Unknown cutoff can permit explicitly exploratory analysis but blocks promotion. Order of adaptation is zero-shot → frozen representation/linear probe → parameter-efficient adapter; full fine-tune requires separate resource/design CR. No CI download or arbitrary remote-code execution.
