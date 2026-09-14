# ADR-002 — Causality and cost application exactly once

Status: ACCEPTED planning correction. Date: 2026-09-14.

Context: old mapper named input expected_net_return but compared it against costs again. Old label example equated availability with exit event time, ignoring source ingestion latency. Legacy plan listed label implementation before its cost/execution dependencies.

Decision:

- Forecast must declare target basis. NET_RETURN compares against safety_margin only. GROSS_RETURN compares against estimated round-trip cost + margin. PROBABILITY maps calibrated probability and expected gross payoff to edge, then subtracts cost once. Reject unknown semantics rather than guessing.
- Label availability is max availability of all outcome source observations; never earlier than final fill/exit event. Apply training cutoff to this value.
- Cash equity already reflects paid fees. Equity = cash + marked assets; subtracting fee expense again double counts. Journal balances valued postings in quote currency and separately tracks asset quantities. No adding koin units to IDR.
- Window boundaries are [start,end); bars require close/availability chronology. Fitted thresholds carry train_end and available_at.
- 2024/2025 roles are a historical proposed split, not automatic sealed status. Record actual exposure; once seen, a holdout cannot be resealed for the same family by renaming it.
- Collector may recognize identical wire duplicates as transport retry; strict accepted trade batches and sentry reject duplicate IDs/conflicts. Dedup never erases conflicting bytes or a gap.

Consequences: LABEL-01 waits for SIM-01 and FEAT-04. ML-02 must add equivalent gross/net forecast regression. Existing historical evidence is not retroactively rewritten as proof of these future capabilities.
