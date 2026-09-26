"""Multi-timeframe trend confirmation strategy candidate (C08-01)."""

from __future__ import annotations

import math
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry


def load_c08_specification(
    config_path: str | Path = "configs/strategies/C08_v1.yaml",
) -> StrategySpecification:
    """Load and validate the canonical C08 specification."""
    return StrategyRegistry().load_specification_from_yaml(config_path)


def c08_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
    """Emit LONG only when daily/4h trends and a lower-timeframe trigger align."""
    spec = spec or load_c08_specification()
    params = spec.parameters
    daily_age_hours = float(params.get("daily_max_age_hours", 36))
    four_hour_age_hours = float(params.get("four_hour_max_age_hours", 6))
    if any(
        not math.isfinite(hours) or hours <= 0
        for hours in (daily_age_hours, four_hour_age_hours)
    ):
        raise ValueError("C08_INVALID_CONTEXT_MAX_AGE")
    daily_max_age = timedelta(hours=daily_age_hours)
    four_hour_max_age = timedelta(hours=four_hour_age_hours)
    trigger_lookback = int(params.get("trigger_lookback_bars", 20))
    atr_multiplier = float(params.get("atr_multiplier", 2.0))
    desired_qty = Decimal(str(params.get("desired_qty", "0.1")))
    if trigger_lookback < 1:
        raise ValueError("C08_TRIGGER_LOOKBACK_MUST_BE_POSITIVE")
    if atr_multiplier <= 0 or not math.isfinite(atr_multiplier) or desired_qty <= 0:
        raise ValueError("C08_INVALID_RISK_OR_SIZE_PARAMETER")

    intents: list[SignalIntent] = []
    for pair in frame.eligible_pairs:
        row = frame.latest_row(pair)
        if row is None:
            continue
        valid = True
        for prefix, max_age in (("daily", daily_max_age), ("four_hour", four_hour_max_age)):
            closed = row.get(f"{prefix}_closed")
            decision_ts = pd.to_datetime(
                row.get(f"{prefix}_decision_ts"), utc=True, errors="coerce"
            )
            ready_at = pd.to_datetime(
                row.get(f"{prefix}_row_ready_at"), utc=True, errors="coerce"
            )
            if (
                pd.isna(closed)
                or not pd.api.types.is_bool(closed)
                or not bool(closed)
                or pd.isna(decision_ts)
                or pd.isna(ready_at)
                or ready_at < decision_ts
                or decision_ts > frame.as_of
                or ready_at > frame.as_of
                or frame.as_of - decision_ts.to_pydatetime() > max_age
            ):
                valid = False
                break
        if not valid:
            continue

        names = (
            "daily_close",
            "daily_ema_fast",
            "daily_ema_slow",
            "four_hour_close",
            "four_hour_ema_fast",
            "four_hour_ema_slow",
            "close",
            f"lower_prev_{trigger_lookback}_high",
            "atr_14",
        )
        values = [row.get(name) for name in names]
        if any(value is None or pd.isna(value) for value in values):
            continue
        try:
            numeric = [float(value) for value in values]
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(value) and value > 0 for value in numeric):
            continue
        (
            daily_close,
            daily_fast,
            daily_slow,
            four_hour_close,
            four_hour_fast,
            four_hour_slow,
            close,
            previous_high,
            atr,
        ) = numeric
        daily_up = daily_close > daily_slow and daily_fast > daily_slow
        four_hour_up = four_hour_close > four_hour_slow and four_hour_fast > four_hour_slow
        if not daily_up or not four_hour_up or close <= previous_high:
            continue

        stop_loss = close - atr_multiplier * atr
        if stop_loss <= 0:
            continue
        intents.append(
            SignalIntent(
                intent_id=f"c08_{pair}_{int(frame.as_of.timestamp())}",
                decision_ts=frame.as_of,
                pair=pair,
                side=OrderSide.BUY,
                desired_qty=desired_qty,
                limit_price=Decimal(str(close)),
                stop_loss=Decimal(str(stop_loss)),
                strategy_id=spec.strategy_id,
            )
        )
    return intents
