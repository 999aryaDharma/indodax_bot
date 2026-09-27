# C07-01 handoff

Status: REVIEW

## Identity
- Sprint ID: C07-01 — Bollinger RSI reversion
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/c07-01-bollinger-rsi-reversion`
- Base SHA: `92b4a5c`
- Code target: `feat(c07-01): bollinger rsi reversion`
- Evidence SHA relation: `6b0be47f0c512fb345b3e8aa9297c787a83b7593`

## Files and contracts
- Planned files:
  - `src/indodax_lab/strategies/c07.py` (load_c07_specification, c07_decide)
  - `src/indodax_lab/strategies/__init__.py` (Package exports)
  - `configs/strategies/C07_v1.yaml` (Canonical C07 configuration)
  - `tests/unit/lab/strategies/test_c07.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `Extreme BB and RSI deviation only under available sideways regime -> versioned LONG/FLAT intent, never direct orders.`
  - Stateless decision function over causal `DecisionFrame`; long-only spot intents (`BUY` / `SELL`, positive desired qty).
  - Strong downtrend (`regime in ("downtrend", "strong_downtrend")` or negative DI spread with high ADX) strictly rejects entry to avoid falling-knife risk.
  - Sideways regime combined with extreme oversold (`bb_z <= -bb_std` and `rsi <= rsi_oversold`) produces bounded LONG `SignalIntent` with ATR stop-loss and take-profit.
  - Zero or degenerate band width produces abstain (FLAT / empty intents).
  - Strategies only produce declarative order intents (`SignalIntent`); zero authority over fills, executions, or ledger balances.
- Migration and compatibility:
  - Additive classical strategies catalog; backward compatible.
  - Dependencies: STRAT-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| C07-01-AC0 (RED) | `test_c07_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_c07.py` | Exit 1 (Failed: assert 0 == 1) | `working tree` |
| C07-01-AC0 (GREEN) | `test_c07_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_c07.py::test_c07_01_valid_contract` | Exit 0 (Passed, produces valid BUY SignalIntent with ATR stop and take-profit) | `6b0be47` |
| C07-01-AC1 (RED) | `test_c07_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_c07.py` | Exit 0 (Initial pass / returns empty) | `working tree` |
| C07-01-AC1 (GREEN) | `test_c07_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_c07.py::test_c07_01_contract_1` | Exit 0 (Passed, strong downtrend strictly rejects entry) | `6b0be47` |
| C07-01-AC2 (RED) | `test_c07_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_c07.py` | Exit 1 (Failed: assert 0 == 1) | `working tree` |
| C07-01-AC2 (GREEN) | `test_c07_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_c07.py::test_c07_01_contract_2` | Exit 0 (Passed, sideways oversold produces bounded entry intent) | `6b0be47` |
| C07-01-AC3 (RED) | `test_c07_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_c07.py` | Exit 0 (Initial pass / returns empty) | `working tree` |
| C07-01-AC3 (GREEN) | `test_c07_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_c07.py::test_c07_01_contract_3` | Exit 0 (Passed, zero band width produces abstain / FLAT) | `6b0be47` |

All 4 tests in `tests/unit/lab/strategies/test_c07.py` passed (1.10s).
Combined suite verification (80 passed across backtest, risk, execution, ledger, costs, features, labels, strategies, and evaluation) passed (2.38s).

## Review
- Spec verdict: PASS (meets all functional requirements of C07-01 and specs/10-strategy-catalog-and-protocol.md).
- Quality verdict: PASS (pure stateless decision protocol, zero ledger mutation, strict causality, sideways regime gating and degenerate band protection).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for C07-01.
- Next unlocked consumers: C10-01, QA-01.

## Independent review — coordinator DONE pass (2026-09-27)

- Verdict: DELTA-PASS. Both prior IMPORTANT findings verified closed in src/indodax_lab/strategies/c07.py + configs/strategies/C07_v1.yaml (config-driven sideways/downtrend allowlists with unknown-regime abstain; configurable di_spread_threshold default -0.15).
- Fresh run `python -m pytest tests/unit/lab/strategies/test_c07.py tests/unit/lab/strategies/test_c10.py tests/unit/lab/strategies/test_registry.py -q`: 28 passed, 0 failed, including 2 new regression tests with demonstrated RED (old code) → GREEN (fixed) cycle.
- First review: ses_f2028e7caffenivpXTpnZ0M1pj. Delta re-review: ses_f1f5b2f07ffe201yXCXjng4hAH. Fix implemented in working tree (uncommitted).
- Reviewed at HEAD 28d89ba with uncommitted working-tree changes present; exact-SHA pinning pending at commit time.

## Cross-sprint registry compatibility correction

- Owner: Codex `/root`; base checkout `e84d88609583be5b8936f1ab0aa8560f932edcac`; reviewer: `/root/docs_review`.
- Scope: make the durable strategy registry accept and preserve the three C07 fields already required by the canonical C07 config and decision function: `di_spread_threshold`, `sideways_regimes`, `downtrend_regimes`.
- Requested paths: `src/indodax_lab/strategies/store.py`, `tests/unit/lab/strategies/test_versioned_registry.py`, this handoff. `src/indodax_lab/strategies/__init__.py` remains owned by the concurrent thread and is excluded.
- Regression evidence before fix: `tests/unit/lab/strategies/test_versioned_registry.py` fails five C07 cases with `extra_forbidden` for those exact YAML fields.
- Delta re-review required; C07-01 status remains REVIEW until coordinator reconciles the exact committed evidence.
- Fix commit: `7269a320c6d9c15644befe3626a575cb29d9c599`.
- Focused GREEN: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/strategies/test_versioned_registry.py -q -p no:cacheprovider` — 14 passed; `test_seed_manifest_preserves_yaml_strategy_and_risk_defaults[C07]` now preserves all canonical parameters.
- Strategy integration gate: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/strategies/test_c07.py tests/unit/lab/strategies/test_c10.py tests/unit/lab/strategies/test_registry.py tests/unit/lab/strategies/test_versioned_registry.py -q -p no:cacheprovider` — 42 passed.
- Full suite at the fix commit: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q -p no:cacheprovider` — 1,695 passed, 2 skipped, 11 warnings. Skips are the existing Linux `/proc` resource smoke and Windows symlink privilege case.
- Lint: `C:/Users/User/miniconda3/envs/ML/Scripts/ruff.exe check --select I,F401 src/indodax_lab/strategies/store.py tests/unit/lab/strategies/test_versioned_registry.py` — passed; scoped diff check passed.
- Independent delta review: pending at exact source SHA `7269a320c6d9c15644befe3626a575cb29d9c599`.
