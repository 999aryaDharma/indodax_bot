# PM-01 Handoff — Authoritative Fail-Closed Pre-Write Gate

Status: REVIEW — Round 2 remediation at SHA 99c3a0c; awaiting re-review

## Identity

- Task: PM-01
- Implementation owner: Codex `/root` (LUNA execution)
- Independent reviewer: PENDING
- Base SHA: `418dda6`
- Code SHA: `d9688f0`
- Branch: `docs/architecture-runtime-plan`
- Scope: Fail-closed pre-write gate enforcing evidence existence, freshness, health, approval drift, and single-use permit at venue boundary

## Implemented

- Added `src/indodax_lab/control/authority.py`:
  - `ExecutionSnapshot`: immutable Pydantic model (frozen, extra=forbid) capturing ledger_revision, oms_revision, risk_revision, available_cash, current_equity, positions, mark_prices, market_healthy, clock_healthy, reconciliation_healthy, reconciliation_scope, reconciliation_time, unknown_orders_count, and `compute_digest()` (deterministic canonical SHA-256).
  - `WritePermit`: frozen single-use permit bound to order_internal_id, order_digest, candidate_ref, snapshot_digest, action ("SUBMIT"/"CANCEL"), created_at, expires_at; has `verify_order()`.
  - `AuthorityGate.authorize()`: fail-closed gate checking (1) evidence existence (AC0), (2) freshness/scope/health (AC1), (3) unknown orders (AC3), (4) approval status, parity, post-approval cash/position/slippage re-risk (AC2); issues WritePermit on pass.
  - `AuthorityGate.authorize_cancel()`: cancel permit with snapshot freshness guard.
  - `compute_order_digest()`: deterministic canonical digest of order parameters.
  - Full exception hierarchy: `MissingEvidenceError`, `StaleEvidenceError`, `FutureEvidenceError`, `WrongScopeError`, `UnhealthyEvidenceError`, `ReapprovalRequiredError`, `UnknownOrdersError`, `InvalidPermitError`, `ExpiredPermitError`, `PermitAlreadyUsedError`.

- Modified `src/indodax_lab/execution/order_router.py`:
  - `OrderRouter.__init__` gains `require_permit: bool = False` and `_consumed_permit_ids: set[str]`.
  - `submit_order()` and `cancel_order()` gain `permit: WritePermit | None = None` — enforce permit when `require_permit=True`, venue is `IndodaxTradingClient`, or permit passed (AC4).
  - `WritePermit` moved to `TYPE_CHECKING` block to break circular import (`execution.__init__` → `order_router` → `control.authority` → `control.__init__` → `pipeline` → `order_router`).

- Modified `src/indodax_lab/control/approval.py`:
  - `PendingProposal.snapshot_digest: str | None = None` — binds approval to specific snapshot at approve time (AC2 drift detection).
  - `propose()` and `approve()` gain `snapshot_digest: str | None = None` parameter.
  - Added `from typing import Any` for type annotation.

- Modified `src/indodax_lab/control/pipeline.py`:
  - `TradingPipeline.__init__` gains `authority_gate`, `require_execution_snapshot`, `release_ref` parameters.
  - `step()` gains `execution_snapshot: ExecutionSnapshot | None = None` — blocks AUTONOMOUS_LIMITED mode when snapshot missing and `require_execution_snapshot=True`; calls `authority_gate.authorize()` and passes permit to `submit_order()`.
  - `execute_approved_proposal()` gains `execution_snapshot: ExecutionSnapshot | None = None` — calls `authority_gate.authorize()` when snapshot provided.

- Created `tests/unit/lab/control/test_authority_gate.py`:
  - `test_pm_01_0`: Missing snapshot blocks venue writes (AC0). PASS.
  - `test_pm_01_1`: Wrong scope / future timestamp fail freshness (AC1). PASS.
  - `test_pm_01_2`: Changed state requires reapproval (AC2). PASS.
  - `test_pm_01_3`: Unknown orders block exposure (AC3). PASS.
  - `test_pm_01_4`: Direct write without permit fails, single-use enforcement, action mismatch (AC4). PASS.

## Observed TDD evidence

- RED: `python -m pytest tests/unit/lab/control/test_authority_gate.py -q` → collection error (ModuleNotFoundError: indodax_lab.control.authority).
- GREEN focused: `python -m pytest tests/unit/lab/control/test_authority_gate.py -q` → 5 passed in 0.71s.
- Ruff: `ruff check src/indodax_lab/control/authority.py src/indodax_lab/control/pipeline.py src/indodax_lab/control/approval.py src/indodax_lab/execution/order_router.py tests/unit/lab/control/test_authority_gate.py` → All checks passed (exit 0).
- Full suite gate: `python -m pytest -q` → 961 passed, 2 skipped (platform), 0 failed in 43.05s (exit 0).
- Diff check: `git diff --check` → exit 0 (CRLF warnings only, not errors).

## Acceptance Criteria Mapping

- PM-01-AC0 (`test_pm_01_0`): No snapshot means zero venue writes. OBSERVED_PASS.
- PM-01-AC1 (`test_pm_01_1`): Wrong scope or future timestamp cannot pass freshness. OBSERVED_PASS.
- PM-01-AC2 (`test_pm_01_2`): Changed cash/positions/price after approval requires reapproval. OBSERVED_PASS.
- PM-01-AC3 (`test_pm_01_3`): Unknown orders block new exposure. OBSERVED_PASS.
- PM-01-AC4 (`test_pm_01_4`): Direct real-writer call without valid permit fails; single-use enforced. OBSERVED_PASS.

## Compatibility and migration

- `approval.py`: Added optional `snapshot_digest` field to `PendingProposal` (default `None`) — backward compatible.
- `order_router.py`: Added optional `require_permit` (default `False`) and `permit` params — backward compatible for all existing callers.
- `pipeline.py`: Added optional `authority_gate`, `require_execution_snapshot`, `release_ref` to `TradingPipeline.__init__` — existing tests not using these params still pass.
- `authority.py`: New module, no existing code broken.

## Safety and scope checks

- No credentials, real order authority, network calls, runtime databases, or production activation.
- No `main` or `dev` branch change, merge, push, or deployment.
- No product-path files outside declared PM-01 scope were modified.
- `dashboard.pen` and `DESIGN.md` were preserved and untouched.

## Reviewer checklist (independent reviewer must verify)

- [ ] AC0: Confirm that missing `ExecutionSnapshot` blocks all `OrderRouter.submit_order()` paths to `IndodaxTradingClient`.
- [ ] AC1: Confirm that wrong scope, future timestamp, and stale evidence all raise before permit is issued.
- [ ] AC2: Confirm that changed qty, cash, position, and slippage after approval all raise `ReapprovalRequiredError`.
- [ ] AC3: Confirm that nonzero `unknown_orders_count` blocks new submissions.
- [ ] AC4: Confirm that `OrderRouter` with `require_permit=True` rejects `None` permit; rejects duplicate permit_id; rejects expired permit; rejects action mismatch.
- [ ] Run focused tests and full suite independently.
- [ ] Verify no bypass path exists (e.g., fake venue, non-`require_permit` router with `IndodaxTradingClient` venue).
