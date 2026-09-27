# CR-EVAL-03 — Bind scored runs to candidate configuration and exposed split

Status: ACCEPTED — owner approved additive split-ID lineage on 2026-09-27.

## Problem

EVAL-03 opens a one-time exposure audit for a candidate version and dataset split, then ranks successful runs. `ExperimentRunRecord` currently carries candidate ID/version, config hash and dataset snapshot ID, while `ExposureAuditRecord` carries candidate ID/version and split ID. The run cannot prove it used the exposed split. A successful run can also carry a config hash different from the registered immutable candidate. A run created before exposure can be supplied to the leaderboard after the gate opens.

The canonical training-dataset identity explicitly separates `dataset_snapshot_id` and `split_id@version` in `docs/research/dataset-feature-contracts.md` §11; treating those IDs as interchangeable would corrupt lineage.

## Decision

- Add optional `dataset_split_id` to `ExperimentRunRecord`; include it in the content digest when non-null and persist it in the experiment registry.
- Apply a reversible additive SQLite migration adding nullable `dataset_split_id`. Existing records remain unchanged and retain their current content digests; their unknown split identity is not inferred.
- A run is leaderboard-eligible only when it is SUCCESS with a finite metric; the registered candidate ID, version and config hash match; the single-use exposure audit exists for that version; run split ID equals the audit split ID; and run creation time is not earlier than exposure time.
- Historical runs with no split ID, or any identity mismatch, remain stored but are excluded from candidate ranking. Re-evaluation under an already opened split does not repair missing historical lineage; a new approved candidate/split exposure is required.
- Keep the change within Research evaluation/registry. No Production, live trading, credential or order authority changes.

## Impact

This changes immutable run identity and the persisted experiment registry schema. Consumers constructing or reading `ExperimentRunRecord` must support the optional field. The registry migration must preserve old bytes/digests, use temporary databases in tests, and never modify a runtime database. EVAL-03 and EVAL-01 contracts/handoffs, manifest mappings and any generated projections must be updated after approval and implementation review.

## Acceptance evidence

- A v2 run round-trips its split ID and has a deterministic content digest.
- Opening an old registry database adds the nullable column without changing historical run digests.
- Candidate config mismatch, run-before-exposure, split mismatch, absent audit, missing split ID, unregistered candidate and non-finite/invalid runs do not rank.
- A successful run with matching candidate ID/version/config, split, exposure chronology and finite metric ranks.
- Migration rollback and focused evaluation/registry tests pass; independent review pins the exact code SHA.

## Rollback

Stop producing split-bound leaderboard output and restore the previous reader/code path. The additive nullable column can remain unused; do not delete or rewrite existing run rows. Do not infer split IDs for historical records.

## Approval

2026-09-27: owner approved the additive `dataset_split_id` field and fail-closed treatment of historical runs without split lineage.
