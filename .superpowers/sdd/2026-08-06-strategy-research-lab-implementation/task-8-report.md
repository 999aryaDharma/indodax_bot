# Task 8 report — immutable Parquet snapshots and manifests

## Scope

Implemented the Task 8 research-only candle store:

- Explicit `CANDLE_SCHEMA_V1` uses UTC microsecond timestamps,
  `decimal128(38,12)` OHLC/quote volume, `decimal128(38,18)` base volume, and
  all required lineage and quality fields from `bronze_candles_v1`.
- `ParquetStore` accepts only validated Task 7 `CandleRecord` values, rejects
  duplicate canonical primary keys, sorts deterministically, partitions by
  interval/pair/UTC year/month, and writes ZSTD Parquet without pandas
  inference.
- Every write uses a unique sibling `.partial`, flushes and fsyncs it, validates
  its Arrow schema and row count after close, then atomically publishes with a
  no-replace filesystem link. Existing content-addressed files are only reused
  after their checksum matches; different bytes raise an immutable-content
  conflict instead of being overwritten.
- Partition facts include relative path, SHA-256, byte size, row count, and
  Arrow schema identity. The canonical sorted-key JSON manifest has no absolute
  path or clock fields. Its `dataset_snapshot_id` is
  `sha256(canonical manifest without dataset_snapshot_id)` and its manifest is
  published only after all partition writes succeed.

No network, credentials, database, local-time behavior, model code, or trade
endpoint was added. Runtime datasets remain caller-supplied paths outside Git.

## RED → GREEN

1. Initial behavioral tests were created before the data package.
   - RED command:
     `PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps python -m pytest tests/unit/lab/data/test_parquet_store.py tests/unit/lab/data/test_manifest.py -q`
   - Result: collection failed with `ModuleNotFoundError: No module named
     'indodax_lab.data'` for both test modules.
   - GREEN after minimal schema, checksum, manifest, and storage modules:
     `5 passed in 0.46s`.
2. The expanded suite added literal assertions for canonical sort order,
   documented Arrow numeric/timestamp types, no absolute/volatile manifest
   fields, one-character source change, immutable collision protection, and
   filesystem failures.
   - Final focused result: `8 passed in 0.43s`.

## Filesystem-failure coverage

- Replacing partition validation with an `OSError` leaves
  `WriteStatus.FAILED_RETRYABLE`, no snapshot manifest, and no `.partial`.
- Injecting `OSError` into the manifest atomic-publish link gives the same
  retryable result and no success manifest.
- Tampering with an already-published content-addressed partition makes retry
  raise `ImmutableContentConflictError`; its bytes remain untouched.

## Final verification

```bash
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m pytest tests/unit/lab/data/test_parquet_store.py \
  tests/unit/lab/data/test_manifest.py -q
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m pytest -q
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m ruff check src tests
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m compileall -q src/indodax_lab
git diff --check
```

Results:

- Focused Task 8 tests: `8 passed in 0.43s`.
- Full non-DL offline suite: `95 passed, 1 warning in 1.88s`.
- Ruff: `All checks passed!`.
- `compileall` and `git diff --check`: exit 0.
- The sole warning is the existing `pandas-ta`/pandas 3.0 `Pandas4Warning`.

## Files and self-review

- `src/indodax_lab/data/checksums.py`: streaming SHA-256 helpers.
- `src/indodax_lab/data/manifest.py`: canonical JSON, snapshot derivation, and
  manifest validation.
- `src/indodax_lab/data/parquet_store.py`: explicit schema, deterministic
  partitions, atomic immutable publication, and retryable outcomes.
- `tests/unit/lab/data/test_manifest.py` and `test_parquet_store.py`: offline
  temp-path behavioral tests.

Reviewed the complete Task 8 diff. All manifest paths are relative; manifests
contain no `created_at` or absolute root; source changes affect Parquet bytes,
partition checksum, and snapshot ID. Atomic publication deliberately uses
`link` rather than `os.replace`: it provides atomic no-clobber publication, so
concurrent/retry writers cannot silently replace different content.

## Concern

Directory fsync is performed after publishing a Parquet partition. Manifest
publication does not perform a post-publication directory fsync, because an
error after an immutable manifest has become visible must never be reported as
`FAILED_RETRYABLE` with a success manifest present. The manifest file itself is
flushed and fsynced before its atomic no-replace publish.

## Fix round 1 — cleanup, namespace durability, and validation classification

Commit: recorded with this Task 8 fix.

### RED → GREEN evidence

1. **Partial cleanup after visible partition**
   - RED: an injected partial-removal failure failed because the store had no
     `_remove_entry` durability boundary; its previous best-effort cleanup could
     return success after leaving a `.partial` behind.
   - GREEN: every successful partial removal unlinks then fsyncs its directory.
     If removal fails after a newly published entry, the store removes and fsyncs
     that final entry before returning `FAILED_RETRYABLE`. If rollback cannot
     establish the namespace state, it raises `IndeterminatePublicationError`
     rather than reporting success.
2. **Namespace fsync for new and idempotent writes**
   - RED: the injected fsync recorder saw no calls during an idempotent retry;
     the original writer only synced a newly published partition and never the
     manifest directory.
   - GREEN: missing directory chains are synced from each parent before use;
     partition and manifest directories are synced after new publication,
     same-content reuse, removal, and rollback. The test records both a new
     write's parent-chain calls and retry's partition/manifest namespace calls.
3. **Corrupt storage validation**
   - RED: injected `pyarrow.ArrowInvalid` escaped the write call; corrupt
     existing manifest bytes raised an unclassified immutable-content error.
   - GREEN: unreadable/incorrect Parquet, malformed manifest JSON, and manifest
     identity validation failures become `StorageValidationError` and return
     `FAILED_RETRYABLE` without publishing a new success manifest. Different
     valid content at an occupied content-addressed destination remains the
     explicit `ImmutableContentConflictError` path.

### Focused verification

```bash
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m pytest tests/unit/lab/data/test_parquet_store.py \
  tests/unit/lab/data/test_manifest.py -q
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m ruff check src/indodax_lab/data tests/unit/lab/data
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps \
  python -m compileall -q src/indodax_lab/data
git diff --check
```

Result: `13 passed in 0.55s`; Ruff reported `All checks passed!`; compile and
diff check exited 0. Full non-DL suite: `100 passed, 1 warning in 2.15s`; the
sole warning remains the existing `pandas-ta`/pandas 3.0 `Pandas4Warning`.

### Deferred minor

`build_dataset_manifest` still sorts only by relative `path` and does not reject
duplicate paths. This is deferred as directed: the current caller emits one
content-addressed audit entry per partition, while a broader duplicate-path
contract is outside this repair round.
