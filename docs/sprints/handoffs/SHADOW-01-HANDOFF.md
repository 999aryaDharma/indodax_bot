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

---

## Sprint review fix cycle — SHADOW-01 (batch `ops-shadow`)

Actor: `opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)`
Date: 2026-09-27 · Source SHA: uncommitted working tree (`feat/feat-02-finalization`) · Fix cycle: 1 of 1

### Findings fixed

| ID | Severity | Finding |
|---|---|---|
| SHADOW-01-F1 | Critical | `PaperDecisionStore.record_decision` did not require an expected bundle hash. A decision produced against model bundle A could be recorded while bundle B was live, and the store accepted it. The audit trail then claimed a decision was bound to a model that never produced it. |
| SHADOW-01-F2 | Critical | `ForwardDecision.feature_snapshot_age_seconds` accepted `NaN` and negative values, and `max_staleness_seconds` had no lower bound. A `NaN` age compares false against every staleness limit, so the staleness gate was silently bypassed and an arbitrarily old feature snapshot was recorded as fresh. |
| SHADOW-01-F3 | Critical | `ForwardDecision.probability` accepted `NaN` and values outside `[0, 1]`. A `NaN` probability is storable, and `NaN > threshold` is false, so a downstream threshold comparison would treat it either as a silent reject or — depending on the comparison direction — as an unconditional accept. |
| SHADOW-01-F4 | Important | The hash-mismatch check ran *after* the staleness check, so a mismatched bundle on stale data reported the wrong rejection reason, hiding the more serious model-binding failure from operators. |
| SHADOW-01-F5 | Important | A rejected decision left no record at all. There was no way to evidence how many decisions were refused, which is the primary signal that a mis-bound model is live. |

### RED evidence (real assertion failures)

Command: `python -m pytest tests/unit/lab/paper/test_forward_decision_fail_closed.py -p no:cacheprovider -q`
Result: **5 failed** — observed failures:
- A `ForwardDecision` with a deliberately mismatched `bundle_hash` was accepted into the store (`DID NOT RAISE`).
- `AssertionError` on `feature_snapshot_age_seconds=float("nan")` being stored.
- `AssertionError` on `feature_snapshot_age_seconds=-1.0` being stored.
- `AssertionError` on `probability=float("nan")` being stored.
- `AssertionError` on `rejected_decision_count` — no rejection record existed.

### Fix

- `ForwardDecision.feature_snapshot_age_seconds` and `max_staleness_seconds` are now `Field(ge=0, allow_inf_nan=False)`; `probability` is now `Field(ge=0.0, le=1.0, allow_inf_nan=False)`. The same constraints were applied to `ForwardDecisionRecord`.
- `ForwardDecision.parameters` is now `Field(default_factory=dict)` so the snapshot is always a real dict rather than a shared mutable default.
- `PaperDecisionStore(expected_bundle_hash=None)` — the store fails closed with `ModelMismatchError("EXPECTED_BUNDLE_HASH_REQUIRED: ...")` when no expected hash is configured, so a store can no longer record unbound decisions.
- The bundle-hash check now runs **before** the staleness check, so a model-binding failure is reported as such.
- New `RejectedDecision` model plus `PaperDecisionStore.rejected_decisions` / `rejected_decision_count` record every refusal.

### GREEN evidence

Commands and results:
- `python -m pytest tests/unit/lab/paper/test_forward_decision_fail_closed.py -p no:cacheprovider -q` → **6 passed**
- `python -m pytest tests/unit/lab/paper -p no:cacheprovider -q` → **54 passed**

### Files changed
- `src/indodax_lab/paper/contracts.py`
- `src/indodax_lab/paper/__init__.py` (new export: `RejectedDecision`)
- `tests/unit/lab/paper/test_forward_decision_fail_closed.py` (new RED suite)
- `tests/unit/lab/paper/test_forward_decisions.py` (existing suite updated to construct `PaperDecisionStore(expected_bundle_hash=ACTIVE_BUNDLE_HASH)`; no assertion removed or relaxed)

### Isolation
All tests use `tmp_path` stores and constructed models only. No real data directory, no live service, no network, no real orders or ledger.

## Independent review — coordinator pass (2026-09-27)

- Verdict: PASS. Full read of src/indodax_lab/paper/contracts.py (341 lines) and
  both suites (11 tests). Fresh run
  `python -m pytest tests/unit/lab/paper/test_forward_decisions.py tests/unit/lab/paper/test_forward_decision_fail_closed.py -v`:
  11 passed, 0 failed, exit 0 (AC0–AC3 + idempotency + 6 fail-closed guards).
- AC0 holds (PENDING before outcome; frozen immutable record); AC1 holds
  (telegram failure preserves PENDING with error recorded); AC2 holds (stale +
  mismatch rejected; NaN/negative age and NaN proba blocked at model
  validation; missing hash refused); AC3 holds (manual flag preserved; manual
  cannot become ground truth). Rejections observable via rejected_decisions.
- MINOR (backlog, non-blocking): mark_as_ground_truth non-manual path falls
  through returning None (success semantics unmarked/untested); notify unknown
  id raises raw KeyError (typed-error theme); VOIDED status has no producing
  code path (operator-void API would be a CR); fail-closed tests accept any
  exception type (semantically aligned but weak to wrong-exception bugs).
- No Critical/Important findings.
- Reviewer: coordinator inline review (implementation pre-exists committed;
  reviewer wrote no code here). Status transition (manifest/spec) left to
  coordinator DONE pass / main agent — not touched.
