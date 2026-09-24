# Production Risk Policy v1 — decision register

Date: 2026-09-24. Documentation/planning only; no activation or live execution evidence. Read with [Bot Trade Program](BOT-TRADE-PROGRAM.md) and [ADR-010](../decisions/ADR-010-multi-strategy-production-and-guarded-controls.md). The sprint manifest remains the sole status/DAG authority.

`DECIDED` means owner-confirmed behavior, not implemented/qualified. `PROPOSED` means a baseline awaiting policy acceptance or remaining parameter decisions. `OPEN/BLOCKING` means required evidence/definitions are missing. Existing confirmed controls remain effective until an explicitly approved replacement is qualified.

## 1. Portfolio risk and exposure

- DECIDED: centralized shared cash, exclusive pair ownership, candidate-owned adaptive sizing/exits within portfolio gates; absolute IDR 100,000 drawdown from adjusted peak equity.
- DECIDED DEFAULT FOR QUALIFICATION: IDR 4,000 maximum modeled risk/trade; IDR 10,000 global open/pending risk; IDR 8,000 combined BTC/ETH/SOL cluster risk. For these three agents the effective cluster allowance is IDR 8,000, not IDR 10,000. These are ceilings, not target usage or guaranteed realized-loss limits.
- Risk reservations persist through submission/cancel uncertainty. Confirmed fills transfer pending risk into position risk atomically; partial fills retain risk for both filled quantity and unresolved remainder. Confirmed cancellation frees only the reconciled unfilled remainder. Exposure and risk are distinct and neither may be counted twice.
- OPEN: freeze the conservative definition of remaining risk at stop for existing positions, cost/slippage allowance and treatment of trailing stops before activation. Stop-based loss is modeled, not worst-case gap/outage loss.
- Owners: RP-03, PM-08, PM-04.

## 2. Daily loss brake

- DECIDED DEFAULT FOR QUALIFICATION: IDR 15,000 loss from UTC day-opening flow-adjusted equity, including unrealized PnL and applicable costs. At/above the loss threshold, latch no-new-entry and retain eligible protective exits.
- OPEN POLICY DECISION: clear only the daily-stop latch at the next UTC day after fresh HEALTHY reconciliation and zero UNKNOWN. Never clear an independent drawdown breach, operational halt or incident latch. This limited automatic daily reset requires explicit policy amendment/qualification; it is not currently authorized by the general manual-resume rule.
- Owner: PM-08; API-04/UI-03 display the distinct stop reason.

## 3. External capital flows

- DECIDED: deposits/withdrawals are external capital flows, not trading PnL; adjusted peak/current equity must use the same basis.
- PROPOSED FORMULA: on a verified flow F (positive deposit, negative withdrawal), adjust peak by F while equity changes by the same amount. Example: peak 520000/equity 500000 plus deposit 100000 becomes peak 620000/equity 600000; drawdown remains 20000.
- OPEN: define exact credited/debited amounts, transfer-fee treatment and IDR valuation/timestamp for non-IDR flows. Reconcile and deduplicate flows; unknown/unvalued flows block entry rather than reset drawdown. Owner approval of the formula and those semantics is required before activation.
- Owners: PM-07, PM-08.

## 4. Absolute drawdown and new risk periods

- DECIDED: peak minus IDR 100,000 is the active floor. At/below it, prohibit entry, persist controlled close-out, cancel/reconcile entry remainders, and exit bot-owned positions only when required write gates permit.
- DECIDED: after completed close-out, a separately approved new risk period may start from actual reconciled equity with incident review and qualified release/risk policy. Preserve old peak/loss/fill evidence and cumulative results. Ordinary resume cannot reset a peak; approval of a new period does not itself resume trading.
- Operational HALT still forbids unsafe writes. Do not label entry blocking plus eligible close-out as an unconditional HALT exit exception.
- Owners: PM-08, PM-09, API-04, UI-03.

## 5. Three immutable candidates

- DECIDED: BTC-C07, ETH-C02 and SOL-C02 are the owner-selected agents. Models are components inside agents.
- OPEN/BLOCKING: bind each exact version to model/feature/scaler/calibrator hashes, thresholds, pair/timeframe, risk/execution policies, dataset/report evidence and code/environment/release provenance. Existing research names or reports do not certify the final bundle.
- Owners: RW2-01/02/03, RW4-01, PM-05. Verify applicable DL artifacts/dependencies if the selected BTC bundle uses them.

## 6. Signal contention and capacity

- DECIDED CURRENT ORDER: policy priority, then strategy ID, then intent ID; reserve atomically against one portfolio revision.
- DECIDED DEFAULT FOR QUALIFICATION: one position per pair, at most two concurrently occupied live pair slots, notional at most 25% of current equity per pair and 50% total deployed. Pending entries consume cash, exposure, risk and pair slots; a partial fill plus its remainder is one occupied pair slot.
- PROPOSED REPLACEMENT: rank by comparable expected net edge per risk after gates. OPEN/BLOCKING: common horizon, estimator/calibration/cost identity and missing-score behavior. Raw probabilities across models are not comparable by assumption; do not silently replace the current deterministic ordering.
- Owners: RP-03, PM-08, RW6-01.

## 7. Order execution

- PROPOSED: limit-first entries, no market chasing; emergency market exit only under an explicitly qualified execution policy. A limit order alone does not prove maker fees.
- DECIDED: partial fills create their actual positions; uncertain submission/cancellation is reconciled before replacement; no blind retry or oversell. Order creation/exit policies remain candidate/release-bound.
- OPEN: per-policy entry timeout, cancel/reprice limits, price/slippage tolerances, time-in-force selection and emergency exit semantics. Unsupported order types reject, without implicit fallback.
- Owners: PM-04, RP-04, PM-09.

## 8. Venue protection and disconnection

- VERIFIED DOCUMENTATION ONLY: Deadman Switch supports a per-pair countdown cancelling all open orders; documentation gives 30-second heartbeat/120-second countdown as an example. It does not close filled positions. Test its interaction with protective/exit orders; do not assume entry-only cancellation.
- OPEN/BLOCKING for unattended activation requiring venue protection: verify protective order creation, acknowledgement, persistence during host/network loss, fill/cancel semantics and Deadman interaction in the applicable demo/venue flow. `stoplimit` in an open-order response is not proof of a supported create-stop API.
- VERIFIED CODE INVENTORY: the read-only adapter already uses Trade API v2 history. Its integration/evidence should be verified rather than rebuilt solely due legacy endpoint decommissioning.
- Owners: PM-04, RP-04, OPS-01, QA-03, PM-06; documentation is not demo/live qualification.

## 9. Pair liquidity gates

- PROPOSED: spread at most 0.25%, near-book executable depth at least 5 times intended order notional, impact ceiling in the suggested 0.20-0.25% range, and a suggested 120-second feed-age ceiling.
- OPEN/BLOCKING: choose one impact ceiling, exact depth price band and side, quote units, timestamp origin and separate freshness limits for bars versus executable orderbook. Apply to executable quantity and cost evidence; 24-hour volume alone is insufficient. Ineligible pairs accept no new exposure; do not indiscriminately block required risk-reducing exits using entry-only liquidity rules.
- Owners: RP-03/RP-04, PM-08, DATA-07.

## 10. Agent evaluation and retirement

- DECIDED: negative months cause review, not automatic shutdown while risk and operational conditions remain satisfied. Safety breaches take immediate precedence; failed candidates are not rescued by unbounded threshold retuning.
- PROPOSED: rolling 30 closed trades as a degradation diagnostic, including net expectancy, observed slippage and calibration. OPEN: agent-specific drawdown allowance, confidence/sample policy and exact drift/slippage thresholds before automated retirement or return-to-shadow.
- DECIDED: 30 portfolio trades do not replace the existing at-least-90-days AND 100-closed-forward-trades candidate qualification. Open positions remain managed when entry is disabled or the agent is retired.
- Owners: EVAL-02/03, RW5-01, PM-09.

## 11. Notifications and incident response

- PROPOSED levels: INFO summary/dashboard; ACTION order lifecycle/daily stop; CRITICAL drawdown breach, reconciliation mismatch, persistent UNKNOWN, protection/heartbeat/auth failure. CRITICAL blocks entry; request entry cancellation only when safe. Acknowledgement silences/escalates notifications, never clears a trading gate.
- OPEN: notification channel, stale-UNKNOWN duration, heartbeat failure criteria, retry/escalation intervals and delivery evidence. Do not spam once per minute or assume a dashboard-only alarm reaches a sleeping operator.
- DECIDED: allow for 8-12 hours without operator response. Safe handling cannot depend on acknowledgement; no promise of fills during an outage.
- Owners: OPS-01, QA-03, API-04/UI-03. Notification delivery ownership requires a scoped follow-up before implementation; do not silently reuse Research credentials or grant Telegram trading control.

## 12. Operations and security

- DECIDED: trading authority stays in the backend, no withdrawal permission, no secrets in browser/repo/logs, Research isolated from Production credentials/state. The read-only dashboard key remains view-only; adding trade permission is not authorized for that key.
- DECIDED CURRENT RECOVERY: restart enters RECOVERY, restores durable state and reconciles before explicitly authorized trading. Never replay old write requests blindly. A suggested READ_ONLY/RECONCILE/SHADOW sequence must not replace canonical mode transitions without an amendment.
- PROPOSED: disk above 80% warning and above 90% no-new-entry, applied per actual mount alongside absolute free-space/durability requirements; upgrades in maintenance with unresolved orders addressed before change.
- OPEN: mount-specific absolute thresholds, maintenance treatment of open positions/protection and restore/rollback drill evidence. No automatic live phase rollback or failover is authorized.
- Owners: OPS-01/02/03, QA-03, PM-06.

## 13. Staged launch

- DECIDED: qualified immutable releases, first micro-live with one candidate, then qualified multi-agent expansion; isolated shadow and shared-capital evidence remain required.
- PROPOSED phase ceilings: first candidate MANUAL_APPROVAL at most IDR 2,000/trade; two agents at most IDR 6,000 global risk; three agents at most IDR 10,000 global subject also to the IDR 8,000 cluster and two-position cap; AUTONOMOUS_LIMITED only after separate qualification.
- OPEN: duration/trade/incident criteria for each phase. Failure must block entry and enter the applicable safe state; returning automatically to an earlier trading phase cannot bypass the failed gate. No guaranteed calendar launch date or live order authorization follows from these proposals.
- Owners: PM-05/06, RW5-01, RW6-01, QA-03.

## 14. Performance target and reporting

- DECIDED: 5% net per calendar month after trading costs, server operating costs excluded; reinvest profits during initial evidence-building. Evaluate rolling 90 days as well, without changing the target to 5% per quarter.
- DECIDED: display active-risk-period and cumulative all-period results. Risk-period renewal never resets calendar-month/rolling reports or candidate qualification history. Unknown costs/marks produce unavailable metrics, not zero or claimed profit.
- PROPOSED: cash, passive buy-and-hold and risk-matched benchmarks. OPEN: exact benchmark series, cost assumptions and risk matching. A month without closed trades is not necessarily 0% return when open positions or costs change equity. No target forces entry.
- Owners: RW3-01, RW6-01, UI-03; existing reporting/evaluation components should be reused.

## Verified venue references

Checked 2026-09-24 from official documentation, not authenticated account access or live writes:

- [Deadman Switch](https://github.com/btcid/indodax-official-api-docs/blob/master/Deadman-switch.md): pair-scoped cancel-all countdown and heartbeat example.
- [Private REST API](https://github.com/btcid/indodax-official-api-docs/blob/master/Private-RestAPI.md): documented limit/market creation, client order ID, GTC/MOC, stoplimit in read responses and April 7, 2026 legacy history decommissioning.
- [Trade API v2](https://github.com/btcid/indodax-official-api-docs/blob/master/INDODAX-TradeAPI-2.md): current order/trade history interfaces.

Authoritative release qualification, current fees, candidate identity and physical venue behavior remain separate evidence requirements. This register does not assert whether an independently running live deployment has passed those checks.
