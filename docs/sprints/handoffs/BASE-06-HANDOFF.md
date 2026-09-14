# BASE-06 — historical handoff import

Sprint: BASE-06 — Baseline trust checkpoint
Implementation agent / independent reviewer: prior agent sessions; individual identity unavailable.
Branch of imported code: `feat/strategy-research-lab-implementation-20260806`.
Baseline: `8a8e9f2`; evidence code target: `785d7a4`.
Legacy task: 6.

## Evidence

Source: `docs/research/phase0-verification.md`. Final review completion is reported in conversation checkpoint; no fabricated new reviewer verdict. Code and regression test files are listed in sprint spec. Historical command outputs are in the cited evidence document and were not rerun in this docs session. The Phase1 full suite evidence covers the combined committed base; individual test count per capability is not inferred.

## Contracts and migration

Committed source SHA + command exits -> phase0 evidence.

SQLite backup-first; exact accounting TEXT; preserve triggers, FK children and high-water mark. No production DB touched by tests.

## Acceptance mapping

- BASE-06-AC1: Semua field v2 termasuk maker flag fee dan unit diverifikasi
- BASE-06-AC2: Mutation kontrak membuat checkpoint merah
- BASE-06-AC3: Evidence membedakan SHA kode dari SHA dokumen

Map these behaviors to actual baseline tests before modifying the capability. Proposed test aliases in manifest do not claim named functions exist.

## Known risks and next consumers

Offline fixtures prove contracts, not live provider health, real historical completeness, or host capacity. Original environment paths in evidence may no longer exist. Reverify affected contract after any implementation change. Next: DATA-06.
