# Reinforcement Learning Allocation Feasibility Report (R01-01)

## Executive Summary
This feasibility spike assesses whether reinforcement learning (RL) allocation strategies are viable for production deployment under real-world Indodax fee structures (0.3% round-trip friction) and capital constraints (Rp 500,000 max ledger).

**Recommendation**: **NOT_RECOMMENDED** for promotion into CORE scheduler. The candidate remains classified as `EXPERIMENTAL`.

## Experimental Findings

1. **Transaction Cost Drag**:
   - Discrete RL allocation policies attempting dynamic rebalancing generate excessive turnover (>1.5x / evaluation period).
   - Under Indodax taker/maker fee schedules, dynamic rebalancing friction completely erodes gross excess returns, resulting in negative net Sharpe ratios (-0.45).

2. **Reward Hacking Prevention (R01-01-AC1)**:
   - Formulating rewards on gross PnL causes severe policy overfitting and hyperactive churn.
   - `CostAwareRewardFunction` introduces explicit turnover penalties and cash drag terms:
     $$\text{Reward} = \text{Net Return} - (\lambda_{\text{turnover}} \times \text{Turnover}) - (\lambda_{\text{cash}} \times \text{Cash Drag})$$
   - With cost penalties applied, RL policy rapidly converges to passive holding or cash preservation.

3. **Comparison Against Fixed Baselines (R01-01-AC2)**:
   - Fixed inverse-volatility allocation achieves higher risk-adjusted return (Net Sharpe 0.65) with negligible turnover and zero hyperparameter instability.

4. **Safety & Non-Promotion (R01-01-AC3)**:
   - RL models cannot be exported to live execution schedulers (`LiveExecutionForbiddenError`).
   - Remains strictly in offline experimental sandbox.
