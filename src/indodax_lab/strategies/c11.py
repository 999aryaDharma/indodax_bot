"""Inverse-volatility allocation using explicit simulator cash context."""

from __future__ import annotations

from decimal import Decimal, DecimalException
from pathlib import Path

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry


def load_c11_specification(
    config_path: str | Path = "configs/strategies/C11_v1.yaml",
) -> StrategySpecification:
    return StrategyRegistry().load_specification_from_yaml(config_path)


def c11_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
    """Return cash-bounded LONG intents; missing capital context means abstain."""
    if spec is None:
        spec = load_c11_specification()
    cash = frame.available_cash_idr
    if cash is None or cash <= 0:
        return []

    params = spec.parameters
    volatility_feature = str(params.get("volatility_feature", "rv_24_1h"))
    price_feature = str(params.get("price_feature", "close"))
    try:
        min_pairs = int(params.get("minimum_valid_pairs", 2))
        deployment = Decimal(str(params.get("deployment_fraction", "0.50")))
        pair_fraction = Decimal(str(params.get("max_pair_fraction", "0.25")))
        min_notional = Decimal(str(params.get("min_notional_idr", "10000")))
    except (DecimalException, TypeError, ValueError) as exc:
        raise ValueError("INVALID_C11_ALLOCATION_PARAMETERS") from exc
    if (
        min_pairs < 2
        or not deployment.is_finite()
        or deployment <= 0
        or deployment > Decimal("0.50")
        or not pair_fraction.is_finite()
        or pair_fraction <= 0
        or pair_fraction > Decimal("0.25")
        or not min_notional.is_finite()
        or min_notional <= 0
    ):
        raise ValueError("INVALID_C11_ALLOCATION_PARAMETERS")
    pair_cap = cash * pair_fraction
    pool = cash * deployment

    candidates: list[tuple[str, Decimal, Decimal]] = []
    for pair in sorted(frame.eligible_pairs):
        row = frame.latest_row(pair)
        if row is None:
            continue
        try:
            rv = Decimal(str(row[volatility_feature]))
            price = Decimal(str(row[price_feature]))
        except (DecimalException, KeyError, TypeError, ValueError):
            continue
        if not rv.is_finite() or rv <= 0 or not price.is_finite() or price <= 0:
            continue
        try:
            inverse_vol = Decimal(1) / rv
        except DecimalException:
            continue
        if inverse_vol.is_finite() and inverse_vol > 0:
            candidates.append((pair, inverse_vol, price))

    if len(candidates) < min_pairs:
        return []

    weight_sum = sum((weight for _, weight, _ in candidates), Decimal(0))
    intents: list[SignalIntent] = []
    remaining = pool
    for pair, weight, price in candidates:
        try:
            allocation = min(pool * weight / weight_sum, pair_cap, remaining)
            if allocation < min_notional:
                continue
            quantity = allocation / price
            while quantity > 0 and quantity * price > allocation:
                quantity = quantity.next_minus()
        except DecimalException:
            continue
        notional = quantity * price
        if quantity <= 0 or notional < min_notional or notional > allocation:
            continue
        intents.append(
            SignalIntent(
                intent_id=f"c11_{pair}_{int(frame.as_of.timestamp())}",
                decision_ts=frame.as_of,
                pair=pair,
                side=OrderSide.BUY,
                desired_qty=quantity,
                limit_price=price,
                strategy_id=spec.strategy_id,
            )
        )
        remaining -= notional
    return intents
