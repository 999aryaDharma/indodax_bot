from datetime import UTC, datetime
from decimal import Decimal

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.ledger import Position
from indodax_lab.backtest.risk import PortfolioRiskManager, RiskPolicy
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.market.health import MarketHealthState
from indodax_lab.portfolio.constructor import PendingReservation, PortfolioState
from indodax_lab.risk.engine import RiskEngine

NOW = datetime(2025, 1, 1, tzinfo=UTC)


def _policy(**changes: object) -> RiskPolicy:
    values: dict[str, object] = {
        "policy_id": "parity-policy",
        "version": "1",
        "max_position_fraction": Decimal("0.50"),
        "max_open_positions": 3,
        "min_order_notional": Decimal("10000"),
        "max_daily_loss_fraction": Decimal("0.05"),
        "max_weekly_loss_fraction": Decimal("0.10"),
        "max_drawdown_halt_fraction": Decimal("0.15"),
        "max_account_leverage": Decimal("1.0"),
    }
    values.update(changes)
    return RiskPolicy(**values)


def _intent(pair: str = "btc_idr", qty: str = "1", stop: str | None = None) -> SignalIntent:
    return SignalIntent(
        intent_id="intent-1",
        decision_ts=NOW,
        pair=pair,
        side=OrderSide.BUY,
        desired_qty=Decimal(qty),
        limit_price=Decimal("500000000"),
        stop_loss=Decimal(stop) if stop else None,
        strategy_id="agent-c07",
    )


def test_rp_03_2_same_portfolio_cost_and_intent_match_backtest_quantity() -> None:
    state = PortfolioState(
        valuation_currency="IDR",
        cash_balance=Decimal("1000000"),
        mark_prices={"btc_idr": Decimal("500000000")},
        revision=5,
    )
    policy = _policy()
    manager = PortfolioRiskManager(policy, state.equity, NOW)
    intent = _intent(qty="0.001")
    direct = manager.assess_order(
        intent,
        state.equity,
        state.positions_by_pair,
        state.mark_prices_by_pair,
        NOW,
        state.available_cash,
        estimated_fee_rate=Decimal("0.003"),
        fee_precision=0,
        quantity_precision=8,
    )

    result = RiskEngine(manager).assess_intent(
        intent,
        portfolio_state=state,
        evaluation_time=NOW,
        estimated_fee_rate=Decimal("0.003"),
        fee_precision=0,
        quantity_precision=8,
        market_health=MarketHealthState.HEALTHY,
    )

    assert result == direct


def test_rp_03_3_pending_notional_and_fee_reduce_cash_and_exposure_once() -> None:
    state = PortfolioState(
        valuation_currency="IDR",
        cash_balance=Decimal("20000"),
        positions=(Position(pair="btc_idr", base_qty=Decimal("1"), cost_basis=Decimal("80000")),),
        mark_prices={"btc_idr": Decimal("80000"), "eth_idr": Decimal("1"), "sol_idr": Decimal("1")},
        revision=9,
    )
    manager = PortfolioRiskManager(
        _policy(max_position_fraction=Decimal("0.90"), max_account_leverage=Decimal("1.0")),
        state.equity,
        NOW,
    )
    engine = RiskEngine(manager)
    first = engine.assess_intent(
        _intent(pair="eth_idr", qty="10000"),
        portfolio_state=state,
        evaluation_time=NOW,
        estimated_fee_rate=Decimal("0.003"),
        fee_precision=0,
        quantity_precision=8,
    )
    assert first.approved
    fee = (first.approved_notional * Decimal("0.003")).quantize(Decimal("1"))
    updated_state = PortfolioState(
        valuation_currency="IDR",
        cash_balance=state.cash_balance,
        positions=state.positions,
        mark_prices=state.mark_prices,
        reservations=(PendingReservation(
            order_id="pending-eth",
            strategy_id="agent-c07",
            pair="eth_idr",
            side=OrderSide.BUY,
            remaining_qty=first.approved_qty,
            reserved_notional=first.approved_notional,
            reserved_fee=fee,
            reserved_risk=Decimal("4000"),
        ),),
        revision=state.revision + 1,
    )

    result = engine.assess_intent(
        _intent(pair="sol_idr", qty="15000"),
        portfolio_state=updated_state,
        evaluation_time=NOW,
        estimated_fee_rate=Decimal("0.003"),
        fee_precision=0,
        quantity_precision=8,
    )

    assert updated_state.available_cash == Decimal("9970")
    assert updated_state.pending_exposure_by_pair == {"eth_idr": Decimal("10000")}
    assert updated_state.pending_risk_by_strategy == {"agent-c07": Decimal("4000")}
    assert result.approved is False
    assert result.reason_code == "BELOW_MIN_SIZE_REJECTED"


def test_rp_03_program_4_strategy_stop_distance_caps_requested_risk() -> None:
    state = PortfolioState(
        valuation_currency="IDR",
        cash_balance=Decimal("100000"),
        mark_prices={"btc_idr": Decimal("100000")},
        revision=1,
    )
    manager = PortfolioRiskManager(
        _policy(max_position_fraction=Decimal("0.90")), state.equity, NOW
    )

    result = RiskEngine(manager).assess_intent(
        _intent(qty="1", stop="90000"),
        portfolio_state=state,
        evaluation_time=NOW,
        estimated_fee_rate=Decimal("0.001"),
        fee_precision=0,
        quantity_precision=8,
        max_risk_amount=Decimal("4000"),
    )

    gross_stop_loss = result.approved_qty * Decimal("10000")
    entry_fee = (result.approved_notional * Decimal("0.001")).quantize(Decimal("1"))
    exit_fee = (result.approved_qty * Decimal("90000") * Decimal("0.001")).quantize(Decimal("1"))
    assert result.approved
    assert result.approved_qty < Decimal("0.4")
    assert gross_stop_loss + entry_fee + exit_fee <= Decimal("4000")


def test_state_entry_rejects_missing_cost_inputs_instead_of_assuming_zero() -> None:
    state = PortfolioState(
        valuation_currency="IDR",
        cash_balance=Decimal("100000"),
        mark_prices={"btc_idr": Decimal("100000")},
        revision=1,
    )
    engine = RiskEngine(PortfolioRiskManager(_policy(), state.equity, NOW))

    result = engine.assess_intent(
        _intent(qty="0.2"),
        portfolio_state=state,
        evaluation_time=NOW,
    )

    assert result.approved is False
    assert result.reason_code == "COST_AND_PRECISION_REQUIRED"


def test_state_entry_rejects_duplicate_financial_authority() -> None:
    state = PortfolioState(
        valuation_currency="IDR",
        cash_balance=Decimal("100000"),
        mark_prices={"btc_idr": Decimal("100000")},
        revision=1,
    )
    engine = RiskEngine(PortfolioRiskManager(_policy(), state.equity, NOW))

    result = engine.assess_intent(
        _intent(qty="0.2"),
        portfolio_state=state,
        current_equity=state.equity,
        evaluation_time=NOW,
    )

    assert result.approved is False
    assert result.reason_code == "DUPLICATE_PORTFOLIO_STATE"


def test_pending_sell_reservation_cannot_sell_inventory_twice() -> None:
    state = PortfolioState(
        valuation_currency="IDR",
        cash_balance=Decimal("100000"),
        positions=(Position(pair="btc_idr", base_qty=Decimal("10"), cost_basis=Decimal("100000")),),
        mark_prices={"btc_idr": Decimal("10000")},
        reservations=(PendingReservation(
            order_id="sell-1", strategy_id="agent-c07", pair="btc_idr", side=OrderSide.SELL,
            remaining_qty=Decimal("10"), reserved_notional=Decimal("100000"),
        ),),
        revision=2,
    )
    sell = SignalIntent(
        intent_id="sell-2", decision_ts=NOW, pair="btc_idr", side=OrderSide.SELL,
        desired_qty=Decimal("10"), strategy_id="agent-c07",
    )

    result = RiskEngine(PortfolioRiskManager(_policy(), state.equity, NOW)).assess_intent(
        sell, portfolio_state=state, evaluation_time=NOW
    )

    assert result.approved is False
    assert result.approved_qty == Decimal("0")
    assert result.reason_code == "NO_POSITION_TO_SELL"


def test_portfolio_rejects_sell_reservations_above_inventory() -> None:
    import pytest

    with pytest.raises(ValueError, match="SELL_RESERVATIONS_EXCEED_POSITION"):
        PortfolioState(
            valuation_currency="IDR", cash_balance=Decimal("0"),
            positions=(Position(pair="btc_idr", base_qty=Decimal("1"), cost_basis=Decimal("1")),),
            mark_prices={"btc_idr": Decimal("1")},
            reservations=(PendingReservation(
                order_id="sell-1", strategy_id="agent-c07", pair="btc_idr",
                side=OrderSide.SELL, remaining_qty=Decimal("2"), reserved_notional=Decimal("2"),
            ),), revision=1,
        )
