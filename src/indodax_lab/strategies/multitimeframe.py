"""Causal alignment helpers for multi-timeframe research strategies."""

from __future__ import annotations

from datetime import datetime, timedelta
import pandas as pd


def align_closed_context(
    signal_rows: pd.DataFrame,
    context_rows: pd.DataFrame,
    *,
    signal_ts: str = "decision_ts",
    context_ts: str = "decision_ts",
    context_ready: str = "row_ready_at",
    pair_column: str = "pair",
) -> pd.DataFrame:
    """Attach the latest *available* closed context row to each signal row.

    The backward as-of join is additionally guarded by ``row_ready_at``.  A
    context candle may be chronologically older but still unavailable due to
    publication delay; such a row is therefore rejected rather than silently
    forward-filled.
    """
    if signal_rows.empty:
        return signal_rows.copy()
    required = {signal_ts, pair_column}
    if not required.issubset(signal_rows.columns) or not required.issubset(context_rows.columns):
        raise ValueError("MTF_REQUIRED_COLUMNS_MISSING")
    if context_ready not in context_rows.columns:
        raise ValueError("MTF_CONTEXT_AVAILABILITY_REQUIRED")

    left = signal_rows.copy()
    right = context_rows.copy()
    left[signal_ts] = pd.to_datetime(left[signal_ts], utc=True)
    right[context_ts] = pd.to_datetime(right[context_ts], utc=True)
    right[context_ready] = pd.to_datetime(right[context_ready], utc=True)
    if left[signal_ts].isna().any() or right[[context_ts, context_ready]].isna().any().any():
        raise ValueError("MTF_UTC_TIMESTAMPS_REQUIRED")
    if (right[context_ready] < right[context_ts]).any():
        raise ValueError("MTF_CONTEXT_READY_BEFORE_DECISION_FORBIDDEN")

    # Merge by pair and timestamp, then enforce availability at the signal time.
    left = left.sort_values([pair_column, signal_ts])
    right = right.sort_values([pair_column, context_ts])
    merged = pd.merge_asof(
        left,
        right,
        left_on=signal_ts,
        right_on=context_ts,
        by=pair_column,
        direction="backward",
        suffixes=("", "_context"),
    )
    if merged[context_ts].isna().any():
        raise ValueError("MTF_CONTEXT_UNAVAILABLE")
    ready = merged[context_ready]
    invalid = ready.notna() & (ready > merged[signal_ts])
    if invalid.any():
        # Do not return a future context row.  Fail closed so callers cannot
        # accidentally treat a missing context as a valid neutral signal.
        raise ValueError("MTF_FUTURE_CONTEXT_FORBIDDEN")
    return merged
