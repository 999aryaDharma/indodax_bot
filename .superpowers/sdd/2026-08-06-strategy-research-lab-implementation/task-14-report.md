# Task 14: Phase 1 data pipeline checkpoint

Verification target: `f093407c9f77d18c5412267a8a007b7aa6319889`.

The checkpoint now derives trade and cap facts from verified provider bytes.
Every durable trade batch has actual typed wire references; loaders verify exact
raw bodies and strict metadata, parse them through the Task 11 pure parser, and
require field-for-field equality between batch events and the deterministic
wire-derived concatenation. Garbage payloads, missing/fabricated references, or
event substitution fail closed. The global decision is regenerated from that
canonical set and must match its persisted bytes and identity.

CoinGecko observations, ranks, timestamps, source, and provider asset identity
are reconstructed solely from verified response body and metadata through the
same pure parser used by the adapter. Retained caller data must exactly equal the
reconstruction. Current and `HISTORICAL_UNSUPPORTED` evidence are distinguished
honestly. Listing artifacts explicitly bind pair, base symbol, quote symbol, and
provider asset ID; listing, target, and cap component mismatches use stable
fail-closed codes.

Pipeline lineage consists of exactly 45 distinct verified artifact references
for candle wire, bronze snapshot/manifest, candle quality, trade wires, every
durable batch, global trade quality, bar output/manifest/config/bar IDs, book,
listing, cap provider response, materialization profile, and universe policy.
Production loaders verify actual schemas, checksums, and content identities;
arbitrary SHA strings and semantic type substitution are rejected.
Materialization uses an explicit fixed cutoff and stable chronology/identity
gates.

Current named deterministic identities:

| Artifact | Content identity |
| --- | --- |
| final universe snapshot | `sha256:a427297b830e2304b49ba675a00bda1400615d8cd1c9090bcc778f29481faa24` |
| global trade decision | `sha256:5b422231814c7ac899768ee2ba7a803e335826f4954d266bb3b56d054f33b712` |

The regression test asserts the complete literal 45-source-ID tuple and the
separately named global decision ID in two independent replay roots.

| Command | Exit | Current result |
| --- | ---: | --- |
| focused pipeline/regression | 0 | 7 passed in 14.54 s |
| focused data/universe/integration/regression | 0 | 219 passed in 15.89 s |
| full suite | 0 | 306 passed; one third-party warning; 12.60 s |
| Ruff | 0 | passed |
| compileall | 0 | passed |
| diff check | 0 | clean |
| bounded resource child | 0 | 1,728 rows; 9.048601 s; 199,448 KiB VmHWM |

The four requested adversarial cases were first observed failing, then passed
through production loaders after implementation: garbage trade payload with a
supplied valid event, batch/wire event divergence, forged cap observation over a
genuine provider response, and listing component mismatch.

The resource test remains measurement-only and contains no fabricated ASUS
threshold. Its child executes bounded writer → verified wire reconstruction →
global sentry decision → public bar CLI. Live exchange completeness and actual
ASUS capacity remain outside this offline checkpoint.
