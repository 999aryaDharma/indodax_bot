# Trusted judge and risk-aware virtual portfolios

## Purpose and responsibilities

Trusted judge and risk-aware virtual portfolios. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `src/indodax_lab/backtest`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| COST-01 | Lookup fee memilih schedule historis yang tepat atau memblokir klaim promosi. | `docs/sprints/simulation/COST-01-time-valid-exchange-cost-schedules.md` |
| LED-01 | Simulasi kas dan posisi memakai posting balance dengan cost basis exact. | `docs/sprints/simulation/LED-01-balanced-research-postings.md` |
| SIM-01 | Order intent menghasilkan fill paling awal di event yang eligible berikutnya dengan biaya realistis. | `docs/sprints/simulation/SIM-01-conservative-execution-simulator.md` |
| SIM-02 | Sizing menghormati modal bersama, exposure dan batas rugi sebelum order dibuat. | `docs/sprints/simulation/SIM-02-portfolio-risk-and-circuit-breakers.md` |
| SIM-03 | Replay market memproduksi fill, posting dan equity identik pada input identik. | `docs/sprints/simulation/SIM-03-deterministic-replay-judge.md` |
| SIM-04 | Report menghitung performa dari ledger dan menunjukkan batas data serta kapasitas. | `docs/sprints/simulation/SIM-04-net-cost-risk-and-capacity-metrics.md` |

## Inputs, outputs and public interfaces

### COST-01 — Time-valid exchange cost schedules

market, side, role, fee_basis_ts -> service/tax/exchange components and min notional with sources; [valid_from,valid_to). Intervals are not eligible for lookup unless their source evidence is explicitly reviewed and verified. For limit orders use the order-created timestamp as the fee basis; for market orders use the execution timestamp.

Acceptance boundary:
- Overlap schedule key sama ditolak.
- Boundary end memilih interval berikutnya.
- Periode unknown tidak memakai fee hari ini.

### LED-01 — Balanced research postings

Fill -> cash/asset/fee/PnL postings in one valuation currency; quantity tracked separately; Decimal.

Acceptance boundary:
- Buy partial sell final sell menjaga quantity nonnegative.
- Fee lebih tinggi tidak meningkatkan fixed-path PnL.
- Duplicate fill ID tidak menggandakan posting.

### SIM-01 — Conservative execution simulator

SignalIntent + market + schedule -> REJECTED/PARTIAL/FILLED; next-open, precision, SL_FIRST, latency.

Acceptance boundary:
- Same-close execution ditolak.
- Insufficient depth dan min-size menghasilkan reject atau partial.
- Limit touch tidak otomatis maker fill.

### SIM-02 — Portfolio risk and circuit breakers

equity + open risk + intent + versioned risk policy -> approved size or reasoned rejection.

Acceptance boundary:
- Size di bawah minimum ditolak bukan dibulatkan naik.
- Daily dan weekly loss memasukkan unrealized PnL.
- Drawdown halt tidak hilang setelah restart.

### SIM-03 — Deterministic replay judge

market -> pending fills -> barriers -> decision -> risk -> orders -> mark; stable event/pair/order sort.

Acceptance boundary:
- Dua replay memberi posting exact dan metrics sama.
- Crash sebelum publish tidak menghasilkan run sukses.
- Independent ledger tidak dijumlah sebagai modal bersama.

### SIM-04 — Net-cost risk and capacity metrics

postings + equity + rejected orders -> metrics by year/regime/tier/asset and 1.5x/2x stress.

Acceptance boundary:
- No-trade dan zero-loss PF menghasilkan undefined beralasan.
- Fee tidak dikurangi dua kali dari net cash equity.
- Missing spread tidak dilaporkan sebagai biaya nol.

## Data model, persistence and lifecycle

Decimal valued double-entry journal; separate asset units from IDR valuation; exact fees, partial fills and market rules.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

Stable market event ordering; posting keyed by fill; risk/cash reservation atomically shared across candidates.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

No order-routing/network write capability. Unknown historical cost blocks promotion; signed or locally reviewed schedules.

## Failure, retry, migration and recovery

Ledger mismatch invalidates run; restore last complete checkpoint and replay, never patch PnL in reports.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)

## Execution and accounting contracts

`lookup_cost(market, side, role, fee_basis_ts)` returns schedule ID and separated fee/tax/CFX components, precision, minimum notional and source evidence; missing interval gives UnknownCostSchedule and a matching unverified interval fails with `UNVERIFIED_COST_SCHEDULE`. Reject negative/nonfinite rates and ambiguous overlapping schedule keys. Dated Rp25k minimum is inherited illustration only; active/historical values must be sourced during COST-01. Begin with IDR ledger; quote-separated USDT experimentation needs explicit FX valuation before IDR aggregation. See [CR-COST-01](../decisions/CR-COST-01-provenance-and-fee-time-basis.md).

`SignalIntent(decision_ts, pair, side=LONG|FLAT, strength, stop_loss?, take_profit?, strategy_id, strategy_version)` cannot specify its own fill. `simulate_execution(intent, market_event, execution_policy, cost_schedule)` returns zero or more fills plus reject/unfilled quantities. Reject stale/unknown-depth orders under the configured conservative fidelity tier; do not assume a missing book has zero spread. Quantize quantities down to permitted precision; never round up beyond risk size. Partial fills allocate exact gross cost basis; cancellation cannot consume unfilled quantity.

Journal uses valued balanced postings with consistent signs plus separate base-quantity deltas. Example: BUY spends IDR10000 gross and IDR20 fee; cash changes -10020, asset basis +10000 and expense +20. These valued postings sum0. SELL credit is already net of fee. Equity=cash+marked asset; no second expense subtraction. If fee paid in base asset, record its quantity and value explicitly and reconcile net received units. No mix of IDR value and BTC quantity in the balance equation.

Risk defaults in risk register are versioned: big0.5% risk/trade, small0.25%, max shared2 positions; daily1.5%, weekly4%, DD8%. UTC day/week boundaries, previous period start equity and high-water equity must be explicit in risk config before tests. Halt includes realized/unrealized PnL and persists across restart. Open-position exit behavior during stale data follows the last valid executable event and registered policy; do not invent fills when market data is missing.

Golden fixture must assert exact order of events, fills, rejected orders, postings and equity with independent arithmetic, including cost stress. Strategy-close decisions never fill on that same bar close under next-open policy. Same-bar stop/target ambiguity uses SL_FIRST. Capacity grid compares fixed notional scenarios against observed depth and records unsupported scenarios instead of perfect fills.
