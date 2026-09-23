# PM-03 handoff

Status: REVIEW

## Identity
- Sprint ID: PM-03 — Recovery mode and durable operator risk governance
- Implementation agent: Antigravity
- Independent reviewer: Pending independent review
- Branch / worktree: `docs/architecture-runtime-plan`
- Base SHA: `256163b`
- Code target: `feat(pm-03): recovery mode and durable operator risk governance`
- Code SHA: `b998fd7`

## Implementation Summary

Implemented institutional recovery authority, durable mode store boot invariants, authoritative kill switch governance, and replay-preventing cryptographic tokens:
1. **Durable Mode Store & Boot Invariants (`src/indodax_lab/control/mode.py`)**:
   - Invariant (PM-03-FR0 / AC0): Every boot/restart enters `ExecutionMode.RECOVERY`. The desired/requested mode is persisted and tracked separately (`get_requested_mode()`).
   - Journal Integrity (PM-03-FR1 / AC1): Journal hash chain tampering is detected upon load; mode transitions on corrupt journals fail closed raising `CorruptModeJournalError`.
   - Transactional Rollback (PM-03-FR2 / AC2): If mode persistence fails during `transition_to()`, in-memory mutations are rolled back and `RuntimeError("MODE_PERSISTENCE_FAILED")` is raised so writes remain disabled.
   - Normative Contracts: Implemented `RecoveryReport` and `RecoveryService.restore(namespace)` aggregating journal integrity, risk engine verification, and execution state snapshot.

2. **Authoritative Risk State & Kill Switch Governance (`src/indodax_lab/risk/engine.py`)**:
   - Integrity Check: Added `RiskEngine.verify_risk_state_integrity()` ensuring throttle and risk history files are uncorrupted.
   - Authoritative Health Evidence (PM-03-FR3 / AC3): `reset_kill_switch()` requires valid `HealthEvidence`. Fails closed if evidence is missing (`HEALTH_EVIDENCE_REQUIRED`), stale >300s (`HEALTH_EVIDENCE_STALE`), reconciliation is unhealthy, or UNKNOWN orders > 0 exist.
   - Bounded Cryptographic Authorization (PM-03-FR4 / AC4): `generate_reset_token()` binds action, subject, operator, nonce, and expiration. Replay of used nonces raises `PermissionError("NONCE_ALREADY_USED")`; expired tokens raise `TimeoutError("RESET_TOKEN_EXPIRED")`.

3. **Cryptographic Approval Token Governance (`src/indodax_lab/control/approval.py`)**:
   - `generate_approval_token()` and `verify_approval_token()` support bounded tokens with single-use nonce tracking and proposal expiry checks.
   - `ManualApprovalStore.approve()` records and rejects reused nonces with `PermissionError("NONCE_ALREADY_USED")`.

4. **CLI Enforcement (`src/indodax_lab/cli/kill_switch.py`)**:
   - Replaced unevidenced zero/healthy defaults with mandatory health evidence (`--evidence-path`, `--oms-db-path`, or `--reconcile-report-path`). Fails closed (exit code 1) without evidence.

## Files and contracts
- Planned files:
  - `src/indodax_lab/control/mode.py` (Durable mode store, journal integrity, RecoveryService, RecoveryReport)
  - `src/indodax_lab/risk/engine.py` (HealthEvidence, integrity verification, single-use token governance)
  - `src/indodax_lab/control/approval.py` (Manual approval store nonce binding and replay prevention)
  - `src/indodax_lab/cli/kill_switch.py` (CLI disarm requiring authoritative health evidence)
  - `tests/integration/lab/test_control_recovery_authority.py` (Comprehensive AC0–AC4 behavioral tests)
- Affected existing unit tests aligned:
  - `tests/unit/lab/control/test_mode_durability_and_shadow_isolation.py` (Aligned reload expectation to boot into RECOVERY)
  - `tests/unit/lab/cli/test_operator_clis.py` (Provided HealthEvidence fixture for clear subcommand test)

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| PM-03-AC0 (GREEN) | `test_pm_03_0` | `pytest tests/integration/lab/test_control_recovery_authority.py::test_pm_03_0` | Exit 0 (Passed, all modes restart into RECOVERY; requested mode separate) | `b998fd7` |
| PM-03-AC1 (GREEN) | `test_pm_03_1` | `pytest tests/integration/lab/test_control_recovery_authority.py::test_pm_03_1` | Exit 0 (Passed, corrupt/missing risk state prevents active mode; journal hash tamper halts) | `b998fd7` |
| PM-03-AC2 (GREEN) | `test_pm_03_2` | `pytest tests/integration/lab/test_control_recovery_authority.py::test_pm_03_2` | Exit 0 (Passed, persistence failure rolls back in-memory mode, writes stay disabled) | `b998fd7` |
| PM-03-AC3 (GREEN) | `test_pm_03_3` | `pytest tests/integration/lab/test_control_recovery_authority.py::test_pm_03_3` | Exit 0 (Passed, reset with absent/stale evidence rejects; CLI clear rejects without evidence) | `b998fd7` |
| PM-03-AC4 (GREEN) | `test_pm_03_4` | `pytest tests/integration/lab/test_control_recovery_authority.py::test_pm_03_4` | Exit 0 (Passed, reused or expired approval/reset token rejects) | `b998fd7` |

Integration suite: 5 passed in 0.84s.
Full test suite: 986 passed, 2 skipped, 0 failed in 32.21s.
Lint check: `ruff check` passed cleanly (exit 0).
Diff check: `git diff --check` passed cleanly (exit 0).

## Review
- Independent review pending subagent execution.

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None.
- Next unlocked capabilities: PM-05.
