"""Triple barrier outcome labelling with causal barriers and concurrency weighting (LABEL-02)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, Mapping, Sequence
from pydantic import BaseModel, ConfigDict, Field


class BarrierTouch(StrEnum):
    """Barrier touch event outcome."""

    UPPER = "upper"
    LOWER = "lower"
    VERTICAL = "vertical"


class TripleBarrierConfig(BaseModel):
    """Configuration for triple barrier labelling."""

    model_config = ConfigDict(frozen=True)

    label_set_id: str = "triple_barrier"
    version: str = "1.0.0"
    pt_multiplier: Decimal = Decimal("2.0")
    sl_multiplier: Decimal = Decimal("1.5")
    vertical_horizon: timedelta = timedelta(hours=24)


class TripleBarrierLabel(BaseModel):
    """One immutable triple barrier label record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str
    label_set_id: str
    label_version: str
    pair: str
    decision_ts: datetime
    entry_ts: datetime | None = None
    label_end_ts: datetime | None = None
    entry_price: Decimal | None = None
    upper_barrier: Decimal | None = None
    lower_barrier: Decimal | None = None
    first_touch: BarrierTouch | None = None
    outcome: int | None = None
    mfe: Decimal | None = None
    mae: Decimal | None = None
    concurrency_weight: Decimal = Decimal("1.0")
    status: str = "VALID"
    exclusion_reason: str | None = None


def _get_val(bar: Any, key: str) -> Any:
    if isinstance(bar, Mapping):
        return bar[key]
    return getattr(bar, key)


def build_triple_barrier_label(
    sample_id: str,
    pair: str,
    decision_ts: datetime,
    decision_volatility: Decimal,
    bars: Sequence[Any],
    config: TripleBarrierConfig,
) -> TripleBarrierLabel:
    """Evaluate triple barrier outcome starting at next-open after decision_ts."""
    if not bars:
        raise ValueError("EMPTY_BARS")

    # Strict causality: entry at next eligible open >= decision_ts
    eligible_entry_bars = [b for b in bars if _get_val(b, "open_time") >= decision_ts]
    if not eligible_entry_bars:
        raise ValueError("ENTRY_BEFORE_OR_AT_DECISION")

    sorted_entry_bars = sorted(eligible_entry_bars, key=lambda b: _get_val(b, "open_time"))
    entry_bar = sorted_entry_bars[0]
    entry_ts = _get_val(entry_bar, "open_time")
    entry_price = Decimal(str(_get_val(entry_bar, "open")))

    # Calculate frozen barrier levels using decision-time volatility
    upper_barrier = entry_price * (Decimal("1") + config.pt_multiplier * decision_volatility)
    lower_barrier = entry_price * (Decimal("1") - config.sl_multiplier * decision_volatility)
    vertical_barrier_ts = entry_ts + config.vertical_horizon

    # Outcome evaluation over bars during [entry_ts, vertical_barrier_ts]
    outcome_bars = [
        b
        for b in bars
        if _get_val(b, "close_time") > entry_ts and _get_val(b, "open_time") < vertical_barrier_ts
    ]
    sorted_outcome_bars = sorted(outcome_bars, key=lambda b: _get_val(b, "open_time"))

    max_high = entry_price
    min_low = entry_price

    for bar in sorted_outcome_bars:
        b_high = Decimal(str(_get_val(bar, "high")))
        b_low = Decimal(str(_get_val(bar, "low")))
        b_close_time = _get_val(bar, "close_time")

        max_high = max(max_high, b_high)
        min_low = min(min_low, b_low)

        upper_hit = b_high >= upper_barrier
        lower_hit = b_low <= lower_barrier

        # LABEL-02-FR1: If both touched in same candle, conservative choice is LOWER
        if upper_hit and lower_hit:
            mfe = (max_high - entry_price) / entry_price
            mae = (entry_price - min_low) / entry_price
            return TripleBarrierLabel(
                sample_id=sample_id,
                label_set_id=config.label_set_id,
                label_version=config.version,
                pair=pair,
                decision_ts=decision_ts,
                entry_ts=entry_ts,
                label_end_ts=b_close_time,
                entry_price=entry_price,
                upper_barrier=upper_barrier,
                lower_barrier=lower_barrier,
                first_touch=BarrierTouch.LOWER,
                outcome=-1,
                mfe=mfe,
                mae=mae,
                status="VALID",
            )
        elif lower_hit:
            mfe = (max_high - entry_price) / entry_price
            mae = (entry_price - min_low) / entry_price
            return TripleBarrierLabel(
                sample_id=sample_id,
                label_set_id=config.label_set_id,
                label_version=config.version,
                pair=pair,
                decision_ts=decision_ts,
                entry_ts=entry_ts,
                label_end_ts=b_close_time,
                entry_price=entry_price,
                upper_barrier=upper_barrier,
                lower_barrier=lower_barrier,
                first_touch=BarrierTouch.LOWER,
                outcome=-1,
                mfe=mfe,
                mae=mae,
                status="VALID",
            )
        elif upper_hit:
            mfe = (max_high - entry_price) / entry_price
            mae = (entry_price - min_low) / entry_price
            return TripleBarrierLabel(
                sample_id=sample_id,
                label_set_id=config.label_set_id,
                label_version=config.version,
                pair=pair,
                decision_ts=decision_ts,
                entry_ts=entry_ts,
                label_end_ts=b_close_time,
                entry_price=entry_price,
                upper_barrier=upper_barrier,
                lower_barrier=lower_barrier,
                first_touch=BarrierTouch.UPPER,
                outcome=1,
                mfe=mfe,
                mae=mae,
                status="VALID",
            )

    # Neither upper nor lower was touched: check if vertical horizon was fully reached
    max_covered_time = max((_get_val(b, "close_time") for b in bars), default=entry_ts)
    if max_covered_time < vertical_barrier_ts:
        # LABEL-02-FR3: Missing exit data before vertical horizon is EXCLUDED/CENSORED, never 0
        return TripleBarrierLabel(
            sample_id=sample_id,
            label_set_id=config.label_set_id,
            label_version=config.version,
            pair=pair,
            decision_ts=decision_ts,
            entry_ts=entry_ts,
            label_end_ts=max_covered_time,
            entry_price=entry_price,
            upper_barrier=upper_barrier,
            lower_barrier=lower_barrier,
            first_touch=None,
            outcome=None,
            status="EXCLUDED",
            exclusion_reason="INCOMPLETE_BARS_BEFORE_VERTICAL_BARRIER",
        )

    # Full vertical horizon reached without early touch -> FLAT outcome (0)
    mfe = (max_high - entry_price) / entry_price
    mae = (entry_price - min_low) / entry_price
    return TripleBarrierLabel(
        sample_id=sample_id,
        label_set_id=config.label_set_id,
        label_version=config.version,
        pair=pair,
        decision_ts=decision_ts,
        entry_ts=entry_ts,
        label_end_ts=vertical_barrier_ts,
        entry_price=entry_price,
        upper_barrier=upper_barrier,
        lower_barrier=lower_barrier,
        first_touch=BarrierTouch.VERTICAL,
        outcome=0,
        mfe=mfe,
        mae=mae,
        status="VALID",
    )


def compute_concurrency_weights(labels: Sequence[TripleBarrierLabel]) -> dict[str, Decimal]:
    """Calculate sample concurrency weights based on temporal overlap of active label spans."""
    valid_labels = [
        l for l in labels if l.entry_ts is not None and l.label_end_ts is not None and l.status == "VALID"
    ]
    if not valid_labels:
        return {l.sample_id: Decimal("1.0") for l in labels}

    weights: dict[str, Decimal] = {}
    for i_label in valid_labels:
        start_i = i_label.entry_ts
        end_i = i_label.label_end_ts

        # Count overlapping intervals
        overlap_count = 0
        for j_label in valid_labels:
            start_j = j_label.entry_ts
            end_j = j_label.label_end_ts

            if max(start_i, start_j) < min(end_i, end_j):
                overlap_count += 1

        if overlap_count < 1:
            overlap_count = 1

        weights[i_label.sample_id] = Decimal("1.0") / Decimal(str(overlap_count))

    # Any label not valid gets default weight
    for l in labels:
        if l.sample_id not in weights:
            weights[l.sample_id] = Decimal("1.0")

    return weights
