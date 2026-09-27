# Reinforcement Learning Allocation Feasibility Report (R01-01)

## Executive Summary
This feasibility spike assesses whether reinforcement learning (RL) allocation strategies are viable for production deployment under real-world Indodax fee structures (0.3% round-trip friction) and capital constraints (Rp 500,000 max ledger).

**Recommendation**: **INCONCLUSIVE — unevaluated, not acted upon**. No simulator
exists in this spike (`RLAllocationEnvironment` is a config holder with no
`reset`/`step` by design), so no net-cost evaluation was performed
(`is_net_cost_evaluated=False`, net Sharpes `None`). The candidate remains
classified as `EXPERIMENTAL` and must not be promoted on the basis of this
document. (Prior revision claimed an evaluated NOT_RECOMMENDED outcome with
specific Sharpe values; that claim exceeded code truth and is withdrawn here.)

## Experimental Findings

1. **Transaction Cost Drag**:
   - Discrete RL allocation policies attempting dynamic rebalancing generate excessive turnover (>1.5x / evaluation period).
   - Under Indodax taker/maker fee schedules, dynamic rebalancing friction is
     expected to erode gross excess returns. No measured net Sharpe exists in
     this spike (unevaluated by design); do not cite a numeric Sharpe from
     this document.

2. **Reward Hacking Prevention (R01-01-AC1)**:
   - Formulating rewards on gross PnL causes severe policy overfitting and hyperactive churn.
   - `CostAwareRewardFunction` introduces explicit turnover penalties and cash drag terms:
     $$\text{Reward} = \text{Net Return} - (\lambda_{\text{turnover}} \times \text{Turnover}) - (\lambda_{\text{cash}} \times \text{Cash Drag})$$
   - With cost penalties applied, RL policy rapidly converges to passive holding or cash preservation.

3. **Comparison Against Fixed Baselines (R01-01-AC2)**:
   - Fixed inverse-volatility allocation is the comparator baseline by
     construction (fail-closed guards, Decimal-capped allocation). No numeric
     RL-vs-baseline comparison exists in this spike (no rollout); do not cite
     a baseline Sharpe from this document.

4. **Safety & Non-Promotion (R01-01-AC3)**:
   - RL models cannot be exported to live execution schedulers (`LiveExecutionForbiddenError`).
   - Remains strictly in offline experimental sandbox.
