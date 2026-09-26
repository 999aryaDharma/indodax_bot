# C06-01 handoff

Status: DONE

## Identity

- Sprint ID: C06-01 — Directional trend strength
- Implementation agent: Codex
- Independent reviewer: `/root/docs_review` (PASS)
- Branch: `feat/feat-02-finalization`
- Code SHA: `e410907a64d0135c86be5d449baf6413c8139e8b`
- Environment: Windows, Python 3.12.13, `C:/Users/User/miniconda3/envs/ML/python.exe`

## Files and contract

- `configs/strategies/C06_v1.yaml`: canonical normalized feature thresholds and risk defaults.
- `src/indodax_lab/strategies/c06.py`: loader and pure causal decision function.
- `src/indodax_lab/strategies/__init__.py`: public exports.
- `tests/unit/lab/strategies/test_c06.py`: AC0–AC3 tests.
- Emit a BUY when registered normalized `adx_14 >= 0.25` and `di_spread_14 > 0`; equality qualifies at ADX and zero DI abstains. Incomplete, nonfinite or out-of-range feature values abstain. Stop is `close - 2 * atr_14`; the strategy creates intents only.

## Acceptance evidence

| AC | Test | Result |
|---|---|---|
| AC0 | `test_c06_01_valid_contract` | Valid BUY with candidate identity, quantity and ATR stop |
| AC1 | `test_c06_01_contract_1_high_adx_negative_di_does_not_buy` | Strong ADX with negative signed DI abstains |
| AC2 | `test_c06_01_contract_2_incomplete_warmup_abstains` | Missing indicator value abstains |
| AC3 | `test_c06_01_contract_3_threshold_equality_is_deterministic` | ADX equality qualifies; DI equality at zero does not |

- Behavioral RED before implementation: `test_c06_01_valid_contract` failed because the initial stub returned no intent.
- `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/strategies/test_c06.py -q -p no:cacheprovider` — 4 passed.
- Strategy suite: 76 passed.
- `rtk ruff check src/indodax_lab/strategies/c06.py tests/unit/lab/strategies/test_c06.py` — passed.
- `git diff --check` — passed.

## Scope and gates

- No scheduler, downstream evaluator, direct order, venue, ledger or Production integration added.
- EXTENSION remains owner-gated and defaults are research hypotheses, not profitability or promotion evidence.
- Independent exact-SHA review PASS on `e410907a64d0135c86be5d449baf6413c8139e8b`; no Critical/Important findings. Reviewer focused tests: 4 passed plus 8 numeric/threshold negative probes.
