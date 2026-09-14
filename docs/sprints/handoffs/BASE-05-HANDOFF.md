# BASE-05 — historical handoff import

Sprint: BASE-05 — Unbiased signal observations
Implementation agent / independent reviewer: prior agent sessions; individual identity unavailable.
Branch of imported code: `feat/strategy-research-lab-implementation-20260806`.
Baseline: `8a8e9f2`; evidence code target: `785d7a4`.
Legacy task: 5.

## Evidence

Source: `docs/research/phase0-verification.md`. Final review completion is reported in conversation checkpoint; no fabricated new reviewer verdict. Code and regression test files are listed in sprint spec. Historical command outputs are in the cited evidence document and were not rerun in this docs session. The Phase1 full suite evidence covers the combined committed base; individual test count per capability is not inferred.

## Contracts and migration

Decision key -> observation; exec/skip/paper:<id> -> separate intent; closed bar -> SL_FIRST outcome.

SQLite backup-first; exact accounting TEXT; preserve triggers, FK children and high-water mark. No production DB touched by tests.

## Acceptance mapping

- BASE-05-AC1: Decision collision tidak mengaitkan intent ke keputusan lama
- BASE-05-AC2: Bar sebelum boundary keputusan tidak menentukan outcome
- BASE-05-AC3: Close dan checkpoint atomik saat restart

Map these behaviors to actual baseline tests before modifying the capability. Proposed test aliases in manifest do not claim named functions exist.

## Known risks and next consumers

Offline fixtures prove contracts, not live provider health, real historical completeness, or host capacity. Original environment paths in evidence may no longer exist. Reverify affected contract after any implementation change. Next: BASE-06.
