"""RW5-01 isolated durable forward-shadow agents (integration).

Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

Contract under test (docs/implementation/CONTRACTS.md + RW5-01 spec):
- AgentFactory.register/start/pause/retire/recover/get over the shared
  RP-04 RuntimeKernel + simulator/shadow venues + ExecutionStateStore
  per-agent namespaces.
- Agent A trade cannot move B cash/positions/orders/cursor (AC0).
- Namespace collision / candidate replacement reject, prior evidence kept (AC1).
- Restart restores exactly; duplicate events are no-ops (AC2).
- Corrupt A halts A only; B keeps trading (AC3).
- Retire preserves all evidence (AC4).
- Program: isolated wallets + candidate-bound exits across partial fill
  and restart (AC5).
- Capacity (offline portion): admission bound defers with reason; slow
  consumer pause preserves other agents; resume is durable (AC6).
  Measured host artifact remains operator-owned pending evidence.

No real network / credentials / live DB. Fake clocks, tmp_path only.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import MarketBar
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.contracts.identity import ArtifactRef, manifest_digest
from indodax_lab.contracts.workbench import AgentManifest
from indodax_lab.paper.agents import AgentError, AgentFactory
from indodax_lab.runtime.candidate import CanonicalMarketEvent

BASE_TS = datetime(2025, 1, 1, tzinfo=UTC)
CASH = Decimal("10000000")

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64


def _ref(candidate_id: str, sha: str, version: str = "v1") -> ArtifactRef:
    return ArtifactRef(kind="candidate", id=candidate_id, version=version, sha256=sha)


def _manifest(
    agent_id: str,
    *,
    namespace: str | None = None,
    candidate_id: str = "cand_exp1",
    sha: str = SHA_A,
    version: str = "v1",
    cash: Decimal = CASH,
) -> AgentManifest:
    return AgentManifest(
        agent_id=agent_id,
        version=version,
        candidate_ref=_ref(candidate_id, sha),
        cohort_id="cohort_rw5",
        initial_virtual_cash=cash,
        currency="IDR",
        runtime_policy_refs=(),
        namespace_id=namespace or f"ns_{agent_id}",
        canonical_feed_identity="feed-p",
    )


def _binding(sha: str) -> SimpleNamespace:
    return SimpleNamespace(candidate_digest=sha, plan_digest=f"plan_{sha[:8]}")


def _factory(
    root: Path,
    *,
    behaviors: dict | None = None,
    bindings: dict | None = None,
    venues: dict | None = None,
    max_agents: int | None = None,
) -> AgentFactory:
    behaviors = behaviors or {}
    bindings = bindings or {}

    def _resolve(ref: ArtifactRef) -> SimpleNamespace:
        key = (ref.id, ref.version)
        if key not in bindings:
            raise KeyError(f"CANDIDATE_NOT_FOUND:{ref.id}:{ref.version}")
        bound = bindings[key]
        if bound.candidate_digest != ref.sha256:
            raise ValueError("CANDIDATE_IDENTITY_MISMATCH")
        return bound

    def _behavior(agent_id: str):
        return behaviors.get(agent_id, lambda event, state: ())

    def _venue(agent_id: str):
        if venues is not None and agent_id in venues:
            return venues[agent_id]()
        from indodax_lab.execution.simulator_venue import SimulatorVenueAdapter

        return SimulatorVenueAdapter()

    return AgentFactory(
        root,
        candidate_resolver=_resolve,
        behavior_resolver=_behavior,
        venue_factory=_venue,
        max_agents=max_agents,
    )


def _bar(pair: str, close_time: datetime, price: str = "100") -> MarketBar:
    return MarketBar(
        pair=pair,
        open_time=close_time - timedelta(minutes=1),
        close_time=close_time,
        open=Decimal(price),
        high=Decimal(price),
        low=Decimal(price),
        close=Decimal(price),
        base_volume=Decimal("1"),
        quote_volume=Decimal(price),
    )


def _event(feed_id: str, sequence: int, price: str = "100") -> CanonicalMarketEvent:
    ts = BASE_TS + timedelta(minutes=sequence)
    return CanonicalMarketEvent(
        event_id=f"{feed_id}:{sequence}",
        feed_id=feed_id,
        sequence=sequence,
        pair="btc_idr",
        event_time=ts,
        available_at=ts,
        observation=_bar("btc_idr", ts, price=price),
        quality_ref=None,
    )


def _intent(intent_id: str, price: str = "100000000", qty: str = "0.001") -> SignalIntent:
    return SignalIntent(
        intent_id=intent_id,
        decision_ts=BASE_TS,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal(qty),
        limit_price=Decimal(price),
        stop_loss=Decimal("99000000"),
        take_profit=Decimal("102000000"),
    )


def _fill_for(order_id: str, fill_id: str, qty: str = "0.001") -> object:
    from indodax_lab.backtest.orders import Fill, OrderRole

    return Fill(
        fill_id=fill_id,
        order_id=order_id,
        event_id=f"evt_{fill_id}",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        qty=Decimal(qty),
        price=Decimal("100000000"),
        fees=Decimal("1000"),
        timestamp=BASE_TS + timedelta(minutes=10),
    )


def _snapshot(factory: AgentFactory, agent_id: str) -> object:
    return factory._store_of(agent_id).restore()


def test_rw5_01_0(tmp_path: Path) -> None:
    """RW5-01-AC0: Agent A trade cannot change B cash/positions/risk/cursor."""
    behaviors = {
        "agent_a": lambda event, state: (_intent(f"A{event.sequence:02d}_entry_candA"),),
    }
    factory = _factory(
        tmp_path / "agents",
        behaviors=behaviors,
        bindings={("cand_exp1", "v1"): _binding(SHA_A), ("cand_exp2", "v1"): _binding(SHA_B)},
    )
    factory.register(_manifest("agent_a", candidate_id="cand_exp1", sha=SHA_A))
    factory.register(_manifest("agent_b", candidate_id="cand_exp2", sha=SHA_B))
    factory.start("agent_a")
    factory.start("agent_b")

    event = _event("feed-p", 1)
    factory.process("agent_a", event)

    order_ids = sorted(_snapshot(factory, "agent_a").orders)
    assert len(order_ids) == 1
    factory.apply_fill("agent_a", _fill_for(order_ids[0], "fill_a_001"))

    snap_a = _snapshot(factory, "agent_a")
    snap_b = _snapshot(factory, "agent_b")
    assert snap_a.cash == CASH - Decimal("100000") - Decimal("1000")
    assert snap_a.positions != {}
    assert snap_b.cash == CASH
    assert snap_b.positions == {}
    assert snap_b.orders == {}
    assert factory.get("agent_b").cursor is None
    assert factory.get("agent_a").cursor == "feed-p:1"

    # B processing its (no-op) decision cannot move A either.
    factory.process("agent_b", event)
    assert _snapshot(factory, "agent_a").cash == snap_a.cash
    assert factory.get("agent_b").cursor == "feed-p:1"
    assert _snapshot(factory, "agent_b").cash == CASH

    # Research path carries no live writer authority.
    for module in ("src/indodax_lab/paper/agents.py", "src/indodax_lab/cli/shadow.py"):
        source = (Path.cwd() / module).read_text(encoding="utf-8")
        assert "indodax_trading" not in source


def test_rw5_01_1(tmp_path: Path) -> None:
    """RW5-01-AC1: namespace collision or candidate replacement rejects."""
    factory = _factory(
        tmp_path / "agents", bindings={("cand_exp1", "v1"): _binding(SHA_A)}
    )
    first = factory.register(_manifest("agent_a", namespace="ns_shared"))
    assert first.lifecycle == "REGISTERED"

    with pytest.raises(AgentError, match="AGENT_NAMESPACE_COLLISION"):
        factory.register(
            _manifest("agent_b", namespace="ns_shared", candidate_id="cand_exp1")
        )
    assert factory.count() == 1

    with pytest.raises(AgentError, match="AGENT_CANDIDATE_REPLACEMENT_REJECTED"):
        factory.register(_manifest("agent_a", namespace="ns_other", sha=SHA_B))
    assert factory.count() == 1
    assert factory.get("agent_a").manifest_digest == first.manifest_digest
    assert factory.get("agent_a").namespace == "ns_shared"

    # Identical bytes are idempotent, not a conflict.
    same = factory.register(_manifest("agent_a", namespace="ns_shared"))
    assert same.manifest_digest == first.manifest_digest
    assert factory.count() == 1


def test_rw5_01_2(tmp_path: Path) -> None:
    """RW5-01-AC2: restart restores exactly with duplicate event no-op."""
    behaviors = {
        "agent_a": lambda event, state: (_intent(f"A{event.sequence:02d}_entry_candA"),),
    }
    root = tmp_path / "agents"
    factory = _factory(
        root, behaviors=behaviors, bindings={("cand_exp1", "v1"): _binding(SHA_A)}
    )
    factory.register(_manifest("agent_a"))
    factory.start("agent_a")
    events = [_event("feed-p", 1), _event("feed-p", 2)]
    for event in events:
        factory.process("agent_a", event)
    before = _snapshot(factory, "agent_a")
    assert len(before.orders) == 2
    assert factory.get("agent_a").cursor == "feed-p:2"

    # Restart: fresh factory over the same durable root.
    restarted = _factory(
        root, behaviors=behaviors, bindings={("cand_exp1", "v1"): _binding(SHA_A)}
    )
    assert restarted.get("agent_a").lifecycle == "RUNNING"
    assert restarted.get("agent_a").cursor == "feed-p:2"
    report = restarted.recover("agent_a")
    assert report.status == "RECOVERED"
    assert report.cursor == "feed-p:2"
    assert restarted.get("agent_a").lifecycle == "PAUSED"
    restarted.start("agent_a")

    for event in events:
        result = restarted.process("agent_a", event)
        assert result.status == "ACKNOWLEDGED"
    after = _snapshot(restarted, "agent_a")
    assert after.cash == before.cash
    assert after.positions == before.positions
    assert len(after.orders) == 2
    assert after.revision == before.revision


def test_rw5_01_3(tmp_path: Path) -> None:
    """RW5-01-AC3: corrupt A halts A without corrupting B."""
    behaviors = {
        "agent_a": lambda event, state: (_intent(f"A{event.sequence:02d}_entry_candA"),),
        "agent_b": lambda event, state: (_intent(f"B{event.sequence:02d}_entry_candB"),),
    }
    factory = _factory(
        tmp_path / "agents",
        behaviors=behaviors,
        bindings={("cand_exp1", "v1"): _binding(SHA_A), ("cand_exp2", "v1"): _binding(SHA_B)},
    )
    factory.register(_manifest("agent_a", candidate_id="cand_exp1", sha=SHA_A))
    factory.register(_manifest("agent_b", candidate_id="cand_exp2", sha=SHA_B))
    factory.start("agent_a")
    factory.start("agent_b")

    event = _event("feed-p", 1)
    factory.process("agent_a", event)
    cash_a = _snapshot(factory, "agent_a").cash

    # Same event ID with different bytes delivered to A: corruption.
    corrupt = _event("feed-p", 1, price="999")
    with pytest.raises(AgentError, match="AGENT_EVENT_CONFLICT"):
        factory.process("agent_a", corrupt)
    halted = factory.get("agent_a")
    assert halted.lifecycle == "HALTED"
    assert any("AGENT_EVENT_CONFLICT" in ref for ref in halted.incident_refs)
    assert _snapshot(factory, "agent_a").cash == cash_a
    assert len(_snapshot(factory, "agent_a").orders) == 1

    with pytest.raises(AgentError, match="AGENT_NOT_RUNNING"):
        factory.process("agent_a", _event("feed-p", 2))

    # B is unaffected and keeps trading on the clean feed.
    factory.process("agent_b", event)
    factory.process("agent_b", _event("feed-p", 2))
    assert factory.get("agent_b").lifecycle == "RUNNING"
    assert len(_snapshot(factory, "agent_b").orders) == 2
    assert factory.get("agent_b").cursor == "feed-p:2"


def test_rw5_01_4(tmp_path: Path) -> None:
    """RW5-01-AC4: retire preserves all evidence."""
    behaviors = {
        "agent_a": lambda event, state: (_intent(f"A{event.sequence:02d}_entry_candA"),),
    }
    root = tmp_path / "agents"
    factory = _factory(
        root, behaviors=behaviors, bindings={("cand_exp1", "v1"): _binding(SHA_A)}
    )
    manifest = _manifest("agent_a")
    digest = manifest_digest(manifest)
    factory.register(manifest)
    factory.start("agent_a")
    factory.process("agent_a", _event("feed-p", 1))
    order_ids = sorted(_snapshot(factory, "agent_a").orders)
    factory.apply_fill("agent_a", _fill_for(order_ids[0], "fill_a_001"))
    cash_before = _snapshot(factory, "agent_a").cash

    retired = factory.retire("agent_a")
    assert retired.lifecycle == "RETIRED"
    assert retired.cursor == "feed-p:1"
    assert retired.manifest_digest == digest

    # All evidence remains queryable after retirement.
    record = factory.get("agent_a")
    assert record.lifecycle == "RETIRED"
    assert record.manifest_digest == digest
    assert record.cursor == "feed-p:1"
    snap = _snapshot(factory, "agent_a")
    assert snap.cash == cash_before
    assert len(snap.orders) == 1

    with pytest.raises(AgentError, match="AGENT_RETIRED"):
        factory.process("agent_a", _event("feed-p", 2))

    # Read-only CLI queries see the retired agent with its evidence.
    from indodax_lab.cli.shadow import main as shadow_main

    out = io.StringIO()
    assert shadow_main(["--root", str(root), "show", "--agent-id", "agent_a"], stdout=out) == 0
    shown = json.loads(out.getvalue())
    assert shown["agent_id"] == "agent_a"
    assert shown["lifecycle"] == "RETIRED"
    assert shown["manifest_digest"] == digest
    out = io.StringIO()
    assert shadow_main(["--root", str(root), "list"], stdout=out) == 0
    listed = json.loads(out.getvalue())
    assert [row["agent_id"] for row in listed] == ["agent_a"]


def test_rw5_01_program_5(tmp_path: Path) -> None:
    """RW5-01-AC5: isolated wallets + candidate-bound exits across partial
    fill and restart."""
    held = {"opened": False}

    def _agent_a_behavior(event: CanonicalMarketEvent, state: object) -> tuple:
        if not held["opened"]:
            held["opened"] = True
            return (_intent(f"A{event.sequence:02d}_entry_candA"),)
        if event.sequence >= 2:
            return (
                SignalIntent(
                    intent_id=f"A{event.sequence:02d}_exit_candA",
                    decision_ts=event.event_time,
                    pair="btc_idr",
                    side=OrderSide.SELL,
                    desired_qty=Decimal("0.0004"),
                    limit_price=Decimal("90000000"),
                ),
            )
        return ()

    root = tmp_path / "agents"
    factory = _factory(
        root,
        behaviors={"agent_a": _agent_a_behavior},
        bindings={("cand_exp1", "v1"): _binding(SHA_A), ("cand_exp2", "v1"): _binding(SHA_B)},
    )
    factory.register(_manifest("agent_a", candidate_id="cand_exp1", sha=SHA_A))
    factory.register(_manifest("agent_b", candidate_id="cand_exp2", sha=SHA_B))
    factory.start("agent_a")
    factory.start("agent_b")

    entry = _event("feed-p", 1, price="100000000")
    factory.process("agent_a", entry)
    factory.process("agent_b", entry)
    order_ids = sorted(_snapshot(factory, "agent_a").orders)
    assert len(order_ids) == 1

    # Partial fill moves A's wallet only.
    result = factory.apply_fill("agent_a", _fill_for(order_ids[0], "fill_a_p1", qty="0.0004"))
    assert result.is_duplicate is False
    snap_a = _snapshot(factory, "agent_a")
    assert snap_a.cash == CASH - Decimal("40000") - Decimal("1000")
    assert snap_a.positions["btc_idr"]["base_qty"] == Decimal("0.0004")
    assert _snapshot(factory, "agent_b").cash == CASH
    assert _snapshot(factory, "agent_b").positions == {}

    # Stop-gap bar fires A's candidate-bound exit; B stays flat.
    crash = _event("feed-p", 2, price="90000000")
    factory.process("agent_a", crash)
    factory.process("agent_b", crash)
    orders_a = _snapshot(factory, "agent_a").orders
    exits = [o for o in orders_a.values() if str(o.get("side")).upper() == "SELL"]
    assert len(exits) == 1
    assert _snapshot(factory, "agent_b").orders == {}
    assert _snapshot(factory, "agent_b").cash == CASH

    # Restart: duplicate fill is a no-op, replayed events add nothing.
    restarted = _factory(
        root,
        behaviors={"agent_a": _agent_a_behavior},
        bindings={("cand_exp1", "v1"): _binding(SHA_A), ("cand_exp2", "v1"): _binding(SHA_B)},
    )
    restarted.recover("agent_a")
    restarted.recover("agent_b")
    restarted.start("agent_a")
    restarted.start("agent_b")
    cash_before = _snapshot(restarted, "agent_a").cash
    dup = restarted.apply_fill("agent_a", _fill_for(order_ids[0], "fill_a_p1", qty="0.0004"))
    assert dup.is_duplicate is True
    assert _snapshot(restarted, "agent_a").cash == cash_before
    restarted.process("agent_a", entry)
    restarted.process("agent_a", crash)
    assert len(_snapshot(restarted, "agent_a").orders) == 2
    assert _snapshot(factory, "agent_b").cash == CASH


def test_rw5_01_capacity_6(tmp_path: Path) -> None:
    """RW5-01-AC6 (offline portion): admission reserves bounded slots and
    defers with reason; slow-consumer pause preserves other agents; resume
    is durable.

    Measured host artifact (ASUS mixed-load qualification) remains pending
    operator evidence; this test pins only the offline admission/defer and
    resume-durable mechanism, never a host throughput claim.
    """
    behaviors = {
        "agent_a": lambda event, state: (_intent(f"A{event.sequence:02d}_entry_candA"),),
        "agent_b": lambda event, state: (_intent(f"B{event.sequence:02d}_entry_candB"),),
    }
    bindings = {("cand_exp1", "v1"): _binding(SHA_A), ("cand_exp2", "v1"): _binding(SHA_B)}
    root = tmp_path / "agents"
    factory = _factory(root, behaviors=behaviors, bindings=bindings, max_agents=2)
    factory.register(_manifest("agent_a", candidate_id="cand_exp1", sha=SHA_A))
    factory.register(_manifest("agent_b", candidate_id="cand_exp2", sha=SHA_B))
    factory.start("agent_a")
    factory.start("agent_b")

    with pytest.raises(AgentError, match="AGENT_ADMISSION_DEFERRED"):
        factory.register(_manifest("agent_c", namespace="ns_agent_c"))
    assert factory.count() == 2

    events = [_event("feed-p", seq) for seq in range(1, 4)]
    for event in events[:2]:
        factory.process("agent_a", event)
        factory.process("agent_b", event)

    # Slow consumer A pauses with gap evidence; B keeps consuming.
    paused = factory.pause("agent_a")
    assert paused.lifecycle == "PAUSED"
    assert paused.cursor == "feed-p:2"
    factory.process("agent_b", events[2])
    assert factory.get("agent_b").cursor == "feed-p:3"
    assert factory.get("agent_a").cursor == "feed-p:2"
    with pytest.raises(AgentError, match="AGENT_NOT_RUNNING"):
        factory.process("agent_a", events[2])

    # Durable resume: recover replays nothing, then A catches up exactly.
    report = factory.recover("agent_a")
    assert report.status == "RECOVERED"
    assert report.cursor == "feed-p:2"
    assert report.coverage_gap == "feed-p:2"
    factory.start("agent_a")
    factory.process("agent_a", events[2])
    assert factory.get("agent_a").cursor == "feed-p:3"
    assert len(_snapshot(factory, "agent_a").orders) == 3
    assert len(_snapshot(factory, "agent_b").orders) == 3


def test_rw5_01_2_window_rehydration(tmp_path: Path) -> None:
    """RW5-01-AC2 (windows): restart rehydrates feature/exit windows from
    the durable inbox journal — the resumed agent observes the same
    feature-bar count and exit state as an uninterrupted agent."""
    seen_restarted: list = []
    seen_control: list = []

    def _recorder(seen: list):
        def _evaluate(event: CanonicalMarketEvent, state: object) -> tuple:
            bars = state.feature_state.bars if state.feature_state else ()
            seen.append((event.sequence, len(bars), state.exit_state))
            return ()

        return _evaluate

    bindings = {("cand_exp1", "v1"): _binding(SHA_A)}
    root = tmp_path / "agents"
    factory = _factory(
        root,
        behaviors={"agent_a": _recorder(seen_restarted)},
        bindings=bindings,
    )
    factory.register(_manifest("agent_a"))
    factory.start("agent_a")
    events = [_event("feed-p", seq, price=str(100 + seq)) for seq in range(1, 4)]
    for event in events:
        factory.process("agent_a", event)
    assert [row[1] for row in seen_restarted] == [0, 1, 2]

    control = _factory(
        tmp_path / "control",
        behaviors={"agent_a": _recorder(seen_control)},
        bindings=bindings,
    )
    control.register(_manifest("agent_a"))
    control.start("agent_a")
    for event in events:
        control.process("agent_a", event)
    fourth = _event("feed-p", 4, price="104")
    control.process("agent_a", fourth)
    assert seen_control[-1][1] == 3

    restarted = _factory(root, behaviors={}, bindings=bindings)
    restarted.recover("agent_a")
    restarted.start("agent_a")
    # Duplicate replay re-evaluates nothing.
    restarted._kernels.clear()
    before = len(seen_restarted)
    for event in events:
        result = restarted.process("agent_a", event)
        assert result.status == "ACKNOWLEDGED"
    assert len(seen_restarted) == before
    # A fresh behavior on the rebuilt kernel observes the rehydrated window.
    restarted._kernels.clear()
    restarted._resolve_behavior = lambda _agent_id: _recorder(seen_restarted)
    restarted.process("agent_a", fourth)
    assert seen_restarted[-1][1] == 3
    assert seen_restarted[-1] == seen_control[-1]


def test_rw5_01_5_registry_bound_candidate(tmp_path: Path) -> None:
    """RW5-01-AC5 (binding): the agent register path consumes a real
    RW4-01 CandidateRegistry package (SUCCESS experiment + verify) and a
    real CandidateRuntime.load evaluator, not fake digest namespaces."""
    import hashlib
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from indodax_lab.contracts.workbench import (
        PipelineManifest,
        PipelineNode,
        RuntimePlan,
        VerifiedRuntimePlan,
    )
    from indodax_lab.evaluation.candidates import CandidateRegistry, ExperimentEvidence
    from indodax_lab.runtime.candidate import CandidateRuntime
    from indodax_lab.strategies.base import RegisteredStrategy, StrategySpecification

    now = _datetime(2026, 1, 1, 12, 0, tzinfo=_UTC)
    blobs: dict[str, bytes] = {}

    def _put(payload: bytes) -> str:
        digest = hashlib.sha256(payload).hexdigest()
        blobs[digest] = payload
        return digest

    def _resolve(ref: ArtifactRef) -> bytes:
        try:
            return blobs[ref.sha256]
        except KeyError as exc:
            raise LookupError(f"EVIDENCE_MISSING:{ref.kind}:{ref.id}") from exc

    policy = ArtifactRef(kind="policy", id="pol", version="v1", sha256=_put(b"policy-bytes"))
    strategy_ref = ArtifactRef(
        kind="strategy_manifest", id="strat_rw5", version="v1", sha256=_put(b"strat-bytes")
    )
    pipeline = PipelineManifest(
        pipeline_id="pipe_rw5",
        version="1.0.0",
        nodes=(PipelineNode(node_id="strat_rw5", kind="ta", output_port="out"),),
        edges=(),
        component_refs=(strategy_ref,),
        dataset_timeframe_constraints={},
        sizing_policy_ref=policy,
        exit_policy_ref=policy,
        risk_policy_ref=policy,
        cost_policy_ref=policy,
        execution_policy_ref=policy,
    )
    pipeline_ref = ArtifactRef(
        kind="pipeline",
        id="pipe_rw5",
        version="1.0.0",
        sha256=hashlib.sha256(pipeline.model_dump_json().encode()).hexdigest(),
    )
    blobs[pipeline_ref.sha256] = pipeline.model_dump_json().encode()
    plan = RuntimePlan(
        plan_id="plan_rw5",
        version="1.0.0",
        universe=("btc_idr",),
        timeframe="1h",
        dataset_refs=(),
        pipeline_ref=pipeline_ref,
        feature_schema_hash=_put(b"features"),
        ordered_feature_names=("ema_fast", "ema_slow", "atr_14"),
        sizing_policy_ref=policy,
        exit_policy_ref=policy,
        risk_policy_ref=policy,
        cost_policy_ref=policy,
        execution_policy_ref=policy,
        git_sha="aa" * 20,
        environment_digest="bb" * 32,
        seed=7,
    )
    verified_plan = VerifiedRuntimePlan(
        plan=plan, plan_digest=manifest_digest(plan), verified_at_utc=now
    )
    result_path = tmp_path / "result.json"
    result_path.write_bytes(b'{"result_digest":"digest-1"}')
    experiment = ExperimentEvidence(
        experiment_id="exp_rw5_001",
        status="SUCCESS",
        plan=verified_plan,
        result_digest="digest-1",
        artifact_path=str(result_path),
    )
    registry = CandidateRegistry(
        root=tmp_path / "candidates", clock=lambda: now, artifact_resolver=_resolve
    )
    manifest = registry.package(experiment.experiment_id, "review-pass-001", experiment=experiment)
    ref = manifest.to_artifact_ref()
    assert registry.get(ref) == manifest
    verified = registry.verify(ref)
    assert verified.candidate_digest == manifest_digest(manifest)

    def _decide(frame: object) -> list:
        # Stateless w.r.t. the logic hash (which covers closure values):
        # emit once, on the first feed minute only.
        minute = getattr(frame, "as_of", BASE_TS).minute
        if minute == 1:
            return [
                SignalIntent(
                    intent_id="raw_first",
                    decision_ts=BASE_TS,
                    pair="btc_idr",
                    side=OrderSide.BUY,
                    desired_qty=Decimal("0.001"),
                    limit_price=Decimal("100000000"),
                    stop_loss=Decimal("99000000"),
                    take_profit=Decimal("102000000"),
                )
            ]
        return []

    strategy = RegisteredStrategy(
        specification=StrategySpecification(
            strategy_id="strat_rw5",
            version="v1",
            family="ta",
            timeframes=["1h"],
            parameters={},
            risk_profile={},
            split="test",
        ),
        decide_fn=_decide,
    )
    runtime = CandidateRuntime.load(
        verified, plan=verified_plan, pipeline=pipeline, strategy_resolver=lambda _ref: strategy
    )

    root = tmp_path / "agents"
    factory = AgentFactory(
        root,
        candidate_resolver=lambda _ref: runtime,
        behavior_resolver=lambda _agent_id: runtime.evaluate,
    )
    record = factory.register(
        AgentManifest(
            agent_id="agent_real",
            version="v1",
            candidate_ref=ref,
            cohort_id="cohort_rw5",
            initial_virtual_cash=CASH,
            currency="IDR",
            runtime_policy_refs=(),
            namespace_id="ns_agent_real",
            canonical_feed_identity="feed-p",
        )
    )
    assert record.candidate_ref.sha256 == verified.candidate_digest
    factory.start("agent_real")
    events = [_event("feed-p", 1), _event("feed-p", 2)]
    for event in events:
        assert factory.process("agent_real", event).status == "ACKNOWLEDGED"
    # The real evaluator's one entry intent became exactly one kernel order.
    assert len(_snapshot(factory, "agent_real").orders) == 1
    assert factory.get("agent_real").cursor == "feed-p:2"

    # Restart over the same root: duplicate replay is a no-op and the real
    # evaluator keeps passing feature identity on new events.
    restarted = AgentFactory(
        root,
        candidate_resolver=lambda _ref: runtime,
        behavior_resolver=lambda _agent_id: runtime.evaluate,
    )
    restarted.recover("agent_real")
    restarted.start("agent_real")
    for event in events:
        assert restarted.process("agent_real", event).status == "ACKNOWLEDGED"
    assert len(_snapshot(restarted, "agent_real").orders) == 1
    assert restarted.process("agent_real", _event("feed-p", 3)).status == "ACKNOWLEDGED"
    assert restarted.get("agent_real").cursor == "feed-p:3"
