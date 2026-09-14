# Clear read-only operational and research reports

## Purpose and responsibilities

Clear read-only operational and research reports. Owns the behavior of the capabilities below, not adjacent subsystem implementation. Source ownership: `src/indodax_lab/reporting, src/telegram_bot.py`. Existing equivalent modules must be extended instead of duplicated merely to match proposed filenames.

## Non-responsibilities

No real-money execution, no silent evaluator policy changes, and no direct mutation of upstream artifacts. This subsystem consumes verified contracts; it cannot repair unavailable upstream information by inventing values.

## Capability boundaries

| Sprint | Observable result | Detailed execution scope |
|---|---|---|
| REPORT-01 | Pengguna dapat melihat kualitas data, performa net dan alasan penolakan tanpa membaca raw logs. | `docs/sprints/reporting/REPORT-01-compact-experiment-reports.md` |
| REPORT-02 | Telegram menampilkan queue, champion dan health secara read-only dengan otorisasi chat. | `docs/sprints/reporting/REPORT-02-read-only-telegram-research-status.md` |

## Inputs, outputs and public interfaces

### REPORT-01 — Compact experiment reports

run artifacts -> Markdown/JSON summary with provenance, costs, baselines, validity and forward counts.

Acceptance boundary:
- No-data berbeda dari zero profit.
- Shared dan independent dipisahkan.
- Run invalid tidak ranking.

### REPORT-02 — Read-only Telegram research status

allowlisted chat -> status/history/report; bounded messages and deterministic error states.

Acceptance boundary:
- Unauthorized chat tidak mendapat holdings.
- Markdown escaped dan token redacted.
- Rate-limit retry tidak menggandakan notifikasi.

## Data model, persistence and lifecycle

Compact Markdown/JSON; validity, snapshot/config IDs, net/gross distinction, trial count, forward age/trades.

Identity and temporal primitives: [domain data model](02-domain-data-model.md). Implemented schemas stay backward compatible unless an accepted migration ADR states otherwise. Optional or absent data retains explicit unknown/missing semantics.

## Runtime flow and internal interfaces

Validate inputs and provenance → execute the owning capability → validate invariants → publish result and diagnostic. The contract above owns this domain's public surface; implementations can refactor private helpers without changing semantics. A failure does not advance a dependent job or candidate state. Pure transforms never perform network I/O. External adapters take injected transports and clocks in tests.

## Concurrency, caching and idempotency

Idempotent report key and bounded delivery retries; reporting failure never deletes observations.

Caching is optional and keyed by immutable input IDs plus policy/config version. A cache hit must not bypass integrity or availability checks. There is no requirement to introduce a cache where bounded direct computation suffices.

## Security and privacy

Allowlisted chats; escape Markdown; no tokens or sensitive balances to unknown recipients.

## Failure, retry, migration and recovery

Serve stale report only with as_of label; missing data is unavailable not zero; regenerate from verified artifacts.

Malformed input is not a transient retry. Preserve stable reason codes and the original failing input identity. Retry I/O only under explicit bounded policy; a retry cannot change config, event history or evaluation folds. Prior successful immutable outputs remain addressable.

## Observability

Emit capability ID, input IDs, policy/config version, output identity, success/failure reason and elapsed/resource observations where relevant. Record counts of rejected inputs and blocked outputs, not only successful rows. Never emit tokens, auth headers or unredacted private account payloads. Reports distinguish unavailable, failed and numeric zero.

## Performance and scale

Measure the actual data size touched by the contracts above. For data transforms record rows, pairs, window length, bytes and peak RSS; for search record trials × folds × seeds and elapsed CPU/GPU time; for stateful services record queue age, event lag and checkpoint latency. Use bounded iteration/partitioning and establish measured thresholds before activation. No SLA has been validated for the deployment hardware yet.

## Tests and acceptance

Every acceptance boundary above must map to named tests in its sprint handoff. Include normal behavior, targeted invalid input, and failure injection when persistence/concurrency is involved. Cross-domain checkpoint tests must traverse public interfaces with actual artifacts; sharing a fabricated string ID is not integration evidence. DONE requires all scope acceptance plus an independent reviewer verdict on the exact code SHA. Historical DONE imports are qualified in repository audit.

## References

[Master](00-master-product-technical-spec.md) · [Data contracts](../research/dataset-feature-contracts.md) · [Status](../sprints/SPRINT-STATUS.md) · [Change decisions](../decisions/README.md)
