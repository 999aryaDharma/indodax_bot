# PM-03 independent review

Status: PASS on Round 1; reviewed content SHA `b998fd773ace7ff8d14908c095e2e6b7eecd780a` (`b998fd7`). Maximum five rounds; history preserved below.

## Identity

- Sprint ID: PM-03 — Recovery mode and durable operator risk governance
- Implementation owner: Antigravity
- Independent reviewer: Antigravity Independent Reviewer
- Reviewed code SHA: `b998fd773ace7ff8d14908c095e2e6b7eecd780a` (`b998fd7`)
- Handoff commit SHA: `1f03416dbefa547bf6eaddd7d5e3eb0f682eef40` (`1f03416`)
- Handoff doc: `docs/sprints/handoffs/PM-03-HANDOFF.md`
- Sprint spec doc: `docs/sprints/production-main/PM-03-recovery-mode-and-durable-operator-risk-governance.md`
- Base SHA: `256163b`
- Branch: `docs/architecture-runtime-plan`
- Round: 1

## Formal verdicts

- Spec verdict: PASS
- Quality verdict: PASS
- Overall verdict: PASS

Summary: PM-03 implementation fulfills all requirements and invariants defined in `PM-03-recovery-mode-and-durable-operator-risk-governance.md` and `docs/implementation/CONTRACTS.md`. Every boot/restart deterministically enters `ExecutionMode.RECOVERY` with requested mode preserved separately. Corrupted mode journals and compromised risk states prevent active transitions and cause `RecoveryService.restore()` to report `HALTED`. Transitions are transactionally rolled back in memory if persistence fails. Disarming the emergency kill switch requires authoritative, un-stale health evidence (reconciliation healthy and unknown orders == 0), rejecting default assumptions in both service and CLI. Single-use replay protection with nonces and token expiration is enforced for both manual approvals and kill-switch disarms.

---

## Spec compliance analysis

| Requirement / Invariant | Spec reference | Code location | Evaluation | Verdict |
|---|---|---|---|---|
| **PM-03-AC0**: All persisted modes restart into RECOVERY | PM-03-FR0, AC0 | `src/indodax_lab/control/mode.py:226-250` | `DurableModeStore._load()` initializes `_effective_mode = ExecutionMode.RECOVERY` regardless of the mode saved on disk. The target mode from persistence is isolated into `_requested_mode`. A journal entry recording `BOOT_RESTART_RECOVERY_ENFORCED` is recorded and saved. Verified across all operational modes (`READ_ONLY`, `SHADOW`, `MANUAL_APPROVAL`, `AUTONOMOUS_LIMITED`, `DISABLED`, `HALTED`). | PASS |
| **PM-03-AC1**: Corrupt/missing risk state prevents active mode | PM-03-FR1, AC1 | `src/indodax_lab/control/mode.py:267-298, 401-408`, `src/indodax_lab/risk/engine.py:74-87` | Tampered SHA-256 hash chains in mode journal fail `verify_journal_integrity()`, setting `_journal_corrupt` and causing `transition_to()` to raise `CorruptModeJournalError`. In `RecoveryService.restore()`, corrupted mode journals emit `CORRUPT_MODE_JOURNAL` and corrupted throttle/risk files emit `CORRUPT_OR_MISSING_RISK_STATE`, driving `effective_state="HALTED"` and restricting next actions to `["AUDIT", "INSPECT_JOURNAL", "RECOVER"]`. | PASS |
| **PM-03-AC2**: Persistence failure leaves writes disabled | PM-03-FR2, AC2 | `src/indodax_lab/control/mode.py:305-332` | `transition_to()` captures prior effective mode, requested mode, and journal length before provisional mutation. If `_save()` fails, the catch block rolls back in-memory mode and truncates uncommitted journal entries, re-raising `RuntimeError("MODE_PERSISTENCE_FAILED")`. Effective mode remains `RECOVERY` (`can_write_venue == False`), ensuring writes remain disabled. | PASS |
| **PM-03-AC3**: Reset with absent/stale evidence rejects | PM-03-FR3, AC3 | `src/indodax_lab/risk/engine.py:183-210`, `src/indodax_lab/cli/kill_switch.py:123-198` | `reset_kill_switch()` requires `HealthEvidence`. Missing evidence raises `ValueError("HEALTH_EVIDENCE_REQUIRED")`. Evidence older than 300 seconds raises `ValueError("HEALTH_EVIDENCE_STALE")`. Unhealthy reconciliation raises `RuntimeError("CANNOT_RESET_KILL_SWITCH_UNHEALTHY_RECONCILIATION")`. Non-zero unknown orders count raises `RuntimeError("CANNOT_RESET_KILL_SWITCH_UNKNOWN_ORDERS_EXIST")`. The CLI clear subcommand rejects unless valid `--evidence-path` or verifiable `--oms-db-path`/`--reconcile-report-path` are provided; unevidenced clear attempts exit with code 1. | PASS |
| **PM-03-AC4**: Reused or expired approval/reset token rejects | PM-03-FR4, AC4 | `src/indodax_lab/control/approval.py:224-255`, `src/indodax_lab/risk/engine.py:213-264` | `ManualApprovalStore.approve()` checks `at > current.expires_at` raising `TimeoutError("PROPOSAL_EXPIRED")` and tracks used nonces in `_used_nonces`, raising `PermissionError("NONCE_ALREADY_USED")` on replay. `RiskEngine.reset_kill_switch()` validates cryptographic HMAC token bound to action, subject, operator, expiry, and nonce; expired tokens raise `TimeoutError("RESET_TOKEN_EXPIRED")` and replayed nonces raise `PermissionError("NONCE_ALREADY_USED")`. | PASS |
| **RecoveryReport Contract**: Normative recovery contract compliance | CONTRACTS.md line 89 | `src/indodax_lab/control/mode.py:361-375, 429-440` | `RecoveryReport` provides all required fields: `namespace`, `effective_mode`, `requested_mode`, `reloaded_revision`, `feed_cursor`, `journal_integrity_ok`, `halt_reasons`, `effective_state`, `permitted_next_actions`, and `status`. Aligned with CONTRACTS.md. | PASS |

---

## Code quality, safety & security analysis

1. **Fail-Closed Governance**:
   - Zero optimistic assumptions or defaulting to healthy states.
   - Boot sequence always enters `ExecutionMode.RECOVERY`. Active execution can only be initiated through explicit transitions after system health is verified.
   - `kill_switch clear` CLI subcommand enforces mandatory health evidence, preventing unauthorized manual overrides without audit trail.

2. **Durable Integrity & Rollback**:
   - Mode journal uses SHA-256 hash chaining where each entry binds `prev_hash`, modes, operator, reason, and UTC timestamp.
   - File persistence uses atomic temporary file replacement (`.tmp` write followed by `replace()`), preventing corrupt partial writes on sudden shutdown.
   - Persistence failures rollback all in-memory changes, leaving the store safely in its previous state with writes disabled.

3. **Cryptographic Protection & Replay Prevention**:
   - Reset and approval tokens use HMAC-SHA256 with constant-time equality checks (`hmac.compare_digest`), preventing timing side-channel attacks.
   - Tokens are cryptographically bound to action, subject, operator, nonce, and ISO UTC expiration timestamp.
   - Single-use nonces are recorded upon use; attempts to replay any nonce reject immediately.

4. **Concurrency & Thread Safety**:
   - `DurableModeStore` and `ManualApprovalStore` guard all state reads and transitions with `threading.RLock`.

5. **Operational Safety & Scope Limits**:
   - No trade or withdrawal API keys or live venue order execution.
   - Research workbench / paper shadow boundaries maintained.
   - Pydantic models use `ConfigDict(frozen=True, extra="forbid")`.
   - Critical configuration files `dashboard.pen` and `DESIGN.md` were untouched.

---

## Findings summary

| ID | Severity | Category | Description | Resolution / Status |
|---|---|---|---|---|
| **O-01** | Minor (Advisory) | Durability | `_used_nonces` in `RiskEngine` and `ManualApprovalStore` is maintained as an in-memory `set[str]`. If the process restarts, prior used nonces are cleared from memory. However, this is fully mitigated by the fact that every restart forces `ExecutionMode.RECOVERY`, clearing all in-flight proposals and requiring a complete fresh recovery cycle before any order authorization can proceed. For future distributed multi-process operator scaling, persisting used nonces in SQLite can be considered. | NOTED (No action required; safe by design due to boot recovery invariant) |

**Total Findings**:
- Critical: 0
- Important: 0
- Minor: 1 (Advisory observation)

---

## Independent verification evidence

### 1. Integration acceptance suite
- Command: `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/integration/lab/test_control_recovery_authority.py -v`
- Result: **5 passed in 0.92s** (Exit 0)
  - `test_pm_03_0`: PASSED (AC0: all persisted modes restart into RECOVERY; requested mode separate)
  - `test_pm_03_1`: PASSED (AC1: corrupt/missing risk state prevents active mode; journal tamper halts)
  - `test_pm_03_2`: PASSED (AC2: persistence failure rolls back in-memory mode, writes stay disabled)
  - `test_pm_03_3`: PASSED (AC3: reset with absent/stale evidence rejects; CLI clear rejects without evidence)
  - `test_pm_03_4`: PASSED (AC4: reused or expired approval/reset token rejects)

### 2. Affected unit test suites
- Command: `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/control/test_mode_durability_and_shadow_isolation.py tests/unit/lab/cli/test_operator_clis.py -v`
- Result: **9 passed in 1.01s** (Exit 0)

### 3. Code formatting & lint gate
- Command: `C:\Users\User\miniconda3\envs\ML\python.exe -m ruff check src/indodax_lab/control/mode.py src/indodax_lab/risk/engine.py src/indodax_lab/control/approval.py src/indodax_lab/cli/kill_switch.py tests/integration/lab/test_control_recovery_authority.py`
- Result: **Exit 0** (All checks passed!)

### 4. Git diff check
- Command: `git diff --check`
- Result: **Exit 0** (Clean diff, no whitespace or formatting errors)

### 5. Full test suite regression gate
- Command: `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest -q`
- Result: **986 passed, 2 skipped, 3 warnings in 34.06s** (Exit 0)
  - Note: 2 skipped tests are existing platform-specific skips (Linux `/proc` and Windows symlink privilege). Zero test failures.

### 6. Independent edge-case verification
Executed independent verification script exercising:
- Chained multi-step journal integrity through 4 state transitions and tamper detection on intermediate entries: verified raise `CorruptModeJournalError`.
- Rollback of journal history upon `_save()` I/O failure: verified that in-memory journal length remains 1, matching disk.
- Exact stale evidence boundary testing: evidence at exactly 300s accepts; evidence at 301s rejects with `HEALTH_EVIDENCE_STALE`.
- Token action and subject binding: tokens generated with mismatched action reject with `INVALID_CONFIRMATION_TOKEN`.
- Result: **All independent negative edge-case assertions PASSED cleanly**.

---

## Verdict and next steps

- **Verdict**: **PASS**
- PM-03 implementation is verified, robust, and compliant with all sprint requirements and domain contracts.
- Next sprint unlocked: PM-05.
