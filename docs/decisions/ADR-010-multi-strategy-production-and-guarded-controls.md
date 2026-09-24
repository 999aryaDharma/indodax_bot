# ADR-010 — Multi-strategy Production release and guarded controls

Date: 2026-09-24. Status: ACCEPTED owner decision; implementation and qualification pending.

## Context

The owner selected multiple Production strategies (for example BTC, ETH and altcoins) sharing one account's capital. Earlier frozen text uses a singular candidate. The previously admitted control-plane delivery is read-only. The owner now requests planned guarded allocation and lifecycle controls.

## Decision

One reviewed release may bind multiple immutable candidates with exclusive pair ownership, a versioned allocation policy and per-candidate qualification evidence. There remains one central portfolio/risk/OMS/ledger/reconciliation authority. A one-candidate release is the cardinality-one case; legacy evidence remains readable but cannot silently satisfy the new schema.

All account assets are observed and reconciled; existing assets require reviewed adoption before strategy execution. Account use is bot-exclusive. Equity-based risk sizing, shared-pool risk and exposure limits, confirmed-fill accounting and draining replacement follow the [program contract](../implementation/BOT-TRADE-PROGRAM.md).

API-04 and UI-03 are admitted for guarded adoption, allocation, pause-entry, resume, halt and draining commands. Their backend authority, authentication, audit, revision fencing and idempotency are mandatory. This supersedes the earlier CR's read-only admission only for those new tasks; completed read routes do not acquire writes. No direct exchange order or withdrawal control is admitted.

## Supersession and consequences

This explicitly amends singular-candidate interpretation in frozen Production Main, its candidate/release contract and G2/G3/G6/G7 wording: every included candidate must carry required evidence; micro-live begins with one reviewed candidate before any qualified multi-candidate expansion. New multi-strategy releases also require shared-capital evaluation of their exact candidate set and policy. No duration/trade-count or operational gate is weakened. Approval remains release-specific.

Research tournament wallets remain isolated. Portfolio Shadow is the distinct shared-capital qualification environment. Policy identity or candidate changes invalidate applicability of prior combination evidence and require new evaluation; unchanged per-candidate evidence retains its original provenance.

SL/TP execution depends on verified venue capability and declared adapter behavior. Stops cannot promise execution price or outage protection. Production credentials, live state and deployment are outside this documentation delivery. ADR-009 host isolation and mixed-load qualification remain in force.

## Alternatives rejected

Per-strategy Production wallets/ledgers create competing financial authorities. Overlapping pair ownership requires subposition/fill arbitration the owner did not select. Automatic asset rebalancing and hot-edited candidate exit rules are excluded. Shared-pool access is not cross-cap borrowing because agents have no fixed capital quotas.

## Validation

Implement the program's targeted tests, independently review exact SHAs, then satisfy existing release gates. Documentation acceptance is not implementation PASS or live authorization.

## Owner amendment — dynamic shared pool (2026-09-24)

The owner supersedes the earlier fixed per-strategy capital-cap allocation and sum-at-most-one rule with one dynamic shared pool. Agent-owned immutable rules determine adaptive sizing, SL and TP; central risk, cash, reservations and venue constraints remain authoritative. Below-minimum proposals reject without increasing risk or changing the stop merely to meet a minimum. This amendment supersedes fixed-quota wording in the original program and frozen Main amendment; PM-08 and downstream Portfolio Shadow consume the revised program. Existing release gates and credential isolation are unchanged.

## Owner amendment — dashboard defaults and capital floor (2026-09-24)

Accept the program's configurable Main/agent drafts with separate default, draft and active values. The initial-capital 20% rule originally accepted in this amendment is superseded by the absolute peak-equity drawdown amendment below. At/below the floor, centrally governed controlled close-out supersedes waiting for candidate exit signals, but never bypasses operational write gates, ownership, fill accounting or reconciliation. Candidate replacement draining and operational HALT retain their existing meanings. Resume is manual and cannot bypass the floor.

Defaults never overwrite active settings. Per-trade risk remains an evaluation choice between 0.5% and 1%; aggregate/daily-loss limits and cash-flow baseline adjustment are not silently invented. Missing mandatory settings block activation of the new policy. PM-08, PM-09, API-04 and UI-03 own integration through existing interfaces. Existing read-only API/UI and live runtime remain unchanged by this documentation.

## Owner amendment — absolute drawdown and unattended operation (2026-09-24)

Supersede the 20% initial-capital loss rule with an absolute IDR 100,000 decline from cash-flow-adjusted peak equity. Floor = adjusted peak minus IDR 100,000; valid new trading peaks raise it, losses do not lower it. Persist peak and breach state across restart; manual resume cannot reset them. The floor is an action trigger, not a guaranteed maximum realized loss. Reviewed cash-flow adjustment remains required; no formula is inferred from deposits/withdrawals.

Reinvest profits during initial qualification. A negative month prompts evaluation, not automatic shutdown while all risk/operational conditions remain valid. The 5% monthly target is net of trading costs and excludes server operating costs. Operator response may be absent for 8-12 hours; qualify autonomous safe incident handling without admitting automatic resume/failover or assuming stops work during outages. Program, PM-08/PM-09/API-04/UI-03 and OPS-01/QA-03 carry the current requirements. Historical handoffs retain their original evidence and do not certify this amendment.

## Owner amendment — risk-period renewal and reporting horizon (2026-09-24)

After the absolute drawdown triggers completed close-out, the owner may approve a new risk period through a separate audited decision with incident review, zero UNKNOWN, full reconciliation and qualified release/risk policy. Supersede any interpretation that the old breached peak permanently prevents all future periods: the old period remains immutable while the newly approved period starts from verified actual equity. Ordinary resume never resets a peak, creates a period or erases losses. New-period approval does not resume trading; existing explicit resume and write gates still apply.

Retain the 5% net calendar-month target after trading costs, excluding server operating costs; add rolling 90-day evaluation, not a replacement 5% quarterly target. Preserve cumulative all-period performance and the unchanged 90-day AND 100-closed-forward-trade candidate gate. PM-08, PM-09, API-04 and UI-03 consume the program contract through existing proposal/state authorities. Other suggested baseline amounts are not frozen by this amendment.

## Owner amendment — numeric baseline for qualification (2026-09-24)

The owner explicitly approves these policy v1 defaults for testing before activation: IDR 4,000 per trade, IDR 10,000 global open/pending risk, IDR 8,000 combined BTC/ETH/SOL cluster risk, IDR 15,000 daily loss, two simultaneous live positions, 25% equity notional per pair and 50% total deployment. These supersede the prior unset numerical settings and 0.5%/1% sizing choice as current defaults; they do not certify safe live behavior or permit activation without evidence. Pending entries consume capacity; actual fills transfer reservation risk into position risk. Daily reset, execution/liquidity/incident details and other proposals remain separately marked in the linked decision register.
