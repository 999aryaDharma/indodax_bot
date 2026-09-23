# API-03 Handoff

## Implementation

- Sprint: API-03 — fail-closed Production read capability and audit context.
- Source commit: pending coordinator commit; this worker did not commit.
- Scope: explicit principal and actor-class contract, request-ID middleware, audited `production.read` policy, and guarded Production service resolution.
- No authentication provider, Production writer, credential access, host change, or runtime deployment was added.

## Verification

- RED: API-03 tests failed collection because `indodax_lab.api.auth` did not exist yet.
- `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/api/test_capability_policy.py tests/integration/lab/api/test_api_audit.py tests/unit/lab/api/test_common_contracts.py -q -p no:cacheprovider` — PASS, 11 tests.
- `C:\Users\User\miniconda3\envs\ML\python.exe -m ruff check src/indodax_lab/api/auth.py src/indodax_lab/api/audit.py src/indodax_lab/api/dependencies.py tests/unit/lab/api/test_capability_policy.py tests/integration/lab/api/test_api_audit.py` — PASS.
- Trailing-whitespace check across the five implementation/test files and this handoff — PASS.
- `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest -q -p no:cacheprovider` — 1026 passed, 2 skipped, 2 failed. Both failures are in concurrent API-01 read-model work: `tests/unit/lab/api/test_production_read_models.py::test_api_01_0_missing_authority_never_becomes_healthy_or_zero` and `::test_api_01_2_non_production_namespace_and_unverified_release_fail_closed`; both assert `.status` on nested `evidence` models. They are outside API-03 ownership.

## Acceptance Evidence

- Missing, anonymous, Research, and capability-less identities are denied before the Production service resolver runs.
- `research.read` does not satisfy `production.read`; a Research-class principal is denied even if it is incorrectly supplied `production.read`.
- Explicit operator `production.read` is allowed.
- Allow/deny records contain request ID, actor class, capability, resource, decision, reason, policy revision, and UTC timestamp. Principal subject and authorization headers are excluded.
- Missing auth provider remains intentionally unavailable: only trusted middleware may set `request.state.principal`; development/test identities use explicit dependency injection.

## Review and Gates

- Independent review: pending.
- Source SHA: pending coordinator commit and exact-SHA review.
- Runtime/deployment gates: unchanged; no host was inspected or modified.
