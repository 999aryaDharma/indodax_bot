# RP-02 Handoff — Shared candidate feature and exit evaluation

## Identity

- Sprint: RP-02 (`docs/sprints/runtime-parity/RP-02-shared-candidate-feature-and-exit-evaluation.md`)
- Implementation owner: OpenCode subagent (task 9), worktree `D:\bot-trading\.worktrees\feat-rp-02`
- Independent reviewer: UNASSIGNED — coordinator assigns after this handoff
- Branch: `feat/rp-02-shared-candidate-feature-and-exit-evaluation`
- Base SHA: `31fef79`
- Implementation/evidence SHA: `97885e9a4f0aa681f470eef9c41fa4f16b7f469a` (`97885e9`)
  — commit `feat(rp-02): shared candidate feature and exit evaluation`, contains tests + implementation
- Environment: Windows (win32), Python 3.14.0, pytest 9.0.3, pydantic 2.12.3, pandas 2.3.3, PyYAML 6.0.3

## Scope delivered

New, additive package `src/indodax_lab/runtime/` — one verified evaluator
(features + exits) independent of venue, training and ambient clock — plus a
single causal feature-builder extension to `backtest/feature_replay.py`. No
existing behavior was restructured.

| Actual path | Action | Notes |
|---|---|---|
| `src/indodax_lab/runtime/__init__.py` | CREATE | package export surface |
| `src/indodax_lab/runtime/candidate.py` | CREATE | `CanonicalMarketEvent`, `RuntimeState`, `CandidateRuntime`, `intent_id`, `feature_state_digest` |
| `src/indodax_lab/runtime/exits.py` | CREATE | C02 trailing/breakeven exit state machine (`ExitState`, `PositionExitState`, `advance_exit_state`, `exit_decisions`, `open_position`) |
| `src/indodax_lab/backtest/feature_replay.py` | MODIFY | added `build_c02_feature_rows` + `C02_FEATURE_COLUMNS` (extend only; no adjacent refactor) |
| `tests/unit/lab/runtime/__init__.py` | CREATE | package marker |
| `tests/unit/lab/runtime/test_candidate_runtime.py` | CREATE | 12 behavioral tests (7 AC + 5 supporting) |

Declared interface implemented exactly:
`CandidateRuntime.evaluate(event, state) -> tuple[SignalIntent, ...]`;
`CandidateRuntime.load_plan(plan) -> CandidateRuntime`;
`CandidateRuntime.load(candidate, *, plan=None, plan_resolver=None) -> CandidateRuntime`
(`load` accepts the verified plan — or a plan resolver — to verify candidate/package
linkage, then delegates to the identical evaluator; the declared positional
`load(candidate)` shape is preserved).

## Reuse (nothing rebuilt)

- `VerifiedRuntimePlan` / `VerifiedCandidate` / `verify_runtime_plan` / `manifest_digest` / `canonical_bytes` — RW0-01 `contracts/workbench.py` + `contracts/identity.py` (read-only).
- `SignalIntent` — shared contract `contracts/decision.py` (RP-01 ownership).
- C02 strategy — `strategies/c02.py` `c02_decide` resolved through the real RW2-01 `StrategyRegistry` (builtin), not re-implemented.
- Feature computation — `build_c02_feature_rows` reuses FEAT-02 golden transforms (`features.technical.atr` Wilder ATR; pandas `ewm` with the pinned first-observation/adjust=False EMA policy) and the existing `create_decision_frame` causal frame.
- C02 exit semantics — `runtime/exits.py` mirrors `paper/live_shadow_engine.py` `check_open_positions` (trailing 2.0x ATR behind highest; time-decay breakeven after 14 bars if not up 1.0x ATR; advance once per new closed bar). Behavior reused, strategy not forked.
- Model artifact resolution — `ModelRegistry.load_verified` (RW2-02); missing declared artifacts surface as `RUNTIME_MODEL_ARTIFACT_MISSING`.
- Pipeline node resolution — reads `PipelineManifest` nodes/`component_refs` directly to bind the ta strategy ref and ml/dl model refs by digest (no second validator).

## TDD evidence

### RED (before behavior was present)

- Command: `python -m pytest tests/unit/lab/runtime/test_candidate_runtime.py -q`
- Exit: **1** — collection error `ImportError: cannot import name 'build_c02_feature_rows'`
  (runtime package absent). This is the missing-dependency RED.
- Behavior RED (implementation present, guard removed — proves the tests catch real regressions):

| Test | Temporary break | RED failure |
|---|---|---|
| `test_rp_02_2` (AC2) | disabled `_verify_feature_identity` | `Failed: DID NOT RAISE CandidateRuntimeError` |
| `test_rp_02_4` (AC4) | disabled `_verify_models` | `Failed: DID NOT RAISE CandidateRuntimeError` (silent TA-only) |
| `test_rp_02_bootstrap_recovery` (AC5) | intent `output_node` depended on candidate digest | `AssertionError: decision trace diverged` (bytes differ) |

### GREEN (after implementation)

- Command: `python -m pytest tests/unit/lab/runtime/test_candidate_runtime.py -q`
- Exit: **0** — `12 passed in 8.40s`

## AC → test mapping

| Acceptance | Test | Required assertion | Result |
|---|---|---|---|
| RP-02-AC0 / FR0 | `test_rp_02_0` | Same candidate/event/state → identical intent bytes; intent ID = H(plan_digest, event_id, output_node, ordinal) | PASS (RED → GREEN) |
| RP-02-AC1 / FR1 | `test_rp_02_1` | Future-row perturbation leaves past decisions unchanged (bar-by-bar byte equality up to the perturbation point) | PASS (RED → GREEN) |
| RP-02-AC2 / FR2 | `test_rp_02_2` | Feature/model mismatch rejects before decision (`FEATURE_SCHEMA_MISMATCH`) | PASS (RED → GREEN) |
| RP-02-AC3 / FR3 | `test_rp_02_3` | C02 trailing/breakeven advances once per new closed bar (ratchet, idempotent per bar, breakeven after 14 bars) | PASS (RED → GREEN) |
| RP-02-AC4 / FR4 | `test_rp_02_4` | Missing M02/D04 declared artifact BLOCKS (`MODEL_ARTIFACT_MISSING`); TA-only pipeline unaffected | PASS (RED → GREEN) |
| RP-02-AC5 | `test_rp_02_bootstrap_recovery` | Historical plan executes before candidate packaging; identical decision trace when later wrapped as a candidate | PASS (RED → GREEN) |
| RP-02-AC6 | `test_rp_02_program_6` | Candidate stop and exit state have identical semantics before venue effects (stop-first, conservative exit price) | PASS (RED → GREEN) |
| (supporting) | `test_intent_id_is_independent_of_candidate_digest` | intent ID stability/independence | PASS |
| (supporting) | `test_evaluate_rejects_future_availability` | availability violation rejects | PASS |
| (supporting) | `test_evaluate_rejects_state_plan_digest_mismatch` | plan digest mismatch rejects | PASS |
| (supporting) | `test_load_rejects_candidate_plan_linkage_mismatch` | candidate/plan linkage mismatch rejects | PASS |
| (supporting) | `test_evaluate_emits_exit_intent_when_mark_hits_stop` | evaluate emits a SELL exit intent when the mark hits the stop | PASS |

## Gates (run inside the worktree, in order)

| # | Command | Result | Exit |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/lab/runtime/test_candidate_runtime.py -q` | `12 passed` | 0 |
| 2 | `python -m pytest tests/unit/lab/backtest -q` | `122 passed` | 0 |
| 3 | `python -m pytest tests/unit/lab -q` | `1503 passed` (baseline 1491 + 12 new) | 0 |
| 4 | `python -m ruff check src/indodax_lab/runtime tests/unit/lab/runtime` | `All checks passed!` | 0 |
| 5 | `git diff --check` / `git diff --cached --check` | clean | 0 |

- Pre-change baseline: `python -m pytest tests/unit/lab -q` → `1491 passed`, exit 0.
- `ruff check` on `src/indodax_lab/backtest/feature_replay.py` reports only the
  12 pre-existing findings present before this sprint (verified against
  `git show HEAD:`); the added `build_c02_feature_rows` lines are clean.
- No required tests skipped; the only warning is the pre-existing langsmith
  `pydantic.v1` / Python 3.14 `UserWarning` (unrelated to RP-02).

## Behavior summary (what the evaluator enforces)

- **Identity verification:** `evaluate` rejects unless `state.runtime_plan_digest`
  matches the verified plan and `state.candidate_digest` matches the candidate
  binding (None for historical bootstrap).
- **Causal availability:** `available_at <= event_time`; state bars and the
  event observation must not close after the event time; no bfill, no future rows.
- **Feature identity:** the computed C02 feature schema
  (`ema_fast`, `ema_slow`, `atr_14`) must equal the plan's
  `ordered_feature_names`; mismatch rejects before decision.
- **Model artifact resolution:** every ml/dl node's declared model ref is
  verified through `ModelRegistry.load_verified` at load; a missing artifact
  raises `RUNTIME_MODEL_ARTIFACT_MISSING` — never a silent TA-only degradation.
- **Content-derived intent IDs:** `intent_id = sha256(canonical_bytes({plan_digest,
  event_id, output_node, ordinal}))`; candidate digest is separate provenance.
- **Exit state:** C02 trailing (2.0x ATR ratchet) + time-decay breakeven
  (after 14 bars if not up 1.0x ATR), advancing exactly once per new closed bar;
  stop-first on ambiguous OHLCV; conservative exit price `min(close, trigger)`.

## Self-review notes (owner cannot final-approve)

- Full scoped diff reviewed (6 files, +1554/-0; only `feature_replay.py` modified, additively).
- Tests drive the public `CandidateRuntime` / `exits` boundaries only; temp
  model registry, synthetic in-process bars — no network, Telegram, production
  DB, real market data or live credentials.
- `CandidateRuntime.load` accepts the verified plan (or a plan resolver) to
  verify candidate/package linkage; the declared positional `load(candidate)`
  shape is preserved and fail-closed (`CANDIDATE_PLAN_UNRESOLVED`) when the
  plan cannot be resolved. Documented as a design decision below.
- No test was weakened, skipped or deleted; `docs/sprints/sprint-manifest.json`
  untouched; `src/indodax_lab/models/`, `src/indodax_lab/pipelines/`,
  `src/indodax_lab/strategies/` untouched.
- No `git push`, no `git merge`, no worktree/branch deletion, no production activation.

## Deviations / design decisions

1. **`CandidateRuntime.load` dependency injection.** The declared
   `load(candidate)` verifies candidate/package linkage, which requires the
   verified `RuntimePlan`. The plan (or a `plan_resolver` callable) is accepted
   as a keyword-only parameter; `load(plan)` / `load_plan(plan)` remain the
   primary entries. Fail-closed when unresolvable.
2. **Output node in intent ID.** The output node is derived from the plan's
   bound policy refs (`sizing:<sizing_policy_ref.id>` for entry intents,
   `exits:<exit_policy_ref.id>` for exit intents) — stable, plan-bound and
   independent of presentation order. The plan digest already binds the full
   pipeline graph.
3. **`observation` typed as a closed-bar market observation.** The evaluator
   requires a closed-bar OHLCV observation (candle-close evaluation); the
   shared contract's other observation kinds are additive future work.
4. **Pipeline node resolution is by digest, not a second validation pass.**
   The runtime reads `PipelineManifest` nodes/`component_refs` to bind the ta
   strategy ref and ml/dl model refs; full graph validation remains RW2-03's
   job at plan-creation time.

## Migration / rollback

- Additive-only: no schema migration, no data backfill, no existing manifest
  or store altered. `build_c02_feature_rows` is a new function; the existing
  `FeatureReplayAdapter` / `load_bars_from_parquet*` are unchanged.
- Rollback = delete `src/indodax_lab/runtime/` and `tests/unit/lab/runtime/`,
  and revert the `feature_replay.py` addition; no other file depends on them yet.
- Tests use `pytest.tmp_path` for the model registry; no production database
  is touched.

## Pending external gates

- Independent review of `97885e9` — not dispatched by the owner; coordinator assigns.
- No production activation, deployment, push or merge is authorized by this sprint.
- Forward shadow/production wiring (RuntimeKernel, ExecutionStateStore,
  adapters) is owned by RP-04/PM-02 and is out of scope.
