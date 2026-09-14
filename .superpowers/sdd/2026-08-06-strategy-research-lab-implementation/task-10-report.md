# Task 10 report: data sentry and snapshot quality gate

## Scope delivered

- Added a deterministic candle quality validator with stable `QualityFinding` values.
- Added a read-only snapshot sentry that checks manifest identity, partition checksums,
  canonical candle invariants, closed/available data, coverage gaps, and staleness.
- Added immutable quality/quarantine decision records. Bronze Parquet and raw wire are never
  modified by validation; `FAIL` returns `QUARANTINED` and writes under `quarantine/`.
- Added a structured CLI: `0=PASS`, `2=WARN`, `3=FAIL`, `4=invalid invocation`.

## RED to GREEN evidence

1. Added the required invariant, staleness, checksum, immutability, and CLI tests before the
   new modules existed.
2. RED command:

   ```text
   PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
     python -m pytest tests/unit/lab/data/test_quality.py \
     tests/integration/lab/test_snapshot_validation.py -q
   ```

   Result: collection failed as expected with `ModuleNotFoundError` for
   `indodax_lab.data.quality` and `indodax_lab.cli.validate_snapshot`.
3. Implemented the smallest validator/sentry/CLI path, then added the explicit upstream-WARN
   approval behavior and a quarantine namespace assertion through another RED-to-GREEN cycle.
4. GREEN focused result: `14 passed in 0.48s`.

## Verification

| Command | Result |
| --- | --- |
| Focused quality and snapshot tests | `14 passed` |
| `python -m pytest tests/unit/lab tests/integration/lab -q` | `64 passed` |
| `python -m pytest -q` | `137 passed, 1 warning` |
| Ruff on Task 10 modules/tests | `All checks passed!` |
| `python -m compileall -q` on Task 10 modules | exit 0 |
| `git diff --check` | exit 0 |
| Direct offline CLI exercise | `pass_exit=0`, `warn_exit=2`, `fail_exit=3`, `invalid_exit=4` |

The one full-suite warning is from the installed `pandas_ta` dependency about a deprecated
Pandas option; no Task 10 test warnings were emitted.

## Quarantine and immutability check

The checksum-mismatch integration test changes an already-published bronze byte, then validates
it. The sentry reports only `PARTITION_CHECKSUM_MISMATCH`, returns `QUARANTINED`, publishes an
immutable quarantine record, and asserts both the tampered bronze byte and the original raw-wire
body remain unchanged. It does not repair, delete, or overwrite either evidence source.

## Self-review and concerns

- Reports are canonical JSON-ready and contain no runtime clock or local-path value. Staleness is
  controlled solely by the injected `as_of` timestamp.
- All findings are sorted and contain a literal code, severity, pair, UTC range, row count, and
  string details; corrupt snapshots return a structured `SNAPSHOT_INVALID` report rather than a
  traceback-only CLI result.
- `WARN` is deliberately limited to explicit upstream quality warnings. Hard dataset-contract
  failures remain `FAIL`; no silver writer is introduced in this task, and the sentry exposes
  `eligible_for_silver` only for PASS or explicitly-approved WARN.

## Fix round 1/5

### Blocking findings resolved

- Source `quality_status` is fail-closed: only `PASS` passes, `WARN` remains an advisory finding,
  and `FAIL`, `QUARANTINED`, missing, and unknown values emit deterministic FAIL findings.
- Gap findings now use clipped end-exclusive ranges and carry the exact missing-bar count; ranges
  are coalesced deterministically and an observed bar beyond the requested window is ignored for
  coverage purposes.
- The sentry normalizes snapshot-content `ValueError` into `SNAPSHOT_CONTENT_INVALID`. The CLI
  validates arguments and snapshot-id safety before validation, preserving exit 4 strictly for
  invalid invocation and exit 3 for corrupt content.
- Immutable quality-record conflicts and indeterminate publication outcomes now produce
  `QUALITY_RECORD_CONFLICT` and `QUALITY_RECORD_INDETERMINATE`, respectively, with no claimed
  durable record.
- Snapshot IDs must be a safe single path segment before any snapshot or decision path is built;
  all derived paths also resolve and prove containment below `data_root`.

### Fix-round evidence

| Command | Result |
| --- | --- |
| Focused Task 10 suite | `23 passed` |
| Relevant Task 8/9 manifest, publication, and backfill tests | `36 passed` |
| Full non-DL suite | `146 passed, 1 dependency warning` |
| Ruff, compile, and diff check | clean |

The explicit approved/unapproved WARN CLI regression remains deferred as requested. The existing
unit-level approval policy and direct CLI exit-2 evidence remain unchanged; no further loop was
opened solely for that coverage.

## Fix round 2/5

### Blocking findings resolved

- Added `InvalidValidationWindowError` at the quality/sentry boundary. A valid snapshot with an
  end-exclusive window that is too short, misaligned, or otherwise incompatible with its stored
  interval now returns `INVALID_INVOCATION` and CLI exit 4. Stored unsupported intervals still
  normalize to `SNAPSHOT_CONTENT_INVALID` and exit 3.
- Wrapped root, manifest, partition, and decision-record path resolution. Symlink loops and
  relevant resolution failures produce structured `SNAPSHOT_PATH_UNRESOLVABLE` failures and no
  decision record claim; path containment is still checked after resolution.

### Fix-round evidence

| Command | Result |
| --- | --- |
| Focused Task 10 suite | `27 passed` |
| Relevant Task 8/9 manifest, publication, and backfill tests | `36 passed` |
| Ruff and compile | clean |
| Diff check | clean |

RED cases initially returned exit 3 for 30-minute/misaligned 1h windows and raised a symlink-loop
traceback. The final focused run returned structured exit 4 and exit 3 outcomes respectively.
