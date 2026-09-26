"""Passive mean-reversion research candidate (S08-01)."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import Decimal, DecimalException
from pathlib import Path

import numpy as np
import pandas as pd

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry


def load_s08_specification(
    config_path: str | Path = "configs/strategies/S08_v1.yaml",
) -> StrategySpecification:
    return StrategyRegistry().load_specification_from_yaml(config_path)


def _utc(value: object) -> datetime | None:
    try:
        parsed = pd.Timestamp(value).to_pydatetime()
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        return None
    return parsed


def s08_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
    """Emit passive LONG intents from causal LOB evidence; execution stays external."""
    if spec is None:
        spec = load_s08_specification()
    if frame.feature_set_id != "lob_v1" or not frame.feature_set_version:
        return []
    try:
        params = spec.parameters
        min_book_imbalance = float(params["min_book_imbalance_l5"])
        max_trade_imbalance = float(params["max_trade_imbalance_10s"])
        max_spread = float(params["max_spread_bps"])
        quote_offset = Decimal(str(params["quote_offset_bps"]))
        stop_pct = Decimal(str(params["stop_loss_pct"]))
        target_pct = Decimal(str(params["take_profit_pct"]))
        target_notional = Decimal(str(params["target_notional_idr"]))
    except (DecimalException, KeyError, OverflowError, TypeError, ValueError) as exc:
        raise ValueError("INVALID_S08_PARAMETERS") from exc
    if (
        not all(
            math.isfinite(value)
            for value in (min_book_imbalance, max_trade_imbalance, max_spread)
        )
        or not 0 <= min_book_imbalance <= 1
        or not -1 <= max_trade_imbalance <= 0
        or max_spread <= 0
        or not quote_offset.is_finite()
        or quote_offset <= 0
        or not stop_pct.is_finite()
        or not target_pct.is_finite()
        or not 0 < stop_pct < 1
        or target_pct <= 0
        or not target_notional.is_finite()
        or target_notional < Decimal("10000")
    ):
        raise ValueError("INVALID_S08_PARAMETERS")

    intents: list[SignalIntent] = []
    for pair in sorted(frame.eligible_pairs):
        row = frame.latest_row(pair)
        if row is None:
            continue
        sequence = row.get("book_sequence_contiguous")
        session_id = row.get("book_session_id")
        if (
            pd.isna(sequence)
            or not isinstance(sequence, (bool, np.bool_))
            or not bool(sequence)
            or not isinstance(session_id, str)
            or not session_id.strip()
        ):
            continue
        event_at = _utc(row.get("book_event_ts"))
        available_at = _utc(row.get("book_available_at"))
        row_ready_at = _utc(row.get("row_ready_at"))
        if (
            event_at is None
            or available_at is None
            or row_ready_at is None
            or event_at > frame.as_of
            or available_at > frame.as_of
            or available_at > row_ready_at
        ):
            continue
        values = (
            row.get("close"),
            row.get("mid_price"),
            row.get("spread_bps"),
            row.get("book_imbalance_l5"),
            row.get("trade_imbalance_10s"),
        )
        if any(value is None or pd.isna(value) for value in values):
            continue
        try:
            close, mid, spread, book_imbalance, trade_imbalance = map(float, values)
        except (TypeError, ValueError):
            continue
        if (
            not all(
                math.isfinite(value)
                for value in (close, mid, spread, book_imbalance, trade_imbalance)
            )
            or close <= 0
            or mid <= 0
            or not 0 <= spread <= max_spread
            or not -1 <= book_imbalance <= 1
            or not -1 <= trade_imbalance <= 1
            or book_imbalance < min_book_imbalance
            or trade_imbalance > max_trade_imbalance
            or close >= mid
        ):
            continue
        try:
            price = Decimal(str(close)) * (Decimal(1) - quote_offset / Decimal(10000))
            quantity = target_notional / price
            while quantity * price < target_notional:
                quantity = quantity.next_plus()
            stop_loss = price * (Decimal(1) - stop_pct)
            take_profit = price * (Decimal(1) + target_pct)
        except DecimalException:
            continue
        intents.append(
            SignalIntent(
                intent_id=f"s08_{pair}_{int(frame.as_of.timestamp())}",
                decision_ts=frame.as_of,
                pair=pair,
                side=OrderSide.BUY,
                desired_qty=quantity,
                limit_price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                role_preference=OrderRole.MAKER,
                strategy_id=spec.strategy_id,
            )
        )
    return intents
