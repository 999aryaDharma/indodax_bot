# Phase 0 verification evidence

Evidence was collected from Git SHA `785d7a4` before this checkpoint commit.

| Command | Exit code | Result |
| --- | ---: | --- |
| `PYTHONPATH=/tmp/indobot-task5-deps python -m pytest tests/regression/test_phase0_invariants.py -q` | 0 | 1 passed; validates the combined public, offline Phase 0 checkpoint. |
| `PYTHONPATH=/tmp/indobot-task5-deps python -m pytest -q` | 0 | 73 passed, 1 warning. |
| `PYTHONPATH=/tmp/indobot-task5-deps python -m ruff check src tests` | 0 | All checks passed. |

The test suite includes temporary-SQLite migration tests for paper-trade and
signal-observer schemas, including backup-first, rollback, idempotence, and
schema-rebuild cases. This evidence does not assert migration-on-copy beyond
those temporary-SQLite tests.

## Known limitations

`pandas-ta` emits one pandas 3.0 copy-on-write deprecation warning during the
suite. It originates in the third-party dependency; it was not suppressed and
no runtime dependency was changed for this checkpoint.
