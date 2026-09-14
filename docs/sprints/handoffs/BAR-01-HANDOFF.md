# BAR-01 — historical handoff import

Sprint: BAR-01 — Causal time and event bars
Implementation agent / independent reviewer: prior agent sessions; individual identity unavailable.
Branch of imported code: `feat/strategy-research-lab-implementation-20260806`.
Baseline: `8a8e9f2`; evidence code target: `f093407`.
Legacy task: 13.

## Evidence

Source: `docs/research/phase1-data-verification.md`. Final review completion is reported in conversation checkpoint; no fabricated new reviewer verdict. Code and regression test files are listed in sprint spec. Historical command outputs are in the cited evidence document and were not rerun in this docs session. The Phase1 full suite evidence covers the combined committed base; individual test count per capability is not inferred.

## Contracts and migration

PASS trades + continuity + fixed/train-only threshold -> separate bar_type datasets, end-exclusive windows.

End-exclusive windows, session continuity, threshold and artifact lineage, official anchor validates whole input.

## Acceptance mapping

- BAR-01-AC1: Threshold available setelah event ditolak
- BAR-01-AC2: Session gap tidak boleh disebrangi event bar
- BAR-01-AC3: Seluruh official file divalidasi sebelum filter interval

Map these behaviors to actual baseline tests before modifying the capability. Proposed test aliases in manifest do not claim named functions exist.

## Known risks and next consumers

Offline fixtures prove contracts, not live provider health, real historical completeness, or host capacity. Original environment paths in evidence may no longer exist. Reverify affected contract after any implementation change. Next: DATA-06, SIM-01.
