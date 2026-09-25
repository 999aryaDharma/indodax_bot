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

AC1 and AC2 pass. Independent focused label tests: 21 passed, but passing tests do not cover these findings. Owner decision (2026-09-25): use candidate-specific sizing per sample. Next: change-control design for the sample intent/quantity and immutable candidate lineage, then align actual labels with the shared fill model. No code/schema changes authorized by this decision alone; do not claim DONE or promotion qualification meanwhile.

## Deviations and known risks
- Deviation: implementation is currently an open-price research proxy, not the shared execution simulator required by AC0/AC3.
- Unresolved issues: two Important findings remain open (fill-model alignment/fill-unavailable exclusion; unsupported canonical execution model).
- LABEL-02 remains unavailable until LABEL-01 returns to DONE.
