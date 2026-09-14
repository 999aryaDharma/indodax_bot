# LABEL-01 handoff

Status: REVIEW

## Identity
- Sprint ID: LABEL-01 — Execution-aligned net return labels
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
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
| LABEL-01-AC0 (RED) | `test_label_01_valid_contract` | `python -m pytest tests/unit/lab/labels/test_returns.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| LABEL-01-AC0 (GREEN) | `test_label_01_valid_contract` | `python -m pytest tests/unit/lab/labels/test_returns.py::test_label_01_valid_contract` | Exit 0 (Passed, measures net proceeds relative to gross debit from execution model) | `f323cd0` |
| LABEL-01-AC1 (RED) | `test_label_01_contract_1` | `python -m pytest tests/unit/lab/labels/test_returns.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| LABEL-01-AC1 (GREEN) | `test_label_01_contract_1` | `python -m pytest tests/unit/lab/labels/test_returns.py::test_label_01_contract_1` | Exit 0 (Passed, entry before decision is strictly rejected) | `f323cd0` |
| LABEL-01-AC2 (RED) | `test_label_01_contract_2` | `python -m pytest tests/unit/lab/labels/test_returns.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| LABEL-01-AC2 (GREEN) | `test_label_01_contract_2` | `python -m pytest tests/unit/lab/labels/test_returns.py::test_label_01_contract_2` | Exit 0 (Passed, incomplete horizon produces excluded sample, never zero) | `f323cd0` |
| LABEL-01-AC3 (RED) | `test_label_01_contract_3` | `python -m pytest tests/unit/lab/labels/test_returns.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| LABEL-01-AC3 (GREEN) | `test_label_01_contract_3` | `python -m pytest tests/unit/lab/labels/test_returns.py::test_label_01_contract_3` | Exit 0 (Passed, unavailable cost schedule excludes sample) | `f323cd0` |

All 4 tests in `tests/unit/lab/labels/test_returns.py` passed (0.93s).
Combined suite verification (59 passed across backtest, risk, execution, ledger, costs, features, and labels) passed (2.04s).

## Review
- Spec verdict: PASS (meets all functional requirements of LABEL-01 and specs/09-labels-splits-and-training-data.md).
- Quality verdict: PASS (Decimal precision, strict causality, non-zero incomplete horizon, UTC-aware).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for LABEL-01.
- Next unlocked capabilities: LABEL-02 (Triple barrier outcomes).
