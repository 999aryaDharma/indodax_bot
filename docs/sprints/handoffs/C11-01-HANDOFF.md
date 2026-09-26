# C11-01 handoff

Status: DELTA_REVIEW

## Identity

- Sprint ID: C11-01 — Volatility allocation
- Implementation agent: Codex
- Independent reviewer: `/root/docs_review` (first and second reviews CHANGES_REQUESTED; final delta review pending)
- Branch: `feat/feat-02-finalization`
- Initial review SHA: `56c6e055cafbf01cc20d2c4c09f72dcdecacce8c`
- Delta review SHA: `46c2abcf7b9a104a8f399877a6727be3722e5c47`
- Final delta review SHA: `b75dfe6b7ddba903c5ae0ac5e2ac7a93560cb176`
- Environment: Windows, Python 3.12.13, `C:/Users/User/miniconda3/envs/ML/python.exe`

## Files and contract

- `configs/strategies/C11_v1.yaml`, `src/indodax_lab/strategies/c11.py`: inverse-volatility intents; at least two valid pairs; no more than 50% cash total and 25% cash per pair; Rp10.000 minimum intent notional.
- `src/indodax_lab/strategies/base.py`: optional finite, nonnegative Decimal `DecisionFrame.available_cash_idr`.
- `src/indodax_lab/backtest/feature_replay.py`: optional simulator-supplied cash is forwarded; adapter does not source it.
- `tests/unit/lab/strategies/test_c11.py` and `tests/unit/lab/backtest/test_feature_replay.py`: allocation, abstention, cash contract and forwarding regressions.
- `docs/decisions/CR-C11-simulator-cash-context.md` and `ADR-013-simulator-cash-context.md`: owner-approved change control; no Production/live account source or strategy order authority.

## Acceptance evidence

| AC | Evidence | Result |
|---|---|---|
| AC0 | `test_c11_candidate_sized_inverse_volatility_respects_cash_and_pair_caps` | Valid intents, inverse-vol ordering, per-pair and total cash bounds |
| AC1 | `test_c11_excludes_zero_and_nonfinite_volatility_and_requires_two_pairs` | Zero/NaN RV excluded; fewer than two valid pairs abstains |
| AC2 | `test_c11_candidate_sized_inverse_volatility_respects_cash_and_pair_caps`, `test_c11_respects_indodax_minimum_notional` | Total <=50%, pair <=25%, below Rp10.000 excluded |
| AC3 | `test_c11_missing_cash_abstains` | Missing cash abstains explicitly |
| Delta guards | `test_c11_excludes_missing_volatility_without_crashing`, `test_c11_rechecks_minimum_after_decimal_quantity_rounding`, `test_c11_rejects_parameters_above_frozen_allocation_caps` | Missing numeric values abstain, rounded notional remains >= Rp10.000, unsafe/nonfinite configuration rejected |

- Initial focused: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/strategies/test_c11.py tests/unit/lab/backtest/test_feature_replay.py tests/unit/lab/strategies/test_registry.py -q` — 37 passed.
- Delta focused, same command — 40 passed.
- Targeted lint: `C:/Users/User/miniconda3/envs/ML/python.exe -m ruff check src/indodax_lab/strategies/c11.py src/indodax_lab/strategies/base.py tests/unit/lab/strategies/test_c11.py` — passed.
- Planning: `C:/Users/User/miniconda3/envs/ML/python.exe docs/quality/validate_planning.py` — PASS, 134 nodes, 264 edges, 0 cycles.
- Full suite: 1,154 passed, 2 skipped, 1 failed. Failure: pre-existing dirty `tests/unit/lab/strategies/test_c04.py::test_c04_volume_nan_fail_open` against concurrently dirty C04 implementation; those paths were not changed or staged by this sprint.
- `git diff --check` on owned paths passed. Whole-worktree diff-check is obstructed by trailing whitespace in unrelated dirty C01/C02/C04/C07/S01 files.

## Scope and gates

- No live account, Production ledger, venue, order, fill, or runtime state access.
- Simulator caller remains responsible for supplying fresh unreserved cash; no simulator orchestration caller currently supplies it automatically.
- Candidate is research-only and not activated or qualified for trading.
- First independent review found 3 Important findings; all were reproduced RED, fixed, and covered by regressions. Delta review requested for `46c2abcf7b9a104a8f399877a6727be3722e5c47`; keep sprint in REVIEW until PASS.
- Second review found the strategy minimum could be lowered below the venue's Rp10.000 floor. Regression reproduced RED; configuration now rejects any minimum below Rp10.000. Final delta review requested for `b75dfe6b7ddba903c5ae0ac5e2ac7a93560cb176`.
