# LUNA-NEXT — PM-01 only

## TASK ID

PM-01

## OBJECTIVE

All real writes need trusted current scoped evidence and exact approval re-risk. Implement the authoritative fail-closed pre-write gate (`AuthorityGate`), `ExecutionSnapshot`, and `WritePermit` to prevent unauthorized or stale venue writes.

## ARCHITECTURAL CONTEXT

Pipeline conditionally checks reconciliation; manual execution defaults missing capital. Shared-runtime and frozen authority contracts apply (`docs/production/FROZEN-SYSTEMS.md`, `docs/production/main/SOP-AND-GATES.md`, `docs/implementation/CONTRACTS.md`, `ADR-002`, `ADR-005`).
1. `AuthorityGate.authorize(order, execution_snapshot, release_ref, approval, now) -> WritePermit`: Verifies freshness, health, reconciliation, scope, unknown orders, and exact order parameters against approval.
2. `ExecutionSnapshot`: Contains ledger/OMS/risk revisions, cash/positions/equity, market/clock health, reconciliation scope/time, and unknown count.
3. `WritePermit`: Bound to order/candidate/snapshot digest and single-use submission.
4. Fail-closed: Zero report or missing portfolio snapshot means zero venue writes. Any stale revision, unknown order, or expired permit fails immediately.

## ALLOWED SCOPE

- Create `src/indodax_lab/control/authority.py` (AuthorityGate, ExecutionSnapshot, WritePermit, related exceptions and validators).
- Modify `src/indodax_lab/control/pipeline.py` (integrate authoritative pre-write gate check before dispatch).
- Modify `src/indodax_lab/control/approval.py` (support exact re-risk and permit binding).
- Modify `src/indodax_lab/execution/order_router.py` (require valid WritePermit at venue writer boundary).
- Create `tests/unit/lab/control/test_authority_gate.py`.
- Record handoff at `docs/sprints/handoffs/PM-01-HANDOFF.md`.

## DO NOT TOUCH

- Do not touch `dashboard.pen` or `DESIGN.md`.
- Do not touch live trading credentials, real orders, withdrawal keys, production DB, or external network calls.
- Do not weaken fail-closed invariants or invent fallback equity/cash defaults.
- Do not modify historical test fixtures or unrelated components.
- Do not touch `main` or `dev` branches.

## PRECONDITIONS

- RW0-01 status is DONE in `docs/sprints/sprint-manifest.json` (verified with full suite 956 PASS).
- PM-01 status is READY in manifest.
- Recommended branch: `feat/pm-01-authoritative-fail-closed-pre-write-gate`.
- Python isolated research environment: `C:\Users\User\miniconda3\envs\ML\python.exe`.

## IMPLEMENTATION STEPS

1. Create `tests/unit/lab/control/test_authority_gate.py` with behavioral RED tests for PM-01-AC0 through PM-01-AC4:
   - AC0 (`test_pm_01_0`): No report or portfolio snapshot means zero venue writes.
   - AC1 (`test_pm_01_1`): Wrong scope or future timestamp cannot pass freshness.
   - AC2 (`test_pm_01_2`): Changed cash/positions/price after approval requires fresh rejection/reapproval.
   - AC3 (`test_pm_01_3`): Unknown orders block new exposure.
   - AC4 (`test_pm_01_4`): Direct real-writer call without valid permit fails.
2. Implement `src/indodax_lab/control/authority.py`:
   - `ExecutionSnapshot` immutable model with revisions, cash/positions/equity, market/clock health, reconciliation scope/time, unknown count.
   - `WritePermit` single-use token bound to order/candidate/snapshot digest.
   - `AuthorityGate.authorize(...)` fail-closed verification.
3. Wire `AuthorityGate` into `pipeline.py`, `approval.py`, and `order_router.py`.
4. Run focused tests, linting, full suite, and diff check:
   - `python -m pytest tests/unit/lab/control/test_authority_gate.py -q`
   - `ruff check src/indodax_lab/control src/indodax_lab/execution tests/unit/lab/control`
   - `python -m pytest -q`
   - `git diff --check`
5. Create `docs/sprints/handoffs/PM-01-HANDOFF.md` and submit for independent review.

## FILES

- Create `src/indodax_lab/control/authority.py`
- Modify `src/indodax_lab/control/pipeline.py`
- Modify `src/indodax_lab/control/approval.py`
- Modify `src/indodax_lab/execution/order_router.py`
- Create `tests/unit/lab/control/test_authority_gate.py`
- Create `docs/sprints/handoffs/PM-01-HANDOFF.md`

## TESTS

```text
python -m pytest tests/unit/lab/control/test_authority_gate.py -q
ruff check src/indodax_lab/control src/indodax_lab/execution tests/unit/lab/control
python -m pytest -q
git diff --check
```

## ACCEPTANCE CHECKS

- PM-01-AC0: `test_pm_01_0` passes. Zero report/snapshot rejects all venue writes.
- PM-01-AC1: `test_pm_01_1` passes. Stale/future/wrong-scope evidence fails freshness.
- PM-01-AC2: `test_pm_01_2` passes. State change after approval forces fresh approval.
- PM-01-AC3: `test_pm_01_3` passes. Unknown order count > 0 blocks exposure.
- PM-01-AC4: `test_pm_01_4` passes. Direct venue submit/cancel fails without permit.
- Zero regressions in full pytest suite (956+ tests pass).

## EXPECTED OUTPUT

- Independently reviewable committed unit and exact-SHA handoff at `docs/sprints/handoffs/PM-01-HANDOFF.md`.
- Manifest remains READY during implementation, moving to REVIEW on handoff submission.
- Once PM-01 is DONE, downstream tasks `PM-03` and `PM-04` become eligible for evaluation.

## STOP CONDITIONS

- Any bypass of fail-closed pre-write gate.
- Acceptance of unverified or invented cash/positions/reconciliation.
- Execution on live venue or credential exposure.
- Failure of full-suite regression test.
