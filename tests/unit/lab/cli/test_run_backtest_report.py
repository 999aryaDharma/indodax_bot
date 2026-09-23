from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from indodax_lab.cli.run_backtest import _build_report


def test_report_does_not_claim_unmaterialized_feature_registry() -> None:
    result = SimpleNamespace(
        ending_cash=Decimal("100"),
        ending_equity=Decimal("100"),
        total_gross_pnl=Decimal("0"),
        total_net_pnl=Decimal("0"),
        total_fees_paid=Decimal("0"),
        fill_count=0,
        postings_hash="sha256:test",
        execution_version="test",
        execution_assumptions=(),
    )
    metrics = SimpleNamespace(
        max_drawdown_amount=Decimal("0"),
        max_drawdown_pct=Decimal("0"),
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
