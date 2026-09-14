# Repository and planning audit — 2026-09-14

## Observed baseline

Repository code present in local checkout. Implementation branch `feat/strategy-research-lab-implementation-20260806`; HEAD `8a8e9f2` (Phase1 evidence), prior code `f093407`. Documentation branch `docs/trading-bot-master-plan-20260914` created in separate worktree from that HEAD. Original WIP paths: `src/indodax_lab/features/`, `tests/fixtures/features/`, `tests/unit/lab/features/`; untouched by this docs task.

Existing flat modules: main/signal/risk/Telegram/position/paper. Adjacent lab: contracts, data, universe, paths and five public CLI adapters. Actual source and tests inspected before architecture proposal. Git history includes baseline corrections, migration rounds and provider-derived snapshot fixes. Existing CI uses Python3.11, requirements-dev/research, pytest and Ruff; Ruff explicitly excludes several legacy modules. A green lint result is therefore not proof every old file is lint-clean.

## Evidence already recorded

Phase0 source evidence `785d7a4`: 73 full tests recorded. Phase1 target `f093407`: checkpoint219/full306 recorded; final review PASS reported in supplied conversation. These are historical, not test executions during this documentation session. Known pandas_ta/pandas warning remains. Phase1 uses synthetic offline data and measured only its runner; it does not establish live data quality or ASUS production capacity.

## Gaps and resolutions

| Observation | Resolution |
|---|---|
| Task15 untracked partial code | FEAT-01…04 new scopes; WIP inspection before reuse, no fabricated completion |
| Old task16 labels use later cost/execution | DAG requires SIM-01 before LABEL-01 |
| Net mapper could subtract costs twice | ADR-002 explicit forecast basis and once-only costs |
| Fixed annual split could be mistaken for sealed truth | Exposure audit mandatory; no resealing viewed data |
| Current cap historical ambiguity | Provider-byte reconstruction; LIQUIDITY_ONLY historical fallback |
| Wave1 old narrative calls 31 features | Expanded dataset contract actually specifies 41 scalar names; registry must match exact expanded set |
| Job queue cross-host ownership implicit | Local SQLite per host; immutable transfer; no network WAL |
| Plan includes advanced catalog without detailed tasks | Individual extension sprints, explicit optional activation |
| Backup/restore/retention absent from 35-task coverage | OPS-02/03 and acceptance added |
| Agent coordination confused with running scheduler | `.agents/orchestrator` explicitly documented-only |
| Real deployment and model profitability unproven | External gates/risk register; software release distinct from champion |

## Classification and scope

PARTIALLY IMPLEMENTED and RESEARCH/EXPERIMENTAL. Not greenfield, not a proven profitable product. Current task only adds planning/control-plane docs and its structural validator. No product implementation, account activity, service activation, data purchase or real trading happens here.
