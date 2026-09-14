# REL-01 handoff

Status: REVIEW

## Identity
- Sprint ID: REL-01 — Paper research release candidate
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/rel-01-paper-research-release-candidate`
- Base SHA: `adb9960`
- Code target: `feat(rel-01): paper research release candidate`
- Evidence SHA relation: `4558fbb`

## Files and contracts
- Actual files:
  - `src/indodax_lab/verification/release.py` (ExperimentalPromotionForbiddenError, RollbackIntegrityError, ReleaseCandidatePackage, ReleaseCandidateManager)
  - `src/indodax_lab/verification/__init__.py` (Package exports)
  - `tests/regression/test_release_candidate.py` (AC0..AC3 release candidate qualification tests)
  - `deploy/release-lab.sh` (Packaging and verification runbook script)
  - `docs/quality/release-evidence.md` (Release metadata, verification matrix, and rollback evidence)
- Contract:
  - `frozen SHA + tested artifacts + release checklist -> candidate tag and reviewable release record.`
  - Release candidate packaging: Bundles verified git SHA, core sprint verification manifest, rollback target, and decoupled champion forward status into an immutable package (REL-01-AC0).
  - Rollback integrity: Verification against target artifact checksums strictly proves safe rollback to previous compatible versions without corruption (REL-01-AC1).
  - Experimental isolation: Prevents silent promotion of experimental or extension candidates into release runtime without explicit owner approval (REL-01-AC2).
  - Forward gate transparency: Candidate software readiness is decoupled from champion forward longevity; candidates pending the 90-day / 100-trade gate are clearly presented as `PENDING_FORWARD_EVALUATION` (REL-01-AC3).
- Migration and compatibility:
  - Additive package `src/indodax_lab/verification/` and deploy runbook `deploy/release-lab.sh`; no breaking changes.
  - Dependencies: QA-02 (REVIEW), QA-03 (REVIEW), QA-01 (REVIEW), REPORT-02 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| REL-01-AC0 (RED) | `test_rel_01_valid_contract` | `python -m pytest tests/regression/test_release_candidate.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.verification') | `working tree` |
| REL-01-AC0 (GREEN) | `test_rel_01_valid_contract` | `python -m pytest tests/regression/test_release_candidate.py::test_rel_01_valid_contract` | Exit 0 (Passed, release candidate packaged cleanly with checksum manifest and rollback plan) | `4558fbb` |
| REL-01-AC1 (RED) | `test_rel_01_contract_1` | `python -m pytest tests/regression/test_release_candidate.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| REL-01-AC1 (GREEN) | `test_rel_01_contract_1` | `python -m pytest tests/regression/test_release_candidate.py::test_rel_01_contract_1` | Exit 0 (Passed, rollback verified against artifact checksums and fails closed on mismatch) | `4558fbb` |
| REL-01-AC2 (RED) | `test_rel_01_contract_2` | `python -m pytest tests/regression/test_release_candidate.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| REL-01-AC2 (GREEN) | `test_rel_01_contract_2` | `python -m pytest tests/regression/test_release_candidate.py::test_rel_01_contract_2` | Exit 0 (Passed, experimental/extension candidates barred from unapproved promotion) | `4558fbb` |
| REL-01-AC3 (RED) | `test_rel_01_contract_3` | `python -m pytest tests/regression/test_release_candidate.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| REL-01-AC3 (GREEN) | `test_rel_01_contract_3` | `python -m pytest tests/regression/test_release_candidate.py::test_rel_01_contract_3` | Exit 0 (Passed, unmet forward duration/trades clearly marked as pending champion qualification) | `4558fbb` |

All 4 tests in `tests/regression/test_release_candidate.py` passed (0.36s).
Full lab suite verification: 223 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, reporting, paper, security, capacity, and regression.

## Review
- Spec verdict: PASS (meets all requirements of REL-01 and docs/specs/20-testing-strategy.md).
- Quality verdict: PASS (clean packaging, proven checksum rollback, experimental isolation, decoupled forward status, fail-closed design).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for REL-01.
- Next unlocked consumers: Full research lab release qualification complete.
