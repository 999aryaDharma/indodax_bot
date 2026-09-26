# CR-S04 — Order flow decision inputs

Status: ACCEPTED — owner approved on 2026-09-27.

## Problem

S04-01 requires registered book/trade imbalance plus sequence, session, and availability evidence, but the canonical feature registry does not expose an approved LOB feature set to `DecisionFrame`. LOB-01 validates eligible book windows and computes depth imbalance; it does not define the S04 decision-frame fields or a trade/book imbalance horizon contract. Implementing S04 against ad hoc row keys would create an unversioned feature schema and could let stale, future, or sequence-broken book data enter research labels or signals.

## Proposed decision

Define an additive `lob_v1` S04 input contract, consumed only from the research `DecisionFrame`:

- `book_imbalance_l5`: normalized book-depth imbalance in `[-1, 1]`.
- `trade_imbalance_10s`: normalized signed trade imbalance in `[-1, 1]`.
- `book_event_ts` and `book_available_at`: UTC timestamps, both `<= DecisionFrame.as_of`.
- `book_session_id`: non-empty source session identity.
- `book_sequence_contiguous`: explicit boolean; false, missing or unknown abstains.

Candidate default decision gates: both imbalance values `>= 0.10`, book event age at most 5 seconds, and positive finite close. Thresholds remain research hypotheses in `S04_v1.yaml`; no performance claim is made. Missing/invalid timestamps or flags fail closed. Strategy output remains `SignalIntent` only; no fill/order authority is added.

## Impact

- Add versioned `lob_v1` features and exact units/source/availability to the research feature contract and registry.
- Add S04 config/source/tests and a small S04 spec update after approval.
- No generic `DecisionFrame` fields, Production authority, credentials, live order behavior, or database migrations change; the approved feature row carries these additive, versioned inputs.
- Existing LOB sequence/session validation remains the producer boundary. Real Indodax book/trade collection and >=90-day coverage remain external qualification gates; this CR does not claim either exists.

## Validation and rollback

Tests must cover valid aligned book/trade inputs, exact imbalance thresholds, missing/unknown sequence state, sequence gaps, stale books, future event/availability timestamps, invalid session identity, and no execution side effects. If rejected, leave the canonical feature contract unchanged and keep S04-01 READY. Rollback disables S04/`lob_v1` consumption and retains immutable raw/event data.

## Decision

Owner approval: accepted on 2026-09-27. Implement the versioned research inputs and gates above. The 0.10 imbalance thresholds and 5-second maximum book age are research defaults only; real-feed coverage and >=90-day qualification remain external gates.
