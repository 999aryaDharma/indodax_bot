# S09-01 handoff — risk period history and Research gate slices

Status: IN_PROGRESS — implementation slices reviewed; full acceptance and external qualification gates remain.

## Identity

- Sprint: S09-01 — Research tail-risk gate and breach history
- Implementation owner: Codex /root
- Independent reviewer: `/root/docs_review` (PASS for implemented S09 slice at final source SHA; S09 remains IN_PROGRESS on external gates)
- Branch: `feat/feat-02-finalization`
- Risk-period history code SHA: `da7c50cfd13f46a32f4bdd4d7f5e4c55cb0b83c7`
- Opt-in Research gate code SHA: `75e2d587b3b47894e2ee37e27283f5a1c3211c6f` (supersedes `13b67ca37e24487f3be3f1153480b088cddc3583` and `cafd1fdfab3a57a2a2092b20aa33c6ab2ef933d8`)

## Implemented slice

- `LiveShadowEngine` assigns and checkpoints a risk-period ID; reset starts a new ID and writes the old/new transition and prior halt reason to the append-only event log.
- Authorized reset refuses to run while positions remain open and carries remaining ledger cash into the new period instead of refilling the configured seed.
- Closed trades remain available across periods and carry their originating period ID. Existing checkpoints without a period ID load under a stable `legacy:<risk-start-time>` ID.
- Failed checkpoint writes restore the previous in-memory period, risk manager, ledger, positions, starting capital and audit trail. Checkpoints retain configured genesis cash separately so a restart can restore a reduced current period with the same startup config.
- A real loss test debits Rp20 from Rp500,000; the separately authorized period starts at Rp499,980 and retains that as its opening equity across restart. No pump-gap evaluator or new risk threshold is implemented. No Production behavior changed.

## Research RiskEngine gate slice (75e2d58)

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
| GREEN: malformed evidence/policy decimals and risk regressions | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/risk/test_research_tail_risk_gate.py tests/unit/lab/risk/test_risk_engine.py tests/unit/lab/risk/test_risk_engine_governance.py tests/unit/lab/risk/test_risk_parity.py -q` | 39 passed |
| RED/GREEN: stale evidence during delayed assessment | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/risk/test_research_tail_risk_gate.py::test_research_tail_gate_checks_freshness_at_assessment_time -q` | Expected RED: assessment approved stale evidence; GREEN: stale evidence rejected at assessment time |
| Import/unused lint for gate files | `C:/Users/User/miniconda3/envs/ML/python.exe -m ruff check --select I,F401 src/indodax_lab/risk/engine.py src/indodax_lab/risk/research_tail_risk.py src/indodax_lab/risk/__init__.py tests/unit/lab/risk/test_research_tail_risk_gate.py` | Passed |
| Full suite at final code SHA | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q` | 1572 passed, 2 skipped, 11 warnings in 44.44s; platform-specific `/proc` RSS and Windows symlink skips |
| Import/unused lint | `C:/Users/User/miniconda3/envs/ML/python.exe -m ruff check --select I,F401 src/indodax_lab/paper/live_shadow_engine.py tests/unit/lab/paper/test_live_shadow_engine_governance.py` | Passed |
| Full suite before TRAIN-01 checksum fix | `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q` | 1547 passed, 2 skipped, 1 unrelated failure, subsequently fixed at TRAIN-01 source SHA `7e97539861eda3b1cdbffb159d2f435f730a737b` |

## Acceptance state

- S09-01-AC0: reviewed implementation at the existing RiskEngine assessment boundary creates no order/intent. No Research agent runtime currently opts in.
- S09-01-AC1: reviewed contract tests cover missing/stale/invalid evidence and configured breaches blocking BUY, while SELL bypasses this additional gate. End-to-end runtime wiring and real producer evidence remain outstanding.
- S09-01-AC2: source inspection and the exact-SHA full suite support separately authorized reset, closed-portfolio guard, remaining-equity opening, prior breach/trade retention and restart persistence. Reviewer could not independently rerun persistence tests because of temporary-directory permission errors.
- S09-01-AC3: missing/unapproved policy or missing evidence fails closed. Producer registration/provenance qualification and numeric thresholds remain external blockers; the sprint is not qualification eligible.

## Independent review

- Review round 1 at `cafd1fdfab3a57a2a2092b20aa33c6ab2ef933d8`: CHANGES_REQUESTED for malformed decimal values escaping validation (`"bad"`, `{}`, `True`); reviewer reproduced the issue.
- Corrected both evidence measurements and policy thresholds. Invalid values now become Pydantic validation errors; evidence rejects with `RESEARCH_TAIL_EVIDENCE_INVALID`, while malformed policy prevents engine construction.
- Review round 2 at exact code SHA `75e2d587b3b47894e2ee37e27283f5a1c3211c6f`: PASS for the scoped correction; no remaining Critical/Important finding in the correction. Reviewer inspection confirmed reset/history behavior but could not run persistence tests because of temporary-directory permission errors. The exact-SHA owner full suite above passed, including those repository tests.
- Overall implemented-slice review at exact source SHA `75e2d587b3b47894e2ee37e27283f5a1c3211c6f`: PASS across AC0-AC3; reviewer combined full source review at `cafd1fd` with correction review at `75e2d58`. Reviewer independently ran 12 gate tests at `cafd1fd` and inspected corrective tests at `75e2d58`; reviewer did not independently reproduce the full suite.
- This scoped PASS does not clear S09's external producer/policy and runtime wiring gates; sprint remains IN_PROGRESS.

## Historical pump-gap range evidence

- Evidence source: `lab-data-fetch2/` Indodax hourly bronze candles, 2021-01-01 through 2025-12-31 UTC. The measurement script verifies 120 snapshot manifests and all referenced partition SHA-256, byte-size, row-count, pair/interval identity and candle quality before calculating returns.
- Reproducible implementation/output: measurement/report commit `0ad47109c919c83abf9dd1184b963c37c5dfcebf`, with manifest-identity correction at `85e9142d4e61a05b1e47972e295aff6f05427314`; `scripts/research/measure_s09_pump_gap_ranges.py` and `docs/research/s09-pump-gap-historical-range-v1.json`; readable summary in `docs/research/s09-pump-gap-historical-range-v1.md`.
- Command: `C:/Users/User/miniconda3/envs/ML/python.exe scripts/research/measure_s09_pump_gap_ranges.py --output docs/research/s09-pump-gap-historical-range-v1.json` — exit 0; 43,823 contiguous returns per pair, zero hourly gaps. Positive-return p95 across years ranged 0.8205–1.6651% BTC/IDR and 0.9089–2.2537% ETH/IDR.
- Corrected evidence check: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/research/test_s09_pump_gap_ranges.py -q -p no:cacheprovider` — 2 passed; manifest canonical ID and snapshot-directory binding now use `indodax_lab.data.manifest` and have negative regression coverage. Exact JSON reproduction was rechecked after the correction. Independent re-review of the correction is pending.
- This measures historical price movement only. The archived median `available_at - close_time` is about 101 million seconds, so the data cannot establish point-in-time producer freshness or an input-age limit. It does not qualify a live producer or justify numeric threshold approval; preserve the fail-closed, IN_PROGRESS disposition.

## External gates / risks

- Owner has not approved numeric pump-gap threshold or evidence-age limit; do not infer Production values. Test fixture numbers are not defaults.
- No point-in-time pump-gap producer/provenance is registered. Risk evaluation and qualification remain unavailable until both are versioned and qualified.
- The new assessment boundary is opt-in but no running Research agent is wired to it yet; current implementation proves the contract, not end-to-end shadow enforcement.
- Historical full suite after S09 equity carry-forward and TRAIN-01 checksum fix, before the Research gate: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q` — 1548 passed, 2 skipped, 11 warnings in 41.73s. Latest final suite result is listed in the gate evidence table above.
- New period opening equity is the closed portfolio's remaining ledger cash; no reset refills the configured seed capital. The checkpoint stores configured genesis cash separately from current period initial cash so a restart with the same settings resumes the reduced balance correctly.
- Regression evidence in the extended test drives an actual losing buy/sell through `ResearchLedger`: Rp500,000 seed becomes Rp499,980, and the approved next period starts at Rp499,980 after restart.
