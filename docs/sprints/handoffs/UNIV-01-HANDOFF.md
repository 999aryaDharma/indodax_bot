# UNIV-01 — historical handoff import

Sprint: UNIV-01 — Point-in-time investable universe
Implementation agent / independent reviewer: prior agent sessions; individual identity unavailable.
Branch of imported code: `feat/strategy-research-lab-implementation-20260806`.
Baseline: `8a8e9f2`; evidence code target: `f093407`.
Legacy task: 12.

## Evidence

Source: `docs/research/phase1-data-verification.md`. Final review completion is reported in conversation checkpoint; no fabricated new reviewer verdict. Code and regression test files are listed in sprint spec. Historical command outputs are in the cited evidence document and were not rerun in this docs session. The Phase1 full suite evidence covers the combined committed base; individual test count per capability is not inferred.

## Contracts and migration

as_of + availability cutoff + provider response -> BIG_CAP/SMALL_CAP/LIQUIDITY_ONLY and exclusion reasons.

Listing/provider identity and availability join; unknown historical cap yields LIQUIDITY_ONLY. Delisted history retained.

## Acceptance mapping

- UNIV-01-AC1: Current-only cap tidak menjadi historical cap
- UNIV-01-AC2: Delisting tidak menghapus histori
- UNIV-01-AC3: TTL memakai timestamp konsisten dan future payload ditolak

Map these behaviors to actual baseline tests before modifying the capability. Proposed test aliases in manifest do not claim named functions exist.

## Known risks and next consumers

Offline fixtures prove contracts, not live provider health, real historical completeness, or host capacity. Original environment paths in evidence may no longer exist. Reverify affected contract after any implementation change. Next: DATA-06.
