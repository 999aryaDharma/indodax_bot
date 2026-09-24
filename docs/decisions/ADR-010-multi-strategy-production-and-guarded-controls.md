# ADR-010 — Multi-strategy Production release and guarded controls

Date: 2026-09-24. Status: ACCEPTED owner decision; implementation and qualification pending.

## Context

The owner selected multiple Production strategies (for example BTC, ETH and altcoins) sharing one account's capital. Earlier frozen text uses a singular candidate. The previously admitted control-plane delivery is read-only. The owner now requests planned guarded allocation and lifecycle controls.

## Decision

One reviewed release may bind multiple immutable candidates with exclusive pair ownership, a versioned allocation policy and per-candidate qualification evidence. There remains one central portfolio/risk/OMS/ledger/reconciliation authority. A one-candidate release is the cardinality-one case; legacy evidence remains readable but cannot silently satisfy the new schema.

All account assets are observed and reconciled; existing assets require reviewed adoption before strategy execution. Account use is bot-exclusive. Equity-based risk sizing, strategy allocation caps, confirmed-fill accounting and draining replacement follow the [program contract](../implementation/BOT-TRADE-PROGRAM.md).

API-04 and UI-03 are admitted for guarded adoption, allocation, pause-entry, resume, halt and draining commands. Their backend authority, authentication, audit, revision fencing and idempotency are mandatory. This supersedes the earlier CR's read-only admission only for those new tasks; completed read routes do not acquire writes. No direct exchange order or withdrawal control is admitted.

## Supersession and consequences

This explicitly amends singular-candidate interpretation in frozen Production Main, its candidate/release contract and G2/G3/G6/G7 wording: every included candidate must carry required evidence; micro-live begins with one reviewed candidate before any qualified multi-candidate expansion. New multi-strategy releases also require shared-capital evaluation of their exact candidate set and policy. No duration/trade-count or operational gate is weakened. Approval remains release-specific.

Research tournament wallets remain isolated. Portfolio Shadow is the distinct shared-capital qualification environment. Policy identity or candidate changes invalidate applicability of prior combination evidence and require new evaluation; unchanged per-candidate evidence retains its original provenance.

SL/TP execution depends on verified venue capability and declared adapter behavior. Stops cannot promise execution price or outage protection. Production credentials, live state and deployment are outside this documentation delivery. ADR-009 host isolation and mixed-load qualification remain in force.

## Alternatives rejected

Per-strategy Production wallets/ledgers create competing financial authorities. Overlapping pair ownership requires subposition/fill arbitration the owner did not select. Automatic rebalance, automatic cross-cap borrowing and hot-edited candidate exits are excluded.

## Validation

Implement the program's targeted tests, independently review exact SHAs, then satisfy existing release gates. Documentation acceptance is not implementation PASS or live authorization.
