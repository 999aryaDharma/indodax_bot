# API-03 Handoff

## Implementation

- Sprint: API-03 — fail-closed Production read capability and audit context.
- Source commit: `fc40bca766b918191f3748241bb84edd544a04dd`.
- Scope: explicit principal and actor-class contract, request-ID middleware, audited `production.read` policy, and guarded Production service resolution.
- No authentication provider, Production writer, credential access, host change, or runtime deployment was added.

## Verification

- RED: API-03 tests failed collection because `indodax_lab.api.auth` did not exist yet.
- `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/api/test_capability_policy.py tests/integration/lab/api/test_api_audit.py tests/unit/lab/api/test_common_contracts.py -q -p no:cacheprovider` — PASS, 11 tests.
- `C:\Users\User\miniconda3\envs\ML\python.exe -m ruff check src/indodax_lab/api/auth.py src/indodax_lab/api/audit.py src/indodax_lab/api/dependencies.py tests/unit/lab/api/test_capability_policy.py tests/integration/lab/api/test_api_audit.py` — PASS.
- Trailing-whitespace check across the five implementation/test files and this handoff — PASS.
- A concurrent full-suite run before API-01 finished reported 1026 passed, 2 skipped and 2 API-01 failures; API-01 corrected the model assertions. The current combined scoped API suite is recorded below and passed.
- `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/api/test_production_read_models.py tests/unit/lab/api/test_capability_policy.py tests/integration/lab/api/test_api_audit.py tests/unit/lab/api/test_common_contracts.py -q -p no:cacheprovider` — PASS, 19 tests.
- `C:\Users\User\miniconda3\envs\ML\python.exe -m ruff check src/indodax_lab/api tests/unit/lab/api tests/integration/lab/api` — PASS.

## Acceptance Evidence

- Missing, anonymous, Research, and capability-less identities are denied before the Production service resolver runs.
- `research.read` does not satisfy `production.read`; a Research-class principal is denied even if it is incorrectly supplied `production.read`.
- Explicit operator `production.read` is allowed.
- Allow/deny records contain request ID, actor class, capability, resource, decision, reason, policy revision, and UTC timestamp. Principal subject and authorization headers are excluded.
- Missing auth provider remains intentionally unavailable: only trusted middleware may set `request.state.principal`; development/test identities use explicit dependency injection.

## Review and Gates

- Independent review: PASS on exact committed SHA `fc40bca766b918191f3748241bb84edd544a04dd`, no Critical/Important findings.
- Source SHA: `fc40bca766b918191f3748241bb84edd544a04dd`.
- Runtime/deployment gates: unchanged; no host was inspected or modified.
