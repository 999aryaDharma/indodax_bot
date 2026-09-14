# Task 13 Report: Time and Information-Driven Bars

## Status

Implemented deterministic `silver_bars_v1` time bars and CUSUM/range/base-volume/dollar
challengers from offline public `TradeEvent` inputs. No network, credential, realtime, account,
or trading endpoint is used.

## Delivered

- Strict, content-addressed YAML policies in `configs/bars/time_v1.yaml` and
  `configs/bars/event_v1.yaml`.
- Exact `Decimal` OHLC, base/quote volume, trade count, known-side volume, stable event order,
  end-exclusive time buckets, event lineage, and availability gating.
- Explicit empty/incomplete gap records; no synthetic candles and no resampling across missing
  source bars or source snapshots.
- Explicit official-versus-derived delta reports and config-only source selection without blending.
- Deterministic CUSUM positive/negative resets and range/base-volume/dollar boundaries.
- Fixed positive thresholds or point-in-time fit artifacts whose `train_end` and `available_at`
  cannot exceed build as-of.
- Unclosed final event buckets excluded from final bars and retained as auditable remainders.
- Offline CLI with non-writing dry-run, replay-stable output IDs, and immutable data/manifest
  publication.

## TDD Evidence

RED was observed for each production surface before implementation:

1. `test_time_bars.py` failed collection with `ModuleNotFoundError: indodax_lab.data.bars`.
2. `test_event_bars.py` failed collection with `ModuleNotFoundError: indodax_lab.data.event_bars`.
3. CLI tests failed collection with `ModuleNotFoundError: indodax_lab.cli.build_bars`.
4. Provider-lineage test failed because the first implementation emitted `public_trades` rather
   than the actual `indodax_public_stream` source.

Each RED was followed by a minimal implementation and a focused GREEN run.

## Verification

- Focused: `28 passed` for `test_time_bars.py` and `test_event_bars.py`.
- Full non-DL unit/integration/regression: `239 passed`.
- Ruff: clean for Task 13 source and tests.
- Compile: `python -m compileall -q src tests` completed successfully.
- Config validation: both shipped YAML policies load with deterministic SHA-256 source IDs.

## Notes

The full suite emits one existing `pandas_ta` warning about a deprecated Pandas copy-on-write
option; it is unrelated to Task 13. Time resampling intentionally requires target-aligned build
windows and complete contiguous lower-interval buckets, failing closed otherwise.

## Fix Round 1

Review hardening added the following contracts:

- A fitted threshold must have `train_end < first_event_ts`, must be available no later than the
  first input's `available_at`, and must also be available by build as-of. Artifact ID/version and
  availability propagate into result, final bars, CLI payload, and immutable publication.
- Bar IDs now hash threshold value/source, artifact version, lag, provider, boundary direction,
  source snapshot/session, and policy identity in addition to bar boundaries and event lineage.
- Event builds require an exact per-event continuity map. Session changes and declared gaps reset
  CUSUM and other thresholds; unfinished prior segments are quarantined with an audit reason.
- Reconciliation uses the union of keys, reports missing bars, applies explicit Decimal tolerances,
  validates pair/provider/snapshot lineage, and blocks incomplete official selection when required.
- Resampling requires one pair, provider, snapshot, and session across every lower bar.
- Bar-layer dedupe configuration and API behavior were removed; every duplicate event ID fails.
- Fixed and fitted YAML thresholds accept exact strings/integers and reject bool/binary float.

Fix-round RED checks observed missing continuity/reconciliation imports, historical artifact tests
accepting post-event fits, material identity collisions, cross-gap CUSUM closure, intersect-only
reconciliation, mixed resample lineage, and absent reconciliation audit fields. Each was followed
by a focused GREEN run.

Fix-round verification:

- Task 13 plus Task 11 stream/recovery: `81 passed`.
- Full non-DL unit/integration/regression before final gate: `258 passed`.

## Fix Round 2

- Fitted threshold lineage now includes canonical UTC `train_end` and `available_at` on the build
  result, every final bar, serialized output, CLI threshold audit, and immutable manifest.
- Fixed thresholds carry explicit `FIXED` provenance with null artifact ID/version/cutoff fields;
  fitted thresholds carry explicit `FITTED` provenance and all artifact fields.
- Temporal threshold lineage is part of `bar_id`, so changing a cutoff or publication timestamp
  changes immutable identity even when events and the threshold value are unchanged.
- Reconciliation now compares `available_at`, `interval`, and `bar_type` alongside its existing
  key, timestamp, OHLC, volume, side-volume, and count checks.
- Any CLI official input requires independently declared `--official-provider` and
  `--official-snapshot-id`; every official row is validated against those anchors before source
  selection, and the anchors are retained in published output.

Fix-round RED checks observed missing result/bar cutoff attributes, unchanged IDs under temporal
artifact mutations, absent published/manifest cutoff lineage, implicit fixed provenance,
unreported closure-semantic mismatches, and acceptance of unanchored official input.

Fix-round verification before the final gate: Task 13 plus Task 11 stream/recovery `84 passed`;
full non-DL unit/integration/regression `261 passed`.

## Fix Round 3

The CLI now validates the complete official bar file immediately after strict deserialization and
before interval grouping. Every row must match the requested pair, independently declared provider
and snapshot, `TIME` bar type, configured interval set, and final availability semantics. This
gate applies when either official or trade-derived rows are selected, so off-config rows cannot be
silently hidden by per-interval filtering.

RED reproduced publication success with a valid configured official row plus either (a) an
off-config row from the wrong provider or (b) an off-config row with otherwise valid anchors.
Both cases are now GREEN and fail before the output root is created.

Fix-round verification before the final gate: Task 13 plus Task 11 stream/recovery `86 passed`;
full non-DL unit/integration/regression `263 passed`.
