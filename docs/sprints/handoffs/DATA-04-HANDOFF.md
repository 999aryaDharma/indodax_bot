# DATA-04 — historical handoff import

Sprint: DATA-04 — Snapshot quality decisions
Implementation agent / independent reviewer: prior agent sessions; individual identity unavailable.
Branch of imported code: `feat/strategy-research-lab-implementation-20260806`.
Baseline: `8a8e9f2`; evidence code target: `f093407`.
Legacy task: 10.

## Evidence

Source: `docs/research/phase1-data-verification.md`. Final review completion is reported in conversation checkpoint; no fabricated new reviewer verdict. Code and regression test files are listed in sprint spec. Historical command outputs are in the cited evidence document and were not rerun in this docs session. The Phase1 full suite evidence covers the combined committed base; individual test count per capability is not inferred.

## Contracts and migration

validate_snapshot(snapshot, coverage, as_of) -> canonical quality report, CLI exit 0/3/4.

Raw bytes before parse; canonical typed schemas; immutable Parquet/manifest; partial never means success.

## Acceptance mapping

- DATA-04-AC1: FAIL QUARANTINED upstream tidak menjadi PASS
- DATA-04-AC2: Coverage invalid exit 4 dan corrupt content exit 3
- DATA-04-AC3: Path traversal dan symlink loop ditolak terkendali

Map these behaviors to actual baseline tests before modifying the capability. Proposed test aliases in manifest do not claim named functions exist.

## Known risks and next consumers

Offline fixtures prove contracts, not live provider health, real historical completeness, or host capacity. Original environment paths in evidence may no longer exist. Reverify affected contract after any implementation change. Next: UNIV-01, BAR-01.
