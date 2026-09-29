"""Relative strength rotation strategy candidate (C12-01).

Contract:
PIT strength rotation with turnover and cash regime gate -> versioned LONG/FLAT
intent, never direct orders.

Frozen deterministic v1 semantics (config `configs/strategies/C12_v1.yaml`):
- Relative strength: lookback return over closed bars ending at as_of, minus
  the universe median return over the same window (point-in-time, no bfill).
- Ranking: strength descending; ties resolve to canonical pair ascending, so
  tie rank is stable across runs and input row order.
- Cash regime: fraction of valid pairs with positive lookback return (breadth,
  mirroring the registered `market_breadth_pos_24_1h` cross-section feature
  when lookback_bars = 24 and every eligible pair has current valid evidence)
  at or below `cash_breadth_threshold` is a cash regime and blocks reentry:
  every valid pair is BLOCKED and no LONG intent is emitted.
- Turnover: total intent notional is bounded by available cash times
  `max_turnover_fraction`; unknown or nonpositive cash blocks turnover
  (fail-closed), and per-slot quantity rounds down to 0.0001 base units.
- Selection: first `top_k` of pairs with positive lookback return and
  relative strength at or above `min_relative_strength` (equality qualifies).
  The floor is non-negative: a negative `min_relative_strength` is rejected as
  `INVALID_C12_ROTATION_PARAMETERS` at config load and before any decision,
  because it would let a non-positive-return pair pass the strength gate and
  misattribute its breadth rejection.
- Stop: `close - atr_multiplier * atr_14`; missing/nonpositive ATR, close or
  stop excludes the pair from rotation (fail-closed, never traded).
- Delisted or stale pairs (no bar at as_of) stay in the decision history as
  EXCLUDED with an explicit reason and can never re-enter on stale evidence.
- Not-yet-listed pairs (canonical `listed_at`/`listing_date` after as_of) are
  EXCLUDED with `C12_NOT_YET_LISTED` and never enter rotation; rows entirely
  after as_of never reach the frame at all.
- FLAT is an explicit history status; `c12_decide` emits only LONG intents.
"""

from __future__ import annotations

import math
import statistics
from decimal import ROUND_DOWN, Decimal, DecimalException
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry

_INVALID_PARAMETERS = "INVALID_C12_ROTATION_PARAMETERS"


class C12DecisionRecord(BaseModel):
    """One pair's explicit C12-01 decision history entry with reason code."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pair: str
    status: Literal["LONG", "FLAT", "BLOCKED", "EXCLUDED"]
    reason_code: str
    rank: int | None = None
    relative_strength: float | None = None
    intent: SignalIntent | None = None


def _validated_rotation_parameters(
    spec: StrategySpecification,
) -> tuple[int, int, int, float, float, Decimal, float]:
    """Parse and fail closed on unsafe rotation parameters before any decision.

    A negative `min_relative_strength` is rejected: with a negative floor a
    non-positive-return pair passes the strength gate, so its breadth
    (positive-return) rejection would be misattributed as a strength rejection.
    """
    params = spec.parameters
    try:
        lookback_bars = int(params.get("lookback_bars", 24))
        top_k = int(params.get("top_k", 2))
        minimum_valid_pairs = int(params.get("minimum_valid_pairs", 2))
        breadth_threshold = float(params.get("cash_breadth_threshold", 0.5))
        min_strength = float(params.get("min_relative_strength", 0.0))
        turnover_fraction = Decimal(str(params.get("max_turnover_fraction", "0.50")))
        atr_multiplier = float(params.get("atr_multiplier", 2.0))
    except (DecimalException, TypeError, ValueError) as exc:
        raise ValueError(_INVALID_PARAMETERS) from exc
    if (
        lookback_bars < 1
        or top_k < 1
        or minimum_valid_pairs < 2
        or not math.isfinite(breadth_threshold)
        or breadth_threshold < 0.0
        or breadth_threshold > 1.0
        or not math.isfinite(min_strength)
        or min_strength < 0.0
        or not turnover_fraction.is_finite()
        or turnover_fraction <= 0
        or turnover_fraction > 1
        or not math.isfinite(atr_multiplier)
        or atr_multiplier <= 0
    ):
        raise ValueError(_INVALID_PARAMETERS)
    return (
        lookback_bars,
        top_k,
        minimum_valid_pairs,
        breadth_threshold,
        min_strength,
        turnover_fraction,
        atr_multiplier,
    )


def load_c12_specification(
    config_path: str | Path = "configs/strategies/C12_v1.yaml",
) -> StrategySpecification:
    """Load and strictly validate canonical C12 relative strength specification.

    Rotation parameters are validated at load time, so an unsafe config (for
    example a negative `min_relative_strength`) is rejected here rather than at
    the first decision.
    """
    registry = StrategyRegistry()
    specification = registry.load_specification_from_yaml(config_path)
    _validated_rotation_parameters(specification)
    return specification


def _excluded(pair: str, reason_code: str) -> C12DecisionRecord:
    return C12DecisionRecord(pair=pair, status="EXCLUDED", reason_code=reason_code)


def _blocked(entry: dict, reason_code: str) -> C12DecisionRecord:
    return C12DecisionRecord(
        pair=entry["pair"],
        status="BLOCKED",
        reason_code=reason_code,
        rank=entry["rank"],
        relative_strength=entry["strength"],
    )


def _flattened(entry: dict, reason_code: str) -> C12DecisionRecord:
    return C12DecisionRecord(
        pair=entry["pair"],
        status="FLAT",
        reason_code=reason_code,
        rank=entry["rank"],
        relative_strength=entry["strength"],
    )


def c12_decision_history(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[C12DecisionRecord]:
    """Return the causal decision history for every eligible pair.

    Records separate valid LONG/FLAT results from legitimately blocked or
    excluded pairs; each record carries an explicit reason code.
    """
    if spec is None:
        spec = load_c12_specification()

    (
        lookback_bars,
        top_k,
        minimum_valid_pairs,
        breadth_threshold,
        min_strength,
        turnover_fraction,
        atr_multiplier,
    ) = _validated_rotation_parameters(spec)

    records: dict[str, C12DecisionRecord] = {}
    valid: list[dict] = []
    window_bars = lookback_bars + 1

    # Evidence stage: fail closed on stale/delisted, short or invalid market data.
    for pair in sorted(frame.eligible_pairs):
        p_df = frame.get_pair_features(pair)
        if p_df.empty:
            records[pair] = _excluded(pair, "C12_STALE_OR_DELISTED_NO_CURRENT_ROW")
            continue
        latest = p_df.iloc[-1]
        if pd.Timestamp(latest["decision_ts"]) != pd.Timestamp(frame.as_of):
            records[pair] = _excluded(pair, "C12_STALE_OR_DELISTED_NO_CURRENT_ROW")
            continue
        # Explicit listing guard (mirrors C04): DecisionFrame only checks
        # decision_ts/row_ready_at/eligible, so a pair whose canonical listing
        # evidence is after as_of must be rejected here instead of rotating.
        listing_column = next(
            (column for column in ("listed_at", "listing_date") if column in p_df.columns),
            None,
        )
        if listing_column is not None:
            listing_value = latest[listing_column]
            if pd.notna(listing_value):
                listing_dt = pd.to_datetime(listing_value, utc=True, errors="coerce")
                if pd.isna(listing_dt):
                    records[pair] = _excluded(pair, "C12_INVALID_MARKET_DATA")
                    continue
                if listing_dt > frame.as_of:
                    records[pair] = _excluded(pair, "C12_NOT_YET_LISTED")
                    continue
        if len(p_df) < window_bars:
            records[pair] = _excluded(pair, "C12_INSUFFICIENT_LOOKBACK")
            continue
        window_df = p_df.iloc[-window_bars:]
        try:
            start_close = float(window_df.iloc[0]["close"])
            curr_close = float(latest["close"])
            atr_value = float(latest["atr_14"] if "atr_14" in p_df.columns else latest["atr"])
        except (KeyError, TypeError, ValueError):
            records[pair] = _excluded(pair, "C12_INVALID_MARKET_DATA")
            continue
        if not (math.isfinite(start_close) and math.isfinite(curr_close)):
            records[pair] = _excluded(pair, "C12_INVALID_MARKET_DATA")
            continue
        if start_close <= 0 or curr_close <= 0:
            records[pair] = _excluded(pair, "C12_INVALID_MARKET_DATA")
            continue
        if not math.isfinite(atr_value) or atr_value <= 0:
            records[pair] = _excluded(pair, "C12_INVALID_MARKET_DATA")
            continue
        lookback_return = (curr_close - start_close) / start_close
        stop = curr_close - atr_multiplier * atr_value
        if not math.isfinite(lookback_return) or not math.isfinite(stop) or stop <= 0:
            records[pair] = _excluded(pair, "C12_INVALID_MARKET_DATA")
            continue
        valid.append(
            {
                "pair": pair,
                "return": lookback_return,
                "close": curr_close,
                "stop": stop,
                "rank": 0,
                "strength": 0.0,
            }
        )

    if valid:
        median_return = statistics.median(entry["return"] for entry in valid)
        for entry in valid:
            entry["strength"] = entry["return"] - median_return
        ranked = sorted(valid, key=lambda entry: (-entry["strength"], entry["pair"]))
        for rank, entry in enumerate(ranked, start=1):
            entry["rank"] = rank

        # Gate chain: universe floor, then market cash regime, then cash turnover.
        # Blocked pairs keep rank and strength as diagnostics for the rejection.
        cash = frame.available_cash_idr
        gate_reason: str | None = None
        if len(valid) < minimum_valid_pairs:
            gate_reason = "C12_INSUFFICIENT_UNIVERSE_EVIDENCE"
        else:
            positive_count = sum(1 for entry in valid if entry["return"] > 0)
            if positive_count / len(valid) <= breadth_threshold:
                gate_reason = "C12_CASH_REGIME_BLOCKS_REENTRY"
        if gate_reason is None and (cash is None or cash <= 0):
            gate_reason = "C12_CASH_UNAVAILABLE_BLOCKS_TURNOVER"

        if gate_reason is not None:
            for entry in ranked:
                records[entry["pair"]] = _blocked(entry, gate_reason)
        else:
            # The gate chain above guarantees a positive Decimal cash here.
            turnover_cap = cash * turnover_fraction
            qualified = [
                entry
                for entry in ranked
                if entry["return"] > 0 and entry["strength"] >= min_strength
            ]
            qualified_pairs = {entry["pair"] for entry in qualified}
            selected = qualified[:top_k]
            selected_pairs = {entry["pair"] for entry in selected}
            per_slot_turnover = turnover_cap / Decimal(len(selected)) if selected else None
            for entry in ranked:
                pair = entry["pair"]
                if pair not in selected_pairs or per_slot_turnover is None:
                    if pair in qualified_pairs:
                        records[pair] = _flattened(entry, "C12_BELOW_TOP_K")
                    else:
                        records[pair] = _flattened(entry, "C12_STRENGTH_BELOW_MINIMUM")
                    continue
                limit_price = Decimal(str(entry["close"]))
                quantity = (per_slot_turnover / limit_price).quantize(
                    Decimal("0.0001"), rounding=ROUND_DOWN
                )
                if quantity <= 0:
                    records[pair] = _flattened(entry, "C12_TURNOVER_BELOW_MIN_QUANTITY")
                    continue
                intent = SignalIntent(
                    intent_id=f"c12_{spec.version}_{pair}_{int(frame.as_of.timestamp())}",
                    decision_ts=frame.as_of,
                    pair=pair,
                    side=OrderSide.BUY,
                    desired_qty=quantity,
                    limit_price=limit_price,
                    stop_loss=Decimal(str(entry["stop"])),
                    strategy_id=spec.strategy_id,
                )
                records[pair] = C12DecisionRecord(
                    pair=pair,
                    status="LONG",
                    reason_code="C12_LONG_TOP_RELATIVE_STRENGTH",
                    rank=entry["rank"],
                    relative_strength=entry["strength"],
                    intent=intent,
                )

    return [records[pair] for pair in sorted(frame.eligible_pairs)]


def c12_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
    """Return rotation LONG intents in rank order; FLAT means absent intent.

    Pure and stateless over the causal frame: never orders, ledger or network.
    """
    history = c12_decision_history(frame, spec)
    long_records = [
        record for record in history if record.status == "LONG" and record.intent is not None
    ]
    long_records.sort(key=lambda record: record.rank if record.rank is not None else 0)
    return [record.intent for record in long_records if record.intent is not None]
