"""Deterministic time bars built only from reliable, offline public trades."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from indodax_lab.contracts import AggressorSide, QualityStatus, TradeEvent, UtcTimestamp

from .checksums import sha256_bytes
from .manifest import canonical_json_bytes

SCHEMA_VERSION = "1.0.0"
_IDENTITY_PATTERN = r"^sha256:[0-9a-f]{64}$"
_INTERVAL_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
TimeInterval = Literal["1m", "5m", "15m", "1h", "4h", "1d"]


class BarType(StrEnum):
    """Stable silver bar representation labels."""

    TIME = "TIME"
    CUSUM = "CUSUM"
    RANGE = "RANGE"
    VOLUME = "VOLUME"
    DOLLAR = "DOLLAR"


class SourceSelection(StrEnum):
    """Explicit source policy; source rows are never blended."""

    TRADES = "trades"
    OFFICIAL = "official"


class TimeBarConfig(BaseModel):
    """Strict, versioned time-bar build policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    source_selection: SourceSelection
    base_interval: Literal["1m"]
    output_intervals: tuple[TimeInterval, ...]
    availability_lag_seconds: int = Field(ge=0)
    price_tolerance: Decimal
    volume_tolerance: Decimal
    require_complete_reconciliation: bool

    @field_validator("price_tolerance", "volume_tolerance", mode="before")
    @classmethod
    def validate_config_tolerance(cls, value: object) -> Decimal:
        if isinstance(value, bool) or isinstance(value, float):
            raise ValueError("reconciliation tolerance must not use bool or binary float")
        if isinstance(value, (str, int)):
            value = Decimal(str(value))
        if not isinstance(value, Decimal) or value < 0:
            raise ValueError("reconciliation tolerance must be a non-negative Decimal")
        return value

    @model_validator(mode="after")
    def validate_outputs(self) -> TimeBarConfig:
        if not self.output_intervals or self.output_intervals[0] != self.base_interval:
            raise ValueError("output_intervals must begin with base_interval")
        if len(set(self.output_intervals)) != len(self.output_intervals):
            raise ValueError("output_intervals must not contain duplicates")
        seconds = [_INTERVAL_SECONDS[value] for value in self.output_intervals]
        if seconds != sorted(seconds):
            raise ValueError("output_intervals must be ordered from smallest to largest")
        return self


class LoadedTimeBarConfig(BaseModel):
    """Validated config plus the identity of its exact YAML bytes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config: TimeBarConfig
    source_id: str = Field(pattern=_IDENTITY_PATTERN)


class SilverBar(BaseModel):
    """One final silver bar with immutable source-event lineage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = SCHEMA_VERSION
    bar_id: str = Field(pattern=_IDENTITY_PATTERN)
    pair: str = Field(pattern=r"^[a-z0-9]+_[a-z0-9]+$")
    bar_type: BarType
    interval: TimeInterval | None = None
    threshold_config_id: str | None = None
    threshold_value: Decimal | None = None
    threshold_provenance: Literal["FIXED", "FITTED"] | None = None
    threshold_artifact_id: str | None = None
    threshold_artifact_version: str | None = None
    threshold_train_end: UtcTimestamp | None = None
    threshold_available_at: UtcTimestamp | None = None
    policy_id: str = Field(min_length=1)
    availability_lag_microseconds: int = Field(ge=0)
    first_event_ts: UtcTimestamp
    last_event_ts: UtcTimestamp
    open_time: UtcTimestamp
    close_time: UtcTimestamp
    available_at: UtcTimestamp
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    base_volume: Decimal
    quote_volume: Decimal
    trade_count: int = Field(gt=0)
    buy_base_volume: Decimal | None
    sell_base_volume: Decimal | None
    source_snapshot_id: str = Field(pattern=_IDENTITY_PATTERN)
    source: str = Field(min_length=1)
    source_session_id: str = Field(min_length=1)
    source_event_ids: tuple[str, ...]
    quality_status: QualityStatus
    quality_flags: tuple[str, ...]
    boundary_direction: Literal["POSITIVE", "NEGATIVE"] | None = None

    @field_validator(
        "open",
        "high",
        "low",
        "close",
        "base_volume",
        "quote_volume",
        "buy_base_volume",
        "sell_base_volume",
        "threshold_value",
        mode="before",
    )
    @classmethod
    def require_decimal(cls, value: object) -> Decimal | None:
        if value is None:
            return None
        if not isinstance(value, Decimal):
            raise ValueError("bar monetary and quantity values must be Decimal")
        return value

    @model_validator(mode="after")
    def validate_bar(self) -> SilverBar:
        if self.first_event_ts > self.last_event_ts:
            raise ValueError("first_event_ts must not follow last_event_ts")
        if self.bar_type is BarType.TIME:
            if (
                self.interval is None
                or self.threshold_config_id is not None
                or self.threshold_value is not None
                or self.threshold_provenance is not None
                or self.threshold_artifact_id is not None
                or self.threshold_artifact_version is not None
                or self.threshold_train_end is not None
                or self.threshold_available_at is not None
            ):
                raise ValueError("time bars require interval and forbid threshold lineage")
            if self.close_time <= self.open_time:
                raise ValueError("time bar close_time must be end-exclusive after open_time")
            if not (self.open_time <= self.first_event_ts <= self.last_event_ts < self.close_time):
                raise ValueError("time-bar events must fall within [open_time, close_time)")
        else:
            if (
                self.interval is not None
                or self.threshold_config_id is None
                or self.threshold_value is None
                or self.threshold_provenance is None
            ):
                raise ValueError("event bars require threshold lineage and forbid interval")
            fitted_fields = (
                self.threshold_artifact_id,
                self.threshold_artifact_version,
                self.threshold_train_end,
                self.threshold_available_at,
            )
            if self.threshold_provenance == "FITTED" and any(
                value is None for value in fitted_fields
            ):
                raise ValueError("fitted threshold requires complete artifact temporal lineage")
            if self.threshold_provenance == "FIXED" and any(
                value is not None for value in fitted_fields
            ):
                raise ValueError("fixed threshold must have explicit null artifact lineage")
            if self.close_time < self.open_time:
                raise ValueError("event bar close_time must not precede open_time")
        if self.available_at < self.close_time:
            raise ValueError("available_at must not precede close_time")
        if (
            self.threshold_available_at is not None
            and self.available_at < self.threshold_available_at
        ):
            raise ValueError("bar availability must include threshold artifact availability")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC values must be positive")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("OHLC values violate high/low bounds")
        if self.high < self.low:
            raise ValueError("high must not be below low")
        if min(self.base_volume, self.quote_volume) <= 0:
            raise ValueError("final bars require positive volume")
        if self.buy_base_volume is not None and self.buy_base_volume < 0:
            raise ValueError("buy_base_volume must be non-negative")
        if self.sell_base_volume is not None and self.sell_base_volume < 0:
            raise ValueError("sell_base_volume must be non-negative")
        if len(self.source_event_ids) != self.trade_count:
            raise ValueError("trade_count must match source_event_ids")
        if len(set(self.source_event_ids)) != len(self.source_event_ids):
            raise ValueError("bar source_event_ids must be unique")
        if self.quality_status is not QualityStatus.PASS:
            raise ValueError("final bars must be built from reliable PASS inputs")
        return self


class BarGap(BaseModel):
    """An expected interval for which no trustworthy bar was fabricated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: UtcTimestamp
    end: UtcTimestamp
    reason: Literal["EMPTY_BUCKET", "INCOMPLETE_SOURCE_BUCKET", "UNRELIABLE_SOURCE_BUCKET"]


class TimeBarBuildResult(BaseModel):
    """Final bars and explicit missing intervals."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bars: tuple[SilverBar, ...]
    gaps: tuple[BarGap, ...]


class BarMismatch(BaseModel):
    """Deterministic field deltas between aligned official and derived bars."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    open_time: UtcTimestamp
    close_time: UtcTimestamp
    kind: Literal["MISSING_DERIVED", "MISSING_OFFICIAL", "VALUE_MISMATCH"]
    derived_bar_id: str | None
    official_bar_id: str | None
    differing_fields: tuple[str, ...]
    deltas: dict[str, Decimal | int | None]


class SourceComparison(BaseModel):
    """Audited comparison and one explicitly selected source, never a blend."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    selection: SourceSelection
    pair: str
    derived_source: str
    derived_snapshot_id: str
    official_source: str
    official_snapshot_id: str
    price_tolerance: Decimal
    volume_tolerance: Decimal
    require_complete: bool
    selected: tuple[SilverBar, ...]
    mismatches: tuple[BarMismatch, ...]


class ReconciliationPolicy(BaseModel):
    """Explicit completeness, tolerance, pair, provider, and snapshot contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pair: str = Field(pattern=r"^[a-z0-9]+_[a-z0-9]+$")
    derived_source: str = Field(min_length=1)
    derived_snapshot_id: str = Field(pattern=_IDENTITY_PATTERN)
    official_source: str = Field(min_length=1)
    official_snapshot_id: str = Field(pattern=_IDENTITY_PATTERN)
    price_tolerance: Decimal
    volume_tolerance: Decimal
    require_complete: bool

    @field_validator("price_tolerance", "volume_tolerance", mode="before")
    @classmethod
    def validate_tolerance(cls, value: object) -> Decimal:
        if not isinstance(value, Decimal) or value < 0:
            raise ValueError("reconciliation tolerances must be non-negative Decimal")
        return value


def load_time_bar_config(path: Path) -> LoadedTimeBarConfig:
    """Load strict YAML and retain its exact content address."""
    raw = Path(path).read_bytes()
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict):
        raise ValueError("time-bar config YAML must contain one mapping")
    return LoadedTimeBarConfig(
        config=TimeBarConfig.model_validate(parsed), source_id=f"sha256:{sha256_bytes(raw)}"
    )


def aggregate_time_bars(
    trades: Iterable[TradeEvent],
    *,
    interval: TimeInterval = "1m",
    window_start: datetime,
    window_end: datetime,
    availability_lag: timedelta,
    source_snapshot_id: str,
    source_session_id: str | None = None,
    policy_id: str = "direct-time-v1",
) -> TimeBarBuildResult:
    """Aggregate reliable trades into exact UTC buckets and report every empty bucket."""
    seconds = _validate_window(interval, window_start, window_end, availability_lag)
    ordered = _validate_and_order_trades(
        trades,
        window_start=window_start,
        window_end=window_end,
    )
    resolved_session_id = source_session_id or source_snapshot_id
    grouped: dict[datetime, list[TradeEvent]] = defaultdict(list)
    for trade in ordered:
        grouped[_floor_utc(trade.event_ts, seconds)].append(trade)

    bars: list[SilverBar] = []
    gaps: list[BarGap] = []
    cursor = window_start
    while cursor < window_end:
        close_time = cursor + timedelta(seconds=seconds)
        bucket = grouped.get(cursor, [])
        if not bucket:
            gaps.append(BarGap(start=cursor, end=close_time, reason="EMPTY_BUCKET"))
        else:
            bars.append(
                _bar_from_trades(
                    bucket,
                    bar_type=BarType.TIME,
                    interval=interval,
                    threshold_config_id=None,
                    open_time=cursor,
                    close_time=close_time,
                    availability_lag=availability_lag,
                    source_snapshot_id=source_snapshot_id,
                    source=bucket[0].source,
                    source_session_id=resolved_session_id,
                    policy_id=policy_id,
                )
            )
        cursor = close_time
    return TimeBarBuildResult(bars=tuple(bars), gaps=tuple(gaps))


def build_time_bars(*args, **kwargs) -> TimeBarBuildResult:
    """Compatibility name for callers that describe aggregation as a build."""
    return aggregate_time_bars(*args, **kwargs)


def resample_time_bars(
    source_bars: Iterable[SilverBar],
    *,
    target_interval: TimeInterval,
    window_start: datetime,
    window_end: datetime,
    availability_lag: timedelta,
    policy_id: str = "direct-resample-v1",
) -> TimeBarBuildResult:
    """Resample complete contiguous PASS bars without crossing a source gap or snapshot."""
    bars = tuple(sorted(source_bars, key=lambda bar: (bar.open_time, bar.bar_id)))
    target_seconds = _validate_window(target_interval, window_start, window_end, availability_lag)
    if not bars:
        return TimeBarBuildResult(
            bars=(),
            gaps=tuple(
                BarGap(
                    start=cursor,
                    end=cursor + timedelta(seconds=target_seconds),
                    reason="INCOMPLETE_SOURCE_BUCKET",
                )
                for cursor in _bucket_starts(window_start, window_end, target_seconds)
            ),
        )
    if any(
        bar.bar_type is not BarType.TIME or bar.quality_status is not QualityStatus.PASS
        for bar in bars
    ):
        raise ValueError("resampling requires reliable PASS time bars")
    source_intervals = {bar.interval for bar in bars}
    if len(source_intervals) != 1:
        raise ValueError("resampling requires one smallest source interval")
    source_interval = source_intervals.pop()
    assert source_interval is not None
    source_seconds = _INTERVAL_SECONDS[source_interval]
    lineage = {
        (bar.pair, bar.source, bar.source_snapshot_id, bar.source_session_id) for bar in bars
    }
    if len(lineage) != 1:
        raise ValueError("resampling requires one pair, provider, source snapshot, and session")
    if target_seconds <= source_seconds or target_seconds % source_seconds:
        raise ValueError("target interval must be an exact multiple of the source interval")
    by_open = {bar.open_time: bar for bar in bars}
    if len(by_open) != len(bars):
        raise ValueError("duplicate source time-bar key")

    output: list[SilverBar] = []
    gaps: list[BarGap] = []
    for cursor in _bucket_starts(window_start, window_end, target_seconds):
        target_close = cursor + timedelta(seconds=target_seconds)
        expected = list(_bucket_starts(cursor, target_close, source_seconds))
        bucket = [by_open[value] for value in expected if value in by_open]
        reliable = (
            len(bucket) == len(expected)
            and len({bar.source_snapshot_id for bar in bucket}) == 1
            and all(
                bar.close_time == expected[index] + timedelta(seconds=source_seconds)
                for index, bar in enumerate(bucket)
            )
        )
        if not reliable:
            gaps.append(BarGap(start=cursor, end=target_close, reason="INCOMPLETE_SOURCE_BUCKET"))
            continue
        event_ids = tuple(event_id for bar in bucket for event_id in bar.source_event_ids)
        identity_source = bucket[0].source_snapshot_id
        output.append(
            _make_bar(
                trades=None,
                pair=bucket[0].pair,
                bar_type=BarType.TIME,
                interval=target_interval,
                threshold_config_id=None,
                threshold_value=None,
                threshold_provenance=None,
                threshold_artifact_id=None,
                threshold_artifact_version=None,
                threshold_train_end=None,
                threshold_available_at=None,
                policy_id=policy_id,
                availability_lag=availability_lag,
                first_event_ts=bucket[0].first_event_ts,
                last_event_ts=bucket[-1].last_event_ts,
                open_time=cursor,
                close_time=target_close,
                available_at=max(
                    max(bar.available_at for bar in bucket), target_close + availability_lag
                ),
                open_price=bucket[0].open,
                high=max(bar.high for bar in bucket),
                low=min(bar.low for bar in bucket),
                close_price=bucket[-1].close,
                base_volume=sum((bar.base_volume for bar in bucket), Decimal(0)),
                quote_volume=sum((bar.quote_volume for bar in bucket), Decimal(0)),
                trade_count=sum(bar.trade_count for bar in bucket),
                buy_base_volume=_sum_optional(bar.buy_base_volume for bar in bucket),
                sell_base_volume=_sum_optional(bar.sell_base_volume for bar in bucket),
                source_snapshot_id=identity_source,
                source=bucket[0].source,
                source_session_id=bucket[0].source_session_id,
                source_event_ids=event_ids,
                boundary_direction=None,
            )
        )
    return TimeBarBuildResult(bars=tuple(output), gaps=tuple(gaps))


def compare_time_bar_sources(
    *,
    derived: Iterable[SilverBar],
    official: Iterable[SilverBar],
    selection: SourceSelection,
    policy: ReconciliationPolicy,
) -> SourceComparison:
    """Compare aligned fields and return exactly the configured source's rows."""
    derived_rows = tuple(sorted(derived, key=lambda bar: (bar.open_time, bar.bar_id)))
    official_rows = tuple(sorted(official, key=lambda bar: (bar.open_time, bar.bar_id)))
    _validate_reconciliation_source(
        derived_rows,
        label="derived",
        pair=policy.pair,
        source=policy.derived_source,
        snapshot_id=policy.derived_snapshot_id,
    )
    _validate_reconciliation_source(
        official_rows,
        label="official",
        pair=policy.pair,
        source=policy.official_source,
        snapshot_id=policy.official_snapshot_id,
    )
    derived_by_key = {(bar.pair, bar.open_time, bar.close_time): bar for bar in derived_rows}
    official_by_key = {(bar.pair, bar.open_time, bar.close_time): bar for bar in official_rows}
    if len(derived_by_key) != len(derived_rows) or len(official_by_key) != len(official_rows):
        raise ValueError("duplicate time-bar key in source comparison")
    mismatches: list[BarMismatch] = []
    price_fields = ("open", "high", "low", "close")
    volume_fields = (
        "base_volume",
        "quote_volume",
        "buy_base_volume",
        "sell_base_volume",
    )
    exact_fields = (
        "available_at",
        "interval",
        "bar_type",
        "trade_count",
        "first_event_ts",
        "last_event_ts",
    )
    missing = False
    for key in sorted(set(derived_by_key) | set(official_by_key)):
        derived_bar = derived_by_key.get(key)
        official_bar = official_by_key.get(key)
        if derived_bar is None or official_bar is None:
            missing = True
            mismatches.append(
                BarMismatch(
                    open_time=key[1],
                    close_time=key[2],
                    kind="MISSING_DERIVED" if derived_bar is None else "MISSING_OFFICIAL",
                    derived_bar_id=derived_bar.bar_id if derived_bar else None,
                    official_bar_id=official_bar.bar_id if official_bar else None,
                    differing_fields=("bar",),
                    deltas={},
                )
            )
            continue
        deltas: dict[str, Decimal | int | None] = {}
        differing: list[str] = []
        for field in price_fields + volume_fields:
            left = getattr(derived_bar, field)
            right = getattr(official_bar, field)
            tolerance = policy.price_tolerance if field in price_fields else policy.volume_tolerance
            if left is None or right is None:
                if left != right:
                    differing.append(field)
                    deltas[field] = None
            elif abs(right - left) > tolerance:
                differing.append(field)
                deltas[field] = right - left
        for field in exact_fields:
            if getattr(derived_bar, field) != getattr(official_bar, field):
                differing.append(field)
                if field == "trade_count":
                    deltas[field] = official_bar.trade_count - derived_bar.trade_count
        if differing:
            mismatches.append(
                BarMismatch(
                    open_time=key[1],
                    close_time=key[2],
                    kind="VALUE_MISMATCH",
                    derived_bar_id=derived_bar.bar_id,
                    official_bar_id=official_bar.bar_id,
                    differing_fields=tuple(differing),
                    deltas=deltas,
                )
            )
    if selection is SourceSelection.OFFICIAL and policy.require_complete and missing:
        raise ValueError("official source selection requires complete bars with no missing keys")
    selected = derived_rows if selection is SourceSelection.TRADES else official_rows
    return SourceComparison(
        selection=selection,
        pair=policy.pair,
        derived_source=policy.derived_source,
        derived_snapshot_id=policy.derived_snapshot_id,
        official_source=policy.official_source,
        official_snapshot_id=policy.official_snapshot_id,
        price_tolerance=policy.price_tolerance,
        volume_tolerance=policy.volume_tolerance,
        require_complete=policy.require_complete,
        selected=selected,
        mismatches=tuple(mismatches),
    )


def _validate_window(
    interval: TimeInterval, window_start: datetime, window_end: datetime, lag: timedelta
) -> int:
    seconds = _INTERVAL_SECONDS[interval]
    _require_utc(window_start, "window_start")
    _require_utc(window_end, "window_end")
    if window_end <= window_start:
        raise ValueError("window_end must be after window_start")
    if (
        _floor_utc(window_start, seconds) != window_start
        or _floor_utc(window_end, seconds) != window_end
    ):
        raise ValueError("window boundaries must align to interval")
    if lag < timedelta(0):
        raise ValueError("availability_lag must be non-negative")
    return seconds


def _validate_and_order_trades(
    trades: Iterable[TradeEvent],
    *,
    window_start: datetime,
    window_end: datetime,
) -> tuple[TradeEvent, ...]:
    rows = tuple(trades)
    if any(trade.quality_status is not QualityStatus.PASS for trade in rows):
        raise ValueError("time bars require reliable PASS trades")
    pairs = {trade.pair.pair for trade in rows}
    if len(pairs) > 1:
        raise ValueError("all trades must use one canonical pair")
    if len({trade.source for trade in rows}) > 1:
        raise ValueError("all trades must use one source provider")
    seen: dict[str, TradeEvent] = {}
    for trade in rows:
        _validate_trade_runtime(trade)
        existing = seen.get(trade.source_event_id)
        if existing is not None:
            raise ValueError(f"duplicate source_event_id: {trade.source_event_id}")
        seen[trade.source_event_id] = trade
    outside = [
        trade.source_event_id
        for trade in seen.values()
        if not window_start <= trade.event_ts < window_end
    ]
    if outside:
        raise ValueError("trade event falls outside end-exclusive build window")
    return tuple(sorted(seen.values(), key=lambda trade: (trade.event_ts, trade.source_event_id)))


def _validate_trade_runtime(trade: TradeEvent) -> None:
    for name in ("event_ts", "ingested_at", "available_at"):
        _require_utc(getattr(trade, name), name)
    if min(trade.price, trade.base_qty, trade.quote_qty) <= 0:
        raise ValueError("price and quantities must be positive")
    if trade.available_at < trade.ingested_at:
        raise ValueError("trade availability precedes ingestion")


def _bar_from_trades(
    trades: Sequence[TradeEvent],
    *,
    bar_type: BarType,
    interval: TimeInterval | None,
    threshold_config_id: str | None,
    open_time: datetime,
    close_time: datetime,
    availability_lag: timedelta,
    source_snapshot_id: str,
    source: str,
    source_session_id: str,
    policy_id: str,
    threshold_value: Decimal | None = None,
    threshold_provenance: Literal["FIXED", "FITTED"] | None = None,
    threshold_artifact_id: str | None = None,
    threshold_artifact_version: str | None = None,
    threshold_train_end: datetime | None = None,
    threshold_available_at: datetime | None = None,
    minimum_available_at: datetime | None = None,
    boundary_direction: Literal["POSITIVE", "NEGATIVE"] | None = None,
) -> SilverBar:
    first = trades[0]
    known_sides = any(
        trade.aggressor_side in {AggressorSide.BUY, AggressorSide.SELL} for trade in trades
    )
    buy = (
        sum(
            (trade.base_qty for trade in trades if trade.aggressor_side is AggressorSide.BUY),
            Decimal(0),
        )
        if known_sides
        else None
    )
    sell = (
        sum(
            (trade.base_qty for trade in trades if trade.aggressor_side is AggressorSide.SELL),
            Decimal(0),
        )
        if known_sides
        else None
    )
    return _make_bar(
        trades=trades,
        pair=first.pair.pair,
        bar_type=bar_type,
        interval=interval,
        threshold_config_id=threshold_config_id,
        threshold_value=threshold_value,
        threshold_provenance=threshold_provenance,
        threshold_artifact_id=threshold_artifact_id,
        threshold_artifact_version=threshold_artifact_version,
        threshold_train_end=threshold_train_end,
        threshold_available_at=threshold_available_at,
        policy_id=policy_id,
        availability_lag=availability_lag,
        first_event_ts=first.event_ts,
        last_event_ts=trades[-1].event_ts,
        open_time=open_time,
        close_time=close_time,
        available_at=max(
            max(trade.available_at for trade in trades),
            close_time + availability_lag,
            minimum_available_at or close_time,
        ),
        open_price=first.price,
        high=max(trade.price for trade in trades),
        low=min(trade.price for trade in trades),
        close_price=trades[-1].price,
        base_volume=sum((trade.base_qty for trade in trades), Decimal(0)),
        quote_volume=sum((trade.quote_qty for trade in trades), Decimal(0)),
        trade_count=len(trades),
        buy_base_volume=buy,
        sell_base_volume=sell,
        source_snapshot_id=source_snapshot_id,
        source=source,
        source_session_id=source_session_id,
        source_event_ids=tuple(trade.source_event_id for trade in trades),
        boundary_direction=boundary_direction,
    )


def _make_bar(
    *,
    trades: Sequence[TradeEvent] | None,
    pair: str,
    bar_type: BarType,
    interval: TimeInterval | None,
    threshold_config_id: str | None,
    threshold_value: Decimal | None,
    threshold_provenance: Literal["FIXED", "FITTED"] | None,
    threshold_artifact_id: str | None,
    threshold_artifact_version: str | None,
    threshold_train_end: datetime | None,
    threshold_available_at: datetime | None,
    policy_id: str,
    availability_lag: timedelta,
    first_event_ts: datetime,
    last_event_ts: datetime,
    open_time: datetime,
    close_time: datetime,
    available_at: datetime,
    open_price: Decimal,
    high: Decimal,
    low: Decimal,
    close_price: Decimal,
    base_volume: Decimal,
    quote_volume: Decimal,
    trade_count: int,
    buy_base_volume: Decimal | None,
    sell_base_volume: Decimal | None,
    source_snapshot_id: str,
    source: str,
    source_session_id: str,
    source_event_ids: tuple[str, ...],
    boundary_direction: Literal["POSITIVE", "NEGATIVE"] | None,
) -> SilverBar:
    del trades
    identity: Mapping[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "pair": pair,
        "bar_type": bar_type.value,
        "interval": interval,
        "threshold_config_id": threshold_config_id,
        "threshold_value": str(threshold_value) if threshold_value is not None else None,
        "threshold_provenance": threshold_provenance,
        "threshold_source": threshold_artifact_id or "FIXED",
        "threshold_artifact_version": threshold_artifact_version,
        "threshold_train_end": _optional_utc_iso(threshold_train_end),
        "threshold_available_at": _optional_utc_iso(threshold_available_at),
        "policy_id": policy_id,
        "availability_lag_microseconds": _timedelta_microseconds(availability_lag),
        "open_time": open_time.isoformat(),
        "close_time": close_time.isoformat(),
        "source_snapshot_id": source_snapshot_id,
        "source": source,
        "source_session_id": source_session_id,
        "source_event_ids": list(source_event_ids),
        "boundary_direction": boundary_direction,
    }
    bar_id = f"sha256:{sha256_bytes(canonical_json_bytes(identity))}"
    return SilverBar(
        bar_id=bar_id,
        pair=pair,
        bar_type=bar_type,
        interval=interval,
        threshold_config_id=threshold_config_id,
        threshold_value=threshold_value,
        threshold_provenance=threshold_provenance,
        threshold_artifact_id=threshold_artifact_id,
        threshold_artifact_version=threshold_artifact_version,
        threshold_train_end=threshold_train_end,
        threshold_available_at=threshold_available_at,
        policy_id=policy_id,
        availability_lag_microseconds=_timedelta_microseconds(availability_lag),
        first_event_ts=first_event_ts,
        last_event_ts=last_event_ts,
        open_time=open_time,
        close_time=close_time,
        available_at=available_at,
        open=open_price,
        high=high,
        low=low,
        close=close_price,
        base_volume=base_volume,
        quote_volume=quote_volume,
        trade_count=trade_count,
        buy_base_volume=buy_base_volume,
        sell_base_volume=sell_base_volume,
        source_snapshot_id=source_snapshot_id,
        source=source,
        source_session_id=source_session_id,
        source_event_ids=source_event_ids,
        quality_status=QualityStatus.PASS,
        quality_flags=(),
        boundary_direction=boundary_direction,
    )


def _floor_utc(value: datetime, seconds: int) -> datetime:
    epoch_seconds = int(value.timestamp())
    return datetime.fromtimestamp(epoch_seconds - epoch_seconds % seconds, tz=UTC)


def _bucket_starts(start: datetime, end: datetime, seconds: int):
    cursor = start
    while cursor < end:
        yield cursor
        cursor += timedelta(seconds=seconds)


def _require_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be timezone-aware UTC")


def _sum_optional(values: Iterable[Decimal | None]) -> Decimal | None:
    rows = tuple(values)
    if all(value is None for value in rows):
        return None
    return sum((value for value in rows if value is not None), Decimal(0))


def _timedelta_microseconds(value: timedelta) -> int:
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds


def _optional_utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    _require_utc(value, "threshold timestamp")
    return value.isoformat().replace("+00:00", "Z")


def _validate_reconciliation_source(
    bars: Sequence[SilverBar],
    *,
    label: str,
    pair: str,
    source: str,
    snapshot_id: str,
) -> None:
    for bar in bars:
        if bar.pair != pair:
            raise ValueError(f"{label} pair does not match reconciliation policy")
        if bar.source != source:
            raise ValueError(f"{label} source does not match reconciliation policy")
        if bar.source_snapshot_id != snapshot_id:
            raise ValueError(f"{label} source snapshot does not match reconciliation policy")
