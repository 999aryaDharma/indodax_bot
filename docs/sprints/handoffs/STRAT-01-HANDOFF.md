# STRAT-01 handoff

Status: DONE

## Identity
- Sprint ID: STRAT-01 — Declarative strategy protocol
- Implementation agent: Antigravity
- Independent reviewer: `/root/docs_review`
- Branch / worktree: `feat/strat-01-declarative-strategy-protocol`
- Base SHA: `6cf2899`
- Code target: `feat(strat-01): declarative strategy protocol`
- Evidence SHA relation: `5687c100782c6b62de53d643d855df232f6ff7ba`

## Files and contracts
- Planned files:
  - `src/indodax_lab/strategies/base.py` (StrategySpecification, DecisionFrame, create_decision_frame, RegisteredStrategy)
  - `src/indodax_lab/strategies/registry.py` (StrategyRegistry)
  - `src/indodax_lab/strategies/__init__.py` (Package exports)
  - `tests/unit/lab/strategies/test_registry.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `StrategySpecification + DecisionFrame -> list[SignalIntent]; ID/version/family/timeframes/risk/split required.`
  - Stateless decision functions over causal `DecisionFrame`; long-only spot intents (`BUY` / `SELL`, positive desired qty).
  - Registered strategies only produce declarative order intents (`SignalIntent`); zero authority over fills, executions, or ledger balances.
  - Unknown config fields strictly rejected via `extra="forbid"`.
  - Future rows (`decision_ts > as_of` or `row_ready_at > as_of`) and ineligible rows (`eligible == False`) are strictly prohibited from entering `DecisionFrame`.
  - Parameter or logic changes under the same strategy ID require an explicit semantic version bump.
- Migration and compatibility:
  - Additive strategies subsystem; backward compatible.
  - Dependencies: SIM-03 (DONE), FEAT-04 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| STRAT-01-AC0 (RED) | `test_strat_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_registry.py` | Exit 1 (Failed: DID NOT RAISE `TypeError: ONLY_SIGNAL_INTENT_ALLOWED`) | `working tree` |
| STRAT-01-AC0 (GREEN) | `test_strat_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_registry.py::test_strat_01_valid_contract` | Exit 0 (Passed, strategies only produce SignalIntent and cannot execute fills/ledger) | `5687c10` |
| STRAT-01-AC1 (RED) | `test_strat_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_registry.py` | Exit 1 (Failed: DID NOT RAISE `ValidationError`) | `working tree` |
| STRAT-01-AC1 (GREEN) | `test_strat_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_registry.py::test_strat_01_contract_1` | Exit 0 (Passed, unknown config fields strictly rejected) | `5687c10` |
| STRAT-01-AC2 (RED) | `test_strat_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_registry.py` | Exit 1 (Failed: AssertionError, future/ineligible rows present in DecisionFrame) | `working tree` |
| STRAT-01-AC2 (GREEN) | `test_strat_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_registry.py::test_strat_01_contract_2` | Exit 0 (Passed, future and ineligible rows strictly excluded from DecisionFrame) | `5687c10` |
| STRAT-01-AC3 (RED) | `test_strat_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_registry.py` | Exit 1 (Failed: DID NOT RAISE `ValueError: PARAMETER_OR_LOGIC_CHANGE_REQUIRES_VERSION_BUMP`) | `working tree` |
| STRAT-01-AC3 (GREEN) | `test_strat_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_registry.py::test_strat_01_contract_3` | Exit 0 (Passed, parameter and logic modifications require semantic version bump) | `5687c10` |

All 4 tests in `tests/unit/lab/strategies/test_registry.py` passed (1.02s).
Combined suite verification (63 passed across backtest, risk, execution, ledger, costs, features, labels, and strategies) passed (2.20s).

## Review
- Spec verdict: PASS (meets all functional requirements of STRAT-01 and specs/10-strategy-catalog-and-protocol.md).
- Quality verdict: PASS (pure stateless decision protocol, zero ledger mutation, strict causality, fail-closed config validation).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: Added test package `__init__.py` markers under `tests/unit/lab/` to resolve pytest import module collision between feature and strategy registries.
- Unresolved issues / blockers: None for STRAT-01.
- Next unlocked consumers: C01-01, C07-01, C02-01, C03-01, C04-01, S01-01, S02-01, C05-01, C06-01, C08-01, C09-01, C11-01, S03-01, S04-01, S05-01, S06-01, S08-01, S09-01.


## Independent review findings (2026-09-25)

Reviewer `/root/docs_review` reviewed exact repository SHA `e3f1af8d232c1bf43fdf325922c96376bb542bc0` and returned CHANGES_REQUESTED. Independent command `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/backtest/test_metrics.py tests/unit/lab/strategies/test_registry.py -q -p no:cacheprovider` -> 8 passed in 1.07s; negative probes reproduced the findings.

- Important — RegisteredStrategy retains the caller-owned StrategySpecification and writable callback. Mutating nested `spec.parameters` after registration changes the registered strategy without a version bump.
- Important — `_compute_logic_hash` ignores closure captures and callable defaults. `factory(1)` and `factory(2)` behave differently but hash identically; same ID/version registration accepts both.
- Important — nonempty frames may omit `decision_ts`, `row_ready_at`, and `eligible`; direct DecisionFrame also accepts NaT timestamps. AC2 requires causal/eligibility evidence, not optional checks.
- Passing boundaries: unknown config fields and non-SignalIntent returns are rejected; registered strategy has no fill/ledger authority.

## Remediation candidate (2026-09-26)

- Code commit: `14848d303629390a4a64005a8fa50d06c88ffb46` (`fix(strat-01): reject unpinned callback state`).
- Findings corrected: bound Python methods are rejected because receiver state is not frozen; captured `list` and `tuple` values have distinct logic identities. Defensive spec copies, closure/default hashing, callback mutation checks and decision evidence checks remain in place.
- Regressions: `test_stateful_bound_method_is_rejected` and `test_list_and_tuple_captures_have_distinct_logic_identity`.
- Focused check: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/cli/test_run_backtest_report.py tests/unit/lab/strategies/test_registry.py -q -p no:cacheprovider` -> 14 passed (the command includes SIM-04 checks).
- Full check on combined code HEAD `3f2623b884a5066cdbaf8a27f85e517c03fa9885`: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q -p no:cacheprovider` -> 1,103 passed, 2 platform-specific skipped, 4 warnings.
- Independent review of the remediation commit is pending. Keep status CHANGES_REQUESTED until reviewer PASS and manifest update.

### Typed capture identity remediation

- Code commit: `65291562c270b36111873d7dc2e072bc97824c3e` (`fix(strat-01): type-tag strategy capture identities`).
- Finding corrected: every supported captured value uses an unambiguous type-tagged encoding; dictionaries, `Decimal`, sets/frozensets, booleans/integers, models, enums, sequences and scalar values cannot alias by serialization shape.
- Regression: `test_all_capture_types_have_unambiguous_identity` covers `Decimal`/mapping, set/frozenset and bool/int collisions; prior list/tuple and bound-method regressions remain.
- Full verification on combined code HEAD `b177691d19713b901d3a4f2f1b8a5d38779efe0a`: 1,107 passed, 2 platform-specific skipped, 4 warnings.
- Independent exact-SHA review remains pending; status stays CHANGES_REQUESTED.

## Independent review closeout (2026-09-26)

- `/root/docs_review` reviewed exact code SHA `b177691d19713b901d3a4f2f1b8a5d38779efe0a`: **PASS**, no Critical/Important findings. Review confirmed bound callbacks reject and typed captures distinguish Decimal/mapping, set/frozenset, bool/int, and list/tuple identities.
- Independent focused evidence: metrics, CLI reports, strategy registry and labels -> 55 passed in 1.32s. Full local suite on the same source tree -> 1,107 passed, 2 platform-specific skipped, 4 warnings; full suite was not independently rerun.
- Code commits: `14848d303629390a4a64005a8fa50d06c88ffb46` and `65291562c270b36111873d7dc2e072bc97824c3e`.
- Capture identity encoding changed; all future candidate logic hashes use typed canonical values.
