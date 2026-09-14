# SHADOW-03 handoff

Status: REVIEW

## Identity
- Sprint ID: SHADOW-03 — Champion replacement gate
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/shadow-03-champion-replacement-gate`
- Base SHA: `7447937`
- Code target: `feat(shadow-03): champion replacement gate`
- Evidence SHA relation: `586c582`

## Files and contracts
- Actual files:
  - `src/indodax_lab/paper/promotion.py` (ChallengerEvidence, PromotionDecision, ChampionRegistry, InsufficientForwardDurationError, InsufficientForwardTradesError, UnsealedCandidatePromotionError, PolicyBreachPromotionError)
  - `src/indodax_lab/paper/__init__.py` (Package exports — SHADOW-03 symbols added)
  - `tests/unit/lab/paper/test_promotion.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `sealed pass + >=90 days AND >=100 pooled closed forward trades + no policy breach -> versioned promotion.`
  - Champion replacement: `ChampionRegistry.evaluate_promotion()` swaps active champion pointer atomically when candidate possesses sealed pass, >=90 forward evaluation days, and >=100 closed trades without breach (SHADOW-03-AC0).
  - Forward duration requirement: Candidates with >=100 trades but <90 forward days fail duration gate, raising `InsufficientForwardDurationError` (SHADOW-03-AC1).
  - Trade sample size requirement: Candidates with >=90 forward days but <100 closed trades fail sample size gate, raising `InsufficientForwardTradesError` (SHADOW-03-AC2).
  - Champion pointer isolation: Training, logging, or evaluating challengers leaves active champion pointer strictly unaltered (SHADOW-03-AC3).
- Migration and compatibility:
  - Additive module in `src/indodax_lab/paper/`; no existing interfaces modified.
  - Dependencies: SHADOW-02 (REVIEW), EVAL-03 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| SHADOW-03-AC0 (RED) | `test_shadow_03_valid_contract` | `python -m pytest tests/unit/lab/paper/test_promotion.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.paper.promotion') | `working tree` |
| SHADOW-03-AC0 (GREEN) | `test_shadow_03_valid_contract` | `python -m pytest tests/unit/lab/paper/test_promotion.py::test_shadow_03_valid_contract` | Exit 0 (Passed, challenger with >=90 days and >=100 trades replaces champion) | `586c582` |
| SHADOW-03-AC1 (RED) | `test_shadow_03_contract_1` | `python -m pytest tests/unit/lab/paper/test_promotion.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SHADOW-03-AC1 (GREEN) | `test_shadow_03_contract_1` | `python -m pytest tests/unit/lab/paper/test_promotion.py::test_shadow_03_contract_1` | Exit 0 (Passed, 100 trades in 10 days raises InsufficientForwardDurationError) | `586c582` |
| SHADOW-03-AC2 (RED) | `test_shadow_03_contract_2` | `python -m pytest tests/unit/lab/paper/test_promotion.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SHADOW-03-AC2 (GREEN) | `test_shadow_03_contract_2` | `python -m pytest tests/unit/lab/paper/test_promotion.py::test_shadow_03_contract_2` | Exit 0 (Passed, 90 days with 40 trades raises InsufficientForwardTradesError) | `586c582` |
| SHADOW-03-AC3 (RED) | `test_shadow_03_contract_3` | `python -m pytest tests/unit/lab/paper/test_promotion.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SHADOW-03-AC3 (GREEN) | `test_shadow_03_contract_3` | `python -m pytest tests/unit/lab/paper/test_promotion.py::test_shadow_03_contract_3` | Exit 0 (Passed, challenger activity leaves active champion pointer unchanged) | `586c582` |

All 4 tests in `tests/unit/lab/paper/test_promotion.py` passed (0.45s).
Full lab suite verification: 199 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, reporting, and paper.

## Review
- Spec verdict: PASS (meets all functional requirements of SHADOW-03 and docs/specs/14-shadow-portfolios-and-promotion.md).
- Quality verdict: PASS (strict dual-threshold gate: 90 days AND 100 trades, atomic pointer update, unsealed candidate rejection, no real-money execution).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for SHADOW-03.
- Next unlocked consumers: No mandatory downstream.
