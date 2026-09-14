# R01-01 handoff

Status: REVIEW

## Identity
- Sprint ID: R01-01 — Constrained allocation feasibility
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/r01-01-constrained-allocation-feasibility`
- Base SHA: `12811e0`
- Code target: `feat(r01-01): constrained allocation feasibility spike`
- Evidence SHA relation: `1c24f9b`

## Files and contracts
- Actual files:
  - `src/indodax_lab/models/r01_rl_allocator.py` (CostAwareRewardFunction, AllocationBaselineComparator, RLAllocationEnvironment, RLFeasibilityReport, LiveExecutionForbiddenError, evaluate_rl_allocation_feasibility)
  - `tests/research/test_rl_reward_contract.py` (AC0..AC3 test cases)
  - `docs/research/rl-feasibility.md` (Feasibility report, findings, turnover and cost drag analysis)
- Contract:
  - `Offline simulator + fixed allocation baselines -> feasibility report, no scheduler default and no promotion.`
  - Feasibility assessment: Evaluates RL allocation under net transaction costs and Rp 500,000 ledger limits; concludes NOT_RECOMMENDED (R01-01-AC0).
  - Reward hacking defense: CostAwareRewardFunction heavily penalizes turnover and cash drag, turning churning into negative net reward (R01-01-AC1).
  - Comparative baseline: Benchmarks against fixed inverse-volatility allocation on identical budget (R01-01-AC2).
  - Safety & non-promotion: Live execution export is forbidden (`LiveExecutionForbiddenError`), retaining experimental classification (R01-01-AC3).
- Migration and compatibility:
  - Additive research module `src/indodax_lab/models/r01_rl_allocator.py` and documentation `docs/research/rl-feasibility.md`.
  - Dependencies: QA-01 (REVIEW), SHADOW-02 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| R01-01-AC0 (RED) | `test_r01_01_valid_contract` | `python -m pytest tests/research/test_rl_reward_contract.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.r01_rl_allocator') | `working tree` |
| R01-01-AC0 (GREEN) | `test_r01_01_valid_contract` | `python -m pytest tests/research/test_rl_reward_contract.py::test_r01_01_valid_contract` | Exit 0 (Passed, feasibility study completes with net cost accounting and capital constraints) | `1c24f9b` |
| R01-01-AC1 (RED) | `test_r01_01_contract_1` | `python -m pytest tests/research/test_rl_reward_contract.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| R01-01-AC1 (GREEN) | `test_r01_01_contract_1` | `python -m pytest tests/research/test_rl_reward_contract.py::test_r01_01_contract_1` | Exit 0 (Passed, high-turnover reward hacking penalized to negative net reward) | `1c24f9b` |
| R01-01-AC2 (RED) | `test_r01_01_contract_2` | `python -m pytest tests/research/test_rl_reward_contract.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| R01-01-AC2 (GREEN) | `test_r01_01_contract_2` | `python -m pytest tests/research/test_rl_reward_contract.py::test_r01_01_contract_2` | Exit 0 (Passed, budget-constrained inverse volatility baseline correctly computed) | `1c24f9b` |
| R01-01-AC3 (RED) | `test_r01_01_contract_3` | `python -m pytest tests/research/test_rl_reward_contract.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| R01-01-AC3 (GREEN) | `test_r01_01_contract_3` | `python -m pytest tests/research/test_rl_reward_contract.py::test_r01_01_contract_3` | Exit 0 (Passed, live scheduler export strictly forbidden) | `1c24f9b` |

All 4 tests in `tests/research/test_rl_reward_contract.py` passed (1.95s).
Full lab suite verification: 231 passed across all domains.

## Review
- Spec verdict: PASS (meets all requirements of R01-01 and docs/specs/12-tabular-models-and-training.md).
- Quality verdict: PASS (net-cost evaluation, reward hacking tests, baseline comparison, live export forbidden).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for R01-01.
- Next unlocked consumers: Release or owner research review.
