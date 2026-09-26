# S04-01 handoff

Status: REVIEW

## Identity

- Sprint ID: S04-01 — Order flow imbalance
- Implementation owner: Codex `/root`
- Independent reviewer: `/root/docs_review` (pending)
- Branch: `feat/feat-02-finalization`
- Implementation SHA: `8a415f1df109cb15eaaca0b6cb08aa1d317713c8`
- Dependency status: STRAT-01 DONE; LOB-01 DONE
- Environment: Windows, Python 3.12.13, `C:/Users/User/miniconda3/envs/ML/python.exe`

## Contract and files

- `configs/strategies/S04_v1.yaml`: `lob_v1` version `1.0.0`, both imbalance thresholds 0.10, maximum book age 5 seconds, Rp10,000 minimum target notional, and 2% research stop.
- `src/indodax_lab/strategies/s04.py`: pure `DecisionFrame -> list[SignalIntent]`; emits candidate-sized BUY only; no fill, ledger, or order authority.
- `tests/unit/lab/strategies/test_s04.py`: positive candidate sizing, inclusive threshold/freshness boundaries, sequence/session fail-closed, stale/future/unavailable timestamps, invalid timezone, and feature-version mismatch.
- `docs/research/dataset-feature-contracts.md`: additive typed `lob_v1` S04 inputs; does not mutate `tabular_bar_v1`.
- `docs/decisions/CR-S04-order-flow-feature-contract.md`: accepted owner decision, 2026-09-27.

## Acceptance evidence

- AC0: `test_s04_valid_causal_order_flow_emits_candidate_sized_intent` — valid versioned row produces a >=Rp10,000 LONG intent with a stop.
- AC1: `test_s04_missing_unknown_or_invalid_session_sequence_abstains` — false/unknown sequence and empty session abstain.
- AC2: `test_s04_stale_or_future_book_timestamps_abstain` — exactly 5 seconds is accepted; >5 seconds, future events, and availability after decision abstain.
- AC3: same timestamp test — future timestamps reject; naive timestamps reject.
- Additional guards: `test_s04_imbalance_thresholds_are_inclusive` and `test_s04_rejects_wrong_version_and_invalid_causal_timestamps`.
- Focused command: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/strategies/test_s04.py -q` — 5 passed.
- Ruff: `C:/Users/User/miniconda3/envs/ML/python.exe -m ruff check src/indodax_lab/strategies/s04.py tests/unit/lab/strategies/test_s04.py` — passed.
- Planning validator: `C:/Users/User/miniconda3/envs/ML/python.exe docs/quality/validate_planning.py` — passed, 134 nodes, 264 edges, 0 cycles.
- Scoped `git diff --check` — passed.

## Gates and review

- Real Indodax book/trade feed and >=90-day coverage/regime qualification remain external; this implementation uses fixtures and makes no profitability or promotion claim.
- Research strategy only. No Production account, credential, runtime, order, or ledger was accessed or changed.
- Independent review is pending on implementation SHA `8a415f1df109cb15eaaca0b6cb08aa1d317713c8`.
