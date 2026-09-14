# Task 12 report — point-in-time dynamic universe

## Scope

Implemented the Task 12 research-only point-in-time universe path:

- `configs/universe/default_v1.yaml` explicitly versions the rank boundary,
  CoinGecko source/TTL, `LIQUIDITY_ONLY` fallback, and separate big/small listing,
  zero-volume, spread, depth-band, and order-relative depth thresholds.
- Frozen strict contracts reject unknown config fields, binary-float monetary inputs,
  invalid thresholds, non-UTC timestamps, unsafe identities, and malformed pair/asset IDs.
- `classify_pair` is pure and deterministic. It applies the cap tier's liquidity gates,
  emits stable reason codes, rejects input unavailable after the UTC daily cutoff, and
  strips late, future, incomplete, wrong-source, or stale cap facts before falling back.
- The injected CoinGecko adapter persists exact raw bytes plus safe metadata containing
  source timestamps, `available_at`, TTL, expiry, status, and content identities. HTTP
  rate/quota/provider failures and malformed/absent rows become explicit unavailable
  records with null cap values, never numeric zero.
- Daily decisions retain every supplied historical pair, including delisted and newly
  listed pairs. Canonically sorted JSONL and its manifest are content addressed by the
  as-of date, exact policy source, source/input IDs, and complete decisions, then durably
  published through the shared no-clobber publication primitives.
- The CLI consumes explicit offline metrics. Dry-run computes the same deterministic
  snapshot ID but never creates the data root or constructs any network dependency.

No account/trade endpoint, credential, secret, wall clock, local timezone, model code,
or live-bot behavior was added.

## RED → GREEN evidence

Tests were created before the universe package, policy config, snapshot builder, adapter,
or CLI existed.

```bash
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m pytest tests/unit/lab/universe \
  tests/integration/lab/test_universe_snapshot.py -q
```

RED: collection failed with `ModuleNotFoundError` for `indodax_lab.universe` and
`indodax_lab.cli.build_universe`. GREEN after the minimal implementation: `22 passed in
0.41s` on the final fresh rerun.

The focused suite covers exact threshold boundaries and reason codes, big/small rank
selection, listing age, inactive/untradable/quality failures, missing/stale/future/late
cap fallback, delisted retention, newly listed audit rows, strict YAML validation,
typed fake-provider parsing, explicit HTTP unavailability, raw metadata lineage,
deterministic reruns, raw-input ID changes, safe paths, and offline dry-run behavior.

## Final verification

```bash
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m pytest -q
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m ruff check src tests
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m compileall -q src/indodax_lab
git diff --check
```

Results: full non-DL suite `206 passed, 1 warning in 2.09s`; Ruff reported `All
checks passed!`; compileall and diff check exited 0. The warning is the pre-existing
`pandas-ta`/Pandas 4 compatibility warning recorded by earlier tasks.

## Self-review and concern

Mutation review covered wrong rank side, weakened threshold comparison, missing gate,
current-cap backfill, ignored availability/TTL, zero-filled provider failure, dropped
historical row, nondeterministic ordering, omitted raw/policy identity, unsafe path, and
dry-run publication; each is caught by at least one behavioral test.

No blocking concern. Historical market-cap coverage remains provider-dependent by
design: missing or unauditable coverage is preserved as `LIQUIDITY_ONLY`, never inferred
from today's cap.

## Fix round 1/5 — current-only provider, canonical TTL, and response identity

### Important finding 1: honest CoinGecko capability

CoinGecko `/coins/markets` is now modeled explicitly as `CURRENT_ONLY`. The adapter no
longer sends a nonexistent `date` query parameter. A requested snapshot date different
from the injected UTC receipt date makes no HTTP call and durably records a deterministic
`HISTORICAL_UNSUPPORTED` audit artifact with null cap/rank values. Current-date responses
still preserve exact raw bytes and can flow into the existing pure `UniverseMetrics`
boundary; audited point-in-time sources can populate that same boundary independently.

RED: the historical regression showed one `/coins/markets` call containing
`date=2020-01-01`, and the current request test found the invented `date` parameter.
GREEN: the two targeted current/current-only cases passed (`2 passed in 0.29s`).

### Important finding 2: one availability-based TTL contract

`UniverseMetrics` now carries audited `cap_expires_at`. Both adapter and classifier use
exactly `cap_available_at + policy TTL`; classification validates that derivation and
treats expiry as inclusive (`cutoff == expires_at` is valid, one microsecond later is
stale). Both boundaries reject `cap_source_ts > cap_available_at`, and source/availability
after the snapshot cutoff remain unusable. Delayed but causally valid responses no longer
become stale merely because their provider source timestamp is old.

RED: `cap_expires_at` was rejected as an unknown contract field, a delayed response was
classified using source-time expiry, and an observation one microsecond after receipt was
accepted. GREEN: all three exact TTL/causality cases passed (`3 passed in 0.30s`).

### Important finding 3: complete immutable metadata identity

The response ID is now SHA-256 over every persisted metadata field except the derived ID
itself: schema/provider, explicit `coingecko-current-v1` adapter policy, actual request
identity and params, snapshot date, status, all
persisted safe headers, body checksum/size, source timestamps, availability, TTL, and
expiry. The raw/metadata directory uses that complete identity. A regression independently
recomputes the ID from persisted canonical metadata, while another varies only `ETag`.

RED: the second `ETag` response reused the first response path and raised
`ImmutableContentConflictError`. GREEN: the header-only variation produced distinct IDs,
paths, and exact immutable metadata (`1 passed in 0.30s`).
The policy-version field received its own RED (`KeyError` in current and historical audit
tests) and GREEN (`2 passed in 0.29s`) cycle.

### Fix verification

```bash
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m pytest tests/unit/lab/universe \
  tests/integration/lab/test_universe_snapshot.py \
  tests/unit/lab/data/test_parquet_store.py \
  tests/unit/lab/data/test_indodax_candles.py \
  tests/integration/lab/test_candle_backfill.py \
  tests/integration/lab/test_snapshot_validation.py -q
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m pytest -q
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m ruff check src tests
PYTHONPATH=/tmp/indobot-task7-research-deps:/tmp/indobot-task5-deps:src \
  python -m compileall -q src/indodax_lab
git diff --check
```

Results: focused Task 12 plus shared-publication suite `73 passed in 1.10s`; full
non-DL suite `211 passed, 1 warning in 2.50s`; Ruff reported `All checks passed!`;
compileall and diff check exited 0. The warning remains the pre-existing pandas-ta/Pandas
4 compatibility warning.

Minor deferred as directed: cap rejection details still collapse into the existing
`CAP_HISTORY_MISSING`/`SOURCE_STALE` audit vocabulary. Expanding those reason codes is
reserved for final review rather than this fix loop.
