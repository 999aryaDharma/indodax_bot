# S09-01 handoff — risk period history slice

Status: IN_PROGRESS — partial implementation; full sprint acceptance is not met.

## Identity

- Sprint: S09-01 — Research tail-risk gate and breach history
- Implementation owner: Codex /root
- Independent reviewer: `/root/docs_review` (review pending)
- Branch: `feat/feat-02-finalization`
- Code SHA: `3b678e9ba4ad8a9e655869616157ddf9fb2e67c3`

## Implemented slice

- `LiveShadowEngine` assigns and checkpoints a risk-period ID; reset starts a new ID and writes the old/new transition and prior halt reason to the append-only event log.
- Authorized reset refuses to run while positions remain open.
- Closed trades remain available across periods and carry their originating period ID. Existing checkpoints without a period ID load under a stable `legacy:<risk-start-time>` ID.
- Failed checkpoint writes restore the previous in-memory period, risk manager, ledger, positions and audit trail.
- No pump-gap evaluator or new risk threshold is implemented. No Production behavior changed.

## Evidence

| Scope | Command | Result |
|---|---|---|
| RED: period ID/history and closed-portfolio regressions | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/paper/test_live_shadow_engine_governance.py -q` | 2 expected failures before implementation: missing period ID |
| GREEN: shadow governance, engine and state store | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/paper/test_live_shadow_engine_governance.py tests/unit/lab/paper/test_live_shadow_engine.py tests/unit/lab/paper/test_shadow_store.py -q` | 22 passed |
| Import/unused lint | `C:/Users/User/miniconda3/envs/ML/python.exe -m ruff check --select I,F401 src/indodax_lab/paper/live_shadow_engine.py tests/unit/lab/paper/test_live_shadow_engine_governance.py` | Passed |
| Full suite | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q` | 1547 passed, 2 skipped, 1 unrelated failure: `tests/unit/lab/cli/test_build_training_dataset_checksum.py::test_dataset_id_changes_when_split_policy_changes` (split content digest unchanged after changing policy ID) |

## Acceptance state

- S09-01-AC2: implementation slice covers explicit reset authorization, closed-portfolio guard, prior breach event retention and restart persistence. Independent review pending.
- S09-01-AC0, AC1 and AC3: not complete. Risk gate integration, unknown/stale pump-gap evidence behavior, versioned thresholds and producer/provenance remain outstanding.

## External gates / risks

- Owner has not approved numeric pump-gap threshold or evidence-age limit; do not infer Production values.
- No point-in-time pump-gap producer/provenance is registered. Risk evaluation and qualification remain unavailable until both are versioned and qualified.
- Full suite has the unrelated training dataset checksum failure above; it is not represented as passing.
