# API-00 Handoff

## Implementation

- Sprint: API-00
- Commit: `438edbfda7b590167c355466362410c8a6bc868d`
- Scope: shared envelope, closed response-status vocabulary, error/provenance contracts, finite Decimal serialization in both data and error details, and capability vocabulary.
- Production API routes, auth provider, database changes, exchange access, and host changes are not part of this sprint.

## Verification

- `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/api/test_common_contracts.py -q -p no:cacheprovider` — PASS, 3 tests, including nested non-finite Decimal rejection and unsupported status rejection.
- `rtk ruff check src/indodax_lab/api tests/unit/lab/api/test_common_contracts.py` — PASS.
- `python docs/quality/validate_planning.py --refresh --self-test` — PASS, 126 nodes, 226 edges, 0 cycles; seven invalid mutations rejected.
- Independent review: FAIL on prior commit `7315cc1`; fixes for all Important findings are in `438edbf` and re-review is pending.

## Gates

- Current project scope remains paper/shadow only.
- No Production host is selected or deployed. ASUS remains Research Runtime only.
- No live credentials, exchange writes, or Docker deployment were used.
