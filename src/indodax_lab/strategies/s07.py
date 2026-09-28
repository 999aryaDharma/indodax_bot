"""Small cap rotation strategy candidate (S07-01).

Contract:
Liquidity capacity constrained cross-sectional rank turnover -> versioned LONG/FLAT
intent, never direct orders.
"""

from __future__ import annotations

import math
from decimal import ROUND_DOWN, Decimal, DecimalException
from pathlib import Path
from typing import Any

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry

_QUANTITY_TICK = Decimal("0.0001")


def load_s07_specification(
    config_path: str | Path = "configs/strategies/S07_v1.yaml",
) -> StrategySpecification:
    """Load and strictly validate the canonical S07 small cap rotation specification."""
    return StrategyRegistry().load_specification_from_yaml(config_path)


def _finite_float(value: object) -> float | None:
    """Return a finite float or None for missing/NaN/non-finite inputs (fail closed)."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _liquidity_metrics(
    row: Any, min_volume: float, max_spread_bps: float
) -> tuple[str | None, Decimal | None]:
    """Screen one ranked row against the liquidity gates.

    Returns ``(rejection code, depth capacity)``; the code is None only when the pair
    is liquidity-eligible. Missing/NaN values fail closed, never zero-filled.
    """
    volume = _finite_float(row.get("volume"))
    if volume is None:
        volume = _finite_float(row.get("base_volume"))
    if volume is None or volume < min_volume:
        return "S07_ILLIQUID_VOLUME", None

    spread = _finite_float(row.get("spread_bps"))
    if spread is None or spread < 0:
        return "S07_MISSING_LIQUIDITY", None
    if spread > max_spread_bps:
        return "S07_WIDE_SPREAD", None

    depth = _finite_float(row.get("depth_50bps"))
    if depth is None:
        depth = _finite_float(row.get("depth"))
    if depth is None or depth <= 0:
        return "S07_MISSING_LIQUIDITY", None
    return None, Decimal(str(depth))


def s07_evaluate(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> tuple[list[SignalIntent], list[str]]:
    """Return (rotation intents, rejection diagnostics) for one point-in-time frame.

    Rejection diagnostics are ``S07_<REASON>`` or ``S07_<REASON>:<pair>`` strings that
    identify what was rejected without carrying private payloads.
    """
    if spec is None:
        spec = load_s07_specification()

    params = spec.parameters
    try:
        lookback_bars = int(params.get("lookback_bars", 24))
        top_k = int(params.get("top_k", 2))
        min_volume = float(params.get("min_volume", 100.0))
        max_spread_bps = float(params.get("max_spread_bps", 30.0))
        cash_reserve_pct = Decimal(str(params.get("cash_reserve_pct", 0.20)))
        atr_mult = float(params.get("atr_multiplier", 2.0))
    except (DecimalException, TypeError, ValueError) as exc:
        raise ValueError("INVALID_S07_PARAMETERS") from exc
    if (
        lookback_bars < 1
        or top_k < 1
        or not math.isfinite(min_volume)
        or min_volume <= 0
        or not math.isfinite(max_spread_bps)
        or max_spread_bps <= 0
        or not cash_reserve_pct.is_finite()
        or cash_reserve_pct < 0
        or cash_reserve_pct >= 1
        or not math.isfinite(atr_mult)
        or atr_mult <= 0
    ):
        raise ValueError("INVALID_S07_PARAMETERS")

    rejections: list[str] = []

    cash = frame.available_cash_idr
    if cash is None or cash <= 0:
        rejections.append("S07_SHARED_CASH_UNAVAILABLE")
        return [], rejections

    # PIT cross-sectional momentum candidates (C04 lineage): causal rows only,
    # positive lookback return, canonical pair iteration order.
    candidates: list[dict[str, Any]] = []
    for pair in sorted(frame.eligible_pairs):
        p_df = frame.get_pair_features(pair)
        if len(p_df) < lookback_bars + 1:
            continue
        window = p_df.iloc[-lookback_bars - 1 :]
        start_row = window.iloc[0]
        curr_row = window.iloc[-1]
        if "eligible" in curr_row.index and not curr_row["eligible"]:
            continue
        start_close = _finite_float(start_row.get("close"))
        curr_close = _finite_float(curr_row.get("close"))
        if (
            start_close is None
            or curr_close is None
            or start_close <= 0
            or curr_close <= 0
        ):
            continue
        momentum = (curr_close - start_close) / start_close
        if not math.isfinite(momentum) or momentum <= 0.0:
            continue
        candidates.append(
            {
                "pair": pair,
                "close": curr_close,
                "momentum": momentum,
                "row": curr_row,
            }
        )

    if not candidates:
        return [], rejections

    # Deterministic rank: momentum descending, canonical pair ascending on ties.
    candidates.sort(key=lambda cand: (-float(cand["momentum"]), str(cand["pair"])))

    # Liquidity screen while rotation slots fill (S01 lineage): an illiquid top
    # rank never takes a slot automatically; the next liquid rank backfills it.
    selected: list[dict[str, Any]] = []
    for cand in candidates:
        if len(selected) >= top_k:
            break
        rejection, capacity = _liquidity_metrics(cand["row"], min_volume, max_spread_bps)
        if rejection is not None:
            rejections.append(f"{rejection}:{cand['pair']}")
            continue
        cand["capacity"] = capacity
        selected.append(cand)

    # Shared-cash slot rotation: the shared pool is deployed once, reserving
    # cash_reserve_pct, split across top_k slots and bounded by what remains.
    deployable = cash * (Decimal("1") - cash_reserve_pct)
    slot = deployable / Decimal(str(top_k))
    remaining = deployable

    intents: list[SignalIntent] = []
    decision_epoch = int(frame.as_of.timestamp())
    for cand in selected:
        pair = str(cand["pair"])
        row = cand["row"]
        price = Decimal(str(cand["close"]))
        atr_val = _finite_float(row.get("atr_14"))
        if atr_val is None:
            atr_val = _finite_float(row.get("atr"))
        if atr_val is None or atr_val <= 0:
            rejections.append(f"S07_ATR_INVALID:{pair}")
            continue
        notional = min(slot, remaining)
        # Capacity gate: an order above the pair's visible liquidity depth (quote
        # IDR in the 50bps band) is rejected with an explicit reason, never shrunk.
        if notional > cand["capacity"]:
            rejections.append(f"S07_OVER_CAPACITY:{pair}")
            continue
        qty = (notional / price).quantize(_QUANTITY_TICK, rounding=ROUND_DOWN)
        if qty <= 0:
            rejections.append(f"S07_ORDER_NOT_POSITIVE:{pair}")
            continue
        stop_loss = price - Decimal(str(atr_val)) * Decimal(str(atr_mult))
        if stop_loss <= 0:
            rejections.append(f"S07_ATR_INVALID:{pair}")
            continue
        intents.append(
            SignalIntent(
                intent_id=f"s07_{pair}_{decision_epoch}",
                decision_ts=frame.as_of,
                pair=pair,
                side=OrderSide.BUY,
                desired_qty=qty,
                limit_price=price,
                stop_loss=stop_loss,
                strategy_id=spec.strategy_id,
            )
        )
        remaining -= qty * price

    return intents, rejections


def s07_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
    """Pure, stateless decision function for the S07 small cap rotation candidate.

    Invariants:
    - Only liquidity-eligible ranked pairs can take a rotation slot (never automatic).
    - Orders sized above the pair's liquidity capacity are rejected, never shrunk.
    - Slot sizing deploys at most ``(1 - cash_reserve_pct)`` of shared available cash.
    - Strategies only produce SignalIntent, zero ledger or fill authority.
    """
    intents, _ = s07_evaluate(frame, spec)
    return intents
