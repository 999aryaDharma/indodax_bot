# S09-01 handoff — risk period history and Research gate slices

Status: IN_PROGRESS — implementation slices committed; independent review and external qualification gates remain.

## Identity

- Sprint: S09-01 — Research tail-risk gate and breach history
- Implementation owner: Codex /root
- Independent reviewer: `/root/docs_review` (review pending)
- Branch: `feat/feat-02-finalization`
- Risk-period history code SHA: `da7c50cfd13f46a32f4bdd4d7f5e4c55cb0b83c7`
- Opt-in Research gate code SHA: `cafd1fdfab3a57a2a2092b20aa33c6ab2ef933d8` (supersedes the initial gate commit `13b67ca37e24487f3be3f1153480b088cddc3583`)

## Implemented slice

- `LiveShadowEngine` assigns and checkpoints a risk-period ID; reset starts a new ID and writes the old/new transition and prior halt reason to the append-only event log.
- Authorized reset refuses to run while positions remain open and carries remaining ledger cash into the new period instead of refilling the configured seed.
- Closed trades remain available across periods and carry their originating period ID. Existing checkpoints without a period ID load under a stable `legacy:<risk-start-time>` ID.
- Failed checkpoint writes restore the previous in-memory period, risk manager, ledger, positions, starting capital and audit trail. Checkpoints retain configured genesis cash separately so a restart can restore a reduced current period with the same startup config.
- A real loss test debits Rp20 from Rp500,000; the separately authorized period starts at Rp499,980 and retains that as its opening equity across restart. No pump-gap evaluator or new risk threshold is implemented. No Production behavior changed.

## Research RiskEngine gate slice (13b67ca)

- Added opt-in policy/evidence contracts and validation at the existing `RiskEngine` assessment boundary. Default callers remain unchanged; no Production caller opts in.
- BUYs fail closed for missing/unapproved policy, missing/invalid/incomplete evidence, missing risk-period ID, lineage/period mismatch, noncausal or stale evidence, and configured pump-gap/Amihud breach. Eligible SELL intents bypass this additional gate.
- Evidence age is checked at risk assessment time, so an intent delayed after signal creation cannot use evidence that became stale while queued.
- The boundary returns `RiskAssessmentResult` only; it creates neither alpha intents nor orders. No live authority, credential, order, database, or host was accessed or changed.
- No producer is registered or runtime agent wired to supply this evidence. Fixture thresholds are test-only, not operational defaults. Numeric Research policy approval, source qualification, runtime wiring, and S09 qualification remain external gates.

## Evidence

| Scope | Command | Result |
|---|---|---|
| RED: period ID/history and closed-portfolio regressions | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/paper/test_live_shadow_engine_governance.py -q` | 2 expected failures before implementation: missing period ID |
| GREEN: shadow governance, engine and state store | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/paper/test_live_shadow_engine_governance.py tests/unit/lab/paper/test_live_shadow_engine.py tests/unit/lab/paper/test_shadow_store.py -q` | 22 passed |
| RED: Research risk-gate boundary | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/risk/test_research_tail_risk_gate.py -q` | 10 expected failures before implementation: missing gate contract |
| GREEN: risk gate and existing RiskEngine regressions | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/risk/test_research_tail_risk_gate.py tests/unit/lab/risk/test_risk_engine.py tests/unit/lab/risk/test_risk_engine_governance.py tests/unit/lab/risk/test_risk_parity.py -q` | 27 passed after freshness-at-assessment regression |
| RED/GREEN: stale evidence during delayed assessment | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/risk/test_research_tail_risk_gate.py::test_research_tail_gate_checks_freshness_at_assessment_time -q` | Expected RED: assessment approved stale evidence; GREEN: stale evidence rejected at assessment time |
| Import/unused lint for gate files | `C:/Users/User/miniconda3/envs/ML/python.exe -m ruff check --select I,F401 src/indodax_lab/risk/engine.py src/indodax_lab/risk/research_tail_risk.py src/indodax_lab/risk/__init__.py tests/unit/lab/risk/test_research_tail_risk_gate.py` | Passed |
| Full suite after final gate correction | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q` | 1560 passed, 2 skipped, 11 warnings in 42.82s; platform-specific `/proc` RSS and Windows symlink skips |
| Import/unused lint | `C:/Users/User/miniconda3/envs/ML/python.exe -m ruff check --select I,F401 src/indodax_lab/paper/live_shadow_engine.py tests/unit/lab/paper/test_live_shadow_engine_governance.py` | Passed |
| Full suite before TRAIN-01 checksum fix | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q` | 1547 passed, 2 skipped, 1 unrelated failure, subsequently fixed at TRAIN-01 source SHA `7e97539861eda3b1cdbffb159d2f435f730a737b` |

## Acceptance state

- S09-01-AC0: implementation present at the existing RiskEngine assessment boundary; it creates no order/intent. Independent review pending.
- S09-01-AC1: contract tests cover missing/stale/invalid evidence and configured breaches blocking BUY, while SELL bypasses this additional gate. Runtime agent wiring, real producer evidence, and independent review remain outstanding.
- S09-01-AC2: implementation covers explicit reset authorization, closed-portfolio guard, remaining-equity opening, prior breach/trade retention and restart persistence. Independent review pending.
- S09-01-AC3: missing/unapproved policy or missing evidence fails closed. Producer registration/provenance qualification and numeric thresholds remain external blockers; the sprint is not qualification eligible.

## External gates / risks

- Owner has not approved numeric pump-gap threshold or evidence-age limit; do not infer Production values. Test fixture numbers are not defaults.
- No point-in-time pump-gap producer/provenance is registered. Risk evaluation and qualification remain unavailable until both are versioned and qualified.
- The new assessment boundary is opt-in but no running Research agent is wired to it yet; current implementation proves the contract, not end-to-end shadow enforcement.
- Latest full suite after S09 equity carry-forward and TRAIN-01 checksum fix: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q` — 1548 passed, 2 skipped, 11 warnings in 41.73s. Skips are platform-specific `/proc` RSS and Windows symlink capability cases.
- New period opening equity is the closed portfolio's remaining ledger cash; no reset refills the configured seed capital. The checkpoint stores configured genesis cash separately from current period initial cash so a restart with the same settings resumes the reduced balance correctly.
- Regression evidence in the extended test drives an actual losing buy/sell through `ResearchLedger`: Rp500,000 seed becomes Rp499,980, and the approved next period starts at Rp499,980 after restart.
