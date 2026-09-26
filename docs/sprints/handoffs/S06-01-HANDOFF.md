# S06-01 handoff

Status: DONE

## Ownership record

- Sprint ID: S06-01 — Post listing maturation
- Implementation owner: Codex /root
- Branch/worktree: `feat/feat-02-finalization` (shared checkout; no isolated worktree)
- Base SHA: `c7cde3c00e11c21869d8285e7002b23c0216c0d8`
- Implementation and public export target: `faeac7a939862b37f0057d0fbb82072b3fe7ef5f`
- Relevant commits: `ac000a49856060e18f90dd25772808c3a29c8423` (implementation); `7e10cd0be4e872aceae9d1d935b092c1cb31014e` (tolerance documentation correction); `faeac7a939862b37f0057d0fbb82072b3fe7ef5f` (public package exports)
- Independent reviewer: `/root/docs_review` — PASS on implementation, tolerance correction, and public exports at the respective exact SHAs.

## Acceptance evidence

- AC0: versioned S06 emits a BUY `SignalIntent` sized to configured IDR target; shared risk and execution retain authority.
- AC1: rejects initial spike via minimum-age and 24h log-return ceiling.
- AC2: uses registered point-in-time listing-age evidence; minimum age is 180 days with `1e-12` float rounding tolerance.
- AC3: unknown listing age or incomplete history abstains.
- Additional guards: non-finite or invalid inputs/configuration abstain or raise `INVALID_S06_PARAMETERS`; target notional is at least Rp10,000; stop uses 2 ATR by default.
- Focused verification: `pytest tests/unit/lab/strategies tests/unit/lab/features/test_registry.py tests/unit/lab/features/test_availability.py tests/integration/lab/test_feature_materialization.py -q` — 157 passed.
- Final S06 checks: 7 passed; Ruff passed for S06 implementation/tests; package export smoke check passed with `PYTHONPATH=src`.
- Independent review: implementation PASS with 7 tests and 17 additional probes; subsequent tolerance and export deltas PASS. No Critical/Important findings.

## External qualification gate

Verify point-in-time `listed_at` reaches the feature materializer for historical and live data. Missing listing metadata fails closed. This blocks candidate qualification/promotion, not completion of the strategy contract implementation. Portfolio backlog activation remains owner-controlled and outside the default scheduler.

Other pre-existing dirty paths remain outside this sprint and were not staged.
