"""Unit tests for DeepLOB gap enforcement (L01-01 fix cycle).

Covers IMPORTANT findings:
1. `DeepLOBTrainer.validate_unbroken_sequence` must mirror the LOB-01
   boundary/sequence checks (pair/session crossing, sequence_id gaps and
   non-monotonicity, negative deltas), raising GappedBookBlockedError.
2. Gap enforcement must be wired into every train/predict entry point, not
   left as an opt-in helper.

NOTE: this module deliberately imports only `indodax_lab.models.lob` so it
stays collectible without the optional `pyarrow` dependency required by
`indodax_lab.features` (see ENV-GAP record in the fix report).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from indodax_lab.models.lob.dataset import BookLevel, BookSnapshot
from indodax_lab.models.lob.l01_deeplob import (
    DeepLOBConfig,
    DeepLOBTrainer,
    GappedBookBlockedError,
)


def _snap(
    ts: datetime,
    pair: str = "BTC_IDR",
    session: str = "sess-a",
    seq: int | None = None,
) -> BookSnapshot:
    return BookSnapshot(
        timestamp=ts,
        pair=pair,
        session_id=session,
        bids=[BookLevel(price=Decimal("99"), volume=Decimal("1"))],
        asks=[BookLevel(price=Decimal("101"), volume=Decimal("1"))],
        sequence_id=seq,
    )


def _trainer(**overrides) -> DeepLOBTrainer:
    kwargs = {"lookback_len": 4, "num_features": 4, "max_gap_seconds": 10.0}
    kwargs.update(overrides)
    return DeepLOBTrainer(config=DeepLOBConfig(**kwargs))


def test_cross_session_sequence_blocked() -> None:
    """Pair/session crossing must fail closed, not pass as unbroken."""
    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    snapshots = [_snap(t0 + timedelta(seconds=i), session="sess-a", seq=i) for i in range(3)]
    snapshots += [_snap(t0 + timedelta(seconds=3 + i), session="sess-b", seq=3 + i) for i in range(3)]
    with pytest.raises(GappedBookBlockedError, match="GAPPED_BOOK_BLOCKED"):
        _trainer().validate_unbroken_sequence(snapshots)


def test_cross_pair_sequence_blocked() -> None:
    """A pair change inside the window must fail closed."""
    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    snapshots = [_snap(t0 + timedelta(seconds=i), pair="BTC_IDR", seq=i) for i in range(3)]
    snapshots += [_snap(t0 + timedelta(seconds=3 + i), pair="ETH_IDR", seq=3 + i) for i in range(3)]
    with pytest.raises(GappedBookBlockedError, match="GAPPED_BOOK_BLOCKED"):
        _trainer().validate_unbroken_sequence(snapshots)


def test_sequence_id_gap_blocked() -> None:
    """Skipped sequence_id (0,1,3) must fail closed even with 1s spacing."""
    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    snapshots = [_snap(t0 + timedelta(seconds=i), seq=s) for i, s in enumerate((0, 1, 3))]
    with pytest.raises(GappedBookBlockedError, match="GAPPED_BOOK_BLOCKED"):
        _trainer().validate_unbroken_sequence(snapshots)


def test_non_monotonic_sequence_id_blocked() -> None:
    """Non-monotonic sequence_id (0,2,1) must fail closed."""
    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    snapshots = [_snap(t0 + timedelta(seconds=i), seq=s) for i, s in enumerate((0, 2, 1))]
    with pytest.raises(GappedBookBlockedError, match="GAPPED_BOOK_BLOCKED"):
        _trainer().validate_unbroken_sequence(snapshots)


def test_negative_time_delta_blocked() -> None:
    """Backwards timestamps must fail closed, not pass the delta check."""
    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    snapshots = [
        _snap(t0, seq=0),
        _snap(t0 + timedelta(seconds=1), seq=1),
        _snap(t0 + timedelta(seconds=1) - timedelta(milliseconds=500), seq=2),
    ]
    with pytest.raises(GappedBookBlockedError, match="GAPPED_BOOK_BLOCKED"):
        _trainer().validate_unbroken_sequence(snapshots)


def test_time_gap_still_blocked() -> None:
    """Regression guard: plain time gaps keep raising GappedBookBlockedError."""
    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    snapshots = [_snap(t0 + timedelta(seconds=i), seq=i) for i in range(3)]
    snapshots.append(_snap(t0 + timedelta(seconds=120), seq=3))
    with pytest.raises(GappedBookBlockedError, match="GAPPED_BOOK_BLOCKED"):
        _trainer().validate_unbroken_sequence(snapshots)


def test_clean_sequence_passes() -> None:
    """Regression guard: contiguous same-stream snapshots still validate."""
    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    snapshots = [_snap(t0 + timedelta(seconds=i), seq=i) for i in range(6)]
    _trainer().validate_unbroken_sequence(snapshots)


def _gapped_snapshots() -> list[BookSnapshot]:
    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    snapshots = [_snap(t0 + timedelta(seconds=i), seq=i) for i in range(4)]
    snapshots += [_snap(t0 + timedelta(seconds=120 + i), seq=4 + i) for i in range(4)]
    return snapshots


def test_prepare_training_windows_blocks_gapped_books() -> None:
    """Wired train path must block gapped books without an explicit validate call."""
    with pytest.raises(GappedBookBlockedError, match="GAPPED_BOOK_BLOCKED"):
        _trainer().prepare_training_windows(_gapped_snapshots())


def test_prepare_predict_windows_blocks_gapped_books() -> None:
    """Wired predict path must block gapped books without an explicit validate call."""
    with pytest.raises(GappedBookBlockedError, match="GAPPED_BOOK_BLOCKED"):
        _trainer().prepare_predict_windows(_gapped_snapshots())


def test_prepare_training_windows_blocks_cross_session_books() -> None:
    """Wired train path must also block pair/session crossing."""
    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    snapshots = [_snap(t0 + timedelta(seconds=i), session="sess-a", seq=i) for i in range(4)]
    snapshots += [_snap(t0 + timedelta(seconds=4 + i), session="sess-b", seq=4 + i) for i in range(4)]
    with pytest.raises(GappedBookBlockedError, match="GAPPED_BOOK_BLOCKED"):
        _trainer().prepare_training_windows(snapshots)


def test_prepare_training_windows_returns_windows_for_clean_books() -> None:
    """Wired train path returns rolling windows for a validated clean sequence."""
    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    snapshots = [_snap(t0 + timedelta(seconds=i), seq=i) for i in range(8)]
    windows = _trainer().prepare_training_windows(snapshots, window_len=4, stride=4)
    assert len(windows) == 2
    assert all(len(w) == 4 for w in windows)
