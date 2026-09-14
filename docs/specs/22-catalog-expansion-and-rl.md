# Technical specification — expanded catalog and RL allocation

Status: integrated PLANNED scope, 2026-09-14. Implementation and research execution are not complete. User authorized docs integration; runtime activation remains separate.

## Canonical catalog
| Sprint | Design alias | Component | Technical detail |
|---|---|---|---|
| C13-01 | EXP-H01 | Cross-sectional reversal | 24h losers, BTC regime, 5 slots, bounded holding |
| C14-01 | EXP-H02 | Size-conditioned momentum/reversal | PIT cohorts, 7d winners vs 1d losers |
| S10-01 | EXP-H03 | Microprice benchmark | RELIABLE L2, cost gate, depth/latency-aware taker |
| C15-01 | EXP-O01 | Equal-risk allocation | Shrunk covariance, solver residual, cap then cash |
| M07-01 | EXP-O02 | Conformal abstention | Chronological residual calibration, finite-sample rank |
| R01-01 | Existing canonical ID | RL allocation feasibility | Bounded actions/reward/episodes in spec 23 |

Normative exact formulas, default configs, golden cases and rejection behavior: [candidate cards](../research/catalog-expansion/03-candidate-specifications.md). Each new sprint embeds its full card and maps AC to tests; manifest controls readiness. Required common data/evaluation schema: [experiment contract](../research/catalog-expansion/02-experiment-contract.md).

## Interface ownership
StrategySpecification + eligible DecisionFrame -> intent/target allocation. Judge owns fills, account and risk. ABSTAIN must preserve intent state without forcing exit; TARGET_ZERO requests liquidation under execution rules. Resolve any FLAT ambiguity in canonical STRAT-01 before consumers. No secondary simulator, feature registry or capital ledger.

## Budgets and ancestry
H01: C04/C07; H02: C04/C13/C12/S07; H03: S04; O01: C11; O02: M04/M05. Alias maps to canonical ID, never new budget. Pilot one config first, <=6 per unit within stricter remaining ADR-003 family limits. RL budget in spec 23 is a proposed bounded spike cap, requires owner activation before compute.

## Data gates and scope
H02 requires archived PIT cap, H03 verified continuous L2. Offline synthetic math fixtures prove implementation only. SHORT cointegration and multi-order market-making require separate design, not hidden adaptations. No claim every earlier C13–C36 chat suggestion is novel: dedup mapping retained for audit.

## Rollout
Existing Wave 1 and QA remain priority. Added PLANNED dependencies do not change initial READY queue. Module paths are planned ownership boundaries; map to existing equivalents before coding. Paper eligibility still follows master and EVAL gates. Source research is not proof of transfer to Indodax.
