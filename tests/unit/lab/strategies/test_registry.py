"""Unit tests for declarative strategy protocol and registry (STRAT-01)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
import pandas as pd
import pytest
from pydantic import ValidationError

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.strategies.base import (
    DecisionFrame,
    RegisteredStrategy,
    StrategySpecification,
    create_decision_frame,
)
from indodax_lab.strategies.registry import StrategyRegistry


def _make_sample_features(
    as_of: datetime,
    include_future: bool = True,
    include_ineligible: bool = True,
) -> pd.DataFrame:
    """Helper to generate a feature dataframe with valid, future, and ineligible rows."""
    rows: list[dict[str, Any]] = [
        # Valid historical row
        {
            "pair": "btc_idr",
            "decision_ts": as_of - timedelta(hours=1),
            "row_ready_at": as_of - timedelta(hours=1),
            "close": 1000000000.0,
            "atr_14": 15000000.0,
            "eligible": True,
            "missing_feature_count": 0,
            "reason_codes": (),
        },
        # Current valid row at as_of
        {
            "pair": "btc_idr",
            "decision_ts": as_of,
            "row_ready_at": as_of,
            "close": 1050000000.0,
            "atr_14": 16000000.0,
            "eligible": True,
            "missing_feature_count": 0,
            "reason_codes": (),
        },
        # Valid row for second pair at as_of
        {
            "pair": "eth_idr",
            "decision_ts": as_of,
            "row_ready_at": as_of,
            "close": 50000000.0,
            "atr_14": 1200000.0,
            "eligible": True,
            "missing_feature_count": 0,
            "reason_codes": (),
        },
    ]

    if include_future:
        # Future row (row_ready_at > as_of or decision_ts > as_of)
        rows.append(
            {
                "pair": "btc_idr",
                "decision_ts": as_of + timedelta(hours=1),
                "row_ready_at": as_of + timedelta(hours=1),
                "close": 1100000000.0,
                "atr_14": 17000000.0,
                "eligible": True,
                "missing_feature_count": 0,
                "reason_codes": (),
            }
        )

    if include_ineligible:
        # Ineligible row (e.g. insufficient lookback or missing feature)
        rows.append(
            {
                "pair": "sol_idr",
                "decision_ts": as_of,
                "row_ready_at": as_of,
                "close": 2000000.0,
                "atr_14": 100000.0,
                "eligible": False,
                "missing_feature_count": 1,
                "reason_codes": ("INSUFFICIENT_LOOKBACK",),
            }
        )

    df = pd.DataFrame(rows)
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    return df


def test_strat_01_valid_contract():
    """STRAT-01-AC0: Strategi terdaftar hanya menghasilkan intent dan tidak memiliki otoritas fill atau ledger."""
    spec = StrategySpecification(
        strategy_id="C01_test",
        version="1.0.0",
        family="breakout",
        universe_tier="top_liquid",
        timeframes=["1h"],
        signal_timing="bar_close",
        execution_timing="next_bar_open",
        parameters={"lookback_bars": 20, "atr_multiplier": 2.0},
        risk_profile={"max_position_pct": 0.25, "stop_loss_pct": 0.02},
        split="train",
        status="active",
    )

    def simple_breakout_decide(frame: DecisionFrame) -> list[SignalIntent]:
        intents: list[SignalIntent] = []
        for pair in frame.eligible_pairs:
            pair_df = frame.get_pair_features(pair)
            if not pair_df.empty:
                last_row = pair_df.iloc[-1]
                intents.append(
                    SignalIntent(
                        intent_id=f"intent_{pair}_{int(frame.as_of.timestamp())}",
                        decision_ts=frame.as_of,
                        pair=pair,
                        side=OrderSide.BUY,
                        desired_qty=Decimal("0.1"),
                        limit_price=Decimal(str(last_row["close"])),
                        role_preference=OrderRole.TAKER,
                        strategy_id=spec.strategy_id,
                    )
                )
        return intents

    registry = StrategyRegistry()
    registered = registry.register(spec, simple_breakout_decide)

    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    df = _make_sample_features(as_of, include_future=False, include_ineligible=False)
    frame = create_decision_frame(df, as_of=as_of)

    # Strategy produces intents over decision frame
    intents = registered.decide(frame)

    assert isinstance(intents, list)
    assert len(intents) == 2
    for intent in intents:
        assert isinstance(intent, SignalIntent)
        assert intent.strategy_id == "C01_test"
        assert intent.decision_ts == as_of
        assert intent.side in (OrderSide.BUY, OrderSide.SELL)

    # Verify strategy has zero fill or ledger authority:
    # 1. RegisteredStrategy does not expose any fill/ledger mutation methods
    assert not hasattr(registered, "fill")
    assert not hasattr(registered, "ledger")
    assert not hasattr(registered, "process_fill")
    assert not hasattr(registered, "update_balance")

    # 2. If a decide function attempts to return non-SignalIntent objects, it is rejected
    def rogue_decide(frame: DecisionFrame) -> list[Any]:
        return [{"status": "filled", "amount": 1000}]  # Attempting to return fake fill

    rogue_spec = spec.model_copy(update={"strategy_id": "rogue_strat"})
    rogue_strategy = RegisteredStrategy(specification=rogue_spec, decide_fn=rogue_decide)
    with pytest.raises(TypeError, match="ONLY_SIGNAL_INTENT_ALLOWED"):
        rogue_strategy.decide(frame)


def test_strat_01_contract_1():
    """STRAT-01-AC1: Unknown config ditolak."""
    # Extra field passed directly to StrategySpecification must be rejected
    with pytest.raises(ValidationError) as exc_info:
        StrategySpecification(
            strategy_id="C01_test",
            version="1.0.0",
            family="breakout",
            universe_tier="top_liquid",
            timeframes=["1h"],
            parameters={"lookback_bars": 20},
            risk_profile={"max_position_pct": 0.25},
            split="train",
            status="active",
            unknown_arbitrary_field="not_allowed",  # Forbidden extra field
        )
    assert "extra_forbidden" in str(exc_info.value) or "unknown_arbitrary_field" in str(exc_info.value)

    # Also reject unknown fields when loaded via registry / dict
    registry = StrategyRegistry()
    raw_config = {
        "strategy_id": "C01_test",
        "version": "1.0.0",
        "family": "breakout",
        "universe_tier": "top_liquid",
        "timeframes": ["1h"],
        "parameters": {"lookback_bars": 20},
        "risk_profile": {"max_position_pct": 0.25},
        "split": "train",
        "status": "active",
        "unauthorized_key": 12345,
    }
    with pytest.raises(ValueError, match="UNKNOWN_CONFIG_FIELDS|extra_forbidden|unauthorized_key"):
        registry.load_specification_from_dict(raw_config)


def test_strat_01_contract_2():
    """STRAT-01-AC2: Future atau ineligible row tidak masuk DecisionFrame."""
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    df_raw = _make_sample_features(as_of, include_future=True, include_ineligible=True)

    # create_decision_frame must strictly filter out future and ineligible rows
    frame = create_decision_frame(df_raw, as_of=as_of)

    # Assert no future rows exist in frame
    assert (frame.features["decision_ts"] <= as_of).all()
    assert (frame.features["row_ready_at"] <= as_of).all()

    # Assert no ineligible rows exist in frame
    assert (frame.features["eligible"] == True).all()
    assert "sol_idr" not in frame.eligible_pairs  # sol_idr was ineligible

    # Pairs must only contain eligible pairs present in the filtered features
    assert frame.eligible_pairs == ("btc_idr", "eth_idr")

    # Direct construction of DecisionFrame with future or ineligible rows must be rejected
    future_row = df_raw[df_raw["decision_ts"] > as_of]
    with pytest.raises(ValueError, match="FUTURE_OR_INELIGIBLE_ROWS_FORBIDDEN"):
        DecisionFrame(as_of=as_of, features=future_row, eligible_pairs=("btc_idr",))

    ineligible_row = df_raw[df_raw["eligible"] == False]
    with pytest.raises(ValueError, match="FUTURE_OR_INELIGIBLE_ROWS_FORBIDDEN"):
        DecisionFrame(as_of=as_of, features=ineligible_row, eligible_pairs=("sol_idr",))


def test_strat_01_contract_3():
    """STRAT-01-AC3: Parameter atau logic change memerlukan versi baru."""
    spec_v1 = StrategySpecification(
        strategy_id="C01_donchian",
        version="1.0.0",
        family="breakout",
        universe_tier="top_liquid",
        timeframes=["1h"],
        parameters={"lookback_bars": 20},
        risk_profile={"max_position_pct": 0.25},
        split="train",
        status="active",
    )

    def logic_v1(frame: DecisionFrame) -> list[SignalIntent]:
        return []

    registry = StrategyRegistry()
    registry.register(spec_v1, logic_v1)

    # 1. Attempting to register the same strategy ID and version with altered parameters must fail
    spec_v1_modified_params = spec_v1.model_copy(
        update={"parameters": {"lookback_bars": 30}}
    )
    with pytest.raises(ValueError, match="PARAMETER_OR_LOGIC_CHANGE_REQUIRES_VERSION_BUMP"):
        registry.register(spec_v1_modified_params, logic_v1)

    # 2. Attempting to register the same strategy ID and version with altered logic must fail
    def logic_v2(frame: DecisionFrame) -> list[SignalIntent]:
        return [
            SignalIntent(
                intent_id="i1",
                decision_ts=frame.as_of,
                pair="btc_idr",
                side=OrderSide.BUY,
                desired_qty=Decimal("1.0"),
            )
        ]

    with pytest.raises(ValueError, match="PARAMETER_OR_LOGIC_CHANGE_REQUIRES_VERSION_BUMP"):
        registry.register(spec_v1, logic_v2)

    # 3. Registering with bumped semantic version succeeds
    spec_v2 = spec_v1.model_copy(
        update={"version": "1.1.0", "parameters": {"lookback_bars": 30}}
    )
    registered_v2 = registry.register(spec_v2, logic_v2)
    assert registered_v2.specification.version == "1.1.0"
