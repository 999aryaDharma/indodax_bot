# AGENT-01 handoff

Status: REVIEW

## Identity
- Sprint ID: AGENT-01 — Governed research curator
- Implementation owner (tunggal): OpenCode / opencode/muse-spark-1.3-contributor-free (fix cycle; independent dari Codex/Antigravity)
- Prior implementation: Antigravity (`54a984a`); this fix cycle owns only the delta below
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `fix/agent-01-remediation` (isolated worktree; base `feat/agent-01-governed-research-curator` @ `7447937`)
- Base SHA: `7447937`
- Code target: `fix(agent-01): HARD_FAIL lookup, budget/branch validators, idempotency`
- Evidence SHA relation: (fix commit SHA, recorded on commit)

## Files and contracts
- Actual files:
  - `src/indodax_lab/orchestration/curator_policy.py` (ChangeRequestProposal, ChangeRequestRecord, CuratorEngine, HardFailTuningForbiddenError, ProposalStatus, SelfApprovalForbiddenError, DuplicateProposalError, MAX_BUDGET_TRIALS, validate_budget_trials, validate_branch_name, sanitize_curator_input)
  - `src/indodax_lab/orchestration/__init__.py` (Package exports — AGENT-01 symbols added)
  - `tests/unit/lab/orchestration/test_curator_policy.py` (AC0..AC3 unit tests + remediation tests)
  - `docs/agent/curator-prompts.md` (Curator prompt and hypothesis guidelines)
- Contract:
  - `report + hypothesis -> change request + bounded candidate branch; no automatic merge or evaluator edits.`
  - Research agent proposals: `CuratorEngine.submit_proposal()` accepts structured `ChangeRequestProposal` with hypothesis, budget (1..30 trials, ADR-003), and namespaced candidate branch (`feat|fix|exp|chore/slug`) (AGENT-01-AC0).
  - HARD_FAIL tuning guard: authoritative `outcome_lookup(candidate_id)` overrides self-reported `prior_outcome`; HARD_FAIL strictly rejected fail-closed with `HardFailTuningForbiddenError` (AGENT-01-AC1).
  - Idempotency: identical `proposal_id` resubmission returns stored record; conflicting reuse raises `DuplicateProposalError`.
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

All 7 tests in `tests/unit/lab/orchestration/test_curator_policy.py` passed (4 AC + 3 remediation).
Affected gate: `tests/unit/lab/orchestration` + `tests/unit/lab/evaluation` — 33 passed.

## Fix cycle delta (this commit)
| Finding | Test (RED→GREEN) | Command | Exit/result |
|---|---|---|---|
| HARD_FAIL self-report spoofable | `test_agent_01_hard_fail_lookup_overrides_claimed_outcome` | `python -m pytest tests/unit/lab/orchestration/test_curator_policy.py` | RED (collection error: no `DuplicateProposalError`/lookup) → GREEN (7 passed) |
| Unbounded budget / unvalidated branch | `test_agent_01_budget_and_branch_validators` | same | RED → GREEN |
| Silent proposal_id overwrite | `test_agent_01_idempotent_resubmit` | same | RED → GREEN |
| Owner ganda di handoff | — | handoff Identity names single owner | fixed |

## Review
- Spec verdict: PASS (meets all functional requirements of AGENT-01 and docs/specs/19-agent-research-governance.md).
- Quality verdict: PASS (HARD_FAIL tuning prevention, data sanitization, separation of duties enforcement, no real-money execution).
- Findings: None.
- Self-review: completed by fix owner (OpenCode); diff scoped to `curator_policy.py`, `orchestration/__init__.py`, `test_curator_policy.py`, `AGENT-01-HANDOFF.md`.
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for AGENT-01.
- Next unlocked consumers: QA-02.
