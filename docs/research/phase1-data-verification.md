# Phase 1 data verification

This evidence was collected after code/test commit
`f093407c9f77d18c5412267a8a007b7aa6319889`. This document is a descendant
evidence commit and makes no claims about earlier revisions.

The deterministic offline replay produces these literal named identities:

| Artifact | Content identity |
| --- | --- |
| final universe snapshot | `sha256:a427297b830e2304b49ba675a00bda1400615d8cd1c9090bcc778f29481faa24` |
| global trade decision | `sha256:5b422231814c7ac899768ee2ba7a803e335826f4954d266bb3b56d054f33b712` |

The final snapshot has exactly 45 typed source inputs. The regression test
asserts the complete literal 45-ID tuple, as well as the separately named global
trade decision ID, in two independent replay roots.

## Provider-byte provenance

Every durable trade batch used by the checkpoint has one or more real typed
trade-wire references. A trade-wire loader first verifies the immutable raw
body, strict canonical metadata, declared body hash and size, metadata hash,
path identity, and content ID. It then invokes the Task 11 pure public-message
parser on those exact bytes. The global sentry proves that every caller-supplied
batch event is field-for-field equal to the canonical concatenation derived from
the referenced wires, including ID, pair, decimal values, timestamps, quality,
session, and sequence. Canonical ordering is deterministic. There is no batch-ID
fallback or synthetic wire reference, so garbage payloads and batches that
differ from their parsed wires fail closed.

CoinGecko evidence follows the same rule. The shared pure reconstruction path
first verifies response identity, exact raw body, strict canonical metadata,
hashes, request parameters, timestamps, source asset IDs, and current or
`HISTORICAL_UNSUPPORTED` semantics. It then parses the body and reconstructs
observations, ranks, timestamps, source, and provider asset identity solely from
those verified bytes. Any retained caller batch must exactly equal that
reconstruction; a forged observation over a genuine response cannot affect
classification.

Listing evidence has explicit `base_asset_symbol`, `quote_asset_symbol`, and
`provider_asset_id` fields. Loading requires
`pair == f"{base_asset_symbol}_{quote_asset_symbol}"`; universe construction also
requires the target pair and cap provider/base identity to match. Component
mismatches fail with stable identity error codes.

The replay additionally covers public candle wire bytes and metadata, the
bronze snapshot and manifest, the complete candle quality report, every durable
trade batch, bar output/manifest/config and all bar IDs, a durable book batch,
the materialization profile, and the universe policy. Each named class is loaded
through a distinct production reference type that verifies its actual bytes,
schema, declared checksums, and content identity. `PipelineLineageInputs` has no
empty/default lineage and rejects substituting one artifact type for another.

The global trade decision is not trusted because a JSON object says `PASS`.
Publication reloads the verified wire and batch bytes, regenerates the canonical
decision, and requires byte-for-byte equality and the same content ID. Mixed
pairs, non-PASS rows, duplicate IDs or batches, mixed sequence presence, and any
sequence or offset duplicate, regression, or gap fail closed.

Candle approval uses the same principle. Its strict report records the complete
validation policy and facts, and the loader rereads verified bronze partitions
to regenerate the whole report. A full-shaped but internally inconsistent PASS
cannot authorize silver.

Universe materialization receives explicit caller-supplied `as_of_date` and
`build_cutoff` values. Trades and books require event time no later than
availability; bars require
`first_event_ts <= last_event_ts <= close_time <= available_at`; listing and cap
evidence enforce source-time ordering and asset identity. All availability is
bounded by the fixed cutoff, and bars must match the target pair, provider, and
bronze snapshot.

## Verification evidence

The commands below were run in the repository after the target commit. The
`PYTHONPATH` prefix selects the cached project test/research dependencies present
on this runner; tests themselves use no network, realtime input, ambient clock,
or trading endpoint.

| Command | Exit | Exact result |
| --- | ---: | --- |
| `PYTHONPATH=/tmp/indobot-task5-deps:/tmp/indobot-task7-research-deps python -m pytest tests/integration/lab/test_raw_to_silver_pipeline.py tests/regression/test_phase1_snapshot.py -q` | 0 | `7 passed in 14.54s` |
| `PYTHONPATH=/tmp/indobot-task5-deps:/tmp/indobot-task7-research-deps python -m pytest tests/unit/lab/data tests/unit/lab/universe tests/integration/lab tests/regression/test_phase1_snapshot.py -q` | 0 | `219 passed in 15.89s` |
| `PYTHONPATH=/tmp/indobot-task5-deps:/tmp/indobot-task7-research-deps python -m pytest -q` | 0 | `306 passed, 1 warning in 12.60s` |
| `PYTHONPATH=/tmp/indobot-task5-deps:/tmp/indobot-task7-research-deps python -m ruff check src tests` | 0 | `All checks passed!` |
| `python -m compileall -q src tests` | 0 | no output; exit 0 |
| `git diff --check` | 0 | no output; exit 0 |

The four new adversarial tests were observed red before implementation and green
in these runs: garbage trade payload with a supplied valid event, a batch event
that differs from its parsed wire, a forged cap observation over a genuine
provider response, and inconsistent listing components.

## Resource smoke measurement

Exact command:

```text
PYTHONPATH=/tmp/indobot-task5-deps:/tmp/indobot-task7-research-deps python -m pytest tests/integration/lab/test_raw_to_silver_pipeline.py -k resource -q -s
```

Exact output:

```text
phase1_resource_smoke child_rows=1728 elapsed_seconds=9.048601 vm_hwm_kib=199448
.
1 passed, 2 deselected in 9.77s
```

The Linux child replays 1,440 UTC minute trades (24 hours), writes bounded
128-record batches through `AppendOnlyStreamWriter`, persists verified raw wire
artifacts for every trade, regenerates the global sentry decision, and invokes
the public bar CLI. `VmHWM` is read in that child after the complete writer →
sentry → CLI pipeline. This remains a measurement-only smoke test: no
fabricated ASUS threshold is encoded. The first measurement on the actual ASUS
host must establish any versioned hardware gate.

## Current limitations

The fixture is intentionally synthetic and offline. It verifies deterministic
interfaces, causal gates, and audit links, not exchange availability, historical
market completeness, or actual ASUS capacity. The full suite has one current
third-party `pandas_ta` Pandas copy-on-write deprecation warning. Resource values
are runner observations, not portable reproducibility inputs or hardware limits.
