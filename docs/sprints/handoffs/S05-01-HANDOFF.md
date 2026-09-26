# S05-01 handoff

Status: IN_PROGRESS

## Ownership record

- Sprint ID: S05-01 — Micro pullback
- Implementation owner: Codex /root
- Branch/worktree: `feat/feat-02-finalization` (shared checkout; no isolated worktree)
- Base SHA: `7c8f0ef01f8962aab30af0f18d60c235ed2f54b2`
- Requested paths: S05 config/source/test, public strategy exports, S05 spec/manifest/projections, this handoff
- Independent reviewer: `/root/docs_review`

## Candidate contract

- Registered causal inputs: `log_ret_12_1h`, `log_ret_1_1h`, and `atr_pct_14_1h`; raw close and `spread_bps` are required.
- Candidate defaults: 12h impulse >=0.05; 1h pullback from -0.015 through -0.001; spread <=25 bps; maker limit at close; 2 ATR stop; Rp10,000 target notional.
- Missing/unknown spread abstains. Spread producer provenance is an external qualification gate.
- Partial quantity remains owned by the existing `ConservativeExecutionSimulator`; S05 produces an intent only and cannot promote a partial fill to full size.

## Verification

- `pytest tests/unit/lab/strategies tests/unit/lab/features/test_registry.py tests/unit/lab/features/test_availability.py tests/integration/lab/test_feature_materialization.py tests/unit/lab/backtest/test_execution.py -q` — 175 passed.
- Ruff for S05 source, tests and strategy exports — passed.
- Public package import smoke check (`PYTHONPATH=src`) — passed.
- Independent review and exact final source SHA: pending.

Other pre-existing dirty paths remain outside this sprint and were not staged.
