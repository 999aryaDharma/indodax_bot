from datetime import UTC, datetime
from decimal import Decimal

import pytest

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.portfolio.constructor import AllocationPolicy, PortfolioConstructor, PortfolioState


def test_rp_03_0_opposing_same_pair_intents_do_not_silently_last_win() -> None:
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    intents = (
        SignalIntent(
            intent_id="buy-1",
            decision_ts=timestamp,
            pair="btc_idr",
            side=OrderSide.BUY,
            desired_qty=Decimal("0.001"),
            strategy_id="strategy-a",
        ),
        SignalIntent(
            intent_id="sell-1",
            decision_ts=timestamp,
            pair="btc_idr",
            side=OrderSide.SELL,
            desired_qty=Decimal("0.001"),
            strategy_id="strategy-b",
        ),
    )

    with pytest.raises(ValueError, match="SAME_PAIR_INTENT_CONFLICT"):
        PortfolioConstructor().construct_exposures(intents, {}, {"btc_idr": Decimal("500000000")})


def test_rp_03_1_construct_orders_preserves_intent_metadata() -> None:
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    intent = SignalIntent(
        intent_id="intent-1",
        decision_ts=timestamp,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.001"),
        limit_price=Decimal("500000000"),
        stop_loss=Decimal("490000000"),
        take_profit=Decimal("520000000"),
        role_preference=OrderRole.MAKER,
        strategy_id="agent-c07",
        time_in_force="GTC",
    )
    state = PortfolioState(
        valuation_currency="IDR",
        cash_balance=Decimal("1000000"),
        mark_prices={"btc_idr": Decimal("500000000")},
        revision=7,
    )

    result = PortfolioConstructor().construct_orders((intent,), state, allocation_policy=None)

    assert result == (intent,)


def test_rp_03_0_explicit_policy_arbitrates_same_pair_deterministically() -> None:
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    buy = SignalIntent(
        intent_id="buy-1", decision_ts=timestamp, pair="btc_idr", side=OrderSide.BUY,
        desired_qty=Decimal("0.001"), strategy_id="strategy-a",
    )
    sell = SignalIntent(
        intent_id="sell-1", decision_ts=timestamp, pair="btc_idr", side=OrderSide.SELL,
        desired_qty=Decimal("0.001"), strategy_id="strategy-b",
    )
    state = PortfolioState(
        valuation_currency="IDR",
        cash_balance=Decimal("1000000"),
        mark_prices={"btc_idr": Decimal("500000000")},
        revision=2,
    )
    policy = AllocationPolicy(
        policy_id="priority-v1",
        version="1",
        strategy_priorities={"strategy-b": 10, "strategy-a": 5},
    )
    constructor = PortfolioConstructor()

    assert constructor.construct_orders((buy, sell), state, policy) == (sell,)
    assert constructor.construct_orders((sell, buy), state, policy) == (sell,)


def test_rp_03_0_construct_orders_rejects_unarbitrated_pair_conflict() -> None:
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    intents = (
        SignalIntent(intent_id="buy", decision_ts=timestamp, pair="btc_idr", side=OrderSide.BUY,
                     desired_qty=Decimal("1"), strategy_id="a"),
        SignalIntent(intent_id="sell", decision_ts=timestamp, pair="btc_idr", side=OrderSide.SELL,
                     desired_qty=Decimal("1"), strategy_id="b"),
    )
    state = PortfolioState(
        valuation_currency="IDR",
        cash_balance=Decimal("10"), mark_prices={"btc_idr": Decimal("1")}, revision=0
    )

    with pytest.raises(ValueError, match="SAME_PAIR_INTENT_CONFLICT"):
        PortfolioConstructor().construct_orders(intents, state, allocation_policy=None)
