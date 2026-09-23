# API-00 Handoff

## Implementation

- Sprint: API-00
- Source commit: `3bb7e0a89fb268c06de279f140e9004455a526b1` (API-00 code unchanged from `438edbf`; reviewed with UI-00 together)
- Scope: shared envelope, closed response-status vocabulary, error/provenance contracts, finite Decimal serialization in both data and error details, and capability vocabulary.
- Production API routes, auth provider, database changes, exchange access, and host changes are not part of this sprint.

## Verification

- `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/api/test_common_contracts.py -q -p no:cacheprovider` — PASS, 3 tests.
- `rtk ruff check src/indodax_lab/api tests/unit/lab/api/test_common_contracts.py` — PASS.
- `python docs/quality/validate_planning.py --refresh --self-test` — PASS, 126 nodes, 226 edges, 0 cycles; seven invalid mutations rejected.
- Independent review: PASS on exact source SHA `3bb7e0a89fb268c06de279f140e9004455a526b1`, no Critical/Important findings.

## Gates

- Production Main is live; API-00 itself only defines read-only control-plane contracts and grants no trading-write capability.
- ASUS is the selected Production Main host and remains the Research Runtime host under ADR-009; this sprint did not deploy or modify either runtime.
- No live credentials, exchange writes, or Docker deployment were used.
