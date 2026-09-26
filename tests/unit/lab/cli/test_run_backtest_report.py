import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from indodax_lab.backtest.events import MarketBar
from indodax_lab.backtest.ledger import ResearchLedger
from indodax_lab.backtest.orders import Fill, OrderRole, OrderSide
from indodax_lab.cli.run_backtest import (
    _build_ledger_equity_curve,
    _build_report,
    write_json_atomically,
)


def test_report_does_not_claim_unmaterialized_feature_registry() -> None:
    result = SimpleNamespace(
        ending_cash=Decimal("100"),
        ending_equity=Decimal("100"),
        total_gross_pnl=Decimal("0"),
        total_net_pnl=Decimal("0"),
        total_fees_paid=Decimal("0"),
        fill_count=0,
        postings_hash="sha256:test",
        market_input_hash="sha256:market",
        cost_schedule_set_id="cost-test",
        cost_schedule_version="2.0.0",
        risk_policy_id="risk-test",
        risk_policy_version="3.0.0",
        status="COMPLETED_WITH_REJECTIONS",
        execution_version="test",
        execution_assumptions=(),
    )
    metrics = SimpleNamespace(
        max_drawdown_amount=None,
        max_drawdown_pct=None,
        drawdown_status="MISSING_EQUITY_CURVE",
        win_rate=None,
        profit_factor=SimpleNamespace(defined=False, reason="NO_TRADES"),
        trade_count=0,
    )
    spec = SimpleNamespace(
        strategy_id="test",
        version="1.0.0",
        parameters_hash=lambda: "sha256:test",
    )
    engine = SimpleNamespace(
        ledger=SimpleNamespace(transactions=(), positions={}),
        rejections=(),
    )

    report = _build_report(
        result=result,
        metrics=metrics,
        spec=spec,
        logic_hash="sha256:test",
        pair="btc_idr",
        start_dt=datetime(2024, 1, 1, tzinfo=UTC),
        end_dt=datetime(2024, 1, 2, tzinfo=UTC),
        initial_cash=Decimal("100"),
        cost_config_path="costs.yaml",
        run_id="run-test",
        engine=engine,
        bars_5m_count=1,
        intent_count=0,
    )

    assert report["feature_set_id"] is None
    assert report["feature_set_version"] is None
    assert report["market_input_hash"] == "sha256:market"
    assert report["cost_schedule_id"] == "cost-test"
    assert report["cost_schedule_version"] == "2.0.0"
    assert report["risk_policy_id"] == "risk-test"
    assert report["risk_policy_version"] == "3.0.0"
    assert report["run_status"] == "COMPLETED_WITH_REJECTIONS"
    assert report["max_drawdown_amount_idr"] is None
    assert report["drawdown_status"] == "MISSING_EQUITY_CURVE"
    assert report["regime_status"] == "MISSING_CLASSIFICATION"
    assert report["tier_status"] == "MISSING_CLASSIFICATION"
    assert report["performance_breakdowns"]["by_regime"] is None
    assert report["performance_breakdowns"]["by_tier"] is None


def test_equity_curve_replays_cash_and_only_available_bar_marks() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    ledger = ResearchLedger(initial_cash=Decimal("1000"), init_timestamp=start)
    ledger.process_fill(Fill(
        fill_id="curve-buy", order_id="curve-buy", event_id="e1", pair="btc_idr",
        side=OrderSide.BUY, role=OrderRole.TAKER, price=Decimal("100"),
        qty=Decimal("1"), fees=Decimal("1"), timestamp=start + timedelta(minutes=2),
    ))

    def bar(index: int, close: str) -> MarketBar:
        open_time = start + timedelta(minutes=index)
        close_time = open_time + timedelta(minutes=1)
        return MarketBar(
            pair="btc_idr", open_time=open_time, close_time=close_time,
            open=Decimal(close), high=Decimal(close), low=Decimal(close),
            close=Decimal(close), base_volume=Decimal("1"), quote_volume=Decimal("1"),
        )

    curve = _build_ledger_equity_curve(ledger, [bar(2, "80"), bar(0, "100"), bar(3, "110")])
    assert curve == [
        (start + timedelta(minutes=1), Decimal("1000")),
        (start + timedelta(minutes=3), Decimal("979")),
        (start + timedelta(minutes=4), Decimal("1009")),
    ]


def test_cli_atomic_writer_preserves_existing_tmp_target(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "report.tmp"
    previous = '{"run_id": "previous"}'
    target.write_text(previous, encoding="utf-8")

    def fail_replace(_source: str | os.PathLike[str], _target: str | os.PathLike[str]) -> None:
        raise OSError("simulated CLI publish interruption")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated CLI publish interruption"):
        write_json_atomically(target, {"run_id": "new"})

    assert target.read_text(encoding="utf-8") == previous
    assert list(tmp_path.glob(".report.tmp.*")) == []
