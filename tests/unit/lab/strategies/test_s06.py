import math
from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd

from indodax_lab.backtest.feature_replay import FeatureReplayAdapter, FeatureReplayConfig
from indodax_lab.features.registry import load_feature_registry
from indodax_lab.strategies.s06 import load_s06_specification, s06_decide

AS_OF = datetime(2025, 1, 1, tzinfo=UTC)


def _frame(
    *,
    age_days=180,
    log_return=0.05,
    completeness=1.0,
    atr_pct=0.01,
    close=100_000.0,
):
    row = {
        "pair": "newcoin_idr",
        "decision_ts": AS_OF,
        "row_ready_at": AS_OF,
        "eligible": True,
        "close": close,
        "log_listing_age_days": math.log1p(age_days) if age_days is not None else None,
        "log_ret_24_1h": log_return,
        "bar_completeness_24_1h": completeness,
        "atr_pct_14_1h": atr_pct,
    }
    adapter = FeatureReplayAdapter(
        FeatureReplayConfig("newcoin_idr", "1h", "1h", require_context=False)
    )
    return adapter.build_decision_frame(
        signal_rows=pd.DataFrame([row]),
        context_rows=pd.DataFrame(),
        as_of=AS_OF,
    )


def test_s06_valid_post_listing_momentum_intent():
    intent = s06_decide(_frame(), load_s06_specification())[0]
    assert intent.pair == "newcoin_idr"
    assert intent.desired_qty * intent.limit_price >= Decimal("10000")
    assert intent.stop_loss == Decimal("98000.0")
    assert intent.strategy_id == "S06"


def test_s06_rejects_initial_listing_spike_and_age_below_boundary():
    spec = load_s06_specification()
    assert s06_decide(_frame(age_days=179), spec) == []
    assert s06_decide(_frame(age_days=200, log_return=0.8), spec) == []


def test_s06_accepts_exact_minimum_age_and_history_boundaries():
    intent = s06_decide(_frame(age_days=180, completeness=0.95), load_s06_specification())
    assert len(intent) == 1


def test_s06_unknown_listing_age_and_incomplete_history_abstain():
    spec = load_s06_specification()
    assert s06_decide(_frame(age_days=None), spec) == []
    assert s06_decide(_frame(completeness=0.949), spec) == []


def test_s06_rejects_nonpositive_or_spike_momentum_and_invalid_prices():
    spec = load_s06_specification()
    assert s06_decide(_frame(log_return=0), spec) == []
    assert s06_decide(_frame(log_return=0.251), spec) == []
    assert s06_decide(_frame(close=float("nan")), spec) == []


def test_s06_rejects_invalid_versioned_parameters():
    spec = load_s06_specification()
    for key, value in (
        ("minimum_listing_age_days", 180.5),
        ("max_24h_log_return", float("nan")),
        ("min_history_completeness", 1.1),
        ("atr_multiplier", 0),
        ("target_notional_idr", "9999"),
    ):
        invalid = spec.model_copy(update={"parameters": spec.parameters | {key: value}})
        try:
            s06_decide(_frame(), invalid)
        except ValueError as exc:
            assert str(exc) == "INVALID_S06_PARAMETERS"
        else:
            raise AssertionError(f"accepted invalid S06 parameter {key}={value!r}")


def test_s06_consumes_registered_features_through_replay_adapter():
    loaded = load_feature_registry("configs/features/tabular_bar_v1.yaml")
    available = {feature.name for feature in loaded.registry.features}
    assert {
        "log_listing_age_days",
        "log_ret_24_1h",
        "bar_completeness_24_1h",
        "atr_pct_14_1h",
    } <= available
    assert len(s06_decide(_frame(), load_s06_specification())) == 1
