# F01-01 handoff

Status: REVIEW

## Identity
- Sprint ID: F01-01 — Foundation provenance gate
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/f01-01-foundation-provenance-gate`
- Base SHA: `1cc7a9c`
- Code target: `feat(f01-01): foundation provenance gate`
- Evidence SHA relation: `68c35c1`

## Files and contracts
- Planned files:
  - `src/indodax_lab/models/foundation/provenance.py` (FoundationModelProvenance, FoundationArtifactStatus, FoundationProvenanceGate, FakeFoundationModelAdapter, ChecksumVerificationFailedError, IncompatibleLicenseError, UnknownCutoffBlockedError)
  - `src/indodax_lab/models/foundation/__init__.py` (Package exports)
  - `tests/unit/lab/models/test_f01_01.py` (AC0..AC3 test cases)
- Contract:
  - `revision checksum license release and cutoff -> verified external artifact or EXPLORATORY`
  - Provenance verification: Asserts revision, license, SHA-256 byte checksum, release date, and cutoff before model artifact is accepted into research runtime (F01-01-AC0).
  - Cutoff enforcement: Models with unknown or lookahead training cutoffs are restricted strictly to `EXPLORATORY` status; promotion to release candidate or benchmark is blocked fail-closed (F01-01-AC1).
  - Unverified byte rejection: SHA-256 mismatch halts loading fail-closed (`ChecksumVerificationFailedError`) preventing malicious or corrupted weight execution (F01-01-AC2).
  - Offline CI fake adapter: Synthetic deterministic adapter satisfies provenance contracts in CI without external downloads or network access (F01-01-AC3).
- Migration and compatibility:
  - Additive package `src/indodax_lab/models/foundation/` with zero breaking changes to existing models.
  - Dependencies: DL-01 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| F01-01-AC0 (RED) | `test_f01_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_f01_01.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.foundation') | `working tree` |
| F01-01-AC0 (GREEN) | `test_f01_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_f01_01.py::test_f01_01_valid_contract` | Exit 0 (Passed, complete provenance verified with SHA-256, approved license, and known cutoff) | `68c35c1` |
| F01-01-AC1 (RED) | `test_f01_01_contract_1` | `python -m pytest tests/unit/lab/models/test_f01_01.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| F01-01-AC1 (GREEN) | `test_f01_01_contract_1` | `python -m pytest tests/unit/lab/models/test_f01_01.py::test_f01_01_contract_1` | Exit 0 (Passed, unknown cutoff restricted to EXPLORATORY and promotion blocked fail-closed) | `68c35c1` |
| F01-01-AC2 (RED) | `test_f01_01_contract_2` | `python -m pytest tests/unit/lab/models/test_f01_01.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| F01-01-AC2 (GREEN) | `test_f01_01_contract_2` | `python -m pytest tests/unit/lab/models/test_f01_01.py::test_f01_01_contract_2` | Exit 0 (Passed, checksum mismatch rejected fail-closed and unverified bytes barred from loading) | `68c35c1` |
| F01-01-AC3 (RED) | `test_f01_01_contract_3` | `python -m pytest tests/unit/lab/models/test_f01_01.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| F01-01-AC3 (GREEN) | `test_f01_01_contract_3` | `python -m pytest tests/unit/lab/models/test_f01_01.py::test_f01_01_contract_3` | Exit 0 (Passed, offline fake adapter verified in CI without remote downloads) | `68c35c1` |

All 4 tests in `tests/unit/lab/models/test_f01_01.py` passed (2.09s).
Full lab suite verification: 243 passed across all domains.

## Review
- Spec verdict: PASS (meets all requirements of F01-01 and docs/specs/15-deep-learning-and-provenance.md).
- Quality verdict: PASS (license whitelist, SHA-256 byte verification, cutoff protection against lookahead, offline fake adapter).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for F01-01.
- Next unlocked consumers: F01-02.

## Fix cycle — empty revision fail-closed (2026-09-26)
- Finding F01-01: `revision=""` / blank constructed successfully and `verify_provenance` returned `VERIFIED` (spec `15-deep-learning-and-provenance.md`: "Missing revision/hash/license rejects load").
- Fix owner: opencode/muse-spark-1.3-contributor-free | Branch: `fix/f01-01-revision-empty` | Base SHA: `fa6d4b5` | Worktree: `.worktrees/fix-f01-01` (main checkout untouched).
- Files:
  - `src/indodax_lab/models/foundation/provenance.py` — `validate_revision` field_validator (reject empty/blank with `MISSING_REVISION`) + defensive fail-closed check at top of `verify_provenance`.
  - `tests/unit/lab/models/test_f01_01.py` — regression `test_f01_01_empty_revision_rejected_fail_closed` ("" and "   " must raise `ValueError` match `REVISION` at construct or verify).
- TDD RED→GREEN:
  - RED: `python -m pytest tests/unit/lab/models/test_f01_01.py::test_f01_01_empty_revision_rejected_fail_closed -q` → Exit 1 (`Failed: DID NOT RAISE ValueError`); plus direct repro `verify_provenance(revision="")` → `STATUS= verified`.
  - GREEN: `python -m pytest tests/unit/lab/models/test_f01_01.py -q` → Exit 0, 5 passed.
- Scope: L01-01 untouched. No push. Lint: ruff unavailable in host (capability gap, `python -m ruff` → No module named ruff); diff check clean via `git diff --stat`.
