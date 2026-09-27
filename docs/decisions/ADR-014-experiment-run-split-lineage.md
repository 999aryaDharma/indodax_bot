# ADR-014 — Bind experiment scores to the exposed dataset split

Status: ACCEPTED — 2026-09-27. Related: CR-EVAL-03.

## Context

EVAL-03 opens a single-use exposure audit for a candidate version and split. `ExperimentRunRecord` previously stored the source `dataset_snapshot_id` but not the `split_id`; those identities are separate in the canonical training-dataset contract. A run on a different split could therefore be ranked after the exposure gate opened. Run config hashes and exposure chronology also need to match the registered candidate and audit.

## Decision

- Store optional `dataset_split_id` on experiment runs and include it in the run's content digest when present.
- Add a nullable SQLite column. Never infer split identity for historical rows; their existing digest bytes remain valid and the missing field remains `None`.
- The EVAL-03 leaderboard requires an exact candidate ID/version/config hash, a matching exposure audit split ID, and `created_at >= exposed_at`, in addition to a successful run with a finite metric.
- Runs missing split lineage remain queryable in the experiment registry but are not candidate-leaderboard eligible.

## Consequences

- The experiment-run public record and SQLite schema are extended additively.
- Old records and digests remain immutable; old binaries may not validate new split-bound run digests, so code rollback after writing such records must preserve the new schema and use a compatible reader. No destructive down migration is allowed.
- This adds no Production integration, credentials, fills, order authority or live account access.

## Validation

Test new-record digest/round-trip, idempotent migration from a legacy database, preservation of old digests, and exclusion of missing or mismatched split lineage at the candidate leaderboard boundary. Use temporary databases only.
