# CR-EVAL-04 — Persist leaderboard metric exclusions

Status: PROPOSED — owner decision required before schema or behavior changes.

## Problem

EVAL-03 currently excludes a successful run with a non-finite selected metric from ranking, but `compute_leaderboard` silently drops it. The run itself remains in the experiment registry, but there is no durable record that the leaderboard rejected its metric. The prior EVAL-03 review recorded this as an Important finding and identified persistence as a schema change.

## Proposed decision

- Persist a reason-coded exclusion for a run that otherwise matches a registered candidate's ID/version/config, has a valid matching exposure audit and split, and is not earlier than exposure, but whose selected ranking metric converts to NaN or infinity.
- Store the exclusion in a new append-only table in the existing candidate lifecycle SQLite database. Bind it to run content digest, exposure ID, candidate/version, split ID, metric name and stable reason `RANK_METRIC_NON_FINITE`; do not copy a NaN/Infinity value into JSON or treat it as zero.
- Derive an idempotent exclusion ID from those immutable identities and insert transactionally. Repeated leaderboard evaluation of the same run/exposure/metric must not create duplicate records.
- Preserve current ranking behavior: excluded runs remain unranked. Add a read-only query for exclusion records so reports/operators can explain why the run did not appear.
- Do not reconstruct exclusion records for legacy runs. Missing metrics, conversion errors, unsuccessful runs and candidate/exposure mismatches remain out of this change unless separately approved.
- Keep the change in Research evaluation. No Production, credential, order, account or live host behavior changes.

## Impact

- Add an additive SQLite table and a small query surface to the existing lifecycle owner; existing candidate/run/exposure rows and content digests are unchanged.
- Update EVAL-03's contract, data/persistence and failure evidence sections, plus the focused handoff/test mapping.
- Use temporary databases only. The migration must be idempotent; rollback leaves the new table and append-only evidence intact, while old readers may ignore it.

## Acceptance evidence

- A candidate/config/exposure-eligible run with NaN or either infinity returns no leaderboard entry and creates exactly one durable reason-coded exclusion.
- Repeating the same evaluation is idempotent; changing candidate, exposure, split or metric identity cannot alias the original exclusion record.
- Invalid, failed, pre-exposure, config-mismatched, split-mismatched or unregistered runs do not create a metric-exclusion record.
- Reopening a legacy lifecycle database adds the table without rewriting existing rows; reopening again is safe.
- The exclusion read path exposes lineage and reason without logging private payloads or serializing a non-finite number.
- Focused evaluation/lifecycle tests pass and an independent reviewer approves the exact SHA.

## Rollback

Stop producing new exclusion records and stop exposing the optional query. Leave the additive table and historical rows intact; do not infer records for prior runs or drop the table during rollback.

## Approval

Owner decision: pending.
