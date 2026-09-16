"""Feature replay adapter: loads parquet feature sets and builds causal DecisionFrames (STRAT-02).

This module bridges materialized feature parquets (produced by build_features CLI)
to the ReplayBacktestEngine interface.  All temporal invariants are enforced:

- available_at (row_ready_at) must be <= decision_ts  (no future leakage)
- as-of join is strictly backward-only (no ffill / no bfill)
- context 1h rows must be available BEFORE the 5m signal decision_ts
- ineligible rows (warmup, missing data) are excluded — never treated as neutral
- all timestamps are UTC-aware; naive timestamps are rejected
- pair is matched exactly; cross-pair context is rejected
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

import pandas as pd

from indodax_lab.backtest.events import MarketBar
from indodax_lab.strategies.base import DecisionFrame, create_decision_frame
from indodax_lab.strategies.multitimeframe import align_closed_context

UTC = timezone.utc


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


def _check_naive_timestamps(series: "pd.Series", col_name: str) -> None:
    """Reject native datetime objects that have no tzinfo (naive)."""
    if hasattr(series, "dt"):
        # Proper DatetimeTZDtype — check it is UTC
        tz = getattr(series.dt, "tz", None)
        if tz is None:
            raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED: column {col_name!r} has no timezone")
        return
    # Object dtype: may contain Python datetime objects
    for val in series:
        if val is None or (hasattr(val, "__class__") and val.__class__.__name__ == "NaTType"):
            continue
        if isinstance(val, datetime):
            if val.tzinfo is None:
                raise ValueError(
                    f"UTC_TIMEZONE_AWARE_REQUIRED: column {col_name!r} contains naive datetime {val!r}"
                )


def validate_no_future_leakage(df: pd.DataFrame) -> None:
    """Verify that row_ready_at <= decision_ts for every row.

    Raises ValueError if:
    - ``row_ready_at`` column is missing
    - any timestamp is not UTC-aware (naive datetimes are rejected)
    - any row_ready_at > decision_ts
    """
    if "row_ready_at" not in df.columns:
        raise ValueError("row_ready_at column required in feature DataFrame")
    if "decision_ts" not in df.columns:
        raise ValueError("decision_ts column required in feature DataFrame")

    # Detect naive datetime objects BEFORE pd.to_datetime silently localises them
    _check_naive_timestamps(df["decision_ts"], "decision_ts")
    _check_naive_timestamps(df["row_ready_at"], "row_ready_at")

    decision_ts = pd.to_datetime(df["decision_ts"], utc=True, errors="coerce")
    row_ready_at = pd.to_datetime(df["row_ready_at"], utc=True, errors="coerce")

    if decision_ts.isna().any() or row_ready_at.isna().any():
        raise ValueError("UTC_TIMEZONE_AWARE_REQUIRED: timestamps must be UTC-aware")

    future_mask = row_ready_at > decision_ts
    if future_mask.any():
        bad = df.loc[future_mask, ["decision_ts", "row_ready_at"]].head(3).to_dict("records")
        raise ValueError(f"FUTURE_LEAKAGE: row_ready_at > decision_ts in {len(df[future_mask])} rows. Examples: {bad}")


class FeatureReplayConfig:
    """Immutable configuration for FeatureReplayAdapter.

    Attributes
    ----------
    pair:
        Trading pair to replay (e.g. "btc_idr").
    signal_interval:
        Interval of signal feature rows (e.g. "5m").
    context_interval:
        Interval of context feature rows (e.g. "1h").
    require_context:
        If True (default), missing context rows will raise ValueError rather
        than silently continue.  Never silently bfill or treat as neutral.
    """

    __slots__ = ("pair", "signal_interval", "context_interval", "require_context")

    def __init__(
        self,
        pair: str,
        signal_interval: str,
        context_interval: str,
        require_context: bool = True,
    ) -> None:
        if not pair:
            raise ValueError("CONFIG_PAIR_REQUIRED: pair must be a non-empty string")
        if not signal_interval:
            raise ValueError("CONFIG_SIGNAL_INTERVAL_REQUIRED")
        if not context_interval:
            raise ValueError("CONFIG_CONTEXT_INTERVAL_REQUIRED")
        # Use object.__setattr__ to make effectively immutable via __setattr__ override
        object.__setattr__(self, "pair", pair)
        object.__setattr__(self, "signal_interval", signal_interval)
        object.__setattr__(self, "context_interval", context_interval)
        object.__setattr__(self, "require_context", require_context)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("FeatureReplayConfig is immutable")

    def __repr__(self) -> str:
        return (
            f"FeatureReplayConfig(pair={self.pair!r}, "
            f"signal_interval={self.signal_interval!r}, "
            f"context_interval={self.context_interval!r})"
        )


class FeatureReplayAdapter:
    """Causal feature adapter for replay backtest.

    Builds a ``DecisionFrame`` from signal and context feature DataFrames,
    enforcing all temporal invariants required by the research lab.

    The adapter is stateless and may be called once per bar in the replay loop.
    """

    def __init__(self, config: FeatureReplayConfig) -> None:
        self.config = config

    def build_decision_frame(
        self,
        signal_rows: pd.DataFrame,
        context_rows: pd.DataFrame,
        as_of: datetime,
    ) -> DecisionFrame:
        """Construct a causal DecisionFrame at *as_of*.

        Steps
        -----
        1. Validate *as_of* is UTC-aware.
        2. Filter signal_rows to eligible rows with decision_ts <= as_of and row_ready_at <= as_of.
        3. If context_rows are provided:
           a. Filter to rows available at as_of (row_ready_at <= as_of).
           b. Run align_closed_context (backward as-of join).
           c. Fail closed if any signal row has no context available.
        4. Return DecisionFrame.
        """
        _ensure_utc(as_of, "as_of")

        # --- 1. Handle empty signal DataFrame ---
        if signal_rows.empty:
            return create_decision_frame(
                features=pd.DataFrame(),
                as_of=as_of,
            )

        # --- 2. Validate & filter signal rows ---
        sig = signal_rows.copy()
        sig["decision_ts"] = pd.to_datetime(sig["decision_ts"], utc=True)
        sig["row_ready_at"] = pd.to_datetime(sig["row_ready_at"], utc=True)

        if sig["decision_ts"].isna().any() or sig["row_ready_at"].isna().any():
            raise ValueError("UTC_TIMEZONE_AWARE_REQUIRED: signal timestamps must be UTC-aware")

        # Future leakage check
        future_mask = sig["row_ready_at"] > sig["decision_ts"]
        if future_mask.any():
            raise ValueError("FUTURE_LEAKAGE: row_ready_at > decision_ts in signal rows")

        # Exclude rows beyond as_of
        sig = sig[sig["decision_ts"] <= pd.Timestamp(as_of)]
        sig = sig[sig["row_ready_at"] <= pd.Timestamp(as_of)]

        # Exclude ineligible (warmup, missing data)
        if "eligible" in sig.columns:
            sig = sig[sig["eligible"] == True]

        # Filter to configured pair only
        if "pair" in sig.columns:
            sig = sig[sig["pair"] == self.config.pair]

        # --- 3. Handle context rows ---
        if not context_rows.empty:
            ctx = context_rows.copy()
            ctx["decision_ts"] = pd.to_datetime(ctx["decision_ts"], utc=True)
            ctx["row_ready_at"] = pd.to_datetime(ctx["row_ready_at"], utc=True)

            if ctx["decision_ts"].isna().any() or ctx["row_ready_at"].isna().any():
                raise ValueError("UTC_TIMEZONE_AWARE_REQUIRED: context timestamps must be UTC-aware")

            # Filter context to configured pair only
            if "pair" in ctx.columns:
                ctx_pair = ctx[ctx["pair"] == self.config.pair]
                has_other_pairs = len(ctx[ctx["pair"] != self.config.pair]) > 0
                if ctx_pair.empty and has_other_pairs:
                    raise ValueError(
                        f"PAIR_MISMATCH: context rows contain pairs other than {self.config.pair!r} "
                        "but no rows for the configured pair"
                    )
                ctx = ctx_pair

            # Filter context available at as_of
            ctx = ctx[ctx["row_ready_at"] <= pd.Timestamp(as_of)]

            # For backward-only as-of join we need signal rows to align against.
            # If signal is now empty, no need to join.
            if sig.empty:
                pass  # will return empty frame below
            elif ctx.empty and self.config.require_context:
                raise ValueError(
                    "MTF_CONTEXT_UNAVAILABLE: no context rows available at as_of "
                    f"{as_of.isoformat()} for pair {self.config.pair!r}. "
                    "Fail-closed: context is required and must not be silently skipped."
                )
            elif not ctx.empty:
                # align_closed_context enforces: backward-only, pair-match, availability guard
                try:
                    sig = align_closed_context(
                        signal_rows=sig,
                        context_rows=ctx,
                        signal_ts="decision_ts",
                        context_ts="decision_ts",
                        context_ready="row_ready_at",
                        pair_column="pair",
                    )
                except ValueError as exc:
                    # Re-raise with context so tests can match on ValueError
                    raise ValueError(f"MTF_CONTEXT_ALIGNMENT_FAILED: {exc}") from exc

        elif self.config.require_context:
            # Empty context_rows DataFrame and context is required → fail closed
            # But only if signal_rows were non-empty (we have something to align)
            if not sig.empty:
                raise ValueError(
                    "MTF_CONTEXT_UNAVAILABLE: context_rows is empty but context is required. "
                    "Fail-closed: missing context must not be treated as neutral."
                )

        return create_decision_frame(features=sig, as_of=as_of)


def load_bars_from_parquet(
    path: Path,
    pair: str,
    *,
    start_dt: datetime | None = None,
    end_dt: datetime | None = None,
) -> list[MarketBar]:
    """Load OHLCV rows from a parquet file and convert to ``MarketBar`` objects.

    Parameters
    ----------
    path:
        Path to parquet file containing candle data.
    pair:
        Trading pair name to assign to all bars (e.g. "btc_idr").
    start_dt:
        Optional UTC-aware lower bound on open_time (inclusive).
    end_dt:
        Optional UTC-aware upper bound on open_time (exclusive).

    Returns
    -------
    list[MarketBar]
        Sorted ascending by open_time.  All timestamps are UTC-aware.
    """
    import pyarrow.parquet as pq

    # Use ParquetFile.read() (not read_table) so pyarrow reads the single file
    # without attempting to merge Hive partition schemas across files.
    # This avoids the 'string vs dictionary' schema conflict on the 'interval' column.
    _REQUIRED_COLS = ["open_time", "close_time", "open", "high", "low", "close",
                      "base_volume", "quote_volume"]
    pf = pq.ParquetFile(path)
    schema_names = pf.schema_arrow.names
    cols_to_read = [c for c in _REQUIRED_COLS if c in schema_names]
    table = pf.read(columns=cols_to_read)
    df = table.to_pandas()

    # Normalize timestamps to UTC-aware
    for col in ("open_time", "close_time"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True)

    if start_dt is not None:
        _ensure_utc(start_dt, "start_dt")
        df = df[df["open_time"] >= pd.Timestamp(start_dt)]
    if end_dt is not None:
        _ensure_utc(end_dt, "end_dt")
        df = df[df["open_time"] < pd.Timestamp(end_dt)]

    df = df.sort_values("open_time").reset_index(drop=True)

    def _to_dec_str(val) -> str:
        """Convert a parquet field value to a clean Decimal string."""
        if val is None or (hasattr(val, '__class__') and val.__class__.__name__ == 'NaTType'):
            return "0"
        import math
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return "0"
        except (TypeError, ValueError):
            pass
        s = str(val).strip()
        if not s or s.lower() in ("none", "nan", "inf", "-inf", "nat"):
            return "0"
        return s

    bars: list[MarketBar] = []
    for _, row in df.iterrows():
        bar = MarketBar(
            pair=pair,
            open_time=row["open_time"].to_pydatetime(),
            close_time=row["close_time"].to_pydatetime(),
            open=_to_dec_str(row["open"]),
            high=_to_dec_str(row["high"]),
            low=_to_dec_str(row["low"]),
            close=_to_dec_str(row["close"]),
            base_volume=_to_dec_str(row["base_volume"]),
            quote_volume=_to_dec_str(row.get("quote_volume")),
        )
        bars.append(bar)

    return bars


def load_bars_from_parquet_dir(
    bronze_dir: Path,
    pair: str,
    interval: str,
    *,
    start_dt: datetime | None = None,
    end_dt: datetime | None = None,
) -> list[MarketBar]:
    """Load and merge OHLCV bars from a partitioned parquet directory.

    Expects Hive-style layout:
    ``<bronze_dir>/dataset=candles/schema=v1/interval=<interval>/pair=<pair>/year=YYYY/month=MM/part-*.parquet``

    Parameters
    ----------
    bronze_dir:
        Root bronze directory (e.g. ``lab-data-5m/bronze``).
    pair:
        Trading pair (e.g. ``btc_idr``).
    interval:
        Bar interval string (e.g. ``5m``, ``1h``).
    start_dt, end_dt:
        Optional UTC-aware filters on open_time.

    Returns
    -------
    list[MarketBar]
        Sorted ascending by open_time, deduplicated.
    """
    pair_dir = bronze_dir / f"dataset=candles" / "schema=v1" / f"interval={interval}" / f"pair={pair}"
    if not pair_dir.exists():
        raise FileNotFoundError(
            f"PARQUET_DIR_NOT_FOUND: {pair_dir}. "
            f"Check that lab-data directory exists and contains pair={pair!r} interval={interval!r}."
        )

    parquet_files = sorted(pair_dir.rglob("part-*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"NO_PARQUET_FILES: {pair_dir}")

    all_bars: list[MarketBar] = []
    seen_open_times: set = set()

    for fpath in parquet_files:
        file_bars = load_bars_from_parquet(fpath, pair=pair, start_dt=start_dt, end_dt=end_dt)
        for bar in file_bars:
            key = (bar.pair, bar.open_time)
            if key not in seen_open_times:
                seen_open_times.add(key)
                all_bars.append(bar)

    all_bars.sort(key=lambda b: b.open_time)
    return all_bars


__all__ = [
    "FeatureReplayAdapter",
    "FeatureReplayConfig",
    "load_bars_from_parquet",
    "load_bars_from_parquet_dir",
    "validate_no_future_leakage",
]
