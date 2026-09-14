from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from indodax_lab.data.quality import QualityFinding, validate_candles

START = datetime(2024, 1, 1, tzinfo=UTC)


def _row(**changes: object) -> dict[str, object]:
    start = changes.pop("open_time", START)
    assert isinstance(start, datetime)
    values: dict[str, object] = {
        "pair": "btc_idr",
        "interval": "1h",
        "source": "indodax",
        "open_time": start,
        "close_time": start + timedelta(hours=1),
        "open": Decimal("100"),
        "high": Decimal("110"),
        "low": Decimal("90"),
        "close": Decimal("105"),
        "base_volume": Decimal("1"),
        "is_closed": True,
        "available_at": start + timedelta(hours=1),
        "quality_status": "PASS",
    }
    values.update(changes)
    return values


@pytest.mark.parametrize(
    ("rows", "code"),
    [
        ([_row(), _row()], "DUPLICATE_PRIMARY_KEY"),
        (
            [_row(open_time=START + timedelta(hours=1)), _row(open_time=START)],
            "TIMESTAMP_NOT_MONOTONIC",
        ),
        (
            [_row(), _row(open_time=START + timedelta(hours=2))],
            "INTERVAL_GAP",
        ),
        ([_row(high=Decimal("104"))], "HIGH_BELOW_CLOSE"),
        ([_row(low=Decimal("101"))], "LOW_ABOVE_OPEN"),
        ([_row(base_volume=Decimal("-1"))], "NEGATIVE_VOLUME"),
        (
            [_row(open_time=datetime(2024, 1, 1), close_time=datetime(2024, 1, 1, 1))],
            "NAIVE_TIMESTAMP",
        ),
    ],
)
def test_dataset_contract_failures_are_structured(rows, code):
    """Removing a gate would allow an invalid candle dataset to become silver-eligible."""
    report = validate_candles(
        rows,
        expected_start=START,
        expected_end=START + timedelta(hours=3),
        interval="1h",
        as_of=START + timedelta(hours=3),
        source_checksums=("sha256:fixture",),
    )

    assert report.status == "FAIL"
    assert any(finding.code == code and finding.severity == "FAIL" for finding in report.findings)
    assert all(isinstance(finding, QualityFinding) for finding in report.findings)


def test_stale_final_bar_is_a_fail_with_injected_as_of():
    """Using wall-clock time would make the same snapshot change status between runs."""
    report = validate_candles(
        [_row()],
        expected_start=START,
        expected_end=START + timedelta(hours=1),
        interval="1h",
        as_of=START + timedelta(hours=3),
        max_final_bar_age=timedelta(hours=1),
    )

    assert report.status == "FAIL"
    assert [finding.code for finding in report.findings] == ["STALE_FINAL_BAR"]


def test_report_preserves_subsecond_staleness_policy_exactly():
    """Truncating the policy duration would make report replay use different validation facts."""
    report = validate_candles(
        [_row()],
        expected_start=START,
        expected_end=START + timedelta(hours=1),
        interval="1h",
        as_of=START + timedelta(hours=1),
        max_final_bar_age=timedelta(microseconds=1),
    )

    assert report.to_dict()["max_final_bar_age_microseconds"] == 1


def test_report_has_stable_content_and_exact_coverage_facts():
    """Nondeterministic report order or hidden clock fields would defeat audit identity."""
    rows = [_row(open_time=START + timedelta(hours=1)), _row(open_time=START)]
    kwargs = {
        "expected_start": START,
        "expected_end": START + timedelta(hours=2),
        "interval": "1h",
        "as_of": START + timedelta(hours=2),
        "source_checksums": ("sha256:z", "sha256:a"),
    }

    first = validate_candles(rows, **kwargs)
    second = validate_candles(rows, **kwargs)

    assert first.to_dict() == second.to_dict()
    assert first.to_dict()["expected_rows"] == 2
    assert first.to_dict()["actual_rows"] == 2
    assert first.to_dict()["coverage"] == {
        "start_ts": "2024-01-01T00:00:00Z",
        "end_ts": "2024-01-01T02:00:00Z",
    }
    assert first.to_dict()["source_checksums"] == ["sha256:a", "sha256:z"]


def test_upstream_warning_requires_explicit_approval_but_is_not_a_contract_failure():
    """Treating source WARN as PASS would let a worker build silver without an approval decision."""
    report = validate_candles(
        [_row(quality_status="WARN")],
        expected_start=START,
        expected_end=START + timedelta(hours=1),
        interval="1h",
        as_of=START + timedelta(hours=1),
    )

    assert report.status == "WARN"
    assert [(finding.code, finding.severity) for finding in report.findings] == [
        ("UPSTREAM_QUALITY_WARN", "WARN")
    ]


@pytest.mark.parametrize(
    ("quality_status", "code"),
    [
        ("FAIL", "UPSTREAM_QUALITY_FAIL"),
        ("QUARANTINED", "UPSTREAM_QUALITY_QUARANTINED"),
        ("UNKNOWN", "UPSTREAM_QUALITY_STATUS_UNKNOWN"),
        (None, "UPSTREAM_QUALITY_STATUS_MISSING"),
    ],
)
def test_non_approved_source_statuses_fail_closed(quality_status, code):
    """Defaulting an unknown source quality state to PASS would leak quarantined data onward."""
    report = validate_candles(
        [_row(quality_status=quality_status)],
        expected_start=START,
        expected_end=START + timedelta(hours=1),
        interval="1h",
        as_of=START + timedelta(hours=1),
    )

    assert report.status == "FAIL"
    assert [(finding.code, finding.severity) for finding in report.findings] == [(code, "FAIL")]


def test_gap_findings_are_clipped_coalesced_and_count_missing_intervals():
    """Using an out-of-window bar as a gap boundary would misstate requested coverage."""
    report = validate_candles(
        [
            _row(open_time=START + timedelta(hours=2)),
            _row(open_time=START + timedelta(hours=4)),
        ],
        expected_start=START,
        expected_end=START + timedelta(hours=3),
        interval="1h",
        as_of=START + timedelta(hours=3),
    )

    gap = next(finding for finding in report.findings if finding.code == "INTERVAL_GAP")
    assert report.gap_ranges == ((START, START + timedelta(hours=2)),)
    assert (gap.start_ts, gap.end_ts, gap.row_count, gap.details) == (
        START,
        START + timedelta(hours=2),
        2,
        {},
    )
