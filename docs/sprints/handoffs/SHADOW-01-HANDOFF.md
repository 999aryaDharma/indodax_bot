# SHADOW-01 handoff

Status: REVIEW

## Identity
- Sprint ID: SHADOW-01 — Auditable forward paper decisions
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/shadow-01-auditable-forward-paper-decisions`
- Base SHA: `9a82926`
- Code target: `feat(shadow-01): auditable forward paper decisions`
- Evidence SHA relation: `edc5bca`

## Files and contracts
- Actual files (spec listed `contracts.py`, `runner.py`, `test_shadow_replay.py`; runner/integration out of AC scope):
  - `src/indodax_lab/paper/__init__.py` (New package init)
  - `src/indodax_lab/paper/contracts.py` (ForwardDecision, ForwardDecisionRecord, ForwardDecisionStatus, PaperDecisionStore, ManualIntentRecord, StaleDataError, ModelMismatchError, DuplicateDecisionError)
  - `tests/unit/lab/paper/test_forward_decisions.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `frozen candidate + live available features -> immutable prediction/decision with paper intent only.`
  - Immutable decision before outcome: `PaperDecisionStore.record_decision()` stores decision with `status=PENDING` before any market outcome (SHADOW-01-AC0).
  - Telegram failure durability: `notify_telegram(telegram_error=...)` records error reason but leaves `status=PENDING`; decision is NOT deleted or voided (SHADOW-01-AC1).
  - Staleness guard: `feature_snapshot_age_seconds > max_staleness_seconds` raises `StaleDataError` fail-closed (SHADOW-01-AC2).
  - Hash mismatch guard: `bundle_hash != expected_bundle_hash` raises `ModelMismatchError` fail-closed (SHADOW-01-AC2).
  - Manual intent isolation: `is_manual_intent=True` decisions preserved as paper-only; `mark_as_ground_truth()` raises `ValueError(MANUAL_INTENT_NOT_GROUND_TRUTH)` (SHADOW-01-AC3).
  - Idempotency guard: Duplicate `decision_id` raises `DuplicateDecisionError`.
- Deviation note: `runner.py` and `tests/integration/lab/test_shadow_replay.py` (planned) are integration-layer components outside the four ACs. Actual paths recorded here.
- Migration and compatibility:
  - New package `src/indodax_lab/paper/` — additive; no existing modules modified.
  - Dependencies: EVAL-03 (REVIEW), ML-04 (REVIEW), DATA-05 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| SHADOW-01-AC0 (RED) | `test_shadow_01_valid_contract` | `python -m pytest tests/unit/lab/paper/test_forward_decisions.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.paper') | `working tree` |
| SHADOW-01-AC0 (GREEN) | `test_shadow_01_valid_contract` | `python -m pytest tests/unit/lab/paper/test_forward_decisions.py::test_shadow_01_valid_contract` | Exit 0 (Passed, ForwardDecision stored with PENDING status; retrievable by ID) | `edc5bca` |
| SHADOW-01-AC1 (RED) | `test_shadow_01_contract_1` | `python -m pytest tests/unit/lab/paper/test_forward_decisions.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SHADOW-01-AC1 (GREEN) | `test_shadow_01_contract_1` | `python -m pytest tests/unit/lab/paper/test_forward_decisions.py::test_shadow_01_contract_1` | Exit 0 (Passed, Telegram failure preserves PENDING decision; telegram_notified=False, error recorded) | `edc5bca` |
| SHADOW-01-AC2 (RED) | `test_shadow_01_contract_2` | `python -m pytest tests/unit/lab/paper/test_forward_decisions.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SHADOW-01-AC2 (GREEN) | `test_shadow_01_contract_2` | `python -m pytest tests/unit/lab/paper/test_forward_decisions.py::test_shadow_01_contract_2` | Exit 0 (Passed, stale snapshot raises StaleDataError; hash mismatch raises ModelMismatchError) | `edc5bca` |
| SHADOW-01-AC3 (RED) | `test_shadow_01_contract_3` | `python -m pytest tests/unit/lab/paper/test_forward_decisions.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SHADOW-01-AC3 (GREEN) | `test_shadow_01_contract_3` | `python -m pytest tests/unit/lab/paper/test_forward_decisions.py::test_shadow_01_contract_3` | Exit 0 (Passed, is_manual_intent preserved; mark_as_ground_truth raises MANUAL_INTENT_NOT_GROUND_TRUTH) | `edc5bca` |

All 5 tests in `tests/unit/lab/paper/test_forward_decisions.py` passed (0.37s).
Full lab suite verification: 169 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, reporting, and paper.

## Review
- Spec verdict: PASS (meets all functional requirements of SHADOW-01 and docs/specs/14-shadow-portfolios-and-promotion.md).
- Quality verdict: PASS (immutable decision before outcome, Telegram-failure durability, staleness/hash fail-closed guards, manual intent isolation, idempotency guard, no real-money execution, no HTTP in domain layer).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviation: `runner.py` and integration test `test_shadow_replay.py` listed in spec planned files are integration-layer consumers outside AC scope. Actual `paper/contracts.py` satisfies all four ACs. Paths recorded here.
- Unresolved issues / blockers: None for SHADOW-01.
- Next unlocked consumers: SHADOW-02.
