"""Behavioral acceptance tests for RP-02: shared candidate feature and exit evaluation.

Every test drives the public ``CandidateRuntime`` boundary inside temporary
namespaces: no network, no Telegram, no production database and no real
market data. Component resolution uses the real RW2-01 strategy registry and
the real RW2-02 model registry with synthetic in-process artifacts.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import MarketBar
from indodax_lab.backtest.feature_replay import build_c02_feature_rows
from indodax_lab.contracts.identity import ArtifactRef, canonical_bytes, manifest_digest
from indodax_lab.contracts.workbench import (
    CandidateManifest,
    PipelineEdge,
    PipelineManifest,
    PipelineNode,
    RuntimePlan,
    VerifiedCandidate,
    verify_runtime_plan,
)
from indodax_lab.models.registry import ModelRegistry
from indodax_lab.runtime import (
    CandidateRuntime,
    CandidateRuntimeError,
    CanonicalMarketEvent,
    ExitState,
    FeatureState,
    RuntimeState,
    advance_exit_state,
    exit_decisions,
    feature_state_digest,
    intent_id,
    open_position,
)
from indodax_lab.strategies.registry import StrategyRegistry

_REPO_ROOT = Path(__file__).resolve().parents[4]
_C02_CONFIG = _REPO_ROOT / "configs" / "strategies" / "C02_v1.yaml"

_PAIR = "btc_idr"
_HERE = datetime(2021, 1, 1, tzinfo=UTC)
_INTERVAL = timedelta(hours=1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bar(
    index: int, close: float, *, low: float | None = None, high: float | None = None
) -> MarketBar:
    close_time = _HERE + _INTERVAL * index
    c = Decimal(str(close))
    return MarketBar(
        pair=_PAIR,
        open_time=close_time,
        close_time=close_time + _INTERVAL,
        open=c,
        high=Decimal(str(high if high is not None else close * 1.001)),
        low=Decimal(str(low if low is not None else close * 0.999)),
        close=c,
        base_volume=Decimal("1"),
        quote_volume=Decimal("1000"),
    )


def _triggering_series(length: int = 60, dip_index: int = 58) -> list[MarketBar]:
    """Rising 1h series with a single pullback dip that triggers a C02 BUY."""
    bars: list[MarketBar] = []
    for i in range(length):
        close = 1000 + i * 10
        if i == dip_index:
            bars.append(_bar(i, close, low=close - 200, high=close + 5))
        else:
            bars.append(_bar(i, close))
    return bars


def _policy_ref(kind: str) -> ArtifactRef:
    return ArtifactRef(kind=kind, id=f"{kind}_v1", version="1.0.0", sha256="0" * 64)


def _experiment_ref() -> ArtifactRef:
    return ArtifactRef(
        kind="experiment", id="exp_1", version="1.0.0", sha256="0" * 64
    )


def _edge(source: str, source_port: str, target: str, target_port: str) -> PipelineEdge:
    return PipelineEdge(
        source_node=source,
        source_port=source_port,
        target_node=target,
        target_port=target_port,
    )


_C02_REGISTERED = None


def _c02_registered():
    global _C02_REGISTERED
    if _C02_REGISTERED is None:
        spec = StrategyRegistry().load_specification_from_yaml(_C02_CONFIG)
        _C02_REGISTERED = StrategyRegistry().register_builtin(spec)
    return _C02_REGISTERED


def _strategy_resolver(ref: ArtifactRef):
    if ref.id == "C02" and ref.kind == "strategy_manifest":
        return _c02_registered()
    raise KeyError(f"unknown strategy ref {ref}")


def _ta_only_pipeline(strategy_ref: ArtifactRef) -> PipelineManifest:
    nodes = (
        PipelineNode(node_id="ds_1", kind="dataset_input", output_port="MarketObservation"),
        PipelineNode(node_id="C02", kind="ta", output_port="DecisionProposal"),
        PipelineNode(node_id="gate", kind="gate_veto", output_port="SignalIntent"),
        PipelineNode(node_id="sizing", kind="sizing", output_port="SignalIntent"),
        PipelineNode(node_id="exits", kind="exits", output_port="SignalIntent"),
    )
    edges = (
        _edge("ds_1", "MarketObservation", "C02", "MarketObservation"),
        _edge("C02", "DecisionProposal", "gate", "DecisionProposal"),
        _edge("gate", "SignalIntent", "sizing", "SignalIntent"),
        _edge("sizing", "SignalIntent", "exits", "SignalIntent"),
    )
    return PipelineManifest(
        pipeline_id="pipe_c02",
        version="1.0.0",
        nodes=nodes,
        edges=edges,
        component_refs=(strategy_ref,),
        dataset_timeframe_constraints={_PAIR: ("1h",)},
        ensemble_parameters={},
        sizing_policy_ref=_policy_ref("sizing_policy"),
        exit_policy_ref=_policy_ref("exit_policy"),
        risk_policy_ref=_policy_ref("risk_policy"),
        cost_policy_ref=_policy_ref("cost_policy"),
        execution_policy_ref=_policy_ref("execution_policy"),
    )


def _strategy_ref() -> ArtifactRef:
    return ArtifactRef(kind="strategy_manifest", id="C02", version="1.0.0", sha256="0" * 64)


def _model_ref(model_id: str = "M02_xgboost") -> ArtifactRef:
    return ArtifactRef(kind="model", id=model_id, version="1.0.0", sha256="0" * 64)


def _pipeline_with_model(strategy_ref: ArtifactRef, model_ref: ArtifactRef) -> PipelineManifest:
    """TA + ML graph where the ML node declares a model artifact ref."""
    nodes = (
        PipelineNode(node_id="ds_1", kind="dataset_input", output_port="MarketObservation"),
        PipelineNode(node_id="feats", kind="indicators_features", output_port="FeatureFrame"),
        PipelineNode(node_id="C02", kind="ta", output_port="DecisionProposal"),
        PipelineNode(node_id=model_ref.id, kind="ml", output_port="ProbabilityVector"),
        PipelineNode(node_id="sizing", kind="sizing", output_port="SignalIntent"),
        PipelineNode(node_id="exits", kind="exits", output_port="SignalIntent"),
    )
    edges = (
        _edge("ds_1", "MarketObservation", "feats", "MarketObservation"),
        _edge("ds_1", "MarketObservation", "C02", "MarketObservation"),
        _edge("feats", "FeatureFrame", model_ref.id, "FeatureFrame"),
        _edge("C02", "DecisionProposal", "sizing", "DecisionProposal"),
        _edge("sizing", "SignalIntent", "exits", "SignalIntent"),
    )
    return PipelineManifest(
        pipeline_id="pipe_c02_ml",
        version="1.0.0",
        nodes=nodes,
        edges=edges,
        component_refs=(strategy_ref, model_ref),
        dataset_timeframe_constraints={_PAIR: ("1h",)},
        ensemble_parameters={},
        sizing_policy_ref=_policy_ref("sizing_policy"),
        exit_policy_ref=_policy_ref("exit_policy"),
        risk_policy_ref=_policy_ref("risk_policy"),
        cost_policy_ref=_policy_ref("cost_policy"),
        execution_policy_ref=_policy_ref("execution_policy"),
    )


def _runtime_plan(*, ordered_features=("ema_fast", "ema_slow", "atr_14")) -> RuntimePlan:
    return RuntimePlan(
        plan_id="plan_c02",
        version="1.0.0",
        universe=(_PAIR,),
        timeframe="1h",
        dataset_refs=(),
        pipeline_ref=ArtifactRef(kind="pipeline", id="pipe_c02", version="1.0.0", sha256="0" * 64),
        feature_schema_hash="0" * 64,
        ordered_feature_names=tuple(ordered_features),
        sizing_policy_ref=_policy_ref("sizing_policy"),
        exit_policy_ref=_policy_ref("exit_policy"),
        risk_policy_ref=_policy_ref("risk_policy"),
        cost_policy_ref=_policy_ref("cost_policy"),
        execution_policy_ref=_policy_ref("execution_policy"),
        git_sha="0" * 40,
        environment_digest="env",
        seed=42,
    )


def _event(sequence: int, bar: MarketBar) -> CanonicalMarketEvent:
    return CanonicalMarketEvent(
        event_id=f"evt_{sequence}",
        feed_id="feed_btc_idr",
        sequence=sequence,
        pair=bar.pair,
        event_time=bar.close_time,
        available_at=bar.close_time,
        observation=bar,
    )


def _state(
    plan_digest: str,
    bars: list[MarketBar],
    *,
    candidate_digest: str | None = None,
    exit_state: ExitState | None = None,
) -> RuntimeState:
    return RuntimeState(
        runtime_plan_digest=plan_digest,
        candidate_digest=candidate_digest,
        feature_state=FeatureState(bars=tuple(bars), digest=feature_state_digest(bars)),
        exit_state=exit_state if exit_state is not None else ExitState(),
    )


def _last_atr(bars: list[MarketBar]) -> Decimal:
    frame = build_c02_feature_rows(bars)
    return Decimal(str(frame.iloc[-1]["atr_14"]))


def _run_series(
    runtime: CandidateRuntime,
    bars: list[MarketBar],
    *,
    candidate_digest: str | None = None,
) -> list[tuple]:
    """Evaluate each bar in order, evolving feature/exit state like a kernel would."""
    traces: list[tuple] = []
    feature_bars: list[MarketBar] = []
    exit_state = ExitState()
    for index, bar in enumerate(bars):
        state = _state(
            runtime.plan_digest,
            feature_bars,
            candidate_digest=candidate_digest,
            exit_state=exit_state,
        )
        intents = runtime.evaluate(_event(index + 1, bar), state)
        traces.append(intents)
        feature_bars.append(bar)
        exit_state = advance_exit_state(exit_state, bar)
        for intent in intents:
            if intent.side == OrderSide.BUY:
                exit_state = open_position(
                    exit_state,
                    pair=intent.pair,
                    strategy_id=intent.strategy_id,
                    entry_price=intent.limit_price,
                    entry_atr=_last_atr(feature_bars),
                    stop_loss=intent.stop_loss,
                    qty=intent.desired_qty,
                )
    return traces


# ---------------------------------------------------------------------------
# RP-02-AC0: Same candidate/event/state gives identical intent bytes
# ---------------------------------------------------------------------------


def test_rp_02_0():
    plan = verify_runtime_plan(_runtime_plan())
    runtime = CandidateRuntime.load_plan(
        plan, pipeline=_ta_only_pipeline(_strategy_ref()), strategy_resolver=_strategy_resolver
    )
    bars = _triggering_series()
    state = _state(plan.plan_digest, bars[:-1])

    first = runtime.evaluate(_event(1, bars[-1]), state)
    second = runtime.evaluate(_event(1, bars[-1]), state)

    assert first, "expected at least one intent from the triggering series"
    assert canonical_bytes(first) == canonical_bytes(second)
    assert first[0].intent_id == second[0].intent_id
    # Intent identity binds the plan digest, event id, output node and ordinal.
    expected_id = intent_id(
        plan.plan_digest, "evt_1", f"sizing:{plan.plan.sizing_policy_ref.id}", 0
    )
    assert first[0].intent_id == expected_id


# ---------------------------------------------------------------------------
# RP-02-AC1: Future-row perturbation leaves past decisions unchanged
# ---------------------------------------------------------------------------


def test_rp_02_1():
    plan = verify_runtime_plan(_runtime_plan())
    runtime = CandidateRuntime.load_plan(
        plan, pipeline=_ta_only_pipeline(_strategy_ref()), strategy_resolver=_strategy_resolver
    )
    base = _triggering_series()
    perturbed = list(base)
    # Wildly perturb every bar AFTER index 55 (the future relative to bar 55).
    for i in range(56, len(perturbed)):
        perturbed[i] = _bar(i, 999999.0, low=1.0, high=9999999.0)

    base_trace = _run_series(runtime, base)
    perturbed_trace = _run_series(runtime, perturbed)

    assert len(base_trace) == len(perturbed_trace)
    for i in range(56):
        assert canonical_bytes(base_trace[i]) == canonical_bytes(perturbed_trace[i]), (
            f"decision at bar {i} changed after future-row perturbation"
        )


# ---------------------------------------------------------------------------
# RP-02-AC2: Feature/model mismatch rejects before decision
# ---------------------------------------------------------------------------


def test_rp_02_2():
    # Plan declares a feature schema the evaluator cannot produce.
    plan = verify_runtime_plan(_runtime_plan(ordered_features=("ema_fast", "ema_slow")))
    runtime = CandidateRuntime.load_plan(
        plan, pipeline=_ta_only_pipeline(_strategy_ref()), strategy_resolver=_strategy_resolver
    )
    bars = _triggering_series()
    state = _state(plan.plan_digest, bars[:-1])

    with pytest.raises(CandidateRuntimeError) as exc:
        runtime.evaluate(_event(1, bars[-1]), state)
    assert "FEATURE_SCHEMA_MISMATCH" in str(exc.value)


# ---------------------------------------------------------------------------
# RP-02-AC3: C02 trailing/breakeven advances once per new closed bar
# ---------------------------------------------------------------------------


def test_rp_02_3():
    bar = _bar(0, 1000.0, high=1005.0, low=995.0)
    state = open_position(
        ExitState(),
        pair=_PAIR,
        strategy_id="C02",
        entry_price=Decimal("1000"),
        entry_atr=Decimal("10"),
        stop_loss=Decimal("950"),
        qty=Decimal("0.1"),
    )
    position = state.for_pair(_PAIR)
    assert position is not None
    initial_stop = position.stop_loss

    # First new closed bar: trailing ratchets the stop up (2.0x ATR behind high).
    advanced = advance_exit_state(state, bar)
    advanced_position = advanced.for_pair(_PAIR)
    assert advanced_position is not None
    assert advanced_position.stop_loss > initial_stop
    assert advanced_position.bars_held == 1
    # trailing_sl = 1005 - 2*10 = 985
    assert advanced_position.stop_loss == Decimal("985")

    # Re-processing the SAME closed bar is a no-op (advance once per bar).
    again = advance_exit_state(advanced, bar)
    assert again == advanced

    # A new closed bar advances again.
    bar2 = _bar(1, 1002.0, high=1006.0, low=1000.0)
    advanced2 = advance_exit_state(advanced, bar2)
    advanced2_position = advanced2.for_pair(_PAIR)
    assert advanced2_position is not None
    assert advanced2_position.bars_held == 2
    assert advanced2_position.stop_loss > advanced_position.stop_loss

    # Time-decay breakeven: after 14 bars, if not up 1.0x ATR, move to breakeven.
    # Keep the highest price (1005) below entry + 1.0x ATR (1010).
    current = advanced2
    for i in range(2, 14):
        current = advance_exit_state(current, _bar(i, 1000.0, high=1005.0, low=995.0))
    breakeven_position = current.for_pair(_PAIR)
    assert breakeven_position is not None
    assert breakeven_position.bars_held == 14
    assert breakeven_position.time_decay_breakeven is True
    # highest (1006) < entry (1000) + 1.0*atr (10) = 1010 -> breakeven at 1000.
    assert breakeven_position.stop_loss == Decimal("1000")


# ---------------------------------------------------------------------------
# RP-02-AC4: Missing M02/D04 declared artifact cannot silently degrade to TA-only
# ---------------------------------------------------------------------------


def test_rp_02_4(tmp_path):
    models = ModelRegistry(tmp_path / "models")
    plan = verify_runtime_plan(_runtime_plan())
    pipeline = _pipeline_with_model(_strategy_ref(), _model_ref("M02_xgboost"))

    # The declared M02 artifact is absent from the registry: load must BLOCK.
    with pytest.raises(CandidateRuntimeError) as exc:
        CandidateRuntime.load_plan(
            plan,
            pipeline=pipeline,
            models=models,
            strategy_resolver=_strategy_resolver,
        )
    assert "MODEL_ARTIFACT_MISSING" in str(exc.value)

    # A TA-only pipeline (no model declaration) is unaffected by the empty registry.
    ta_runtime = CandidateRuntime.load_plan(
        plan,
        pipeline=_ta_only_pipeline(_strategy_ref()),
        strategy_resolver=_strategy_resolver,
    )
    assert ta_runtime.plan_digest == plan.plan_digest


# ---------------------------------------------------------------------------
# RP-02-AC5: Historical plan executes before candidate packaging and yields same
# decision trace when later wrapped as a candidate
# ---------------------------------------------------------------------------


def test_rp_02_bootstrap_recovery():
    plan = verify_runtime_plan(_runtime_plan())
    pipeline = _ta_only_pipeline(_strategy_ref())
    bars = _triggering_series()

    # Historical bootstrap: evaluate directly from the verified plan.
    bootstrap_runtime = CandidateRuntime.load_plan(
        plan, pipeline=pipeline, strategy_resolver=_strategy_resolver
    )
    bootstrap_trace = _run_series(bootstrap_runtime, bars)

    # Package the same plan as a candidate (provenance wrapper).
    manifest = CandidateManifest(
        candidate_id="cand_c02",
        version="1.0.0",
        runtime_plan_ref=plan.plan.to_artifact_ref(),
        completed_experiment_ref=_experiment_ref(),
        pipeline_ref=ArtifactRef(
            kind="pipeline", id="pipe_c02", version="1.0.0", sha256="0" * 64
        ),
        strategy_hashes=("0" * 64,),
        model_hashes=(),
        ordered_feature_schema_hash="0" * 64,
        universe=(_PAIR,),
        timeframe="1h",
        risk_policy_ref=_policy_ref("risk_policy"),
        cost_policy_ref=_policy_ref("cost_policy"),
        execution_policy_ref=_policy_ref("execution_policy"),
        git_sha="0" * 40,
        environment_digest="env",
        evaluation_evidence_refs=(),
    )
    candidate = VerifiedCandidate(
        candidate=manifest, candidate_digest=manifest_digest(manifest)
    )
    candidate_runtime = CandidateRuntime.load(
        candidate, plan=plan, pipeline=pipeline, strategy_resolver=_strategy_resolver
    )
    candidate_trace = _run_series(
        candidate_runtime, bars, candidate_digest=candidate.candidate_digest
    )

    assert bootstrap_trace, "expected a non-empty decision trace"
    assert len(bootstrap_trace) == len(candidate_trace)
    for index, (bootstrap_intents, candidate_intents) in enumerate(
        zip(bootstrap_trace, candidate_trace, strict=True)
    ):
        assert canonical_bytes(bootstrap_intents) == canonical_bytes(candidate_intents), (
            f"decision trace diverged at bar {index} after candidate packaging"
        )


# ---------------------------------------------------------------------------
# RP-02-AC6: Candidate stop and exit state have identical semantics before
# environment-specific venue effects
# ---------------------------------------------------------------------------


def test_rp_02_program_6():
    entry_stop = Decimal("950")
    entry_price = Decimal("1000")
    entry_atr = Decimal("10")
    qty = Decimal("0.1")

    # The candidate's entry intent carries the stop.
    from indodax_lab.contracts.decision import SignalIntent

    entry_intent = SignalIntent(
        intent_id="entry_1",
        decision_ts=_HERE,
        pair=_PAIR,
        side=OrderSide.BUY,
        desired_qty=qty,
        limit_price=entry_price,
        stop_loss=entry_stop,
        strategy_id="C02",
    )

    # The exit state is opened from the same entry: identical stop semantics.
    state = open_position(
        ExitState(),
        pair=_PAIR,
        strategy_id="C02",
        entry_price=entry_price,
        entry_atr=entry_atr,
        stop_loss=entry_intent.stop_loss,
        qty=qty,
    )
    position = state.for_pair(_PAIR)
    assert position is not None
    assert position.stop_loss == entry_intent.stop_loss

    # A mark at/below the stop produces a STOP_LOSS exit at the conservative price.
    exit_bar = _bar(0, 900.0, high=910.0, low=890.0)
    decisions = exit_decisions(state, exit_bar)
    assert len(decisions) == 1
    assert decisions[0].reason == "STOP_LOSS"
    # Conservative exit price: min(close, stop_loss) — never better than the stop.
    assert decisions[0].price == min(exit_bar.close, entry_stop)
    assert decisions[0].price == Decimal("900")

    # A mark at/above the take profit produces a TAKE_PROFIT exit.
    tp_state = open_position(
        ExitState(),
        pair=_PAIR,
        strategy_id="C02",
        entry_price=entry_price,
        entry_atr=entry_atr,
        stop_loss=entry_stop,
        take_profit=Decimal("1100"),
        qty=qty,
    )
    tp_bar = _bar(0, 1150.0, high=1160.0, low=1140.0)
    tp_decisions = exit_decisions(tp_state, tp_bar)
    assert len(tp_decisions) == 1
    assert tp_decisions[0].reason == "TAKE_PROFIT"
    assert tp_decisions[0].price == Decimal("1100")

    # Ambiguous bar spanning both stop and target: stop-first (conservative).
    ambiguous_bar = _bar(0, 1000.0, high=1200.0, low=800.0)
    ambiguous = exit_decisions(tp_state, ambiguous_bar)
    assert len(ambiguous) == 1
    assert ambiguous[0].reason == "STOP_LOSS"


# ---------------------------------------------------------------------------
# Supporting behavioral tests
# ---------------------------------------------------------------------------


def test_intent_id_is_independent_of_candidate_digest():
    a = intent_id("plan_digest", "evt_1", "sizing:node", 0)
    b = intent_id("plan_digest", "evt_1", "sizing:node", 0)
    c = intent_id("plan_digest", "evt_1", "sizing:node", 1)
    d = intent_id("other_plan", "evt_1", "sizing:node", 0)
    assert a == b
    assert a != c
    assert a != d


def test_evaluate_rejects_future_availability():
    plan = verify_runtime_plan(_runtime_plan())
    runtime = CandidateRuntime.load_plan(
        plan, pipeline=_ta_only_pipeline(_strategy_ref()), strategy_resolver=_strategy_resolver
    )
    bars = _triggering_series()
    state = _state(plan.plan_digest, bars[:-1])
    event = _event(1, bars[-1])
    # available_at after event_time is a causality violation.
    future_event = event.model_copy(update={"available_at": event.event_time + timedelta(hours=1)})
    with pytest.raises(CandidateRuntimeError) as exc:
        runtime.evaluate(future_event, state)
    assert "AVAILABILITY_VIOLATION" in str(exc.value)


def test_evaluate_rejects_state_plan_digest_mismatch():
    plan = verify_runtime_plan(_runtime_plan())
    runtime = CandidateRuntime.load_plan(
        plan, pipeline=_ta_only_pipeline(_strategy_ref()), strategy_resolver=_strategy_resolver
    )
    bars = _triggering_series()
    state = _state("f" * 64, bars[:-1])
    with pytest.raises(CandidateRuntimeError) as exc:
        runtime.evaluate(_event(1, bars[-1]), state)
    assert "PLAN_DIGEST_MISMATCH" in str(exc.value)


def test_load_rejects_candidate_plan_linkage_mismatch():
    plan = verify_runtime_plan(_runtime_plan())
    manifest = CandidateManifest(
        candidate_id="cand_bad",
        version="1.0.0",
        runtime_plan_ref=ArtifactRef(
            kind="plan", id="plan_c02", version="1.0.0", sha256="f" * 64
        ),
        completed_experiment_ref=_experiment_ref(),
        pipeline_ref=ArtifactRef(
            kind="pipeline", id="pipe_c02", version="1.0.0", sha256="0" * 64
        ),
        strategy_hashes=("0" * 64,),
        model_hashes=(),
        ordered_feature_schema_hash="0" * 64,
        universe=(_PAIR,),
        timeframe="1h",
        risk_policy_ref=_policy_ref("risk_policy"),
        cost_policy_ref=_policy_ref("cost_policy"),
        execution_policy_ref=_policy_ref("execution_policy"),
        git_sha="0" * 40,
        environment_digest="env",
        evaluation_evidence_refs=(),
    )
    candidate = VerifiedCandidate(candidate=manifest, candidate_digest=manifest_digest(manifest))
    with pytest.raises(CandidateRuntimeError) as exc:
        CandidateRuntime.load(candidate, plan=plan)
    assert "LINKAGE_MISMATCH" in str(exc.value)


def test_evaluate_emits_exit_intent_when_mark_hits_stop():
    plan = verify_runtime_plan(_runtime_plan())
    runtime = CandidateRuntime.load_plan(
        plan, pipeline=_ta_only_pipeline(_strategy_ref()), strategy_resolver=_strategy_resolver
    )
    bars = _triggering_series()
    # Open a position from the entry intent, then mark it down through the stop.
    # The C02 trigger fires on the recovery bar (the final bar of the series).
    entry_bar = bars[-1]
    entry_state = _state(plan.plan_digest, bars[:-1])
    entry_intents = runtime.evaluate(_event(1, entry_bar), entry_state)
    assert entry_intents, "expected an entry intent"
    entry = entry_intents[0]

    exit_state = open_position(
        ExitState(),
        pair=entry.pair,
        strategy_id=entry.strategy_id,
        entry_price=entry.limit_price,
        entry_atr=_last_atr(bars[:-1]),
        stop_loss=entry.stop_loss,
        qty=entry.desired_qty,
    )
    # A bar gapping far below the stop produces a SELL exit intent and, being a
    # clear downtrend bar, does not trigger a fresh C02 entry.
    stop_bar = _bar(999, 500.0, high=510.0, low=490.0)
    stop_state = _state(plan.plan_digest, bars[:-1], exit_state=exit_state)
    exit_intents = runtime.evaluate(_event(2, stop_bar), stop_state)
    assert len(exit_intents) == 1
    assert exit_intents[0].side == OrderSide.SELL
    assert exit_intents[0].pair == entry.pair
