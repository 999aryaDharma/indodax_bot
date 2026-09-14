"""Deterministic, fail-closed quality checks for canonical candle snapshots."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal

POLICY_VERSION = "market-data-sentry-v1"
QUALITY_REPORT_SCHEMA_VERSION = "1.0.0"
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_INTERVALS = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}


class InvalidValidationWindowError(ValueError):
    """The caller's requested coverage window cannot be evaluated for this interval."""


@dataclass(frozen=True)
class QualityFinding:
    """One stable, machine-readable quality rule violation."""

    code: str
    severity: Literal["WARN", "FAIL"]
    pair: str
    start_ts: datetime
    end_ts: datetime
    row_count: int
    details: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "pair": self.pair,
            "start_ts": _timestamp(self.start_ts),
            "end_ts": _timestamp(self.end_ts),
            "row_count": self.row_count,
            "details": dict(sorted(self.details.items())),
        }


@dataclass(frozen=True)
class QualityReport:
    """Content-addressable quality facts for a requested candle coverage window."""

    quality_schema_version: str
    policy_version: str
    expected_start: datetime | None
    expected_end: datetime | None
    interval: str | None
    as_of: datetime | None
    max_final_bar_age_microseconds: int | None
    expected_rows: int
    actual_rows: int
    gap_ranges: tuple[tuple[datetime, datetime], ...]
    duplicate_count: int
    invariant_counts: dict[str, int]
    min_ts: datetime | None
    max_ts: datetime | None
    coverage: tuple[datetime | None, datetime | None]
    source_checksums: tuple[str, ...]
    status: Literal["PASS", "WARN", "FAIL"]
    silver_eligible: bool
    findings: tuple[QualityFinding, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "quality_schema_version": self.quality_schema_version,
            "policy_version": self.policy_version,
            "expected_start": _timestamp(self.expected_start) if self.expected_start else None,
            "expected_end": _timestamp(self.expected_end) if self.expected_end else None,
            "interval": self.interval,
            "as_of": _timestamp(self.as_of) if self.as_of else None,
            "max_final_bar_age_microseconds": self.max_final_bar_age_microseconds,
            "expected_rows": self.expected_rows,
            "actual_rows": self.actual_rows,
            "gap_ranges": [
                {"start_ts": _timestamp(start), "end_ts": _timestamp(end)}
                for start, end in self.gap_ranges
            ],
            "duplicate_count": self.duplicate_count,
            "invariant_counts": dict(sorted(self.invariant_counts.items())),
            "min_ts": _timestamp(self.min_ts) if self.min_ts else None,
            "max_ts": _timestamp(self.max_ts) if self.max_ts else None,
            "coverage": {
                "start_ts": _timestamp(self.coverage[0]) if self.coverage[0] else None,
                "end_ts": _timestamp(self.coverage[1]) if self.coverage[1] else None,
            },
            "source_checksums": list(self.source_checksums),
            "status": self.status,
            "silver_eligible": self.silver_eligible,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def interval_duration(interval: str) -> timedelta:
    """Return the fixed candle duration accepted by the bronze contract."""
    try:
        return _INTERVALS[interval]
    except KeyError as error:
        raise ValueError("UNSUPPORTED_INTERVAL") from error


def validate_candles(
    rows: Iterable[Mapping[str, object] | object],
    *,
    expected_start: datetime,
    expected_end: datetime,
    interval: str,
    as_of: datetime,
    source_checksums: Iterable[str] = (),
    max_final_bar_age: timedelta | None = None,
    policy_version: str = POLICY_VERSION,
) -> QualityReport:
    """Check candle data without mutating the data or relying on wall-clock time."""
    duration = interval_duration(interval)
    _validate_requested_window(expected_start, expected_end, as_of, duration)
    expected_rows_per_series = int((expected_end - expected_start) / duration)
    materialized = [_as_mapping(row) for row in rows]
    findings: list[QualityFinding] = []
    counts: Counter[str] = Counter()
    parsed: list[tuple[int, Mapping[str, object], str, datetime]] = []

    for index, row in enumerate(materialized):
        pair = _pair(row)
        timestamps = _timestamps(row)
        invalid_timestamp = False
        for name, value in timestamps.items():
            if value is None or not _is_utc(value):
                invalid_timestamp = True
                counts["NAIVE_TIMESTAMP"] += 1
                findings.append(
                    _finding(
                        "NAIVE_TIMESTAMP",
                        pair,
                        _safe_timestamp(value),
                        _safe_timestamp(value),
                        1,
                        {"field": name},
                    )
                )
        open_time = timestamps["open_time"]
        if invalid_timestamp or not isinstance(open_time, datetime) or not _is_utc(open_time):
            continue
        parsed.append((index, row, pair, open_time))
        _check_invariants(row, pair, open_time, timestamps, findings, counts, as_of)
        _check_source_status(row, pair, open_time, findings, counts)

    _check_monotonic(parsed, findings, counts)
    _check_duplicates(parsed, findings, counts)
    gap_ranges = _check_gaps(
        parsed, expected_start, expected_end, duration, findings, counts
    )
    _check_staleness(parsed, as_of, duration, max_final_bar_age, findings, counts)

    valid_times = [open_time for _, _, _, open_time in parsed]
    series = {(pair, str(row.get("interval", ""))) for _, row, pair, _ in parsed}
    expected_rows = expected_rows_per_series * len(series) if series else expected_rows_per_series
    min_ts = min(valid_times) if valid_times else None
    max_ts = max(valid_times) if valid_times else None
    coverage_end = max_ts + duration if max_ts is not None else None
    ordered_findings = tuple(sorted(findings, key=_finding_key))
    status: Literal["PASS", "WARN", "FAIL"] = "PASS"
    if any(finding.severity == "FAIL" for finding in ordered_findings):
        status = "FAIL"
    elif ordered_findings:
        status = "WARN"
    return QualityReport(
        quality_schema_version=QUALITY_REPORT_SCHEMA_VERSION,
        policy_version=policy_version,
        expected_start=expected_start,
        expected_end=expected_end,
        interval=interval,
        as_of=as_of,
        max_final_bar_age_microseconds=(
            _timedelta_microseconds(max_final_bar_age)
            if max_final_bar_age is not None
            else None
        ),
        expected_rows=expected_rows,
        actual_rows=len(materialized),
        gap_ranges=tuple(sorted(gap_ranges)),
        duplicate_count=counts["DUPLICATE_PRIMARY_KEY"],
        invariant_counts=dict(sorted(counts.items())),
        min_ts=min_ts,
        max_ts=max_ts,
        coverage=(min_ts, coverage_end),
        source_checksums=tuple(sorted(set(source_checksums))),
        status=status,
        silver_eligible=status == "PASS",
        findings=ordered_findings,
    )


def failure_report(
    code: str,
    *,
    details: Mapping[str, object] | None = None,
    source_checksums: Iterable[str] = (),
    policy_version: str = POLICY_VERSION,
) -> QualityReport:
    """Return a fail-closed report for a snapshot that cannot be safely inspected."""
    finding = _finding(
        code,
        "*",
        _EPOCH,
        _EPOCH,
        0,
        {key: str(value) for key, value in (details or {}).items()},
    )
    return QualityReport(
        quality_schema_version=QUALITY_REPORT_SCHEMA_VERSION,
        policy_version=policy_version,
        expected_start=None,
        expected_end=None,
        interval=None,
        as_of=None,
        max_final_bar_age_microseconds=None,
        expected_rows=0,
        actual_rows=0,
        gap_ranges=(),
        duplicate_count=0,
        invariant_counts={code: 1},
        min_ts=None,
        max_ts=None,
        coverage=(None, None),
        source_checksums=tuple(sorted(set(source_checksums))),
        status="FAIL",
        silver_eligible=False,
        findings=(finding,),
    )


def _as_mapping(row: Mapping[str, object] | object) -> Mapping[str, object]:
    if isinstance(row, Mapping):
        return row
    dumped = getattr(row, "model_dump", None)
    if callable(dumped):
        return dumped(mode="python")
    return {}


def _pair(row: Mapping[str, object]) -> str:
    value = row.get("pair", "*")
    return str(getattr(value, "pair", value))


def _timestamps(row: Mapping[str, object]) -> dict[str, object | None]:
    return {name: row.get(name) for name in ("open_time", "close_time", "available_at")}


def _check_invariants(
    row: Mapping[str, object],
    pair: str,
    open_time: datetime,
    timestamps: Mapping[str, object | None],
    findings: list[QualityFinding],
    counts: Counter[str],
    as_of: datetime,
) -> None:
    close_time = timestamps["close_time"]
    available_at = timestamps["available_at"]
    prices = {field: _decimal(row.get(field)) for field in ("open", "high", "low", "close")}
    for field, value in prices.items():
        if value is None:
            _append("INVALID_OHLC_VALUE", pair, open_time, findings, counts, {"field": field})
    for left, right, code, invalid in (
        ("high", "close", "HIGH_BELOW_CLOSE", lambda first, second: first < second),
        ("high", "open", "HIGH_BELOW_OPEN", lambda first, second: first < second),
        ("low", "open", "LOW_ABOVE_OPEN", lambda first, second: first > second),
        ("low", "close", "LOW_ABOVE_CLOSE", lambda first, second: first > second),
    ):
        first, second = prices[left], prices[right]
        if first is not None and second is not None and invalid(first, second):
            _append(code, pair, open_time, findings, counts, {"left": left, "right": right})
    for volume in ("base_volume", "quote_volume"):
        value = _decimal(row.get(volume))
        required = volume == "base_volume"
        if value is None and (required or row.get(volume) is not None):
            _append("INVALID_VOLUME_VALUE", pair, open_time, findings, counts, {"field": volume})
        elif value is not None and value < 0:
            _append("NEGATIVE_VOLUME", pair, open_time, findings, counts, {"field": volume})
    if row.get("is_closed") is not True:
        _append("CANDLE_NOT_CLOSED", pair, open_time, findings, counts, {})
    if isinstance(close_time, datetime) and isinstance(available_at, datetime):
        if _is_utc(close_time) and _is_utc(available_at) and available_at < close_time:
            _append("AVAILABILITY_BEFORE_CLOSE", pair, open_time, findings, counts, {})
    if isinstance(available_at, datetime) and _is_utc(available_at) and available_at > as_of:
        _append("CANDLE_NOT_AVAILABLE_AS_OF", pair, open_time, findings, counts, {})


def _check_source_status(
    row: Mapping[str, object],
    pair: str,
    open_time: datetime,
    findings: list[QualityFinding],
    counts: Counter[str],
) -> None:
    status = row.get("quality_status")
    if status == "PASS":
        return
    if status == "WARN":
        counts["UPSTREAM_QUALITY_WARN"] += 1
        findings.append(
            _finding(
                "UPSTREAM_QUALITY_WARN",
                pair,
                open_time,
                open_time,
                1,
                {},
                severity="WARN",
            )
        )
        return
    if status == "FAIL":
        _append("UPSTREAM_QUALITY_FAIL", pair, open_time, findings, counts, {})
        return
    if status == "QUARANTINED":
        _append("UPSTREAM_QUALITY_QUARANTINED", pair, open_time, findings, counts, {})
        return
    if status is None:
        _append("UPSTREAM_QUALITY_STATUS_MISSING", pair, open_time, findings, counts, {})
        return
    _append(
        "UPSTREAM_QUALITY_STATUS_UNKNOWN",
        pair,
        open_time,
        findings,
        counts,
        {"status": str(status)},
    )


def _check_monotonic(
    parsed: list[tuple[int, Mapping[str, object], str, datetime]],
    findings: list[QualityFinding],
    counts: Counter[str],
) -> None:
    previous: dict[tuple[str, str], datetime] = {}
    for _, row, pair, timestamp in parsed:
        key = (pair, str(row.get("interval", "")))
        earlier = previous.get(key)
        if earlier is not None and timestamp < earlier:
            _append("TIMESTAMP_NOT_MONOTONIC", pair, timestamp, findings, counts, {})
        previous[key] = timestamp


def _check_duplicates(
    parsed: list[tuple[int, Mapping[str, object], str, datetime]],
    findings: list[QualityFinding],
    counts: Counter[str],
) -> None:
    keys: dict[tuple[str, str, datetime, str], list[datetime]] = defaultdict(list)
    for _, row, pair, timestamp in parsed:
        key = (pair, str(row.get("interval", "")), timestamp, str(row.get("source", "")))
        keys[key].append(timestamp)
    for (pair, _, _, _), timestamps in sorted(keys.items()):
        if len(timestamps) > 1:
            _append(
                "DUPLICATE_PRIMARY_KEY",
                pair,
                min(timestamps),
                findings,
                counts,
                {"duplicates": str(len(timestamps) - 1)},
                row_count=len(timestamps) - 1,
            )


def _check_gaps(
    parsed: list[tuple[int, Mapping[str, object], str, datetime]],
    expected_start: datetime,
    expected_end: datetime,
    duration: timedelta,
    findings: list[QualityFinding],
    counts: Counter[str],
) -> list[tuple[datetime, datetime]]:
    grouped: dict[tuple[str, str], set[datetime]] = defaultdict(set)
    for _, row, pair, timestamp in parsed:
        grouped[(pair, str(row.get("interval", "")))].add(timestamp)
    ranges: list[tuple[datetime, datetime]] = []
    expected_slots: list[datetime] = []
    slot = expected_start
    while slot < expected_end:
        expected_slots.append(slot)
        slot += duration
    groups = sorted(grouped.items()) if grouped else [(("*", ""), set())]
    for (pair, _), timestamps in groups:
        observed = {
            timestamp
            for timestamp in timestamps
            if expected_start <= timestamp < expected_end
            and (timestamp - expected_start) % duration == timedelta()
        }
        missing = [slot for slot in expected_slots if slot not in observed]
        for start, end, row_count in _coalesce_missing(missing, duration):
            ranges.append((start, end))
            counts["INTERVAL_GAP"] += row_count
            findings.append(_finding("INTERVAL_GAP", pair, start, end, row_count, {}))
    return ranges


def _coalesce_missing(
    missing: list[datetime], duration: timedelta
) -> list[tuple[datetime, datetime, int]]:
    if not missing:
        return []
    ranges: list[tuple[datetime, datetime, int]] = []
    start = previous = missing[0]
    count = 1
    for timestamp in missing[1:]:
        if timestamp == previous + duration:
            previous = timestamp
            count += 1
            continue
        ranges.append((start, previous + duration, count))
        start = previous = timestamp
        count = 1
    ranges.append((start, previous + duration, count))
    return ranges


def _check_staleness(
    parsed: list[tuple[int, Mapping[str, object], str, datetime]],
    as_of: datetime,
    duration: timedelta,
    max_final_bar_age: timedelta | None,
    findings: list[QualityFinding],
    counts: Counter[str],
) -> None:
    age_limit = max_final_bar_age if max_final_bar_age is not None else duration
    latest: dict[str, datetime] = {}
    for _, row, pair, timestamp in parsed:
        if row.get("is_closed") is True:
            latest[pair] = max(latest.get(pair, timestamp), timestamp)
    for pair, timestamp in sorted(latest.items()):
        final_at = timestamp + duration
        if as_of - final_at > age_limit:
            _append(
                "STALE_FINAL_BAR",
                pair,
                timestamp,
                findings,
                counts,
                {"max_age_seconds": str(int(age_limit.total_seconds()))},
            )


def _append(
    code: str,
    pair: str,
    timestamp: datetime,
    findings: list[QualityFinding],
    counts: Counter[str],
    details: Mapping[str, str],
    *,
    row_count: int = 1,
) -> None:
    counts[code] += row_count
    findings.append(_finding(code, pair, timestamp, timestamp, row_count, details))


def _finding(
    code: str,
    pair: str,
    start_ts: datetime,
    end_ts: datetime,
    row_count: int,
    details: Mapping[str, str],
    *,
    severity: Literal["WARN", "FAIL"] = "FAIL",
) -> QualityFinding:
    return QualityFinding(code, severity, pair, start_ts, end_ts, row_count, dict(details))


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        decimal = value if isinstance(value, Decimal) else Decimal(str(value))
        return decimal if decimal.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _is_utc(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() == timedelta(0)
    )


def _validate_requested_window(
    expected_start: datetime, expected_end: datetime, as_of: datetime, duration: timedelta
) -> None:
    for value in (expected_start, expected_end, as_of):
        if not _is_utc(value):
            raise InvalidValidationWindowError("NON_UTC_VALIDATION_WINDOW")
    if (
        expected_end <= expected_start
        or (expected_end - expected_start) % duration
        or (expected_start - _EPOCH) % duration
        or (expected_end - _EPOCH) % duration
    ):
        raise InvalidValidationWindowError("INVALID_VALIDATION_WINDOW")


def _require_utc(value: datetime, name: str) -> None:
    if not _is_utc(value):
        raise ValueError(name)


def _safe_timestamp(value: object | None) -> datetime:
    return value if isinstance(value, datetime) and _is_utc(value) else _EPOCH


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _timedelta_microseconds(value: timedelta) -> int:
    return ((value.days * 86_400 + value.seconds) * 1_000_000) + value.microseconds


def _finding_key(finding: QualityFinding) -> tuple[object, ...]:
    return (
        finding.code,
        finding.severity,
        finding.pair,
        finding.start_ts,
        finding.end_ts,
        finding.row_count,
        tuple(sorted(finding.details.items())),
    )
