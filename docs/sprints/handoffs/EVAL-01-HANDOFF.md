# EVAL-01 handoff

Status: DONE

## Identity
- Sprint ID: EVAL-01 — Immutable experiment registry
- Implementation agent: Antigravity
- Independent reviewer: `/root/docs_review` (PASS at exact remediation SHA)
- Branch / worktree: `feat/eval-01-immutable-experiment-registry`
- Base SHA: `81f03df`
- Code target: `feat(eval-01): immutable experiment registry`
- Evidence SHA relation: initial implementation `3f3318e30dd04a0103ef00df04e73f307503bb99`; remediation `be3a40359653a79d9aa7f07152b8d27fcdd6eb6f`

## Files and contracts
- Planned files:
  - `src/indodax_lab/evaluation/registry.py` (ExperimentRunStatus, ExperimentRunRecord, ExperimentRegistry)
  - `src/indodax_lab/evaluation/__init__.py` (Package exports)
  - `tests/unit/lab/evaluation/test_registry.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `run_id + parent + git SHA + environment/data/config/cost/execution hashes -> immutable run record.`
  - SQLite local append-only transactions; unique run IDs and transitions.
  - Every experiment run (SUCCESS, FAILED, or INVALID_RUN) is immutably recorded with complete configuration and ancestry.
  - Dirty worktree (`is_dirty=True`) cannot produce a promotable run (`promotable=False`).
  - Failed/invalid trials are included in the trial count for honest accounting without survivorship bias.
  - Duplicate run key cannot overwrite existing runs with different results.
- Migration and compatibility:
  - Additive evaluation subsystem; backward compatible.
  - Dependencies: SIM-04 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| EVAL-01-AC0 (RED) | `test_eval_01_valid_contract` | `python -m pytest tests/unit/lab/evaluation/test_registry.py` | Exit 1 (Failed: ancestry chain not traced) | `working tree` |
| EVAL-01-AC0 (GREEN) | `test_eval_01_valid_contract` | `python -m pytest tests/unit/lab/evaluation/test_registry.py::test_eval_01_valid_contract` | Exit 0 (Passed, stores parent & child runs and traces ancestry) | `3f3318e` |
| EVAL-01-AC1 (RED) | `test_eval_01_contract_1` | `python -m pytest tests/unit/lab/evaluation/test_registry.py` | Exit 1 (Failed: DID NOT RAISE `ValueError`) | `working tree` |
| EVAL-01-AC1 (GREEN) | `test_eval_01_contract_1` | `python -m pytest tests/unit/lab/evaluation/test_registry.py::test_eval_01_contract_1` | Exit 0 (Passed, dirty worktree cannot be promotable) | `3f3318e` |
| EVAL-01-AC2 (RED) | `test_eval_01_contract_2` | `python -m pytest tests/unit/lab/evaluation/test_registry.py` | Exit 1 (Failed: AssertionError, failed trials omitted from count) | `working tree` |
| EVAL-01-AC2 (GREEN) | `test_eval_01_contract_2` | `python -m pytest tests/unit/lab/evaluation/test_registry.py::test_eval_01_contract_2` | Exit 0 (Passed, failed trials strictly included in trial count) | `3f3318e` |
| EVAL-01-AC3 (RED) | `test_eval_01_contract_3` | `python -m pytest tests/unit/lab/evaluation/test_registry.py` | Exit 1 (Failed: DID NOT RAISE `ValueError`) | `working tree` |
| EVAL-01-AC3 (GREEN) | `test_eval_01_contract_3` | `python -m pytest tests/unit/lab/evaluation/test_registry.py::test_eval_01_contract_3` | Exit 0 (Passed, duplicate run key cannot overwrite different outcome) | `3f3318e` |

All 4 tests in `tests/unit/lab/evaluation/test_registry.py` passed (0.38s).
Combined suite verification (67 passed across backtest, risk, execution, ledger, costs, features, labels, strategies, and evaluation) passed (2.09s).

## Review
- Spec verdict: PASS (meets all functional requirements of EVAL-01 and specs/11-evaluation-and-experiment-lifecycle.md).
- Quality verdict: PASS (content digest checking, append-only SQLite schema, honest trial accounting, dirty worktree gate).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PASS at exact remediation SHA `be3a40359653a79d9aa7f07152b8d27fcdd6eb6f`.

## Remediation review round 1

- Exact reviewed SHA: `b49898c62a2fd9c3f076746f98a8622d292e5379`.
- Verdict: CHANGES_REQUESTED for Important findings: invalid/missing/cyclic ancestry was not rejected; persisted rows were not checked against content hashes on reads; failed or invalid runs could be promotable.
- Fix commit: `be3a40359653a79d9aa7f07152b8d27fcdd6eb6f`.
- Fixes: inserts validate a complete existing parent chain in an immediate transaction; ancestry reads reject missing links and cycles; reads and idempotent duplicate writes verify persisted content hashes; only clean successful runs may be promotable.
- Regression checks: `python -m pytest tests/unit/lab/evaluation/test_registry.py -q` — 9 passed; `python -m ruff check --select I,F401 src/indodax_lab/evaluation/registry.py tests/unit/lab/evaluation/test_registry.py` — passed; `git diff --check` — passed.
- Independent remediation review: PASS at exact fix SHA `be3a40359653a79d9aa7f07152b8d27fcdd6eb6f`; reviewer confirmed all findings closed and no remaining Critical/Important findings.

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for EVAL-01.
- Next unlocked consumers: EVAL-02, ML-03, JOB-01, OPS-03.
