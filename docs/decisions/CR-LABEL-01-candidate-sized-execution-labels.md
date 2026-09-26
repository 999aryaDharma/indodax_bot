# CR-LABEL-01 — Candidate-sized execution labels

Status: ACCEPTED — owner approved the design and written specification on 2026-09-26.

## Problem

Independent review found LABEL-01 can mark a sample valid from raw open prices when the shared simulator rejects it for insufficient depth. The YAML execution version is also unsupported by the label config. A fixed or proxy quantity would not represent the candidate agents selected for research.

## Decision

- Each sample supplies its candidate-generated frozen `SignalIntent` and immutable candidate bundle ID. `desired_qty` is that sample's strategy sizing output. No fixed-size or implicit proxy fallback is permitted.
- Resolve `(candidate_bundle_id, sample_id)` against the authoritative immutable candidate/sample registry, then match registration ID, candidate bundle, strategy, intent ID, pair and decision time before labeling. Reuse identity governed by accepted ADR-006; do not create a parallel identity system.
- Simulate the BUY intent and, at the configured horizon after actual entry fill, a SELL for the quantity actually acquired. Use actual shared-simulator fills, fees and execution timestamps/prices in the outcome.
- No entry fill, no exit fill, or exit quantity that does not fully close acquired quantity yields `EXCLUDED` with a stable reason code. A partial entry may be labeled for actual filled quantity only when the horizon exit fully closes it.
- The target is the candidate entry's fixed-horizon outcome. It is not full-strategy PnL and does not apply candidate SL/TP before the horizon. SL/TP remain lineage inputs but do not trigger this target.
- Unknown/unverified historical fee schedules remain excluded. Labels do not qualify promotion when tariff intervals are unverified.
- Record both the cost schedule set/version and the applied entry/exit fee interval IDs. Availability includes every source bar consulted for the horizon, not only entry and exit bars.

## Impact and compatibility

This changes sample inputs and label meaning, so it requires a new versioned materialization, proposed as `net_return_candidate_horizon_v2`. Existing v1 labels and bytes remain immutable and are never silently rewritten. Consumers must explicitly request v2 and bind candidate bundle IDs. LABEL-02 stays blocked until it consumes reviewed v2 output.

Pin the v2 execution version to the shared simulator's supported version, currently `causal-bar-proxy-v2`; confirm it against code/tests during implementation. Correct the YAML mismatch by aligning the v2 config to that contract, not by adding an alias with different semantics.

No new ledger, database, venue access or production behavior is introduced. The implementation receives a resolver backed by the authoritative registry; no new identity source is created. Accepted ADR-006 governs immutable candidate identity; no new ADR is needed unless implementation changes a source-of-truth or persistence boundary.

## Risks and mitigations

- Bar-proxy fills are research estimates, not proof of live fills. Reports name the simulator/version and do not imply venue execution certainty.
- Candidate sizing may be invalid for historical pair minimums or liquidity. The simulator rejects it; labels are excluded, not rescaled.
- Fixed-horizon labels do not estimate full strategy PnL with SL/TP. Preserve that distinction in names, reports and consumer contracts.
- Cost schedule provenance remains an independent validity gate.

## Rollback

Disable v2 materialization/consumption and return to the last explicitly approved label version. Preserve v2 artifacts and v1 bytes. Corrected semantics require another label version; never overwrite historical output.

## Validation / gates

Owner approved implementation on 2026-09-26 after reviewing the written specification. Implementation must test candidate/intent lineage, candidate-specific quantity, shared entry and exit fills, no fill, incomplete exit, fee provenance and fixed-horizon semantics; obtain independent review on the exact SHA. Keep LABEL-01 in review until every AC passes.

## Owner confirmation

2026-09-25: owner selected candidate strategy quantity per sample and approved this design direction, including simulator-based BUY/exit-horizon labeling, exclusion of missing/incomplete fills, and outcome semantics distinct from SL/TP PnL.
2026-09-26: owner explicitly approved the written LABEL-01 specification and authorized implementation.
