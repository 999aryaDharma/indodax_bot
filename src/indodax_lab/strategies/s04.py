"""Order-flow imbalance candidate using approved, versioned LOB evidence."""

from __future__ import annotations

import math
from datetime import timedelta
from decimal import Decimal, DecimalException
from pathlib import Path

import numpy as np
import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry


def load_s04_specification(
    config_path: str | Path = "configs/strategies/S04_v1.yaml",
) -> StrategySpecification:
    return StrategyRegistry().load_specification_from_yaml(config_path)


def _utc_timestamp(value: object) -> pd.Timestamp | None:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
        return None
    return timestamp


def s04_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
    """Emit candidate-sized LONG intents only from fresh, contiguous lob_v1 rows."""
    if spec is None:
        spec = load_s04_specification()
    params = spec.parameters
    try:
        feature_set_id = str(params["feature_set_id"])
        feature_set_version = str(params["feature_set_version"])
        min_book = float(params["min_book_imbalance_l5"])
        min_trade = float(params["min_trade_imbalance_10s"])
        max_age = float(params["max_book_age_seconds"])
        target_notional = Decimal(str(params["target_notional_idr"]))
        stop_loss_pct = Decimal(str(params["stop_loss_pct"]))
    except (KeyError, DecimalException, OverflowError, TypeError, ValueError) as exc:
        raise ValueError("INVALID_S04_PARAMETERS") from exc
    if (
        feature_set_id != "lob_v1"
        or not feature_set_version
        or not all(math.isfinite(value) for value in (min_book, min_trade, max_age))
        or not -1 <= min_book <= 1
        or not -1 <= min_trade <= 1
        or max_age <= 0
        or not target_notional.is_finite()
        or target_notional < Decimal("10000")
        or not stop_loss_pct.is_finite()
        or not Decimal(0) < stop_loss_pct < Decimal(1)
    ):
        raise ValueError("INVALID_S04_PARAMETERS")
    if (
        frame.feature_set_id != feature_set_id
        or frame.feature_set_version != feature_set_version
    ):
        return []

    intents: list[SignalIntent] = []
    for pair in sorted(frame.eligible_pairs):
        row = frame.latest_row(pair)
        if row is None:
            continue
        session = row.get("book_session_id")
        contiguous = row.get("book_sequence_contiguous")
        values = (row.get("book_imbalance_l5"), row.get("trade_imbalance_10s"), row.get("close"))
        if (
            not isinstance(session, str)
            or not session.strip()
            or not isinstance(contiguous, (bool, np.bool_))
            or not bool(contiguous)
            or any(value is None or not np.isscalar(value) for value in values)
        ):
            continue
        try:
            book_imbalance, trade_imbalance, close = map(float, values)
        except (TypeError, ValueError, OverflowError):
            continue
        if (
            not all(math.isfinite(value) for value in (book_imbalance, trade_imbalance, close))
            or not -1 <= book_imbalance <= 1
            or not -1 <= trade_imbalance <= 1
            or close <= 0
            or book_imbalance < min_book
            or trade_imbalance < min_trade
        ):
            continue

        event_ts = _utc_timestamp(row.get("book_event_ts"))
        available_at = _utc_timestamp(row.get("book_available_at"))
        decision_ts = _utc_timestamp(row.get("decision_ts"))
        row_ready_at = _utc_timestamp(row.get("row_ready_at"))
        if (
            event_ts is None
            or available_at is None
            or decision_ts is None
            or row_ready_at is None
        ):
            continue
        as_of = pd.Timestamp(frame.as_of)
        age_seconds = (decision_ts - event_ts).total_seconds()
        if (
            age_seconds < 0
            or age_seconds > max_age
            or decision_ts != as_of
            or event_ts > decision_ts
            or available_at < event_ts
            or available_at > decision_ts
            or available_at > row_ready_at
        ):
            continue

        try:
            price = Decimal(str(close))
            quantity = target_notional / price
            if quantity * price < target_notional:
                quantity = quantity.next_plus()
            stop_loss = price * (Decimal(1) - stop_loss_pct)
        except DecimalException:
            continue
        if (
            not price.is_finite()
            or not quantity.is_finite()
            or quantity * price < target_notional
            or stop_loss <= 0
        ):
            continue
        intents.append(
            SignalIntent(
                intent_id=f"s04_{pair}_{int(frame.as_of.timestamp())}",
                decision_ts=decision_ts.to_pydatetime(),
                pair=pair,
                side=OrderSide.BUY,
                desired_qty=quantity,
                limit_price=price,
                stop_loss=stop_loss,
                strategy_id=spec.strategy_id,
            )
        )
    return intents
