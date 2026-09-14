# D04-01 handoff

Status: REVIEW

## Identity
- Sprint ID: D04-01 — Compact iTransformer challenger
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/d04-01-compact-itransformer-challenger`
- Base SHA: `0c24844`
- Code target: `feat(d04-01): compact itransformer challenger`
- Evidence SHA relation: `2c3dd55`

## Files and contracts
- Planned files:
  - `src/indodax_lab/models/dl/d04_itransformer.py` (CompactITransformerConfig, CompactITransformer, PointInTimeUniverseGate, PointInTimePanelSnapshot, ITransformerComputeBudgetSummary, InvertedDimensionError, FutureUniverseError)
  - `tests/unit/lab/models/test_d04_01.py` (AC0..AC3 test cases)
- Contract:
  - `Variates as tokens with available input window -> panel forecast`
  - Integrated execution mapping: Produces panel multi-horizon forecasts and directional probabilities connected to common `CostAwareExecutionMapper` (D04-01-AC0).
  - Shape time-feature validation: Explicitly validates that inputs have shape $(B, L, V)$ where temporal dimension $L$ is embedded to hidden dimension $d_{\text{model}}$ and variates $V$ form sequence tokens for cross-variate attention. Swapped $(B, V, L)$ shapes are rejected fail-closed with `InvertedDimensionError` (D04-01-AC1).
  - Missing variate isolation: Accepts `variate_mask` of shape $(B, V)$ and uses key padding masking in cross-variate multihead attention to ensure arbitrary perturbations in missing variates have strictly zero effect on observed variate outputs (D04-01-AC2).
  - Strict point-in-time universe: Point-in-time universe gating rejects assets listed after evaluation timestamp ($t > t_0$) with `FutureUniverseError` and forbids lookahead observation timestamps (D04-01-AC3).
- Migration and compatibility:
  - Additive module `src/indodax_lab/models/dl/d04_itransformer.py` with zero breaking changes.
  - Exported in `src/indodax_lab/models/dl/__init__.py`.
  - Dependencies: D02-01 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| D04-01-AC0 (RED) | `test_d04_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_d04_01.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.dl.d04_itransformer') | `working tree` |
| D04-01-AC0 (GREEN) | `test_d04_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_d04_01.py::test_d04_01_valid_contract` | Exit 0 (Passed, panel multi-horizon forecast produced, mapped through CostAwareExecutionMapper, compute budget validated) | `2c3dd55` |
| D04-01-AC1 (RED) | `test_d04_01_contract_1` | `python -m pytest tests/unit/lab/models/test_d04_01.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| D04-01-AC1 (GREEN) | `test_d04_01_contract_1` | `python -m pytest tests/unit/lab/models/test_d04_01.py::test_d04_01_contract_1` | Exit 0 (Passed, swapped dimension rejected with InvertedDimensionError, variate tokenization verified) | `2c3dd55` |
| D04-01-AC2 (RED) | `test_d04_01_contract_2` | `python -m pytest tests/unit/lab/models/test_d04_01.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| D04-01-AC2 (GREEN) | `test_d04_01_contract_2` | `python -m pytest tests/unit/lab/models/test_d04_01.py::test_d04_01_contract_2` | Exit 0 (Passed, active variates strictly invariant to extreme perturbations in missing variates) | `2c3dd55` |
| D04-01-AC3 (RED) | `test_d04_01_contract_3` | `python -m pytest tests/unit/lab/models/test_d04_01.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| D04-01-AC3 (GREEN) | `test_d04_01_contract_3` | `python -m pytest tests/unit/lab/models/test_d04_01.py::test_d04_01_contract_3` | Exit 0 (Passed, future-listed assets rejected fail-closed with FutureUniverseError, lookahead prevented) | `2c3dd55` |

All 4 tests in `tests/unit/lab/models/test_d04_01.py` passed (4.26s).
Full lab suite verification: 263 passed across all domains (12.65s).

## Review
- Spec verdict: PASS (meets all requirements of D04-01 and docs/specs/15-deep-learning-and-provenance.md).
- Quality verdict: PASS (inverted tokenization, cross-variate attention with key padding masking, point-in-time universe gating, compute budget tracking).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for D04-01.
- Next unlocked consumers: Research tournament comparisons.
