# SHADOW-02 handoff

Status: REVIEW

## Identity
- Sprint ID: SHADOW-02 — Shared capital reconciliation
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/shadow-02-shared-capital-reconciliation`
- Base SHA: `f191e11`
- Code target: `feat(shadow-02): shared capital reconciliation`
- Evidence SHA relation: `8dba5d6`

## Files and contracts
- Actual files:
  - `src/indodax_lab/paper/portfolio.py` (SharedCapitalLedger, PaperOrderIntent, PaperPosition, IntentProcessingResult, SharedLedgerCheckpoint, MaxPositionsExceededError, InsufficientCashError)
  - `src/indodax_lab/paper/__init__.py` (Package exports — SHADOW-02 symbols added)
  - `tests/unit/lab/paper/test_shared_reconciliation.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `durable event IDs + risk policy -> reconciled postings, independent vs shared reports.`
  - Shared capital ledger: `SharedCapitalLedger(initial_cash=Decimal("500000.00"))` tracks cash reservations, cash deductions, and positions using exact Decimal accounting (SHADOW-02-AC0).
  - Deduplication: `process_intent()` checks `event_id in processed_event_ids`. Duplicate events return `approved=False` with `reason="DUPLICATE_EVENT_ID"` without altering balances or positions (SHADOW-02-AC1).
  - Max positions constraint: Ledger enforces `max_open_positions=2` across all candidate strategies. Additional entries raise `MaxPositionsExceededError` fail-closed (SHADOW-02-AC2).
  - Checkpoint and recovery: `create_checkpoint()` and `from_checkpoint()` preserve exact cash balance, open positions, and processed event history across restarts (SHADOW-02-AC3).
- Migration and compatibility:
  - Additive module in `src/indodax_lab/paper/`; no existing interfaces modified.
  - Dependencies: SHADOW-01 (REVIEW), SIM-02 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| SHADOW-02-AC0 (RED) | `test_shadow_02_valid_contract` | `python -m pytest tests/unit/lab/paper/test_shared_reconciliation.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.paper.portfolio') | `working tree` |
| SHADOW-02-AC0 (GREEN) | `test_shadow_02_valid_contract` | `python -m pytest tests/unit/lab/paper/test_shared_reconciliation.py::test_shadow_02_valid_contract` | Exit 0 (Passed, Rp500,000 shared ledger allocates cash and maintains exact decimal balances) | `8dba5d6` |
| SHADOW-02-AC1 (RED) | `test_shadow_02_contract_1` | `python -m pytest tests/unit/lab/paper/test_shared_reconciliation.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SHADOW-02-AC1 (GREEN) | `test_shadow_02_contract_1` | `python -m pytest tests/unit/lab/paper/test_shared_reconciliation.py::test_shadow_02_contract_1` | Exit 0 (Passed, duplicate event_id rejected without duplicate entry or cash change) | `8dba5d6` |
| SHADOW-02-AC2 (RED) | `test_shadow_02_contract_2` | `python -m pytest tests/unit/lab/paper/test_shared_reconciliation.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SHADOW-02-AC2 (GREEN) | `test_shadow_02_contract_2` | `python -m pytest tests/unit/lab/paper/test_shared_reconciliation.py::test_shadow_02_contract_2` | Exit 0 (Passed, 3rd position rejected with MaxPositionsExceededError) | `8dba5d6` |
| SHADOW-02-AC3 (RED) | `test_shadow_02_contract_3` | `python -m pytest tests/unit/lab/paper/test_shared_reconciliation.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SHADOW-02-AC3 (GREEN) | `test_shadow_02_contract_3` | `python -m pytest tests/unit/lab/paper/test_shared_reconciliation.py::test_shadow_02_contract_3` | Exit 0 (Passed, checkpoint restoration yields identical cash, positions, and duplicate protection) | `8dba5d6` |

All 4 tests in `tests/unit/lab/paper/test_shared_reconciliation.py` passed (0.39s).
Full lab suite verification: 191 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, reporting, and paper.

## Review
- Spec verdict: PASS (meets all functional requirements of SHADOW-02 and docs/specs/14-shadow-portfolios-and-promotion.md).
- Quality verdict: PASS (Decimal precision, duplicate protection, 2-position capacity limit, restart checkpointing, no real-money execution).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for SHADOW-02.
- Next unlocked consumers: SHADOW-03, QA-01, R01-01, OPS-01, REPORT-02.

---

## Sprint review fix cycle — SHADOW-02 (batch `ops-shadow`)

Actor: `opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)`
Date: 2026-09-27 · Source SHA: uncommitted working tree (`feat/feat-02-finalization`) · Fix cycle: 1 of 1

Scope note: this sprint owns two files, `src/indodax_lab/paper/portfolio.py` (shared capital ledger) and `src/indodax_lab/paper/live_shadow_engine.py` (forward shadow engine). Both were fixed in this cycle.

### Findings fixed — `portfolio.py`

| ID | Severity | Finding |
|---|---|---|
| SHADOW-02-P1 | Critical | `SharedLedgerCheckpoint.max_open_positions` was not persisted as a *cap*. It was restored as a soft field, so a restart silently reverted the cap to the constructor default of 2. After any restart the shared ledger would accept more concurrent paper positions than the operator had authorised. |
| SHADOW-02-P2 | Critical | `SharedCapitalLedger.from_checkpoint` approved a restart even when the restored position count exceeded the configured cap, so a checkpoint that was already over-limit was restored as a valid, running state. |
| SHADOW-02-P3 | Important | `initial_cash` was never persisted. After a restart the ledger could not prove the restored cash balance against the authorised starting capital, and a tampered cash figure restored as authentic. |
| SHADOW-02-P4 | Important | The checkpoint had no integrity seal. A hand-edited or truncated checkpoint — e.g. one with `available_cash` rewritten to 900000 — was restored and reported as a clean restart. Violates the transactional checkpointing guarantee in `docs/specs/14-shadow-portfolios-and-promotion.md`. |

#### RED evidence (`portfolio.py`)

Command: `python -m pytest tests/unit/lab/paper/test_shared_ledger_restart_hardening.py -p no:cacheprovider -q`
Result: **4 failed** — observed failures:
- `AssertionError` — the max-open-positions cap reverted to `2` after a restart instead of restoring the configured value.
- `AssertionError` — a restart was approved while the position count exceeded the cap.
- `AssertionError: assert None is not None` — `initial_cash` was `None` on the restored ledger.
- `AssertionError` — a tampered checkpoint carrying 900000 cash was restored and accepted as authentic.

#### Fix (`portfolio.py`)

- `SharedLedgerCheckpoint` gained `initial_cash: Decimal | None` and `max_open_positions: int = Field(default=2, ge=1)`.
- `SharedLedgerCheckpoint` is now **auto-sealed**: a `model_validator(mode="after")` computes and stores a canonical `sha256` over the whole checkpoint payload.
- New `CheckpointIntegrityError` plus `_checkpoint_digest()`. `from_checkpoint` recomputes the digest and refuses any checkpoint that does not match, and refuses an unsealed checkpoint outright.
- `from_checkpoint` now restores `initial_cash` and `max_open_positions`, and derives the legacy cost basis as `available_cash + sum(cost_basis)` so a pre-seal checkpoint still restores coherently.
- `SharedCapitalLedger` now carries an `initial_cash` attribute so a restart can be checked against the authorised capital.

### Findings fixed — `live_shadow_engine.py`

| ID | Severity | Finding |
|---|---|---|
| SHADOW-02-L1 | Critical | `LiveShadowEngine.reset_portfolio()` took **no authorization argument**. It rebuilds `PortfolioRiskManager`, which silently clears an active risk hard halt. Any holder of the engine object — an untrusted callback, a scheduler tick, a replay driver — could lift the risk governor. `docs/specs/14-shadow-portfolios-and-promotion.md` requires an *audited control* for exactly this, "never through untrusted callback". |
| SHADOW-02-L2 | Critical | The same method executed `self.audit_log = []`, destroying the audit trail of the very positions it was wiping, and recorded no reason for clearing the halt. |
| SHADOW-02-L3 | Important | Even when authorised, the halt-clearing action left no recorded reason or operator identity, so the cleared hard halt could not be reconstructed after the fact. |

#### RED evidence (`live_shadow_engine.py`)

Command: `python -m pytest tests/unit/lab/paper/test_live_shadow_engine_governance.py -p no:cacheprovider -q`
Result: **4 failed, 2 passed** — observed failures:
- `AssertionError: reset_portfolio() cleared an active risk hard halt with no authorization requirement; an untrusted caller can silently lift the risk governor` (`assert False is True`).
- `AssertionError: An authorized hard-halt reset left no audit record` (`assert []`).
- `AssertionError: reset_portfolio() destroyed the audit trail of the positions it wiped` (`assert [] == [{'action': 'PRIOR_ENTRY', ...}]`).
- `TypeError: LiveShadowEngine.reset_portfolio() got an unexpected keyword argument 'operator_id'` — the governed API did not exist at all.

The RED run was captured against the final version of the test file by temporarily reverting the source fix and restoring it immediately afterwards.

#### Fix (`live_shadow_engine.py`)

- `reset_portfolio` is now `reset_portfolio(*, operator_id: str, reason: str, authorization_ref: str)`. A blank or whitespace-only value for any of the three raises the new `UnauthorizedPortfolioResetError` (`SHADOW_RESET_AUTHORIZATION_REQUIRED:<field>`) before any state is touched.
- The audit entry `{"action": "PORTFOLIO_RESET_AUTHORIZED", "operator_id", "authorization_ref", "detail", "reason", "timestamp"}` is **appended before** the ledger/positions/risk manager are rebuilt, and `self.audit_log` is never truncated. `detail` records `hard_halt_cleared` vs `no_active_halt` plus the discarded position/trade counts.
- `save_state(event_type="RESET", event_payload={operator_id, authorization_ref, reason})` now persists the authorisation in the causal event, not just the checkpoint.
- `LiveShadowEngine.__init__` still calls `save_state(event_type="INITIALIZE")`; that first-run path is unchanged and unaffected by the new gate.
- Caller updated: `run_shadow_bot.py` now supplies `--operator`, `--reason` and `--authorization-ref` (defaulting to `CLI-RESET-<epoch>`) and prints the audit reference. A bare `reset_portfolio()` call from the CLI is no longer reachable.

### GREEN evidence

Commands and results:
- `python -m pytest tests/unit/lab/paper/test_live_shadow_engine_governance.py -p no:cacheprovider -q` → **6 passed**
- `python -m pytest tests/unit/lab/paper -p no:cacheprovider -q` → **54 passed**
- `python -m pytest tests/unit/lab/paper tests/unit/lab/portfolio tests/unit/lab/operations tests/integration/lab/test_backup_restore.py tests/integration/lab/test_service_lifecycle.py tests/integration/lab/test_operational_recovery.py tests/integration/lab/test_retention.py -p no:cacheprovider -q` → **110 passed**

### Files changed
- `src/indodax_lab/paper/portfolio.py`
- `src/indodax_lab/paper/live_shadow_engine.py`
- `src/indodax_lab/paper/__init__.py` (new export: `CheckpointIntegrityError`)
- `run_shadow_bot.py` (CLI caller updated for the new authorised reset signature)
- `tests/unit/lab/paper/test_shared_ledger_restart_hardening.py` (new RED suite)
- `tests/unit/lab/paper/test_live_shadow_engine_governance.py` (new RED suite)

### Isolation
All tests use a `tmp_path` SQLite state file, a synthetic cost schedule, and a hard halt driven through the public `observe_equity` surface. `fetch_live_market_data` is **never** called. No real data directory, no live service, no network, no real orders or ledger.

### Deferred minors (recorded, not fixed - one fix cycle only)
- `LiveShadowEngine.load_state` truncates the restored audit log to `self.audit_log[-200:]`, so a long-lived shadow deployment silently drops the oldest audit entries on every restart. Worth a separate retention decision for the audit log.
- `save_state` builds `event_id` from `f"{event_type}:{now.isoformat()}:{len(self.closed_trades)}:{len(self.open_positions)}"`; two saves within the same clock tick with identical counts would collide on the event id.

## Independent review — coordinator pass (2026-09-27)

- Verdict: PASS. Full read of src/indodax_lab/paper/portfolio.py (297 lines) and
  src/indodax_lab/paper/live_shadow_engine.py reset/state/governance paths
  (lines 100-379) plus scan of scan/exit paths. Fresh runs:
  test_shared_reconciliation.py 4 passed; test_shared_ledger_restart_hardening.py
  + test_live_shadow_engine_governance.py 14 passed; total 18/18 exit 0.
- AC0 holds (Rp500k shared allocation, exact Decimal); AC1 holds (duplicate
  event → DUPLICATE_EVENT_ID, balances untouched); AC2 holds (max-2 cap +
  survives restart with behavior refusal, not just state); AC3 holds (sealed
  SHA-256 checkpoint restores identical cash/positions/events; tampered
  refused; legacy basis reconstructed). Authorized reset preserves breaches,
  closed trades and audit; failed reset restores in-memory state.
- Seal semantics noted: fingerprint proves integrity-since-creation, not
  authorship — a freshly forged sealed checkpoint would verify. Forgery needs
  code execution; disk-tamper path is covered. Backlog, non-blocking.
- The 2 deferred minors above stand as recorded. No new Critical/Important.
- Reviewer: coordinator inline review (implementation pre-exists committed;
  reviewer wrote no code here). Status transition (manifest/spec) left to
  coordinator DONE pass / main agent — not touched.
