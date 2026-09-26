# S08-01 handoff — passive mean reversion and queue evidence

Status: REVIEWED_PARTIAL — implementation independently passed; external queue qualification remains open.

## Identity

- Sprint: S08-01 — Passive mean reversion
- Implementation owner: Codex `/root`
- Independent reviewer: `/root/docs_review` (PASS on exact remediation SHA)
- Branch: `feat/feat-02-finalization`; base SHA `4e19671d95d9a0c62ff0e9dbb8b16b7f987fcf99`
- Code SHAs: `f193ae76f84fe89a24cc3e9d630160e39b1c76c2` (implementation), `18564d0f7387c5e6c3b5db60f831f08a46997500` (review fixes and AC3 reservation proof).
- Evidence SHA relation: this handoff records both implementation commits; it is a follow-up evidence document.

## Files and contracts

- `configs/strategies/S08_v1.yaml`; `src/indodax_lab/strategies/s08.py`: configurable research hypothesis emits passive LONG intents from causal `lob_v1` inputs. It has no order/ledger authority.
- `src/indodax_lab/strategies/registry.py`: statically allowlists S08 through the existing versioned registry.
- `src/indodax_lab/models/lob/queue_evidence.py`; `src/indodax_lab/models/lob/__init__.py`: frozen `lob_queue_v1` evidence, explicit approved freshness policy, and candidate-bound qualification report.
- `src/indodax_lab/backtest/execution.py`: optional `lob_queue_v1` precondition validates queue evidence at quote creation. Default `bar_proxy_v1` behavior remains unchanged; passing queue validation does not turn bar-proxy fills into observed queue fills.
- `src/indodax_lab/paper/promotion.py`: LOB queue promotion requires a complete qualification report; report and execution contract are covered by the explicit approval digest.
- Tests: `tests/unit/lab/models/lob/test_s08_queue_evidence.py`, `tests/unit/lab/paper/test_s08_queue_promotion.py`, `tests/unit/lab/strategies/test_s08.py`, and `tests/integration/lab/test_disaster_drills.py::test_drill_3_cancel_fill_race_under_partial_fill`.
- Docs: `docs/decisions/CR-S08-queue-evidence.md`, `docs/research/dataset-feature-contracts.md`, this sprint spec.
- No database migration. Promotion evidence digest now includes execution contract and optional queue report; approvals over older digest bytes must be regenerated.

## Acceptance evidence

| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| AC0 RED | Import of not-yet-implemented S08 module | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q tests/unit/lab/strategies/test_s08.py` | Exit 2, collection failed because S08 module did not exist; setup RED only | Working tree before implementation |
| AC0 GREEN | Valid causal `lob_v1` row emits versioned maker intent; registry integration | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q tests/unit/lab/strategies/test_s08.py` | 5 passed | `18564d0f7387c5e6c3b5db60f831f08a46997500` |
| AC1 RED/GREEN | Shared simulator accepts queue mode; limit touch remains no-fill | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q tests/unit/lab/strategies/test_s08.py tests/unit/lab/backtest/test_execution.py` | RED: unsupported `execution_contract` keyword; GREEN: 11 passed, including `LIMIT_TOUCH_NO_FILL` | `18564d0f7387c5e6c3b5db60f831f08a46997500` |
| AC2 GREEN | Promotion rejects missing, unavailable, stale, future, sequence-invalid or candidate-mismatched queue report; report is approval-digest bound | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q tests/unit/lab/paper/test_s08_queue_promotion.py tests/unit/lab/paper/test_promotion.py tests/unit/lab/paper/test_promotion_gate_hardening.py` | 25 passed; no behavioral RED recorded before implementation | `18564d0f7387c5e6c3b5db60f831f08a46997500` |
| AC3 | Shared OMS/venue/ledger partial-fill cancel-race; check OMS remainder, rebased reservation, released amount, available cash, position and balanced posting | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q tests/integration/lab/test_disaster_drills.py::test_drill_3_cancel_fill_race_under_partial_fill` | 1 passed; reserves Rp100.1M, partial fills 0.05 BTC, retains Rp50.05M reserve, then releases Rp50.05M after cancel; available cash reconciles to Rp149.95M | `18564d0f7387c5e6c3b5db60f831f08a46997500` |
| Regression | S08 queue/strategy/promotion/registry and shared execution boundary | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q tests/unit/lab/models/lob/test_s08_queue_evidence.py tests/unit/lab/paper/test_s08_queue_promotion.py tests/unit/lab/strategies/test_s08.py tests/unit/lab/paper/test_promotion.py tests/unit/lab/paper/test_promotion_gate_hardening.py tests/unit/lab/strategies/test_versioned_registry.py tests/unit/lab/backtest/test_execution.py tests/integration/lab/test_disaster_drills.py::test_drill_3_cancel_fill_race_under_partial_fill` | 66 passed | `18564d0f7387c5e6c3b5db60f831f08a46997500` |
| Full regression | Repository suite | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q` | 1602 passed, 2 skipped, 11 warnings in 45.97s. Skips: Linux `/proc` RSS check unavailable on Windows; symlink creation restricted by Windows privilege. | `18564d0f7387c5e6c3b5db60f831f08a46997500` |
| Ruff | Changed S08 code/tests (`F,I,B,UP`) | `C:/Users/User/miniconda3/envs/ML/python.exe -m ruff check src/indodax_lab/models/lob/queue_evidence.py src/indodax_lab/models/lob/__init__.py src/indodax_lab/strategies/s08.py src/indodax_lab/strategies/registry.py src/indodax_lab/backtest/execution.py tests/unit/lab/models/lob/test_s08_queue_evidence.py tests/unit/lab/paper/test_s08_queue_promotion.py tests/unit/lab/strategies/test_s08.py tests/integration/lab/test_disaster_drills.py --select F,I,B,UP`; promotion rules checked separately with `ruff check src/indodax_lab/paper/promotion.py --select F,I,B,UP` | Both passed | `18564d0f7387c5e6c3b5db60f831f08a46997500` |
| Diff | `git diff --check` and `git diff --cached --check` | Exit 0; CRLF notices only | `18564d0f7387c5e6c3b5db60f831f08a46997500` |

## Review

- Self-review: completed; focused and full repository checks passed.
- Review round 1 at exact SHA `f193ae76f84fe89a24cc3e9d630160e39b1c76c2`: CHANGES_REQUESTED for blank queue identities, book availability preceding its event, and missing reservation-release proof at AC3.
- Fixes at `18564d0f7387c5e6c3b5db60f831f08a46997500`: trim/reject blank policy, session, source, candidate and report identity; require `event_at <= available_at <= row_ready_at <= decision`; expand the shared partial-fill/cancel integration to assert reservation rebasing/release and reconciled ledger values.
- Independent re-review at exact SHA `18564d0f7387c5e6c3b5db60f831f08a46997500`: PASS. All three Important findings were resolved; no Critical/Important findings remain.
- Reviewer independently ran queue, strategy, promotion and shared execution checks: 36 passed. Reviewer did not rerun AC3 integration because of the temp-directory limitation. Owner's exact-SHA full suite passed all 1,602 tests, including AC3.
- Sprint remains IN_PROGRESS because the real queue producer and operational qualification are unavailable; no completion is claimed.

## Deviations and known risks

- CR-S08 boundary and 5-second Research freshness default accepted by the owner on 2026-09-27. `observed_at` age is checked at decision/quote time. This default is not real producer qualification.
- S08 thresholds/notional in YAML are research hypothesis defaults, not profitability evidence or Production risk policy.
- There is no qualified real Indodax per-order queue producer/reconstruction or 90-day queue-coverage report. Queue-mode simulation requires explicit policy/evidence; candidate promotion remains blocked without the qualified report.
- A valid queue observation only passes the precondition; fill outcomes still use the existing conservative bar proxy. No strategy-local OMS or ledger was created.
- Rollback: stop selecting S08 and revert the scoped code commit; existing `bar_proxy_v1` call sites retain default behavior. No Production state or credentials were accessed.
- Next gate: real queue source qualification with measured book/trade coverage.

## Owner-approved freshness default

- Owner approved a 5-second maximum queue-evidence age for Research on 2026-09-27; age is measured from `observed_at` at decision/quote time. Exactly 5 seconds is accepted; 5.001 seconds is stale.
- `QueueEvidencePolicy.max_evidence_age_seconds` defaults to `Decimal("5")`; version, approval reference, source ID/version and explicit policy remain required. Missing policy/evidence remains fail-closed.
- Implementation SHA: `8203356edd849e8aa0094120a1b960a3f73049d3`.
- Owner checks after the default change: queue/strategy/promotion/risk focused suite — 64 passed; full repository suite at descendant SHA `40e91215df3f99bd4ecaf2e47aeb76de19e2fb30` — 1,646 passed, 2 platform skips, 11 warnings.
- Independent review of the default at `4bdc2e52eabfd2e50d330cf9197ded4dc5d034ae`: PASS; 31 S08 checks passed. Real Indodax queue reconstruction and measured book/trade coverage remain external gates, so S08 remains IN_PROGRESS.
