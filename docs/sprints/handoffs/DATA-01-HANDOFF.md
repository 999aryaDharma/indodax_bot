# DATA-01 — historical handoff import

Sprint: DATA-01 — Canonical market contracts
Implementation agent / independent reviewer: prior agent sessions; individual identity unavailable.
Branch of imported code: `feat/strategy-research-lab-implementation-20260806`.
Baseline: `8a8e9f2`; evidence code target: `f093407`.
Legacy task: 7.

## Evidence

Source: `docs/research/phase1-data-verification.md`. Final review completion is reported in conversation checkpoint; no fabricated new reviewer verdict. Code and regression test files are listed in sprint spec. Historical command outputs are in the cited evidence document and were not rerun in this docs session. The Phase1 full suite evidence covers the combined committed base; individual test count per capability is not inferred.

## Contracts and migration

CanonicalPair, Candle, TradeEvent + path roots -> validated immutable records.

Raw bytes before parse; canonical typed schemas; immutable Parquet/manifest; partial never means success.

## Acceptance mapping

- DATA-01-AC1: schema_version wajib
- DATA-01-AC2: Interval tidak dikenal ditolak
- DATA-01-AC3: ingested_at sebelum event_ts memerlukan anomaly flag

Map these behaviors to actual baseline tests before modifying the capability. Proposed test aliases in manifest do not claim named functions exist.

## Known risks and next consumers

Offline fixtures prove contracts, not live provider health, real historical completeness, or host capacity. Original environment paths in evidence may no longer exist. Reverify affected contract after any implementation change. Next: DATA-02, COST-01.
