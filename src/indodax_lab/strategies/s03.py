"""Abnormal volume continuation candidate (S03-01)."""

from __future__ import annotations

import math
from decimal import Decimal, DecimalException
from pathlib import Path

import numpy as np
import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry


def load_s03_specification(
    config_path: str | Path = "configs/strategies/S03_v1.yaml",
) -> StrategySpecification:
    return StrategyRegistry().load_specification_from_yaml(config_path)


def s03_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
    """Emit a minimum-notional LONG intent only after volume/price/flag gates pass."""
    if spec is None:
        spec = load_s03_specification()

    params = spec.parameters
    try:
        min_volume_z = float(params.get("min_volume_z", 2.0))
        max_log_return = float(params.get("max_24h_log_return", 0.25))
        atr_multiplier = float(params.get("atr_multiplier", 2.0))
        target_notional = Decimal(str(params.get("target_notional_idr", "10000")))
    except (DecimalException, OverflowError, TypeError, ValueError) as exc:
        raise ValueError("INVALID_S03_PARAMETERS") from exc
    if (
        not all(math.isfinite(v) for v in (min_volume_z, max_log_return, atr_multiplier))
        or min_volume_z <= 0
        or max_log_return <= 0
        or atr_multiplier <= 0
        or not target_notional.is_finite()
        or target_notional < Decimal("10000")
    ):
        raise ValueError("INVALID_S03_PARAMETERS")

    intents: list[SignalIntent] = []
    for pair in sorted(frame.eligible_pairs):
        row = frame.latest_row(pair)
        if row is None:
            continue
        flag = row.get("pump_manipulation_flag")
        fields = (
            row.get("close"),
            row.get("volume_z_20_1h"),
            row.get("log_ret_24_1h"),
            row.get("atr_pct_14_1h"),
        )
        if (
            not isinstance(flag, (bool, np.bool_))
            or bool(flag)
            or any(value is None or pd.isna(value) for value in fields)
        ):
            continue
        try:
            close, volume_z, log_return, atr_pct = map(float, fields)
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in (close, volume_z, log_return, atr_pct)):
            continue
        if (
            close <= 0
            or volume_z < min_volume_z
            or not 0 < log_return <= max_log_return
            or atr_pct <= 0
            or atr_pct * atr_multiplier >= 1
        ):
            continue

        try:
            price = Decimal(str(close))
            quantity = target_notional / price
            while quantity * price < target_notional:
                quantity = quantity.next_plus()
            stop_loss = price * (Decimal(1) - Decimal(str(atr_pct * atr_multiplier)))
        except DecimalException:
            continue
        if stop_loss <= 0:
            continue
        intents.append(
            SignalIntent(
                intent_id=f"s03_{pair}_{int(frame.as_of.timestamp())}",
                decision_ts=frame.as_of,
                pair=pair,
                side=OrderSide.BUY,
                desired_qty=quantity,
                limit_price=price,
                stop_loss=stop_loss,
                strategy_id=spec.strategy_id,
            )
        )
    return intents
