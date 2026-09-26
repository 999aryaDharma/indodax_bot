import math
from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd

from indodax_lab.backtest.feature_replay import FeatureReplayAdapter, FeatureReplayConfig
from indodax_lab.features.registry import load_feature_registry
from indodax_lab.strategies.s03 import load_s03_specification, s03_decide

AS_OF = datetime(2025, 1, 1, tzinfo=UTC)


def _frame(*, volume_z=2.5, log_return=0.05, pump_flag=False, atr_pct=0.01, close=100_000.0):
    row = {
        "pair": "smallcoin_idr",
        "decision_ts": AS_OF,
        "row_ready_at": AS_OF,
        "eligible": True,
        "close": close,
        "volume_z_20_1h": volume_z,
        "log_ret_24_1h": log_return,
        "atr_pct_14_1h": atr_pct,
        "pump_manipulation_flag": pump_flag,
    }
    adapter = FeatureReplayAdapter(
        FeatureReplayConfig("smallcoin_idr", "1h", "1h", require_context=False)
    )
    return adapter.build_decision_frame(
        signal_rows=pd.DataFrame([row]), context_rows=pd.DataFrame(), as_of=AS_OF
    )


def test_s03_valid_volume_continuation_emits_minimum_sized_intent():
    intent = s03_decide(_frame(), load_s03_specification())[0]
    assert intent.pair == "smallcoin_idr"
    assert intent.desired_qty * intent.limit_price >= Decimal("10000")
    assert intent.stop_loss == Decimal("98000.0")
    assert intent.strategy_id == "S03"


def test_s03_accepts_configured_volume_and_return_boundaries():
    assert len(s03_decide(_frame(volume_z=2.0, log_return=0.25), load_s03_specification())) == 1


def test_s03_requires_volume_spike_and_price_follow_through():
    spec = load_s03_specification()
    assert s03_decide(_frame(volume_z=1.99), spec) == []
    assert s03_decide(_frame(log_return=0), spec) == []
    assert s03_decide(_frame(log_return=-0.01), spec) == []
    assert s03_decide(_frame(log_return=0.251), spec) == []


def test_s03_flagged_or_unknown_manipulation_abstains():
    spec = load_s03_specification()
    assert s03_decide(_frame(pump_flag=True), spec) == []
    assert s03_decide(_frame(pump_flag=None), spec) == []
    assert s03_decide(_frame(pump_flag=1), spec) == []


def test_s03_missing_or_nonfinite_inputs_abstain():
    spec = load_s03_specification()
    assert s03_decide(_frame(volume_z=None), spec) == []
    assert s03_decide(_frame(volume_z=math.nan), spec) == []
    assert s03_decide(_frame(close=math.inf), spec) == []
    assert s03_decide(_frame(atr_pct=0), spec) == []


def test_s03_invalid_parameters_reject():
    spec = load_s03_specification()
    for key, value in (
        ("min_volume_z", -1),
        ("max_24h_log_return", math.nan),
        ("atr_multiplier", 0),
        ("target_notional_idr", "9999"),
    ):
        invalid = spec.model_copy(update={"parameters": spec.parameters | {key: value}})
        try:
            s03_decide(_frame(), invalid)
        except ValueError as exc:
            assert str(exc) == "INVALID_S03_PARAMETERS"
        else:
            raise AssertionError(f"accepted invalid S03 parameter {key}={value!r}")


def test_s03_uses_registered_volume_return_and_atr_features():
    loaded = load_feature_registry("configs/features/tabular_bar_v1.yaml")
    names = {feature.name for feature in loaded.registry.features}
    assert {"volume_z_20_1h", "log_ret_24_1h", "atr_pct_14_1h"} <= names
