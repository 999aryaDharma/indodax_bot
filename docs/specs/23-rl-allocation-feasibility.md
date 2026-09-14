# R01 technical contract — reinforcement learning allocation spike

Status: PLANNED / EXPERIMENTAL; canonical sprint R01-01. No automatic scheduler, live learning, order API or policy promotion. Existing QA-01 and SHADOW-02 dependencies remain. Research budget is distinct from unit-test execution.

## Suitability and hypothesis
RL addresses sequential decisions where present allocation changes future exposure, costs and available capital. Proposed first question: can a bounded allocation policy improve net risk-adjusted outcomes over frozen cash/equal-weight/inverse-vol/momentum baselines on the same observations and execution model? Suitability of formulation does not establish positive return or superiority over supervised learning.

Market making is a separate possible RL problem, but needs pending-order state, uncertain queue position, cancellation races, inventory limits and venue-specific matching/latency validation. Spot inventory-constrained selling can be designed without short selling; the current single intent protocol still does not implement a market maker. Do not infer Indodax runs batch matching from an external paper.

## Data, observation and availability
Pilot: fixed train-selected universe of up to 5 liquid eligible pairs, 1h closed decision frequency. Pair slots frozen for each fold, with presence/eligibility masks. A missing/delisted slot cannot be replaced using future rankings. Inputs are approved OHLCV/features, cash and filled weights, pending simulated intents, drawdown, cost quote, feature availability masks. Numeric feature schema/hash and normalizer fit train-only; all fields available at decision. Environment is partially observed; Markov property is not guaranteed.

Holdout cannot update normalizer, weights or policy. Start episodes at flat cash using prior bars only for feature warmup; do not reset losses or positions mid-episode to boost score. Nontradable held asset follows shared simulator valuation/exit policy; never liquidate at stale quote for free. Unresolved valuation -> INVALID_RUN, not zero loss.

## Action contract
Six discrete actions: KEEP current allocation; TARGET_CASH; TARGET_EQUAL selected eligible universe; TARGET_INV_VOL (C11 frozen recipe); TARGET_MOMENTUM (C04 frozen recipe); TARGET_HALF_MOMENTUM. All baseline recipes fixed by hash before training. Target actions request weights; KEEP emits no rebalancing order. Raw targets projected by the same SIM-02 policy: long-only, no borrowing, total exposure <=0.5, per asset <=0.2, cap then leave remainder cash. Invalid/non-finite action -> structured error, never random action.

If required features unavailable, mask that target. KEEP and TARGET_CASH remain defined; cash liquidation still subject to executable market. At evaluation select deterministic argmax with smallest-index tie; no exploration online. Policy cannot alter stops, cost schedules, evaluator or masks. Risk override reason recorded; policy cannot prevent mandatory exit.

## Transition and reward
Use SIM-03 public judge for transition. Observe at t -> action -> next executable opportunity after latency -> fills -> mark equity at next decision -> reward. Environment must not implement duplicate fee or fill logic.

Reward baseline: r_t = log(E_(t+1)/E_t) - lambda_dd * max(0, DD_(t+1)-DD_t), lambda_dd=0.1; DD_t=1-E_t/running_peak_t. E includes cash, mark-to-market holdings and actual costs exactly once. No separate fee deduction in reward. Bankruptcy/nonpositive equity terminates INVALID_RUN with diagnostics instead of log undefined or infinite reward. DD penalty is utility, not booked cash; report unpenalized PnL separately.

Finite episode: 720 consecutive hourly transitions wholly inside one fold. Terminal liquidation via judge with costs; include its equity change/reward once. Insufficient horizon or overlapping label windows are excluded by split policy. Technical data gap terminates invalid episode; no reward manufactured. Training episode resampling only from train, never from validation/evaluation.

## Algorithm and resource budget
Proposed pilot PPO categorical policy, 2 hidden layers of 64 units, tanh; gamma=0.99, GAE lambda=0.95, clip=0.2, learning rate=0.0003, rollout=720, minibatch=120, update epochs=5, entropy coefficient=0, value coefficient=0.5, max grad norm=0.5. Pin RL framework/dependencies in optional research environment; core bot imports without torch.

Three seeds 11,23,47, <=100000 environment transitions/seed, one initial config; no model/hyperparameter sweep by default. Maximum total pilot 300000 transitions and 6 wall-clock hours, stop at first cap; memory cap set from measured local host profile before run. Budget cannot reset by restarting or changing seed. This is a proposed compute ceiling, not a promise of convergence. Pilot activation requires recorded owner approval and host resource admission, following existing experimental gate.

## Baselines and evaluation
Compare same universe/folds/capital/cost/latency to cash, equal-weight, C11, C04, and deterministic rule selecting those recipes. Every baseline uses same feasible action projection. Report each seed, median and range; do not choose best seed on test. Include turnover, drawdown, net PnL, exposure, mask/override rate, action frequencies and cost sensitivity (1x/1.5x/2x). Baseline sensitivity and RL hyperparameters count toward experiment ancestry.

No random chronological split. Train plus validation for any selection, sealed evaluation once. RL exploration in historical replay is on-policy interaction with a simulator, not proof of causal market response; recorded market does not react to counterfactual large orders. Capacity limits and cost stress bound this approximation, not eliminate it.

## Required adversarial tests
| ID | Fixture and expected assertion |
|---|---|
| RL-A | E 100->100 with no trade, DD unchanged: reward 0 |
| RL-B | E 100->99 including fees, peak100: reward log(0.99)-0.001; no second fee deduction |
| RL-C | Same flat-price trajectory with extra paid turnover has lower equity/reward |
| RL-D | Future candle/features changed after t: observation/action at t unchanged |
| RL-E | Masked recipe never selected; NaN action cannot become valid order |
| RL-F | Raw weights [0.8,0.2] project without leverage; sum<=0.5 and max<=0.2 |
| RL-G | End liquidation includes costs once; repeated terminal step rejected |
| RL-H | Held delisted asset cannot disappear or be sold at stale favorable price |
| RL-I | Same seed/config/data yields same trajectory under pinned deterministic runtime or explicitly records nondeterminism and fails reproducibility gate |
| RL-J | Validation/evaluation rows never influence training, normalizer or early stopping selection after sealed exposure |
| RL-K | Equal action sequence produces exactly same cash/fills/equity as public judge replay |
| RL-L | KEEP vs TARGET_CASH remain different when position open; risk override still operates |

## Planned artifacts and task slices
- `src/indodax_lab/models/rl/environment.py`: public judge adapter, observation/action masks, reset/step/termination. Test RL-A through H and K/L before PPO integration.
- `src/indodax_lab/models/rl/train.py`: bounded offline trainer, train-only normalization, seed registry, optional dependencies. Test budget stop and RL-I/J.
- `configs/research/rl_allocation_v1.yaml`: exact baseline above plus hash references; missing resource/activation gate blocks run.
- `tests/research/test_rl_reward_contract.py`: golden and adversarial cases above; temp data and fake transports.
- `docs/research/rl-feasibility.md`: source SHA, frozen recipe/data/cost/split IDs, per-seed results, baselines, runtime/memory, limitations and CONTINUE/ARCHIVE/INSUFFICIENT_EVIDENCE verdict.

One R01 owner; review environment semantics before expensive training. Final independent spec+quality review required. Software PASS alone cannot promote a policy. Positive feasibility permits a new reviewed research sprint, not live deployment.

## Evidence and limits of transfer
[Relaver, Jiang et al., arXiv v1, 18 May 2025](https://arxiv.org/html/2505.12465v1) models latency and inventory with a specific simulated matching mechanism. It motivates execution fidelity; it does not validate this allocation recipe or Indodax matching behavior. [Market Maker's Dilemma, v2](https://arxiv.org/html/2502.18625v2) addresses fill probability and post-fill return trade-offs. These are primary research references inspected for scope, not performance reproduced in this lab. Proposed first use of RL for bounded allocation is an engineering judgment.
