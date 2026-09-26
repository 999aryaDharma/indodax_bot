# LABEL-01 handoff

Status: CHANGES_REQUESTED

## Identity
- Sprint ID: LABEL-01 — Execution-aligned net return labels
- Implementation agent: Antigravity
- Independent reviewer: `/root/docs_review`
- Branch / worktree: `feat/label-01-execution-aligned-net-return-labels`
- Base SHA: `8f13eab`
- Code target: `feat(label-01): execution-aligned net return labels`
- Evidence SHA relation: `f323cd0`

## Files and contracts
- Planned files:
  - `src/indodax_lab/labels/returns.py` (NetReturnConfig, NetReturnLabel, build_net_return_label, build_net_return_labels_frame)
  - `src/indodax_lab/labels/__init__.py` (Public exports for labels domain)
  - `configs/labels/net_return_v1.yaml` (Canonical net return configuration)
  - `tests/unit/lab/labels/test_returns.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `sample + horizon + fill model -> entry/exit, gross/net return, costs and label_available_at`.
  - Exact accounting: `net_return = (net_sell_proceeds / total_buy_cash_debit) - 1` with distinct buy and sell fee tracking.
  - Causal execution: entry happens strictly at next eligible execution bar; entry at or before decision timestamp is strictly rejected.
  - Fail-closed incomplete horizon: missing future terminal bars produce excluded/censored labels, never silent zero returns.
  - Cost schedule gating: missing or unknown fee schedule excludes sample rather than fabricating free execution.
- Migration and compatibility:
  - Additive labels subsystem; backward compatible.
  - Dependencies: FEAT-04 (DONE), SIM-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| LABEL-01-AC0 (RED) | `test_label_01_valid_contract` | `python -m pytest tests/unit/lab/labels/test_returns.py` | Exit 1 (import failure; not behavioral RED evidence) | `working tree` |
| LABEL-01-AC0 (GREEN) | `test_label_01_valid_contract` | `python -m pytest tests/unit/lab/labels/test_returns.py::test_label_01_valid_contract` | Exit 0 (Passed, measures net proceeds relative to gross debit from execution model) | `f323cd0` |
| LABEL-01-AC1 (RED) | `test_label_01_contract_1` | `python -m pytest tests/unit/lab/labels/test_returns.py` | Exit 1 (import failure; not behavioral RED evidence) | `working tree` |
| LABEL-01-AC1 (GREEN) | `test_label_01_contract_1` | `python -m pytest tests/unit/lab/labels/test_returns.py::test_label_01_contract_1` | Exit 0 (Passed, entry before decision is strictly rejected) | `f323cd0` |
| LABEL-01-AC2 (RED) | `test_label_01_contract_2` | `python -m pytest tests/unit/lab/labels/test_returns.py` | Exit 1 (import failure; not behavioral RED evidence) | `working tree` |
| LABEL-01-AC2 (GREEN) | `test_label_01_contract_2` | `python -m pytest tests/unit/lab/labels/test_returns.py::test_label_01_contract_2` | Exit 0 (Passed, incomplete horizon produces excluded sample, never zero) | `f323cd0` |
| LABEL-01-AC3 (RED) | `test_label_01_contract_3` | `python -m pytest tests/unit/lab/labels/test_returns.py` | Exit 1 (import failure; not behavioral RED evidence) | `working tree` |
| LABEL-01-AC3 (GREEN) | `test_label_01_contract_3` | `python -m pytest tests/unit/lab/labels/test_returns.py::test_label_01_contract_3` | Exit 0 (Passed, unavailable cost schedule excludes sample) | `f323cd0` |

All 4 tests in `tests/unit/lab/labels/test_returns.py` passed (0.93s).
Combined suite verification (59 passed across backtest, risk, execution, ledger, costs, features, and labels) passed (2.04s).

## Review
- Original implementation owner verdict: PASS; superseded by independent review below, which found AC0/AC3 incomplete.
- Existing tests verify Decimal arithmetic, strict causality, incomplete horizon and UTC inputs; they do not verify shared simulator fill alignment.
- Independent findings: two Important findings listed below.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: CHANGES_REQUESTED on exact repository SHA `8ecd154f466776a59dfeda38204b40d558efdf8d`; 2 Important findings.

## Independent review findings (2026-09-25)

1. AC0/AC3 are incomplete: `returns.py` computes from raw bar opens and never uses `ConservativeExecutionSimulator`. Reviewer reproduced zero-depth bars yielding `VALID` (`net_return=0.005970077826365251514952114`) while the same one-unit BUY through the simulator returns `INSUFFICIENT_DEPTH` with no fill. AC3 tests only unavailable cost schedules, not unavailable fills.
2. Canonical `configs/labels/net_return_v1.yaml` specifies `conservative_v1`, but `NetReturnConfig` rejects that model as unsupported.

AC1 and AC2 pass. Independent focused label tests: 21 passed, but passing tests do not cover these findings. Owner decision (2026-09-25): use candidate-specific sizing per sample and approved the written design direction. CR and contracts now define immutable candidate bundle lineage, candidate `SignalIntent`, shared simulator BUY and fixed-horizon SELL, exclusions for no/incomplete fills, and target semantics separate from SL/TP PnL. Materialization is versioned `net_return_candidate_horizon_v2`; existing v1 output stays immutable. Written-spec review is pending; no implementation until approval.

## Deviations and known risks
- Deviation: implementation is currently an open-price research proxy, not the shared execution simulator required by AC0/AC3.
- Unresolved issues: two Important findings remain open (fill-model alignment/fill-unavailable exclusion; unsupported canonical execution model).
- LABEL-02 remains unavailable until LABEL-01 returns to DONE.

## Approved change-control implementation candidate (2026-09-26)

- Owner approved the written design and implementation after review: [CR-LABEL-01](../../decisions/CR-LABEL-01-candidate-sized-execution-labels.md). Existing `net_return_v1` path is unchanged; candidate labels use separate `net_return_candidate_horizon_v2` identity and config.
- Code commit: `3f2623b884a5066cdbaf8a27f85e517c03fa9885` (`feat(label-01): add candidate horizon execution labels`).
- Actual surface: `CandidateHorizonSample`, `CandidateHorizonConfig`, `CandidateHorizonLabel`, `load_candidate_horizon_config`, `build_candidate_horizon_label(s)` in `src/indodax_lab/labels/returns.py`, exported by the labels package. Simulator is injected and version-pinned to `causal-bar-proxy-v2`.
- Contract: candidate bundle plus frozen BUY intent and matching strategy/pair/decision lineage; actual strategy-sized BUY and exact-horizon TAKER SELL go through `ConservativeExecutionSimulator`. Return is based on actual fill quantities/prices/fees. Partial entry is recorded only when fully exited. Missing fills, unverified costs, incomplete horizon or incomplete exit are EXCLUDED with stable reasons. SL/TP are not triggered.
- AC evidence: `test_candidate_horizon_v2_uses_actual_candidate_size_and_shared_fills`; `test_candidate_horizon_v2_closes_actual_partial_entry_quantity`; `test_candidate_horizon_v2_excludes_missing_entry_or_incomplete_horizon`; `test_candidate_horizon_v2_rejects_lineage_and_excludes_partial_exit`; `test_candidate_horizon_v2_excludes_unverified_fee_schedule`; `test_candidate_horizon_config_loads_as_separate_version`.
- Focused check: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/labels/test_returns.py tests/unit/lab/cli/test_run_backtest_report.py tests/unit/lab/strategies/test_registry.py -q -p no:cacheprovider` -> 41 passed.
- Full check on combined code HEAD `3f2623b884a5066cdbaf8a27f85e517c03fa9885`: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q -p no:cacheprovider` -> 1,103 passed, 2 platform-specific skipped, 4 warnings. Planning validator -> PASS (134 nodes, 264 edges, no cycles); `rtk git diff --check` -> PASS.
- Baseline behavioral RED evidence is the prior independent review on `8ecd154f466776a59dfeda38204b40d558efdf8d`, which reproduced zero-depth inputs marked VALID despite simulator rejection. The corrected missing-liquidity regression is GREEN on this candidate.
- Independent exact-code-SHA review is pending. Status remains CHANGES_REQUESTED; LABEL-02 stays locked until reviewer PASS and manifest update.

### Registry lineage, availability and fee provenance remediation

- Code commit: `b177691d19713b901d3a4f2f1b8a5d38779efe0a` (`fix(label-01): validate sample lineage and provenance`).
- Public label builder now requires `resolve_registration(bundle_id, sample_id)` and compares the resolved immutable registry record's registration ID, bundle, strategy, sample, intent, pair and decision timestamp. An unresolved bundle/sample is rejected before simulation. The resolver is an injected trusted adapter; this sprint adds no parallel candidate registry or storage.
- V2 rows retain `registration_id`, the schedule-set ID/version, and separate applied entry/exit fee interval IDs. `label_available_at` is the maximum availability of every source bar consulted through the horizon exit.
- Regressions cover unknown bundle, sample/intent identity mismatch, delayed intermediate source, and the actual applied entry/exit intervals.
- Full verification on combined code HEAD `b177691d19713b901d3a4f2f1b8a5d38779efe0a`: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q -p no:cacheprovider` -> 1,107 passed, 2 platform-specific skipped, 4 warnings.
- Independent exact-SHA review is pending. The runtime caller must provide a resolver backed by the authoritative registry; without that adapter no v2 labels can be produced. LABEL-02 remains locked until reviewer PASS and manifest update.
