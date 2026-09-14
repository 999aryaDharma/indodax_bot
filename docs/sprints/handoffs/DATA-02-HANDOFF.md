# DATA-02 — historical handoff import

Sprint: DATA-02 — Durable immutable publication
Implementation agent / independent reviewer: prior agent sessions; individual identity unavailable.
Branch of imported code: `feat/strategy-research-lab-implementation-20260806`.
Baseline: `8a8e9f2`; evidence code target: `f093407`.
Legacy task: 8.

## Evidence

Source: `docs/research/phase1-data-verification.md`. Final review completion is reported in conversation checkpoint; no fabricated new reviewer verdict. Code and regression test files are listed in sprint spec. Historical command outputs are in the cited evidence document and were not rerun in this docs session. The Phase1 full suite evidence covers the combined committed base; individual test count per capability is not inferred.

## Contracts and migration

Arrow explicit schema + ZSTD + partial/fsync/rename + canonical checksum manifest.

Raw bytes before parse; canonical typed schemas; immutable Parquet/manifest; partial never means success.

## Acceptance mapping

- DATA-02-AC1: Konten sama dapat retry tanpa melewati directory fsync
- DATA-02-AC2: Konten berbeda ditolak
- DATA-02-AC3: Failure injection tidak meninggalkan sukses atau partial tersembunyi

Map these behaviors to actual baseline tests before modifying the capability. Proposed test aliases in manifest do not claim named functions exist.

## Known risks and next consumers

Offline fixtures prove contracts, not live provider health, real historical completeness, or host capacity. Original environment paths in evidence may no longer exist. Reverify affected contract after any implementation change. Next: DATA-03, DATA-05.
