# S03-01 handoff

Status: DONE

## Ownership record

- Sprint ID: S03-01 — Abnormal volume continuation
- Implementation owner: Codex /root
- Branch/worktree: `feat/feat-02-finalization` (shared checkout; no isolated worktree)
- Base SHA: `bebf41516fa4bd448854a66db7681bbc1fdd066d`
- Implementation SHA: `43b95b50675d86f3072152cb6fb918d673f0dd2e`
- Independent reviewer: `/root/docs_review` — PASS on the exact implementation SHA.

## Candidate contract

- Registered inputs: `volume_z_20_1h`, `log_ret_24_1h`, `atr_pct_14_1h`, and causal raw close.
- Candidate defaults: volume z-score >=2.0; positive 24h log return <=0.25; pump flag must be explicit false; stop 2 ATR; target notional Rp10,000.
- Missing, unknown or true `pump_manipulation_flag` abstains. No flag producer is currently registered; verify point-in-time delivery and provenance before qualification/promotion.
- Strategy emits only a `SignalIntent`; shared risk and execution remain authoritative.

## Verification

- `pytest tests/unit/lab/strategies tests/unit/lab/features/test_registry.py tests/unit/lab/features/test_availability.py tests/integration/lab/test_feature_materialization.py -q` — 164 passed.
- Ruff for S03 source, tests and strategy exports — passed.
- Public package import smoke check (`PYTHONPATH=src`) — passed.
- Independent reviewer: 7 tests and 15 negative/sizing probes passed; no Critical/Important findings.

## External qualification gate

Verify a point-in-time `pump_manipulation_flag` producer and its provenance. Missing/unknown flags abstain; absent producer evidence blocks qualification/promotion. Portfolio backlog activation remains owner-controlled and outside the default scheduler.

Other pre-existing dirty paths remain outside this sprint and were not staged.
