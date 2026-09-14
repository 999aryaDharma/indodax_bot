# Comparable classical and small-cap hypotheses

## Purpose and responsibilities

Comparable classical and small-cap hypotheses. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `src/indodax_lab/strategies, configs/strategies`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| STRAT-01 | Strategi terdaftar hanya menghasilkan intent dan tidak memiliki otoritas fill atau ledger. | `docs/sprints/strategies/STRAT-01-declarative-strategy-protocol.md` |
| C01-01 | Kandidat C01 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/C01-01-donchian-breakout.md` |
| C07-01 | Kandidat C07 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/C07-01-bollinger-rsi-reversion.md` |
| C02-01 | Kandidat C02 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/C02-01-ema-pullback.md` |
| C03-01 | Kandidat C03 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/C03-01-time-series-momentum.md` |
| C04-01 | Kandidat C04 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/C04-01-cross-sectional-momentum.md` |
| C10-01 | Kandidat C10 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/C10-01-regime-ensemble.md` |
| S01-01 | Kandidat S01 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/S01-01-liquidity-screened-breakout.md` |
| S02-01 | Kandidat S02 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/S02-01-squeeze-expansion.md` |
| C05-01 | Kandidat C05 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/C05-01-volatility-breakout.md` |
| C06-01 | Kandidat C06 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/C06-01-directional-trend-strength.md` |
| C08-01 | Kandidat C08 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/C08-01-multi-timeframe-confirmation.md` |
| C09-01 | Kandidat C09 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/C09-01-vwap-deviation-reversion.md` |
| C11-01 | Kandidat C11 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/C11-01-volatility-allocation.md` |
| C12-01 | Kandidat C12 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/C12-01-relative-strength-rotation.md` |
| S03-01 | Kandidat S03 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/S03-01-abnormal-volume-continuation.md` |
| S04-01 | Kandidat S04 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/S04-01-order-flow-imbalance.md` |
| S05-01 | Kandidat S05 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/S05-01-micro-pullback.md` |
| S06-01 | Kandidat S06 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/S06-01-post-listing-maturation.md` |
| S07-01 | Kandidat S07 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/S07-01-small-cap-rotation.md` |
| S08-01 | Kandidat S08 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/S08-01-passive-mean-reversion.md` |
| S09-01 | Kandidat S09 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama. | `docs/sprints/strategies/S09-01-tail-risk-abstention.md` |

## Inputs, outputs and public interfaces

### STRAT-01 — Declarative strategy protocol

StrategySpecification + DecisionFrame -> list[SignalIntent]; ID/version/family/timeframes/risk/split required.

Acceptance boundary:
- Unknown config ditolak.
- Future atau ineligible row tidak masuk DecisionFrame.
- Parameter atau logic change memerlukan versi baru.

### C01-01 — Donchian breakout

Previous N-bar high breakout with volume gate; ATR stop -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Current bar tidak ikut previous high.
- Breakout confirmed menghasilkan LONG.
- Incomplete bar menghasilkan FLAT.

### C07-01 — Bollinger RSI reversion

Extreme BB and RSI deviation only under available sideways regime -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Strong downtrend menolak entry.
- Sideways oversold memberi bounded intent.
- Zero band width memberi abstain.

### C02-01 — EMA pullback

Long EMA regime plus short EMA pullback and recovery -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Downtrend menolak buy.
- Pullback belum recovered tidak entry.
- Recovery closed bar memberi intent.

### C03-01 — Time series momentum

Positive lookback return with volatility target and cash fallback -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Negative momentum tetap cash.
- Zero volatility memberi reject.
- Future return tidak mengubah sizing.

### C04-01 — Cross sectional momentum

PIT rank return top-K with liquidity and stable tie break -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Future listing tidak masuk rank.
- Rank tie konsisten antar run.
- Cash reserved sekali pada rotasi.

### C10-01 — Regime ensemble

Deterministic trend/reversion switch using available regime and frozen members -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Unknown regime menghasilkan cash.
- Perubahan future regime tidak mengubah decision.
- Member version tercatat di intent.

### S01-01 — Liquidity screened breakout

Breakout with spread/depth gate relative to simulated size -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Wide spread menolak.
- Depth kurang membatasi size.
- Missing liquidity memblokir trade.

### S02-01 — Squeeze expansion

BB/Keltner squeeze followed by volume expansion and no-chase cap -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Squeeze saja belum entry.
- Expansion tanpa volume ditolak.
- Gap di atas chase cap ditolak.

### C05-01 — Volatility breakout

Prior contraction then range expansion with registered ATR risk -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Future range tidak membentuk contraction.
- Expansion memberi intent.
- Degenerate range abstain.

### C06-01 — Directional trend strength

ADX strength and signed DI with ATR protection -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- High ADX negative DI tidak buy.
- Warmup belum lengkap abstain.
- Threshold equality deterministik.

### C08-01 — Multi timeframe confirmation

Closed daily/4h trend and lower timeframe trigger as-of decision -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Partial daily trend ditolak.
- Stale higher timeframe abstain.
- Confirmed alignment memberi LONG.

### C09-01 — VWAP deviation reversion

Rolling VWAP deviation in eligible reversion regime -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Zero denominator abstain.
- Trend risk gate menolak falling price.
- Missing volume tidak diisi nol.

### C11-01 — Volatility allocation

Inverse volatility long-only weights with asset and cash constraints -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Zero volatility tidak mendapat infinite weight.
- Sum allocation tidak melebihi cash.
- Small universe fallback explicit.

### C12-01 — Relative strength rotation

PIT strength rotation with turnover and cash regime gate -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Delisted pair tetap ada dalam histori.
- Cash regime memblokir reentry.
- Tie rank stable.

### S03-01 — Abnormal volume continuation

Volume surprise plus price confirmation with manipulation flags -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Volume spike tanpa price follow-through ditolak.
- Flagged pump abstain.
- Missing volume tidak menjadi surprise.

### S04-01 — Order flow imbalance

Reliable-session trade/book imbalance over registered horizon -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Sequence gap abstain.
- Stale book abstain.
- Imbalance timestamp setelah decision ditolak.

### S05-01 — Micro pullback

Short pullback within liquid impulse with spread-aware timing -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Wide spread menolak.
- Price chase di luar band menolak.
- Partial fill tidak menjadi full size.

### S06-01 — Post listing maturation

Momentum only after registered minimum age and reliable history -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Initial listing spike ditolak.
- Age boundary memakai available listing evidence.
- Unknown listing date abstain.

### S07-01 — Small cap rotation

Liquidity capacity constrained cross-sectional rank turnover -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Illiquid top rank tidak otomatis eligible.
- Order di atas capacity ditolak.
- Rotation respects shared cash.

### S08-01 — Passive mean reversion

Conservative queue-based passive order simulation without guaranteed maker fills -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Price touches quote tidak otomatis fill.
- Queue unknown memblokir promotion.
- Partial cancel menjaga ledger balance.

### S09-01 — Tail risk abstention

Available pump gap and illiquidity state blocks new risk -> versioned LONG/FLAT intent, never direct orders.

Acceptance boundary:
- Unknown data quality fail closed.
- Existing exposure ditangani registered exit policy.
- Gate reset tidak menghapus historical breach.

## Data model, persistence and lifecycle

Stateless decision functions over approved frame; only LONG/FLAT intents; registry version and fixed risk profile.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

Pure deterministic decisions; universe ties use canonical pair order; capital conflicts resolved by judge not strategy.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

Strategies cannot mutate ledger, bypass risk or import live order API. Config implementation allowlist only.

## Failure, retry, migration and recovery

Freeze strategy versions; archive failed hypothesis; never silently retune historical winner.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)

## Registration and hypothesis execution details

Keep stable catalog identity separate from sprint ID: C01 strategy lives in C01-01 sprint, similarly S01/M01 etc. Strategy registry fields include ID, semantic version, family, universe tier, timeframes, signal timing=bar_close, execution timing=next_bar_open, parameters, risk profile, split and status. Unknown fields rejected. Every family begins with frozen declared parameter ranges; numeric strategy thresholds are hypotheses to test on allowed data, not recommendations. Configure a deterministic default before implementation tests, document its formula and boundary cases; do not tune against test fixture outcomes to force profit.

C01 uses previous N completed bars excluding the decision bar for breakout threshold. C07 combines registered BB/RSI extremity with causal sideways gate; falling strong downtrend does not qualify. C04/S07 rank only eligible PIT assets and reserve turnover/cash through shared judge. C10 references frozen C01/C07 member versions; never mutates member rules during regime switching. All produce []/FLAT for incomplete data rather than guessing.

`decide(DecisionFrame)->list[SignalIntent]`: frame includes as_of, ordered eligible pairs, closed feature rows, raw ATR when needed for price-denominated stops and immutable universe/config IDs. Inputs read-only; stable pair ordering. Output has no direct DB/network side effects. Integration compares each strategy against cash and naive baseline on identical snapshot/cost/risk. A correctly implemented strategy can fail evaluation; do not change its goal into guaranteed profit.
