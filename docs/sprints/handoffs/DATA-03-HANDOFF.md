# DATA-03 — historical handoff import

Sprint: DATA-03 — Auditable candle backfill
Implementation agent / independent reviewer: prior agent sessions; individual identity unavailable.
Branch of imported code: `feat/strategy-research-lab-implementation-20260806`.
Baseline: `8a8e9f2`; evidence code target: `f093407`.
Legacy task: 9.

## Evidence

Source: `docs/research/phase1-data-verification.md`. Final review completion is reported in conversation checkpoint; no fabricated new reviewer verdict. Code and regression test files are listed in sprint spec. Historical command outputs are in the cited evidence document and were not rerun in this docs session. The Phase1 full suite evidence covers the combined committed base; individual test count per capability is not inferred.

## Contracts and migration

run_backfill(pair, interval, start, end, transport) -> wire, bronze, manifest, checkpoint; [start,end).

Raw bytes before parse; canonical typed schemas; immutable Parquet/manifest; partial never means success.

## Acceptance mapping

- DATA-03-AC1: Dry-run tidak menulis atau mengakses jaringan
- DATA-03-AC2: Malformed row masuk reject list tanpa harga nol
- DATA-03-AC3: Checkpoint diverifikasi bersama wire metadata dan checksum

Map these behaviors to actual baseline tests before modifying the capability. Proposed test aliases in manifest do not claim named functions exist.

## Known risks and next consumers

Offline fixtures prove contracts, not live provider health, real historical completeness, or host capacity. Original environment paths in evidence may no longer exist. Reverify affected contract after any implementation change. Next: DATA-04.
