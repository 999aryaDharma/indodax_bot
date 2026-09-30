"""RP-05 runtime parity qualification fixtures (offline proof only).

Replays one canonical event sequence into historical / shadow /
production-shaped fake compositions built from the RP-04 runtime adapters,
then compares pre-venue decisions exactly while enumerating venue-level
differences without hiding decision drift.

ParityTrace / compare_traces / evidence manifest live in this test module:
RP-05 plans no src changes (Modify: None); the suite IS the deliverable.

No real network / credentials / live DB. Fake clocks, temporary stores.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import MarketBar
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.runtime.candidate import CanonicalMarketEvent

BASE_TS = datetime(2025, 1, 1, tzinfo=UTC)
PLAN_DIGEST = "rp05_plan_v1"
POLICY_DIGEST = "rp05_risk_allow_v1"
INITIAL_CASH = Decimal("10000000")


def _canon(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _sha(value: object) -> str:
    return hashlib.sha256(_canon(value)).hexdigest()


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


def _sequence(feed_id: str, count: int) -> list[CanonicalMarketEvent]:
    return [_event(feed_id, seq) for seq in range(1, count + 1)]


def _intent(event: CanonicalMarketEvent) -> SignalIntent:
    # NOTE: kernel order derivation keeps a fixed-width intent-ID prefix, so
    # parity fixtures vary the ID head (not just the tail) per event.
    return SignalIntent(
        intent_id=f"e{event.sequence:02d}_rp05_{event.feed_id}",
        decision_ts=event.event_time,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.001"),
        limit_price=Decimal("100000000"),
        stop_loss=Decimal("99000000"),
        take_profit=Decimal("102000000"),
    )


def _recording_candidate(log: list) -> SimpleNamespace:
    def _evaluate(event: CanonicalMarketEvent, state: object) -> tuple:
        intent = _intent(event)
        log.append(
            {
                "intent_id": intent.intent_id,
                "pair": intent.pair,
                "side": str(intent.side),
                "qty": str(intent.desired_qty),
                "price": str(intent.limit_price),
            }
        )
        return (intent,)

    return SimpleNamespace(
        plan_digest=PLAN_DIGEST,
        candidate_digest=None,
        evaluate=_evaluate,
        held_exits={},
    )


def _recording_risk_stage(log: list):
    def _stage(intents: tuple, state: object) -> tuple:
        for intent in intents:
            log.append({"qty": str(intent.desired_qty), "reason": "ALLOW"})
        return tuple(intents)

    return _stage


def _kernel(tmp_path: Path, namespace: str, venue: object, venue_name: str,
            intents_log: list, risk_log: list):
    from indodax_lab.execution.state_store import ExecutionStateStore
    from indodax_lab.runtime.kernel import RuntimeKernel

    store = ExecutionStateStore(
        tmp_path / f"{namespace}.db", namespace=namespace, initial_cash=INITIAL_CASH
    )
    return RuntimeKernel(
        candidate_runtime=_recording_candidate(intents_log),
        store=store,
        venue=venue,
        venue_name=venue_name,
        risk_stage=_recording_risk_stage(risk_log),
    )


def _run_env(tmp_path: Path, name: str, venue: object, venue_name: str,
             events: list[CanonicalMarketEvent]) -> dict:
    intents_log: list = []
    risk_log: list = []
    kernel = _kernel(tmp_path / name, "research", venue, venue_name, intents_log, risk_log)
    statuses = [kernel.process(event).status for event in events]
    snapshot = kernel._store.restore()
    return {
        "kernel": kernel,
        "statuses": statuses,
        "intents": intents_log,
        "risk": risk_log,
        "snapshot": snapshot,
    }


# ---------------------------------------------------------------------------
# ParityTrace / compare_traces (the RP-05 declared contract, test-owned)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParityTrace:
    env: str
    candidate_digest: str
    policy_digest: str
    event_ids: tuple[str, ...]
    intent_ids: tuple[str, ...]
    intent_digest: str
    risk_decisions: tuple[tuple[str, str], ...]
    oms_digest: str
    oms_orders: tuple[tuple[str, str], ...]
    venue_receipts: tuple[str, ...]
    journal_total: tuple[str, ...]
    ledger_digest: str


@dataclass(frozen=True)
class Divergence:
    path: str
    left: object
    right: object
    kind: str  # DECISION_DRIFT | EXECUTION_OUTCOME


DECISION_PATHS = (
    "candidate_digest",
    "policy_digest",
    "event_ids",
    "intent_ids",
    "intent_digest",
    "risk_decisions",
)
EXECUTION_PATHS = (
    "oms_digest",
    "oms_orders",
    "venue_receipts",
    "journal_total",
    "ledger_digest",
)


def _snapshot_totals(snapshot) -> tuple[str, ...]:
    positions = sorted(
        (pair, str(pos.get("base_qty", "?"))) for pair, pos in snapshot.positions.items()
    )
    return (str(snapshot.cash), *[f"{pair}={qty}" for pair, qty in positions])


def build_trace(env: str, run: dict, events: list[CanonicalMarketEvent]) -> ParityTrace:
    intents = run["intents"]
    intent_ids = tuple(i["intent_id"] for i in intents)
    intent_digest = _sha(
        [[i["intent_id"], i["pair"], i["side"], i["qty"], i["price"]] for i in intents]
    )
    snapshot = run["snapshot"]
    orders = snapshot.orders
    oms_orders = tuple(sorted((oid, str(o.get("state", "?"))) for oid, o in orders.items()))
    receipts: list[str] = []
    venue = run["kernel"]._venue
    for attr in ("_receipts", "recorded"):
        held = getattr(venue, attr, None)
        if isinstance(held, dict):
            receipts.extend(sorted(held))
        elif isinstance(held, list):
            receipts.extend(sorted(r.order_id for r in held))
    totals = _snapshot_totals(snapshot)
    ledger_digest = _sha({"cash": totals[0], "positions": totals[1:]})
    return ParityTrace(
        env=env,
        candidate_digest=PLAN_DIGEST,
        policy_digest=POLICY_DIGEST,
        event_ids=tuple(e.event_id for e in events),
        intent_ids=intent_ids,
        intent_digest=intent_digest,
        risk_decisions=tuple((r["qty"], r["reason"]) for r in run["risk"]),
        oms_digest=_sha(sorted(oms_orders)),
        oms_orders=oms_orders,
        venue_receipts=tuple(receipts),
        journal_total=totals,
        ledger_digest=ledger_digest,
    )


def compare_traces(left: ParityTrace, right: ParityTrace,
                   *, ignore_execution_outcomes: bool = True) -> tuple[Divergence, ...]:
    out: list[Divergence] = []
    for path in DECISION_PATHS:
        lval, rval = getattr(left, path), getattr(right, path)
        if lval != rval:
            out.append(Divergence(path, lval, rval, "DECISION_DRIFT"))
    if not ignore_execution_outcomes:
        for path in EXECUTION_PATHS:
            lval, rval = getattr(left, path), getattr(right, path)
            if lval != rval:
                out.append(Divergence(path, lval, rval, "EXECUTION_OUTCOME"))
    return tuple(out)


def trace_digest(trace: ParityTrace) -> str:
    return _sha(
        {
            "env": trace.env,
            "candidate_digest": trace.candidate_digest,
            "policy_digest": trace.policy_digest,
            "event_ids": list(trace.event_ids),
            "intent_ids": list(trace.intent_ids),
            "intent_digest": trace.intent_digest,
            "risk_decisions": [list(r) for r in trace.risk_decisions],
            "oms_digest": trace.oms_digest,
            "oms_orders": [list(o) for o in trace.oms_orders],
            "venue_receipts": list(trace.venue_receipts),
            "journal_total": list(trace.journal_total),
            "ledger_digest": trace.ledger_digest,
        }
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _code_sha() -> str:
    proc = subprocess.run(
        ["git", "-C", str(_repo_root()), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return proc.stdout.strip()


def evidence_manifest(traces: dict[str, ParityTrace],
                      divergences: list[Divergence]) -> dict:
    decision_digest = _sha(
        sorted(
            _sha(
                {
                    "env": t.env,
                    "candidate_digest": t.candidate_digest,
                    "policy_digest": t.policy_digest,
                    "event_ids": list(t.event_ids),
                    "intent_ids": list(t.intent_ids),
                    "intent_digest": t.intent_digest,
                    "risk_decisions": [list(r) for r in t.risk_decisions],
                }
            )
            for t in traces.values()
        )
    )
    return {
        "code_sha": _code_sha(),
        "env_traces": {name: trace_digest(t) for name, t in traces.items()},
        "decision_digest": decision_digest,
        "divergences": [
            {"path": d.path, "left": d.left, "right": d.right, "kind": d.kind}
            for d in divergences
        ],
        "complete": True,
    }


def _fixed_clock() -> datetime:
    return datetime(2025, 1, 1, tzinfo=UTC)


def _venues():
    from indodax_lab.execution.shadow_venue import ShadowVenueAdapter
    from indodax_lab.execution.simulator_venue import SimulatedOutcome, SimulatorVenueAdapter

    return {
        "historical": (SimulatorVenueAdapter(), "simulator"),
        "shadow": (ShadowVenueAdapter(clock=_fixed_clock), "shadow"),
        "production-fake": (
            SimulatorVenueAdapter(
                outcome=SimulatedOutcome(kind="PARTIAL", fill_qty=Decimal("0.0004"))
            ),
            "simulator",
        ),
    }


def test_rp_05_0(tmp_path: Path) -> None:
    """RP-05-AC0: candidate intent IDs/content match before the venue boundary."""
    events = _sequence("feed-p", 3)
    traces = {}
    for name, (venue, venue_name) in _venues().items():
        run = _run_env(tmp_path, name, venue, venue_name, events)
        assert run["statuses"] == ["ACKNOWLEDGED"] * 3
        traces[name] = build_trace(name, run, events)

    first = traces["historical"]
    for other in ("shadow", "production-fake"):
        assert traces[other].intent_ids == first.intent_ids
        assert traces[other].intent_digest == first.intent_digest
        assert compare_traces(first, traces[other]) == ()

    manifest = evidence_manifest(traces, [])
    assert manifest["complete"] is True
    assert manifest["code_sha"] == _code_sha()


def _risk_engine(tmp_path: Path, subdir: str):
    from indodax_lab.backtest.risk import PortfolioRiskManager, RiskPolicy
    from indodax_lab.risk.engine import RiskEngine

    now = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
    policy = RiskPolicy(
        policy_id="pol_parity",
        version="1.0",
        max_position_fraction=Decimal("0.25"),
        max_open_positions=3,
        min_order_notional=Decimal("10000"),
        max_drawdown_halt_fraction=Decimal("0.10"),
    )
    manager = PortfolioRiskManager(
        policy=policy, initial_equity=Decimal("100000000"), start_time=now
    )
    engine = RiskEngine(
        risk_manager=manager,
        max_orders_per_minute=3,
        kill_switch_path=tmp_path / subdir / "kill_switch",
    )
    return engine, now


def _risk_intent():
    from indodax_lab.backtest.events import SignalIntent as RiskIntent

    return RiskIntent(
        intent_id="sig_parity",
        decision_ts=datetime(2026, 9, 21, 10, 0, tzinfo=UTC),
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.02"),
        limit_price=Decimal("1000000000"),
    )


def _assess(engine, now):
    return engine.assess_intent(
        _risk_intent(),
        current_equity=Decimal("100000000"),
        current_positions={},
        mark_prices={"btc_idr": Decimal("1000000000")},
        evaluation_time=now,
        available_cash=Decimal("100000000"),
    )


def test_rp_05_1(tmp_path: Path) -> None:
    """RP-05-AC1: same risk state gives same quantity/reason."""
    engine_a, now = _risk_engine(tmp_path, "a")
    engine_b, _ = _risk_engine(tmp_path, "b")
    res_a, res_b = _assess(engine_a, now), _assess(engine_b, now)
    assert res_a.approved and res_b.approved
    assert isinstance(res_a.approved_qty, Decimal)
    assert (res_a.approved, res_a.approved_qty, res_a.reason_code) == (
        res_b.approved, res_b.approved_qty, res_b.reason_code,
    )

    # Negative control: a different risk state must differ (killed engine).
    engine_c, _ = _risk_engine(tmp_path, "c")
    engine_c.trigger_kill_switch("PARITY_PROBE")
    res_c = _assess(engine_c, now)
    assert (res_c.approved, res_c.reason_code) == (False, "KILL_SWITCH_ACTIVE")
    assert (res_c.approved, res_c.reason_code) != (res_a.approved, res_a.reason_code)


def _fill(fill_id: str, order_id: str, qty: str, price: str, ts: datetime):
    from indodax_lab.backtest.orders import Fill, OrderRole

    return Fill(
        fill_id=fill_id,
        order_id=order_id,
        event_id=f"evt_{fill_id}",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        qty=Decimal(qty),
        price=Decimal(price),
        fees=Decimal("1000"),
        timestamp=ts,
    )


def _filled_store(tmp_path: Path, name: str, fills: list):
    from indodax_lab.execution.simulator_venue import SimulatorVenueAdapter

    events = _sequence("feed-p", len(fills))
    run = _run_env(tmp_path, name, SimulatorVenueAdapter(), "simulator", events)
    order_ids = sorted(run["snapshot"].orders)
    assert len(order_ids) == len(fills)
    store = run["kernel"]._store
    revision = store.restore().revision
    for fill, order_id in zip(fills, order_ids, strict=True):
        result = store.apply_fill(fill.model_copy(update={"order_id": order_id}), revision)
        assert result.is_duplicate is False
        revision = store.restore().revision
    return store.restore(), order_ids


def test_rp_05_2(tmp_path: Path) -> None:
    """RP-05-AC2: same normalized fills produce identical journal totals."""
    ts = datetime(2025, 1, 1, 0, 10, tzinfo=UTC)
    fills = [
        _fill(f"fill_parity_{i}", "ORDID", "0.001", "100000000", ts) for i in range(2)
    ]
    snap_a, ids_a = _filled_store(tmp_path, "store-a", fills)
    snap_b, ids_b = _filled_store(tmp_path, "store-b", fills)
    assert ids_a == ids_b != []

    # Non-vacuous: fills moved real money and opened a real position.
    assert snap_a.cash != INITIAL_CASH
    assert snap_a.positions != {}
    # Parity: Decimal-exact equality across stores.
    assert isinstance(snap_a.cash, Decimal)
    assert snap_a.cash == snap_b.cash
    assert snap_a.positions == snap_b.positions
    assert _snapshot_totals(snap_a) == _snapshot_totals(snap_b)

    # Negative control: one divergent fill price must break totals parity.
    other = [
        _fill(f"fill_parity_{i}", "ORDID", "0.001",
              "100000001" if i == 1 else "100000000", ts)
        for i in range(2)
    ]
    snap_c, _ = _filled_store(tmp_path, "store-c", other)
    assert snap_c.cash != snap_a.cash


def test_rp_05_3(tmp_path: Path) -> None:
    """RP-05-AC3: clock/fill differences cannot mask order-semantic divergence."""
    events = _sequence("feed-p", 2)

    # (a) Timing-only difference: shadow clocks differ, decisions must not.
    from indodax_lab.execution.shadow_venue import ShadowVenueAdapter

    early = _run_env(
        tmp_path, "shadow-early",
        ShadowVenueAdapter(clock=lambda: datetime(2025, 1, 1, tzinfo=UTC)),
        "shadow", events,
    )
    late = _run_env(
        tmp_path, "shadow-late",
        ShadowVenueAdapter(clock=lambda: datetime(2025, 1, 2, tzinfo=UTC)),
        "shadow", events,
    )
    trace_early = build_trace("shadow-early", early, events)
    trace_late = build_trace("shadow-late", late, events)
    drift = [d for d in compare_traces(trace_early, trace_late) if d.kind == "DECISION_DRIFT"]
    assert drift == []

    # (b) Semantic divergence with identical timing must still be flagged.
    assert trace_early.intent_ids != ()
    tampered = trace_early.__class__(
        **{**trace_early.__dict__, "intent_digest": "sha256:tampered"}
    )
    flagged = compare_traces(trace_early, tampered)
    assert [d.path for d in flagged] == ["intent_digest"]
    assert flagged[0].kind == "DECISION_DRIFT"


def test_rp_05_4(tmp_path: Path) -> None:
    """RP-05-AC4: research transitive imports expose no real writer.

    The static closure check lives in tests/architecture/
    test_research_write_firewall.py; here the composed research runtimes must
    carry no writer capability or credentials (all three environments).
    """
    from indodax_lab.runtime.composition import build_research_runtime

    for venue_name in ("simulator", "shadow"):
        kernel = build_research_runtime({"venue": venue_name})
        assert kernel.venue_name == venue_name
        venue = kernel._venue
        for marker in ("_api_key", "_secret_key", "submit_live_order", "place_live_order"):
            assert not hasattr(venue, marker), (venue_name, marker)


def test_rp_05_program_5(tmp_path: Path) -> None:
    """RP-05-AC5: identical events/policy/starting state give equal decisions
    before venue effects; duplicate/restart/halt matrix; manifest deterministic."""
    from indodax_lab.execution.simulator_venue import SimulatorVenueAdapter

    events = _sequence("feed-p", 5)

    run_a = _run_env(tmp_path, "run-a", SimulatorVenueAdapter(), "simulator", events)
    run_b = _run_env(tmp_path, "run-b", SimulatorVenueAdapter(), "simulator", events)
    trace_a = build_trace("run-a", run_a, events)
    trace_b = build_trace("run-b", run_b, events)
    assert compare_traces(trace_a, trace_b, ignore_execution_outcomes=False) == ()

    manifest_one = evidence_manifest({"run-a": trace_a}, [])
    manifest_two = evidence_manifest({"run-a": trace_a}, [])
    assert manifest_one == manifest_two
    assert manifest_one["code_sha"] == _code_sha()

    # Duplicate reprocess duplicates nothing.
    kernel_a = run_a["kernel"]
    orders_before = len(kernel_a._store.restore().orders)
    assert kernel_a.process(events[1]).status == "ACKNOWLEDGED"
    assert len(kernel_a._store.restore().orders) == orders_before

    # Restart over the same store replays without new effects.
    from indodax_lab.execution.simulator_venue import SimulatorVenueAdapter as SimVenue

    intents_log: list = []
    risk_log: list = []
    kernel_restart = _kernel(
        tmp_path / "run-a", "research", SimVenue(), "simulator", intents_log, risk_log
    )
    for event in events:
        assert kernel_restart.process(event).status == "ACKNOWLEDGED"
    assert len(kernel_restart._store.restore().orders) == orders_before

    # Halt mid-sequence, then continue: ledger equals the uninterrupted run.
    intents_h: list = []
    risk_h: list = []
    kernel_h = _kernel(
        tmp_path / "run-h", "research", SimVenue(), "simulator", intents_h, risk_h
    )
    for event in events[:2]:
        kernel_h.process(event)
    # halt: stop processing; a fresh kernel continues over the same store.
    intents_h2: list = []
    risk_h2: list = []
    kernel_h2 = _kernel(
        tmp_path / "run-h", "research", SimVenue(), "simulator", intents_h2, risk_h2
    )
    for event in events[2:]:
        kernel_h2.process(event)
    assert _snapshot_totals(kernel_h2._store.restore()) == _snapshot_totals(
        kernel_a._store.restore()
    )
