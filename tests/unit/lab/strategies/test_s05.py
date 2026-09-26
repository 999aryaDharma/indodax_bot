import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd

from indodax_lab.backtest.costs import CostScheduleInterval, CostScheduleTable, OrderRole, OrderSide
from indodax_lab.backtest.events import ExecutionStatus, MarketBar
from indodax_lab.backtest.execution import ConservativeExecutionSimulator
from indodax_lab.backtest.feature_replay import FeatureReplayAdapter, FeatureReplayConfig
from indodax_lab.features.registry import load_feature_registry
from indodax_lab.strategies.s05 import load_s05_specification, s05_decide

AS_OF = datetime(2025, 1, 1, tzinfo=UTC)


def _frame(*, impulse=0.06, pullback=-0.005, spread_bps=20.0, atr_pct=0.01, close=100_000.0):
    row = {
        "pair": "smallcoin_idr",
        "decision_ts": AS_OF,
        "row_ready_at": AS_OF,
        "eligible": True,
        "close": close,
        "log_ret_12_1h": impulse,
        "log_ret_1_1h": pullback,
        "spread_bps": spread_bps,
        "atr_pct_14_1h": atr_pct,
    }
    adapter = FeatureReplayAdapter(
        FeatureReplayConfig("smallcoin_idr", "1h", "1h", require_context=False)
    )
    return adapter.build_decision_frame(
        signal_rows=pd.DataFrame([row]), context_rows=pd.DataFrame(), as_of=AS_OF
    )


def test_s05_valid_impulse_pullback_emits_maker_minimum_notional_intent():
    intent = s05_decide(_frame(), load_s05_specification())[0]
    assert intent.pair == "smallcoin_idr"
    assert intent.desired_qty * intent.limit_price >= Decimal("10000")
    assert intent.limit_price == Decimal("100000.0")
    assert intent.stop_loss == Decimal("98000.000")
    assert intent.role_preference == OrderRole.MAKER


def test_s05_rejects_wide_spread_and_price_outside_pullback_band():
    spec = load_s05_specification()
    assert s05_decide(_frame(spread_bps=25.01), spec) == []
    assert s05_decide(_frame(impulse=0.049), spec) == []
    assert s05_decide(_frame(pullback=-0.016), spec) == []
    assert s05_decide(_frame(pullback=0.001), spec) == []


def test_s05_missing_or_nonfinite_spread_and_price_inputs_abstain():
    spec = load_s05_specification()
    assert s05_decide(_frame(spread_bps=None), spec) == []
    assert s05_decide(_frame(spread_bps=math.nan), spec) == []
    assert s05_decide(_frame(close=math.inf), spec) == []
    assert s05_decide(_frame(atr_pct=0), spec) == []


def test_s05_partial_fill_remains_partial_at_shared_simulator_boundary():
    spec = load_s05_specification()
    spec = spec.model_copy(
        update={"parameters": spec.parameters | {"target_notional_idr": "20000"}}
    )
    intent = s05_decide(_frame(), spec)[0]
    cost = CostScheduleInterval(
        schedule_id="test-maker",
        market="spot_idr",
        side=OrderSide.BUY,
        role=OrderRole.MAKER,
        valid_from=datetime(2024, 1, 1, tzinfo=UTC),
        valid_to=None,
        service_fee_rate=Decimal("0"),
        tax_rate=Decimal("0"),
        exchange_fee_rate=Decimal("0"),
        min_notional=Decimal("10000"),
        precision=0,
        sources=("test fixture",),
        evidence_verified=True,
    )
    table = CostScheduleTable(schedule_set_id="test", version="1", intervals=(cost,))
    bar = MarketBar(
        pair=intent.pair,
        open_time=AS_OF,
        close_time=AS_OF + timedelta(hours=1),
        open=Decimal("100000"),
        high=Decimal("101000"),
        low=Decimal("99000"),
        close=Decimal("100000"),
        base_volume=Decimal("1"),
        quote_volume=Decimal("100000"),
    )
    result = ConservativeExecutionSimulator(table).simulate_execution(
        intent, bar, order_created_ts=AS_OF
    )
    assert result.status == ExecutionStatus.PARTIAL
    assert result.filled_qty < intent.desired_qty
    assert result.remaining_qty == intent.desired_qty - result.filled_qty


def test_s05_uses_registered_impulse_pullback_and_atr_features():
    loaded = load_feature_registry("configs/features/tabular_bar_v1.yaml")
    names = {feature.name for feature in loaded.registry.features}
    assert {"log_ret_12_1h", "log_ret_1_1h", "atr_pct_14_1h"} <= names
