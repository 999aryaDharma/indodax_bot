# AGENT-01 handoff

Status: REVIEW

## Identity
- Sprint ID: AGENT-01 — Governed research curator
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/agent-01-governed-research-curator`
- Base SHA: `2affed5`
- Code target: `feat(agent-01): governed research curator`
- Evidence SHA relation: `54a984a`

## Files and contracts
- Actual files:
  - `src/indodax_lab/orchestration/curator_policy.py` (ChangeRequestProposal, ChangeRequestRecord, CuratorEngine, HardFailTuningForbiddenError, ProposalStatus, SelfApprovalForbiddenError, sanitize_curator_input)
  - `src/indodax_lab/orchestration/__init__.py` (Package exports — AGENT-01 symbols added)
  - `tests/unit/lab/orchestration/test_curator_policy.py` (AC0..AC3 unit tests and edge cases)
  - `docs/agent/curator-prompts.md` (Curator prompt and hypothesis guidelines)
- Contract:
  - `report + hypothesis -> change request + bounded candidate branch; no automatic merge or evaluator edits.`
  - Research agent proposals: `CuratorEngine.submit_proposal()` accepts structured `ChangeRequestProposal` with hypothesis, budget, and dedicated branch (AGENT-01-AC0).
  - HARD_FAIL tuning guard: Tuning/retry proposals following a `HARD_FAIL` evaluation outcome are strictly rejected fail-closed with `HardFailTuningForbiddenError` (AGENT-01-AC1).
  - Prompt injection neutralization: `sanitize_curator_input()` preserves prompt injection payloads strictly as inert text data without executing instructions (AGENT-01-AC2).
  - Separation of duties: `approve_proposal()` forbids self-approval (`approver_id == proposer_id`), raising `SelfApprovalForbiddenError` (AGENT-01-AC3).
- Migration and compatibility:
  - Additive module in `src/indodax_lab/orchestration/`; no existing interfaces modified.
  - Dependencies: REPORT-01 (REVIEW), JOB-03 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| AGENT-01-AC0 (RED) | `test_agent_01_valid_contract` | `python -m pytest tests/unit/lab/orchestration/test_curator_policy.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.orchestration.curator_policy') | `working tree` |
| AGENT-01-AC0 (GREEN) | `test_agent_01_valid_contract` | `python -m pytest tests/unit/lab/orchestration/test_curator_policy.py::test_agent_01_valid_contract` | Exit 0 (Passed, valid proposal creates PENDING change request with branch and budget) | `54a984a` |
| AGENT-01-AC1 (RED) | `test_agent_01_contract_1` | `python -m pytest tests/unit/lab/orchestration/test_curator_policy.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| AGENT-01-AC1 (GREEN) | `test_agent_01_contract_1` | `python -m pytest tests/unit/lab/orchestration/test_curator_policy.py::test_agent_01_contract_1` | Exit 0 (Passed, tuning following HARD_FAIL raises HardFailTuningForbiddenError) | `54a984a` |
| AGENT-01-AC2 (RED) | `test_agent_01_contract_2` | `python -m pytest tests/unit/lab/orchestration/test_curator_policy.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| AGENT-01-AC2 (GREEN) | `test_agent_01_contract_2` | `python -m pytest tests/unit/lab/orchestration/test_curator_policy.py::test_agent_01_contract_2` | Exit 0 (Passed, prompt injection payload treated strictly as passive text data) | `54a984a` |
| AGENT-01-AC3 (RED) | `test_agent_01_contract_3` | `python -m pytest tests/unit/lab/orchestration/test_curator_policy.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| AGENT-01-AC3 (GREEN) | `test_agent_01_contract_3` | `python -m pytest tests/unit/lab/orchestration/test_curator_policy.py::test_agent_01_contract_3` | Exit 0 (Passed, self-approval raises SelfApprovalForbiddenError, independent approval succeeds) | `54a984a` |

All 4 tests in `tests/unit/lab/orchestration/test_curator_policy.py` passed (1.05s).
Full lab suite verification: 195 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, reporting, and paper.

## Review
- Spec verdict: PASS (meets all functional requirements of AGENT-01 and docs/specs/19-agent-research-governance.md).
- Quality verdict: PASS (HARD_FAIL tuning prevention, data sanitization, separation of duties enforcement, no real-money execution).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for AGENT-01.
- Next unlocked consumers: QA-02.
