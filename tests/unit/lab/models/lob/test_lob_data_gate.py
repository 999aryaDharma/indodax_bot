"""Unit tests for Forward Book Dataset Eligibility Gate (LOB-01).

Guarantees:
1. LOB-01-AC0: LOB dataset only permits PASS sessions with >=90 day coverage and sufficient effective events.
2. LOB-01-AC1: Candle data cannot substitute for order book depth fixtures (CandleSubstitutionForbiddenError).
3. LOB-01-AC2: Gaps in book updates break sequence windows rather than bridging or interpolating.
4. LOB-01-AC3: High event row count across few days fails the >=90 day calendar coverage gate.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import numpy as np
import pytest

from indodax_lab.models.lob.dataset import (
    BookLevel,
    BookSnapshot,
    CandleSubstitutionForbiddenError,
    InsufficientCoverageGateError,
    LOBDatasetEligibilityGate,
    LOBEligibilityReport,
    LOBSessionMetadata,
    SessionGapBrokenWindowError,
    SessionStatus,
)
from indodax_lab.features.lob import (
    compute_depth_imbalance,
    compute_microprice,
    compute_spread,
    extract_lob_tensor,
)


def test_lob_01_valid_contract() -> None:
    """LOB-01-AC0: Positive contract - LOB dataset only permits PASS sessions with >=90 day coverage."""
    gate = LOBDatasetEligibilityGate(min_coverage_days=90, min_events_per_day=50)

    # Construct 92 distinct calendar days of PASS sessions
    base_date = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
    sessions = []
    for day in range(92):
        s_date = base_date + timedelta(days=day)
        sessions.append(
            LOBSessionMetadata(
                session_id=f"sess_{day:03d}",
                pair="BTC_IDR",
                start_ts=s_date,
                end_ts=s_date + timedelta(hours=23, minutes=59),
                event_count=500,
                status=SessionStatus.PASS,
                regime="balanced" if day % 2 == 0 else "volatile",
            )
        )

    report = gate.evaluate_coverage(sessions)
    assert isinstance(report, LOBEligibilityReport)
    assert report.is_eligible is True
    assert report.distinct_pass_days == 92
    assert report.total_events == 92 * 500
    assert "balanced" in report.regimes
    assert "volatile" in report.regimes

    # Test tensor extraction from sample book snapshots
    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    snapshots = [
        BookSnapshot(
            timestamp=t0 + timedelta(seconds=i),
            pair="BTC_IDR",
            bids=[BookLevel(price=Decimal("1000000000"), volume=Decimal("1.5"))],
            asks=[BookLevel(price=Decimal("1000500000"), volume=Decimal("2.0"))],
            sequence_id=i,
        )
        for i in range(10)
    ]
    tensor = extract_lob_tensor(snapshots, levels=1)
    assert tensor.shape == (10, 4)  # 10 timesteps, [bid_p, bid_v, ask_p, ask_v]
    imbalance = compute_depth_imbalance(tensor)
    assert len(imbalance) == 10
    spread = compute_spread(tensor)
    assert np.all(spread > 0)


def test_lob_01_contract_1() -> None:
    """LOB-01-AC1: Candle tidak dapat menjadi book fixture pengganti."""
    gate = LOBDatasetEligibilityGate()

    # Attempt to pass candle / OHLCV dictionary
    candle_payload = {
        "timestamp": datetime(2025, 1, 1, 12, 0, tzinfo=UTC),
        "open": 1000000000.0,
        "high": 1005000000.0,
        "low": 995000000.0,
        "close": 1002000000.0,
        "volume": 15.4,
    }

    with pytest.raises(CandleSubstitutionForbiddenError, match="CANDLE_SUBSTITUTION_FORBIDDEN"):
        gate.validate_book_schema(candle_payload)

    # Attempt to pass payload missing bid/ask book depth levels
    invalid_book_payload = {
        "timestamp": datetime(2025, 1, 1, 12, 0, tzinfo=UTC),
        "price": 1000000000.0,
        "pair": "BTC_IDR",
    }
    with pytest.raises(CandleSubstitutionForbiddenError, match="CANDLE_SUBSTITUTION_FORBIDDEN"):
        gate.validate_book_schema(invalid_book_payload)


def test_lob_01_contract_2() -> None:
    """LOB-01-AC2: Gap memutus sequence window."""
    gate = LOBDatasetEligibilityGate(max_gap_seconds=10.0)

    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    # Segment 1: 5 snapshots spaced by 1s
    seg1 = [
        BookSnapshot(
            timestamp=t0 + timedelta(seconds=i),
            pair="BTC_IDR",
            bids=[BookLevel(price=Decimal("1000000000"), volume=Decimal("1.0"))],
            asks=[BookLevel(price=Decimal("1000500000"), volume=Decimal("1.0"))],
        )
        for i in range(5)
    ]
    # Gap: jump 120 seconds forward (>> max_gap_seconds=10.0)
    gap_t = t0 + timedelta(seconds=125)
    # Segment 2: 5 snapshots spaced by 1s
    seg2 = [
        BookSnapshot(
            timestamp=gap_t + timedelta(seconds=i),
            pair="BTC_IDR",
            bids=[BookLevel(price=Decimal("1000000000"), volume=Decimal("1.0"))],
            asks=[BookLevel(price=Decimal("1000500000"), volume=Decimal("1.0"))],
        )
        for i in range(5)
    ]

    combined_snapshots = seg1 + seg2
    assert len(combined_snapshots) == 10

    # Segment windows: window_len=4, stride=4
    windows = gate.segment_continuous_windows(combined_snapshots, window_len=4, stride=4)
    # Must produce exactly 2 separate non-overlapping windows (one from seg1, one from seg2), NEVER bridging across the 120s gap
    assert len(windows) == 2
    assert len(windows[0]) == 4
    assert len(windows[1]) == 4
    for w in windows:
        # Each window duration is 3 seconds (4 points 1s apart), never crossing the 120s gap
        assert (w[-1].timestamp - w[0].timestamp).total_seconds() <= 4.0
    # The last snapshot of window 0 must be in seg1
    assert windows[0][-1].timestamp == t0 + timedelta(seconds=3)
    # The first snapshot of window 1 must be in seg2
    assert windows[1][0].timestamp == gap_t

    # Attempting to force continuous sequence across gap raises SessionGapBrokenWindowError
    with pytest.raises(SessionGapBrokenWindowError, match="LOB_WINDOW_GAP_DETECTED"):
        gate.validate_contiguous_window(combined_snapshots[:6])  # includes snapshot 4 and 5 (gap)


def test_lob_01_contract_3() -> None:
    """LOB-01-AC3: Banyak row dalam sedikit hari belum memenuhi gate."""
    gate = LOBDatasetEligibilityGate(min_coverage_days=90, min_events_per_day=100)

    # 1,000,000 events concentrated over only 15 distinct days
    base_date = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
    sessions = []
    for day in range(15):
        s_date = base_date + timedelta(days=day)
        sessions.append(
            LOBSessionMetadata(
                session_id=f"sess_{day:03d}",
                pair="BTC_IDR",
                start_ts=s_date,
                end_ts=s_date + timedelta(hours=23, minutes=59),
                event_count=66_667,  # Total ~1,000,000 events
                status=SessionStatus.PASS,
                regime="high_volatility",
            )
        )

    # Despite 1,000,000 events, 15 days is far below 90 days -> fail-closed rejection
    with pytest.raises(InsufficientCoverageGateError, match="COVERAGE_DAYS_INSUFFICIENT"):
        gate.evaluate_coverage(sessions)

    # Also: if sessions have status != PASS (e.g. FAIL / QUARANTINE), those days do not count
    quarantine_sessions = []
    for day in range(95):
        s_date = base_date + timedelta(days=day)
        quarantine_sessions.append(
            LOBSessionMetadata(
                session_id=f"q_sess_{day:03d}",
                pair="BTC_IDR",
                start_ts=s_date,
                end_ts=s_date + timedelta(hours=23, minutes=59),
                event_count=500,
                status=SessionStatus.FAIL if day > 20 else SessionStatus.PASS,  # Only 21 PASS days
                regime="normal",
            )
        )

    with pytest.raises(InsufficientCoverageGateError, match="COVERAGE_DAYS_INSUFFICIENT"):
        gate.evaluate_coverage(quarantine_sessions)
