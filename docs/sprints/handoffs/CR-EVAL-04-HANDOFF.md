# CR-EVAL-04 implementation handoff

Status: REVIEW — approved implementation independently passed; EVAL-03 coordinator sync remains pending.

## Identity

- Change request: CR-EVAL-04 — Persist leaderboard metric exclusions
- Owner: Codex `/root`
- Branch: `feat/feat-02-finalization`
- Implementation commit and source SHA: `64769f883a15c76bbf680b52d6530053edae4ae0`
- EVAL-03 handoff remains owned by another active thread; this supplemental handoff records the approved additive change without editing that working file.

## Scope

- Added additive `leaderboard_metric_exclusions` table, initialized idempotently by `CandidateLifecycleManager`.
- Persisted a deterministic exclusion ID bound to run digest, exposure ID, candidate/version, split, selected metric name and reason `RANK_METRIC_NON_FINITE`.
- Writes are transactional and conflict-idempotent. The non-finite numeric value is not stored in the audit row. Ranking behavior is unchanged.
- Added `get_leaderboard_exclusions()` and exported the immutable record model.
- EVAL-03 spec and approved CR decision updated. No experiment registry rows/digests or Production state changed.

## Evidence

- TDD RED: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/evaluation/test_eval_04_metric_exclusions.py -q -p no:cacheprovider` — 5 failed on the missing query/table behavior.
- Focused GREEN at source SHA above: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/evaluation/test_eval_04_metric_exclusions.py tests/unit/lab/evaluation/test_lifecycle_fail_closed.py tests/unit/lab/evaluation/test_lifecycle.py -q -p no:cacheprovider` — 25 passed.
- Lint: `C:/Users/User/miniconda3/envs/ML/Scripts/ruff.exe check --select I,F401 src/indodax_lab/evaluation/lifecycle.py src/indodax_lab/evaluation/__init__.py tests/unit/lab/evaluation/test_eval_04_metric_exclusions.py` — passed.
- Diff check: `git diff --check` on all scoped paths — passed.
- Full suite: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q -p no:cacheprovider` — 1,684 passed, 2 skipped, 5 failed. All 5 failures are in `tests/unit/lab/strategies/test_versioned_registry.py` and caused by the concurrently modified `configs/strategies/C07_v1.yaml` containing parameters rejected by the current C07 parameter model. No EVAL-04 test failed; unrelated thread changes were preserved.

## Acceptance mapping

- NaN, positive infinity and negative infinity on an otherwise eligible run are excluded and recorded with lineage/reason; repeated evaluation does not duplicate rows.
- Failed, pre-exposure, configuration-mismatched, split-mismatched, missing-split, unregistered, missing-metric and unconvertible-metric cases create no exclusion row.
- Exclusion identity changes with run digest, exposure, candidate, split or metric identity.
- Reopening after removal of the additive table recreates it idempotently without changing candidate or exposure rows.

## Review and gates

- Independent review: PASS at exact source SHA `64769f883a15c76bbf680b52d6530053edae4ae0`; no Critical/Important findings. Reviewer verified eligibility ordering, identity binding, transactional/idempotent writes, additive migration and test coverage. Reviewer did not independently rerun tests; commit-failure/retry behavior was inspected from the transaction and primary-key constraints.
- Shared sprint manifest: not edited while another thread's sprint evidence changes remain unsynced. EVAL-03 remains REVIEW until its coordinator resolves the existing shared handoff and this CR's independent review.
- Rollback: stop invoking the exclusion write/read paths; retain the additive table and records. No destructive migration is needed.
