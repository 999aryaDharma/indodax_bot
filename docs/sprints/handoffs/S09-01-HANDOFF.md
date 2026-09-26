# S09-01 handoff — risk period history slice

Status: IN_PROGRESS — partial implementation; full sprint acceptance is not met.

## Identity

- Sprint: S09-01 — Research tail-risk gate and breach history
- Implementation owner: Codex /root
- Independent reviewer: `/root/docs_review` (review pending)
- Branch: `feat/feat-02-finalization`
- Code SHA: `da7c50cfd13f46a32f4bdd4d7f5e4c55cb0b83c7`

## Implemented slice

- `LiveShadowEngine` assigns and checkpoints a risk-period ID; reset starts a new ID and writes the old/new transition and prior halt reason to the append-only event log.
- Authorized reset refuses to run while positions remain open and carries remaining ledger cash into the new period instead of refilling the configured seed.
- Closed trades remain available across periods and carry their originating period ID. Existing checkpoints without a period ID load under a stable `legacy:<risk-start-time>` ID.
- Failed checkpoint writes restore the previous in-memory period, risk manager, ledger, positions, starting capital and audit trail. Checkpoints retain configured genesis cash separately so a restart can restore a reduced current period with the same startup config.
- A real loss test debits Rp20 from Rp500,000; the separately authorized period starts at Rp499,980 and retains that as its opening equity across restart. No pump-gap evaluator or new risk threshold is implemented. No Production behavior changed.

## Evidence

| Scope | Command | Result |
|---|---|---|
| RED: period ID/history and closed-portfolio regressions | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/paper/test_live_shadow_engine_governance.py -q` | 2 expected failures before implementation: missing period ID |
| GREEN: shadow governance, engine and state store | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/paper/test_live_shadow_engine_governance.py tests/unit/lab/paper/test_live_shadow_engine.py tests/unit/lab/paper/test_shadow_store.py -q` | 22 passed |
| Import/unused lint | `C:/Users/User/miniconda3/envs/ML/python.exe -m ruff check --select I,F401 src/indodax_lab/paper/live_shadow_engine.py tests/unit/lab/paper/test_live_shadow_engine_governance.py` | Passed |
| Full suite before TRAIN-01 checksum fix | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q` | 1547 passed, 2 skipped, 1 unrelated failure, subsequently fixed at TRAIN-01 source SHA `7e97539861eda3b1cdbffb159d2f435f730a737b` |

## Acceptance state

- S09-01-AC2: implementation slice covers explicit reset authorization, closed-portfolio guard, remaining-equity opening, prior breach/trade retention and restart persistence. Independent review pending.
- S09-01-AC0, AC1 and AC3: not complete. Risk gate integration, unknown/stale pump-gap evidence behavior, versioned thresholds and producer/provenance remain outstanding.

## External gates / risks

- Owner has not approved numeric pump-gap threshold or evidence-age limit; do not infer Production values.
- No point-in-time pump-gap producer/provenance is registered. Risk evaluation and qualification remain unavailable until both are versioned and qualified.
- Latest full suite after S09 equity carry-forward and TRAIN-01 checksum fix: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q` — 1548 passed, 2 skipped, 11 warnings in 41.73s. Skips are platform-specific `/proc` RSS and Windows symlink capability cases.
- New period opening equity is the closed portfolio's remaining ledger cash; no reset refills the configured seed capital. The checkpoint stores configured genesis cash separately from current period initial cash so a restart with the same settings resumes the reduced balance correctly.
- Regression evidence in the extended test drives an actual losing buy/sell through `ResearchLedger`: Rp500,000 seed becomes Rp499,980, and the approved next period starts at Rp499,980 after restart.
