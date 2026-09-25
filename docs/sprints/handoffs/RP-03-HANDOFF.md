# RP-03 handoff

## Identity

- Sprint: RP-03 — Shared portfolio sizing and risk semantics
- Implementation owner: `/root`
- Independent reviewer: `/root/docs_review` (rounds 1–4 findings fixed; round 5 final PASS)
- Base SHA: `6f8e5bff` (SIM-02 capability close)
- Initial code SHA: `a108cc102d7afbc5bf629306c5c6426e9f311707`
- Remediation SHAs: `1d2b0990fe1601370b2a4faa47bcc4cd37798a93`,
  `d0aabce80764ceb1a8c95f6ab8ef85cbb803c001`,
  `b93dbe4babfe278483216a4c66868921be14e0d7`
- Final review target SHA: `a87562a8ceb4a4f953520c65bae781ec4506a49f`
- Branch: `feat/feat-02-finalization`

## Scope delivered

- Added immutable `PortfolioState`, pending reservations, and versioned deterministic
  same-pair allocation policy.
- Preserved `SignalIntent` lineage in `construct_orders`; ambiguous same-pair intents
  now reject unless a policy arbitrates them.
- Added the state-based `RiskEngine.assess_intent` path with explicit entry cost and
  precision inputs, pending cash/exposure accounting, and optional stop-risk sizing.
- Adapted `TradingPipeline.step` to arbitrate and assess original intents from one
  typed snapshot, feed configured fee/precision and optional strategy stop-risk
  budgets, and reserve pending OMS orders, manual proposals, and earlier approvals
  in the same cycle. Pending order pairs are marked even on empty-intent cycles;
  identical OMS/manual proposal references reserve once. Inconsistent available
  cash and unmapped strategies under active stop-risk policy fail closed.
- Manual proposal execution requires explicit fees/precision, releases only its own
  stored-limit principal and fee from net available cash, retains other pending
  reservations, and fails closed when strategy/stop lineage cannot be recovered.
- Extended authoritative `ExecutionSnapshot` with order-ID keyed reserved cash,
  included in its digest. The final authority gate restores only the exact approved
  order's evidence-backed reserve; other orders remain deducted. Decimal position
  quantities from the execution snapshot are normalized before risk assessment.
- Kept legacy financial keyword inputs and `generate_rebalance_intents` compatible.
- Made portfolio holding snapshots detached and immutable, included pending SELL
  quantities in sellable inventory, rejected sell reservations above holdings, and
  applied allocation priority across different pairs.
- Actual paths: `src/indodax_lab/backtest/risk.py`,
  `src/indodax_lab/control/pipeline.py`, `src/indodax_lab/portfolio/constructor.py`,
  `src/indodax_lab/control/authority.py`, `src/indodax_lab/risk/engine.py`,
  `tests/unit/lab/control/test_control_pipeline.py`,
  `tests/unit/lab/control/test_manual_approval_execution.py`,
  `tests/unit/lab/control/test_authority_gate.py`,
  `tests/unit/lab/portfolio/test_intent_semantics.py`,
  `tests/unit/lab/risk/test_risk_parity.py`,
  `docs/decisions/CR-RP-03-execution-cash-reservation-evidence.md`, and this handoff.

## Acceptance and verification

Behavioral RED evidence: the same-pair conflict, missing `construct_orders`, and
state-based risk call tests failed before implementation with the expected errors.

Focused checks on final review target `a87562a8ceb4a4f953520c65bae781ec4506a49f`:

- `python -m pytest tests/unit/lab/control/test_authority_gate.py tests/unit/lab/control/test_manual_approval_execution.py tests/unit/lab/control/test_control_pipeline.py -q -p no:cacheprovider` — 21 passed.
- Full suite: `python -m pytest -q -p no:cacheprovider` — 1,083 passed, 2 skipped, 0 failed. Skips: Linux `/proc` resource metric unavailable on Windows; symlink creation privilege unavailable.
- `rtk ruff check` on all changed code/test files — passed.
- `git diff --check` — passed.
- `python docs/quality/validate_planning.py` — PASS (134 nodes, 264 edges, no cycles).

## Boundaries and remaining gates

- The pipeline composes an immutable per-cycle snapshot from its account inputs and
  current OMS/manual-approval reservations. Durable portfolio revisions remain the
  responsibility of the authoritative OMS/storage task.
- Missing fee evidence blocks new BUY entries. Test fixtures use an explicit 0.3%
  fee solely to exercise fee-aware sizing; it is not an Indodax fee claim.
- Snapshot producers must populate `cash_reservations` from authoritative OMS/ledger
  evidence. If the approved order's reservation is absent, the final authority gate
  leaves the cash requirement unchanged and may block execution.
- `max_risk_amount` is a supplied strategy risk input, not an approval of Production
  policy defaults. PM-08 and venue qualification remain separate.
- No live key, order, runtime database, host, or production authority was accessed.

## Review and coordinator state

- Self-review: focused/full-suite evidence above. Independent reviews 1–4 identified Important findings; each was addressed with regression coverage. Round 5 independently reviewed exact SHA `a87562a8ceb4a4f953520c65bae781ec4506a49f` and returned PASS with no remaining Critical/Important findings.
- Coordinator status: DONE; manifest/projections updated after the final PASS.
- No merge, push, deployment, or Production activation.
