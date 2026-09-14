# BASE-03 — historical handoff import

Sprint: BASE-03 — Trade v2 ownership parsing
Implementation agent / independent reviewer: prior agent sessions; individual identity unavailable.
Branch of imported code: `feat/strategy-research-lab-implementation-20260806`.
Baseline: `8a8e9f2`; evidence code target: `785d7a4`.
Legacy task: 3.

## Evidence

Source: `docs/research/phase0-verification.md`. Final review completion is reported in conversation checkpoint; no fabricated new reviewer verdict. Code and regression test files are listed in sprint spec. Historical command outputs are in the cited evidence document and were not rerun in this docs session. The Phase1 full suite evidence covers the combined committed base; individual test count per capability is not inferred.

## Contracts and migration

JSON isBuyer:bool, qty, fee, price, time:milliseconds -> typed trade; seconds only compatibility view.

SQLite backup-first; exact accounting TEXT; preserve triggers, FK children and high-water mark. No production DB touched by tests.

## Acceptance mapping

- BASE-03-AC1: String false ditolak sebagai boolean
- BASE-03-AC2: BUY SELL dalam detik sama diurutkan milidetik
- BASE-03-AC3: Top-level non-object gagal terkendali

Map these behaviors to actual baseline tests before modifying the capability. Proposed test aliases in manifest do not claim named functions exist.

## Known risks and next consumers

Offline fixtures prove contracts, not live provider health, real historical completeness, or host capacity. Original environment paths in evidence may no longer exist. Reverify affected contract after any implementation change. Next: BASE-05.
