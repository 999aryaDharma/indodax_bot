# FEAT-02 handoff

## Revalidation addendum — 2026-09-23

Current implementation target: code SHA `52dddc17e3d040e423692aa6a6b2551e0c8634bf` on branch `feat/feat-02-finalization`. This supersedes the earlier code SHA below for review and acceptance evidence; the historical evidence is retained as provenance.

- The imported WIP is now committed in the current repository history. Both canonical feature registries are version `1.1.0` and pin EMA initialization, Wilder SMA seeding, StochRSI zero-range behavior, and rolling `ddof`; the report's feature-set version matches.
- `technical.py` propagates those policies through registry-callable transforms. Golden values remain hand-literal; tests cover warmup, flat/zero-volume finiteness and future-bar causality.
- Environment: `C:\Users\User\miniconda3\envs\ML\python.exe` on Windows.
- `python -m pytest tests/unit/lab/features -q -p no:cacheprovider` → 38 passed, exit 0.
- `python -m pytest tests/integration/lab/test_feature_materialization.py -q -p no:cacheprovider` → 14 passed, exit 0.
- `python -m ruff check --ignore E501 src/indodax_lab/features/technical.py tests/unit/lab/features/test_technical.py tests/unit/lab/features/test_registry.py` → passed, exit 0. The exception is explicit because touched legacy files contain pre-existing long lines; the narrow check found no other lint issues.
- Reviewer identified an Important mismatch on prior code SHA `5dc3bbf`: the raw-bar pass-through report claimed a registry identity/version it did not use. Fixed in `52dddc1` by emitting null feature-set provenance for that path; the canonical feature builder continues to emit the actual registry ID/version.
- Regression: `python -m pytest tests/unit/lab/cli/test_run_backtest_report.py -q -p no:cacheprovider` → 1 passed, exit 0. It failed against `5dc3bbf` because the report claimed `tabular_bar_5m_v1@1.1.0`.
- Final focused run on `52dddc1`: feature unit tests 38 passed, report-provenance test 1 passed, feature-materialization integration 14 passed; all exit 0.
- `python -m ruff check tests/unit/lab/cli/test_run_backtest_report.py` and the narrow feature lint command above → passed, exit 0.
- `git diff --check` on the six implementation files → passed, exit 0.
- Independent review of exact code SHA `52dddc17e3d040e423692aa6a6b2551e0c8634bf` is pending. Do not transition FEAT-02 to DONE before reviewer PASS and coordinator manifest/projection update.

Current implementation paths: `configs/features/tabular_bar_v1.yaml`, `configs/features/tabular_bar_5m_v1.yaml`, `src/indodax_lab/features/technical.py`, `src/indodax_lab/cli/run_backtest.py`, `tests/unit/lab/features/test_registry.py`, `tests/unit/lab/features/test_technical.py`, and `tests/unit/lab/cli/test_run_backtest_report.py`.

Status: REVIEW

## Identity
- Sprint ID: FEAT-02 — Golden technical and liquidity transforms
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/feat-02-golden-technical-and-liquidity-transforms`
- Base SHA: `47b55e8`
- Code target: `feat(feat-02): golden technical and liquidity transforms`
- Evidence SHA relation: `a978533`

## Files and contracts
- Planned files:
  - `src/indodax_lab/features/technical.py` (verified: normalized price/volume technical transforms)
  - `src/indodax_lab/features/liquidity.py` (verified: normalized liquidity/turnover transforms)
  - `tests/fixtures/features/golden_ohlcv.csv` (golden OHLCV fixture)
  - `tests/unit/lab/features/test_technical.py` (explicit AC0..AC3 test cases)
- Contract:
  - `closed OHLCV -> normalized EMA RSI StochRSI MACD ATR ADX BB Donchian VWAP returns and liquidity features`.
  - Continuous float64 features, auditable warmup, scale invariant.
  - Flat price or zero-volume does not produce infinity.
  - Modifying future bars does not alter past features (strict causal preservation).
- Migration and compatibility:
  - Pure calculation modules; backward compatible.
  - Dependencies: FEAT-01 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| FEAT-02-AC0 | `test_feat_02_valid_contract` | `python -m pytest tests/unit/lab/features/test_technical.py::test_feat_02_valid_contract` | Exit 0 (Passed, validates continuous outputs & auditable warmup) | `a978533` |
| FEAT-02-AC1 | `test_feat_02_contract_1` | `python -m pytest tests/unit/lab/features/test_technical.py::test_feat_02_contract_1` | Exit 0 (Passed, golden expected within explicit tolerances) | `a978533` |
| FEAT-02-AC2 | `test_feat_02_contract_2` | `python -m pytest tests/unit/lab/features/test_technical.py::test_feat_02_contract_2` | Exit 0 (Passed, flat price / zero volume produce no infs) | `a978533` |
| FEAT-02-AC3 | `test_feat_02_contract_3` | `python -m pytest tests/unit/lab/features/test_technical.py::test_feat_02_contract_3` | Exit 0 (Passed, future perturbation does not alter history) | `a978533` |

All 6 tests in `tests/unit/lab/features/test_technical.py` passed (0.89s).
Combined suite verification (19 tests) passed (1.40s).

## Review
- Spec verdict: PASS (meets all functional requirements of FEAT-02 and specs/07-feature-engineering.md).
- Quality verdict: PASS (zero network, pure functions, causality preserved, zero infs on degenerate inputs).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for FEAT-02.
- Next unlocked capabilities: FEAT-04 (Immutable feature materialization).
