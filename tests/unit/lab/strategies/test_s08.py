from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd

from indodax_lab.backtest.costs import OrderRole
from indodax_lab.backtest.events import ExecutionStatus, MarketBar
from indodax_lab.backtest.execution import ConservativeExecutionSimulator
from indodax_lab.models.lob.queue_evidence import QueueEvidence, QueueEvidencePolicy
from indodax_lab.strategies.base import DecisionFrame
from indodax_lab.strategies.registry import StrategyRegistry
from indodax_lab.strategies.s08 import load_s08_specification, s08_decide

AS_OF = datetime(2026, 1, 1, tzinfo=UTC)


def _frame(**updates: object) -> DecisionFrame:
    feature_set_id = str(updates.pop("feature_set_id", "lob_v1"))
    feature_set_version = updates.pop("feature_set_version", "fixture-v1")
    row: dict[str, object] = {
        "pair": "alt_idr",
        "decision_ts": AS_OF,
        "row_ready_at": AS_OF,
        "eligible": True,
        "close": 1000.0,
        "mid_price": 1002.0,
        "spread_bps": 20.0,
        "book_imbalance_l5": 0.25,
        "trade_imbalance_10s": -0.2,
        "book_event_ts": AS_OF - timedelta(seconds=1),
        "book_available_at": AS_OF,
        "book_session_id": "session-1",
        "book_sequence_contiguous": True,
    }
    row.update(updates)
    return DecisionFrame(
        AS_OF,
        pd.DataFrame([row]),
        ["alt_idr"],
        feature_set_id=feature_set_id,
        feature_set_version=feature_set_version,
    )


def test_s08_valid_causal_lob_row_emits_comparable_passive_intent() -> None:
    intent = s08_decide(_frame(), load_s08_specification())[0]

    assert intent.pair == "alt_idr"
    assert intent.desired_qty * intent.limit_price >= Decimal("10000")
    assert intent.limit_price < Decimal("1000")
    assert intent.role_preference == OrderRole.MAKER
    assert intent.stop_loss is not None


def test_s08_is_available_through_versioned_strategy_registry() -> None:
    spec = load_s08_specification()
    registered = StrategyRegistry().register_builtin(spec)

    assert registered.specification.identity_hash() == spec.identity_hash()
    assert registered.decide(_frame())[0].strategy_id == "S08"


def test_s08_invalid_or_missing_market_evidence_abstains() -> None:
    spec = load_s08_specification()
    assert s08_decide(_frame(book_sequence_contiguous=False), spec) == []
    assert s08_decide(_frame(book_available_at=AS_OF + timedelta(seconds=1)), spec) == []
    assert s08_decide(_frame(book_session_id=None), spec) == []
    assert s08_decide(_frame(book_imbalance_l5=None), spec) == []
    assert s08_decide(_frame(spread_bps=100.0), spec) == []
    assert s08_decide(_frame(feature_set_id="tabular_bar_v1"), spec) == []
    assert s08_decide(_frame(feature_set_version=None), spec) == []


def test_s08_touching_maker_quote_does_not_create_fill() -> None:
    intent = s08_decide(_frame(), load_s08_specification())[0]
    cost = _maker_cost()
    bar = MarketBar(
        pair="alt_idr",
        open_time=AS_OF + timedelta(hours=1),
        close_time=AS_OF + timedelta(hours=2),
        open=intent.limit_price,
        high=intent.limit_price + 1,
        low=intent.limit_price,
        close=intent.limit_price,
        base_volume=Decimal("100"),
        quote_volume=Decimal("100000"),
    )

    result = ConservativeExecutionSimulator(cost).simulate_execution(
        intent,
        bar,
        order_created_ts=AS_OF,
        execution_contract="lob_queue_v1",
        queue_evidence=_queue_evidence(),
        queue_policy=_queue_policy(),
    )

    assert result.status == ExecutionStatus.REJECTED
    assert result.reason_code == "LIMIT_TOUCH_NO_FILL"


def test_s08_unknown_queue_blocks_simulation_at_shared_execution_boundary() -> None:
    intent = s08_decide(_frame(), load_s08_specification())[0]
    bar = MarketBar(
        pair="alt_idr",
        open_time=AS_OF + timedelta(hours=1),
        close_time=AS_OF + timedelta(hours=2),
        open=intent.limit_price,
        high=intent.limit_price + 1,
        low=intent.limit_price,
        close=intent.limit_price,
        base_volume=Decimal("100"),
        quote_volume=Decimal("100000"),
    )

    result = ConservativeExecutionSimulator(_maker_cost()).simulate_execution(
        intent,
        bar,
        order_created_ts=bar.open_time,
        execution_contract="lob_queue_v1",
        queue_evidence=None,
        queue_policy=_queue_policy(),
    )

    assert result.status == ExecutionStatus.REJECTED
    assert result.reason_code == "QUEUE_UNAVAILABLE"


def _queue_policy() -> QueueEvidencePolicy:
    return QueueEvidencePolicy(
        policy_id="test-queue-age",
        version="test-v1",
        approved_by="test",
        approval_ref="test-only",
        source_id="fixture",
        source_version="v1",
        max_evidence_age_seconds=5,
    )


def _queue_evidence() -> QueueEvidence:
    return QueueEvidence(
        pair="alt_idr",
        event_at=AS_OF - timedelta(seconds=2),
        available_at=AS_OF - timedelta(seconds=1),
        observed_at=AS_OF - timedelta(milliseconds=500),
        session_id="session-1",
        sequence_contiguous=True,
        book_imbalance_l5="0.2",
        depth_bid_10bps_idr="250000",
        depth_ask_10bps_idr="200000",
        spread_bps="15",
        queue_ahead_base_qty="3.25",
        status="known",
        source_id="fixture",
        source_version="v1",
        source_sha256="a" * 64,
    )


def _maker_cost():
    from indodax_lab.backtest.costs import CostScheduleInterval, CostScheduleTable, OrderSide

    schedule = CostScheduleInterval(
        schedule_id="test-maker",
        market="spot_idr",
        side=OrderSide.BUY,
        role=OrderRole.MAKER,
        valid_from=AS_OF - timedelta(days=1),
        valid_to=None,
        service_fee_rate=Decimal("0"),
        tax_rate=Decimal("0"),
        exchange_fee_rate=Decimal("0"),
        min_notional=Decimal("10000"),
        precision=0,
        sources=("fixture",),
        evidence_verified=True,
    )
    return CostScheduleTable(schedule_set_id="test", version="1", intervals=(schedule,))
