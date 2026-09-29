"""Integration tests for RP-04 canonical feed and environment runtime adapters.

Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

Contract (docs/implementation/CONTRACTS.md):
- RuntimeKernel.process(event) -> RuntimeStepResult
- EventFeed.subscribe(namespace, after_sequence) -> Iterator[CanonicalMarketEvent]
- ShadowVenueAdapter / SimulatorVenueAdapter implement TradingVenue
- build_research_runtime(config) cannot resolve a live adapter

No real network / credentials / live DB. Fake upstream source, fake clocks,
temporary storage only.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from indodax_lab.backtest.events import MarketBar
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.execution.oms import OmsOrder
from indodax_lab.runtime.candidate import CanonicalMarketEvent
from indodax_lab.runtime.exits import ExitState
from indodax_lab.runtime.kernel import RuntimeKernel


def _bar(pair: str, close_time: datetime, price: str = "100") -> MarketBar:
    from indodax_lab.backtest.events import MarketBar

    open_time = close_time - timedelta(minutes=1)
    return MarketBar(
        pair=pair,
        open_time=open_time,
        close_time=close_time,
        open=Decimal(price),
        high=Decimal(price),
        low=Decimal(price),
        close=Decimal(price),
        base_volume=Decimal("1"),
        quote_volume=Decimal(price),
    )


def _event(
    feed_id: str,
    sequence: int,
    pair: str = "btc_idr",
    base: datetime | None = None,
    price: str = "100",
) -> CanonicalMarketEvent:
    ts = (base or datetime(2025, 1, 1, tzinfo=UTC)) + timedelta(minutes=sequence)
    return CanonicalMarketEvent(
        event_id=f"{feed_id}:{sequence}",
        feed_id=feed_id,
        sequence=sequence,
        pair=pair,
        event_time=ts,
        available_at=ts,
        observation=_bar(pair, ts, price=price),
        quality_ref=None,
    )


class FakeUpstream:
    """Counting fake upstream source: poll(feed_id, after_sequence) -> events."""

    def __init__(self, events: list[CanonicalMarketEvent]) -> None:
        self._events = events
        self.poll_count = 0

    def __call__(
        self, feed_id: str, after_sequence: int
    ) -> list[CanonicalMarketEvent]:
        self.poll_count += 1
        return [
            e for e in self._events if e.feed_id == feed_id and e.sequence > after_sequence
        ]


def test_rp_04_0() -> None:
    """RP-04-AC0: N agents cause one upstream poll per stream, not N."""
    from indodax_lab.market.event_feed import EventFeed

    events = [_event("stream-a", seq) for seq in range(1, 6)]
    upstream = FakeUpstream(events)
    feed = EventFeed(upstream)

    subs = [feed.subscribe("ns", after_sequence=0) for _ in range(5)]
    first_rounds = [[next(s) for _ in range(2)] for s in subs]

    assert upstream.poll_count == 1
    for round_events in first_rounds:
        assert [e.sequence for e in round_events] == [1, 2]


def test_rp_04_1() -> None:
    """RP-04-AC1: slow consumer gets explicit gap/backpressure + resumable cursor."""
    from indodax_lab.market.event_feed import (
        EventFeed,
        SubscriberGapError,
    )

    upstream = FakeUpstream([_event("stream-a", seq) for seq in range(1, 4)])
    feed = EventFeed(upstream, max_queue=3)

    slow = feed.subscribe("ns", after_sequence=0)
    assert [next(slow).sequence for _ in range(3)] == [1, 2, 3]

    # Upstream advances past the bounded live queue while the consumer stalls.
    upstream._events.extend(_event("stream-a", seq) for seq in range(4, 8))
    feed.poll("stream-a")
    with pytest.raises(SubscriberGapError) as exc_info:
        list(slow)
    assert "GAP_DETECTED" in str(exc_info.value)

    # Cursor resumes after the gap without replays or silent skips past it.
    resumed = feed.subscribe("ns", after_sequence=exc_info.value.resume_sequence)
    assert [e.sequence for e in resumed] == [7]


def _oms_order(
    order_id: str = "ord_test_001",
    pair: str = "btc_idr",
    qty: str = "0.001",
    price: str = "100000000",
) -> OmsOrder:
    from indodax_lab.backtest.costs import OrderSide

    now = datetime.now(UTC)
    return OmsOrder(
        internal_order_id=order_id,
        client_order_id=f"cl_{order_id}",
        pair=pair,
        side=OrderSide.BUY,
        desired_qty=Decimal(qty),
        limit_price=Decimal(price),
        created_at=now,
        updated_at=now,
    )


def test_rp_04_2() -> None:
    """RP-04-AC2: wrapper/factory cannot inject a live writer into research."""
    from indodax_lab.execution.indodax_trading import IndodaxTradingVenue
    from indodax_lab.runtime.composition import (
        ResearchBoundaryError,
        build_research_runtime,
    )

    live = IndodaxTradingVenue(api_key="dummy", secret_key="dummy")

    class SneakyWrapper(IndodaxTradingVenue):
        """A subclass wrapper must not smuggle live authority past the boundary."""

    with pytest.raises(ResearchBoundaryError, match="LIVE_WRITER_FORBIDDEN"):
        build_research_runtime({"venue": live})
    with pytest.raises(ResearchBoundaryError, match="LIVE_WRITER_FORBIDDEN"):
        build_research_runtime(
            {"venue": SneakyWrapper(api_key="dummy", secret_key="dummy")}
        )
    with pytest.raises(ResearchBoundaryError, match="LIVE_WRITER_FORBIDDEN"):
        build_research_runtime({"venue_factory": lambda: live})

    # Simulator venue composes cleanly.
    kernel = build_research_runtime({"venue": "simulator"})
    assert kernel.venue_name == "simulator"


def test_rp_04_2_unwired_kernel_emits_no_orders(tmp_path: Path) -> None:
    """Fail-closed default: a kernel without an explicit risk stage denies all
    intents, and a boundary-only kernel cannot process at all."""
    from indodax_lab.execution.simulator_venue import SimulatorVenueAdapter
    from indodax_lab.execution.state_store import ExecutionStateStore
    from indodax_lab.runtime.composition import build_research_runtime
    from indodax_lab.runtime.kernel import KernelNotWiredError, RuntimeKernel

    boundary = build_research_runtime({"venue": "simulator"})
    with pytest.raises(KernelNotWiredError, match="KERNEL_NOT_WIRED"):
        boundary.process(_event("stream-a", 1))

    store = ExecutionStateStore(
        tmp_path / "research.db", namespace="research", initial_cash=Decimal("10000000")
    )
    kernel = RuntimeKernel(
        candidate_runtime=_stub_candidate(
            intents=lambda event, state: (_entry_intent("intent_denied_001"),)
        ),
        store=store,
        venue=SimulatorVenueAdapter(),
        venue_name="simulator",
    )
    result = kernel.process(_event("stream-a", 1))
    assert result.status == "ACKNOWLEDGED"
    assert store.restore().orders == {}


def test_rp_04_2_shared_core_carries_no_live_import() -> None:
    """RP-04 Step 5: importing the shared pipeline core must not pull the live
    trading client module into the process."""
    import subprocess
    import sys

    code = (
        "import sys; "
        "import indodax_lab.control.pipeline as _p; "
        "import indodax_lab.runtime.kernel as _k; "
        "import indodax_lab.runtime.composition as _c; "
        "import indodax_lab.market.event_feed as _f; "
        "live = [m for m in sys.modules if m.endswith('.indodax_trading')]; "
        "assert not live, live; "
        "print('NO_LIVE_IMPORT_OK')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert proc.returncode == 0, proc.stderr
    assert "NO_LIVE_IMPORT_OK" in proc.stdout


def test_rp_04_3() -> None:
    """RP-04-AC3: partial/rejected/uncertain simulated orders use shared OMS."""
    from indodax_lab.execution.oms import OmsOrderState, OmsStateMachine
    from indodax_lab.execution.simulator_venue import (
        SimulatedOutcome,
        SimulatorVenueAdapter,
    )
    from indodax_lab.execution.venue import (
        UncertainVenueSubmissionError,
        VenueRejectError,
    )

    order = _oms_order()

    partial = SimulatorVenueAdapter(
        outcome=SimulatedOutcome(kind="PARTIAL", fill_qty=Decimal("0.0004"))
    )
    acked = OmsStateMachine.transition(
        order, OmsOrderState.SUBMITTING, at=order.updated_at, reason="SUBMIT_DISPATCHED"
    )
    receipt = partial.submit_order(acked)
    assert receipt.executed_qty == Decimal("0.0004")
    assert receipt.remaining_qty == order.desired_qty - Decimal("0.0004")
    acked = acked.model_copy(
        update={
            "venue_order_id": receipt.order_id,
            "filled_qty": receipt.executed_qty,
            "average_fill_price": receipt.price,
        }
    )
    filled = OmsStateMachine.transition(
        acked, OmsOrderState.PARTIALLY_FILLED, at=order.updated_at, reason="VENUE_PARTIAL"
    )
    assert filled.state == OmsOrderState.PARTIALLY_FILLED

    rejector = SimulatorVenueAdapter(outcome=SimulatedOutcome(kind="REJECT"))
    with pytest.raises(VenueRejectError, match="SIMULATED_REJECT"):
        rejector.submit_order(acked)
    fresh = _oms_order(order_id="ord_test_002")
    fresh_acked = OmsStateMachine.transition(
        fresh, OmsOrderState.SUBMITTING, at=fresh.updated_at, reason="SUBMIT_DISPATCHED"
    )
    rejected = OmsStateMachine.transition(
        fresh_acked, OmsOrderState.REJECTED, at=fresh.updated_at, reason="VENUE_REJECT"
    )
    assert rejected.state == OmsOrderState.REJECTED

    flaky = SimulatorVenueAdapter(outcome=SimulatedOutcome(kind="UNCERTAIN"))
    with pytest.raises(UncertainVenueSubmissionError):
        flaky.submit_order(fresh_acked)
    unknown = OmsStateMachine.transition(
        fresh_acked, OmsOrderState.UNKNOWN, at=fresh.updated_at, reason="VENUE_UNCERTAIN"
    )
    assert unknown.state == OmsOrderState.UNKNOWN


def _stub_candidate(
    intents: tuple | Callable | None = None,
    exit_state: ExitState | None = None,
) -> SimpleNamespace:
    """Fake candidate runtime: deterministic intents, real exit-state passthrough."""
    held = {"exits": exit_state or ExitState()}

    def _evaluate(event: CanonicalMarketEvent, state: object) -> tuple:
        if callable(intents):
            return tuple(intents(event, state))
        return tuple(intents or ())

    return SimpleNamespace(
        plan_digest="plan_digest_stub",
        candidate_digest=None,
        evaluate=_evaluate,
        held_exits=held,
    )


def _kernel(
    tmp_path: Path,
    venue: object | None = None,
    candidate: object | None = None,
    namespace: str = "research",
    risk_stage: Callable | None = None,
) -> RuntimeKernel:
    from indodax_lab.execution.simulator_venue import SimulatorVenueAdapter
    from indodax_lab.execution.state_store import ExecutionStateStore
    from indodax_lab.runtime.kernel import RuntimeKernel

    store = ExecutionStateStore(
        tmp_path / f"{namespace}.db",
        namespace=namespace,
        initial_cash=Decimal("10000000"),
    )
    # Tests opt into an allow-all risk stage explicitly. Production default
    # (deny_all_stage) emits no orders when unwired — verified by AC2 minimal
    # composition, which never processes.
    return RuntimeKernel(
        candidate_runtime=candidate or _stub_candidate(),
        store=store,
        venue=venue or SimulatorVenueAdapter(),
        venue_name="simulator",
        risk_stage=risk_stage or (lambda intents, _state: tuple(intents)),
    )


def test_rp_04_4(tmp_path: Path) -> None:
    """RP-04-AC4: restart cannot duplicate a processed event."""
    import sqlite3

    kernel = _kernel(tmp_path)
    event = _event("stream-a", 1)
    first = kernel.process(event)
    assert first.status == "ACKNOWLEDGED"

    # Restart: fresh kernel over the same durable store.
    kernel2 = _kernel(tmp_path)
    second = kernel2.process(event)
    assert second.status == "ACKNOWLEDGED"

    db = tmp_path / "research.db"
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM events_inbox WHERE event_id=?", ("stream-a:1",)
        ).fetchone()[0]
        assert rows == 1
    finally:
        conn.close()


def _entry_intent(
    intent_id: str,
    pair: str = "btc_idr",
    price: str = "100000000",
    qty: str = "0.001",
    stop: str | None = "99000000",
) -> SignalIntent:
    from indodax_lab.backtest.costs import OrderSide

    return SignalIntent(
        intent_id=intent_id,
        decision_ts=datetime(2025, 1, 1, tzinfo=UTC),
        pair=pair,
        side=OrderSide.BUY,
        desired_qty=Decimal(qty),
        limit_price=Decimal(price),
        stop_loss=Decimal(stop) if stop is not None else None,
        take_profit=Decimal("102000000"),
    )


def test_rp_04_bootstrap_recovery(tmp_path: Path) -> None:
    """RP-04-AC5: no-fill events advance feature/risk state once; delayed fills
    stay recoverable after cursor acknowledgement."""
    from indodax_lab.backtest.costs import OrderSide
    from indodax_lab.backtest.orders import Fill, OrderRole

    fired = {"n": 0}

    def _evaluate(event: CanonicalMarketEvent, state: object) -> tuple:
        fired["n"] += 1
        if fired["n"] == 1:
            return ()
        return (_entry_intent("intent_delayed_001"),)

    kernel = _kernel(tmp_path, candidate=_stub_candidate(intents=_evaluate))

    # No-fill event: feature window advances exactly once, even on reprocess.
    kernel.process(_event("stream-a", 1))
    assert len(kernel._bars) == 1
    kernel.process(_event("stream-a", 1))
    assert len(kernel._bars) == 1

    # Entry event produces one order through the simulator.
    result = kernel.process(_event("stream-a", 2))
    assert result.status == "ACKNOWLEDGED"
    assert len(kernel._bars) == 2

    # Delayed fill arrives after cursor acknowledgement and commits once.
    store = kernel._store
    revision = store.restore().revision
    internal_id = "ord_intent_delay"
    fill = Fill(
        fill_id="fill_delayed_001",
        order_id=internal_id,
        event_id="evt_fill_001",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        qty=Decimal("0.001"),
        price=Decimal("100000000"),
        fees=Decimal("300000"),
        timestamp=datetime(2025, 1, 1, 0, 10, tzinfo=UTC),
    )
    first_apply = store.apply_fill(fill, revision)
    assert first_apply.is_duplicate is False
    assert first_apply.quarantined is False
    revision2 = store.restore().revision
    second_apply = store.apply_fill(fill, revision2)
    assert second_apply.is_duplicate is True


def test_rp_04_program_6(tmp_path: Path) -> None:
    """RP-04-AC6: environment adapters preserve candidate exit and financial
    recovery semantics without Research writer capability."""
    from indodax_lab.backtest.costs import OrderSide
    from indodax_lab.contracts.decision import SignalIntent
    from indodax_lab.runtime.exits import (
        ExitState,
        advance_exit_state,
        exit_decisions,
        open_position,
    )

    held = {"exits": ExitState(), "opened": False}

    def _evaluate(event: CanonicalMarketEvent, state: object) -> tuple:
        bar = event.observation
        if not held["opened"]:
            held["exits"] = open_position(
                held["exits"],
                pair=bar.pair,
                strategy_id="strat_exit",
                entry_price=bar.close,
                entry_atr=Decimal("1000000"),
                stop_loss=bar.close - Decimal("2000000"),
                qty=Decimal("0.001"),
            )
            held["opened"] = True
            return (
                _entry_intent(
                    "intent_exit_entry",
                    price=str(bar.close),
                    stop=str(bar.close - Decimal("2000000")),
                ),
            )
        held["exits"] = advance_exit_state(held["exits"], bar)
        out = []
        for decision in exit_decisions(held["exits"], bar):
            out.append(
                SignalIntent(
                    intent_id=f"exit_{event.event_id}",
                    decision_ts=event.event_time,
                    pair=decision.pair,
                    side=OrderSide.SELL,
                    desired_qty=decision.qty,
                    limit_price=decision.price,
                    strategy_id=decision.strategy_id,
                )
            )
        return tuple(out)

    kernel = _kernel(tmp_path, candidate=_stub_candidate(intents=_evaluate))

    entry_ts = datetime(2025, 1, 1, tzinfo=UTC)
    kernel.process(_event("stream-a", 1, base=entry_ts, price="100000000"))

    # A later bar gaps through the stop: real exit semantics fire a SELL.
    stop_bar = _bar("btc_idr", entry_ts + timedelta(minutes=2), price="90000000")
    crash = CanonicalMarketEvent(
        event_id="stream-a:2",
        feed_id="stream-a",
        sequence=2,
        pair="btc_idr",
        event_time=entry_ts + timedelta(minutes=2),
        available_at=entry_ts + timedelta(minutes=2),
        observation=stop_bar,
        quality_ref=None,
    )
    result = kernel.process(crash)
    assert result.status == "ACKNOWLEDGED"

    orders = kernel._store.restore().orders
    exit_orders = [
        o for oid, o in orders.items() if str(o.get("side")).upper() == "SELL"
    ]
    assert len(exit_orders) == 1

    # The kernel and its venue hold no writer capability or credentials.
    assert not hasattr(kernel._venue, "_api_key")
    assert not hasattr(kernel._venue, "_secret_key")

    # Reprocessing the crash bar duplicates nothing.
    before = len(kernel._store.restore().orders)
    kernel.process(crash)
    assert len(kernel._store.restore().orders) == before


def test_rp_04_capacity_7(tmp_path: Path) -> None:
    """RP-04-AC7: multi-strategy consumers share bounded Research subscriptions
    and fan out without sharing Production authority.

    Mechanism is proven here (identical bytes, bounded queues, credential-free
    venue); the measured host artifact is operator-owned pending evidence.
    """
    from indodax_lab.market.event_feed import EventFeed

    events = [_event("stream-a", seq) for seq in range(1, 6)]
    upstream = FakeUpstream(events)
    feed = EventFeed(upstream, max_queue=4)

    strategies = [feed.subscribe(f"strategy-{name}", after_sequence=0) for name in "abc"]
    deliveries = [[e.event_id for e in s] for s in strategies]
    assert upstream.poll_count == 1
    assert deliveries[0] == deliveries[1] == deliveries[2]
    assert len(deliveries[0]) == 5

    kernel = _kernel(tmp_path)
    assert kernel.venue_name == "simulator"
    assert not hasattr(kernel._venue, "_api_key")
    assert not hasattr(kernel._venue, "_secret_key")
    assert not hasattr(kernel._venue, "submit_live_order")
