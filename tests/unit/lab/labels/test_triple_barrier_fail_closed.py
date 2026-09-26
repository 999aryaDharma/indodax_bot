"""Fail-closed regression tests for LABEL-02 triple barrier labelling.

Review finding covered:
- LABEL-02-F1 (Important): bars were consumed as a continuous sequence with no coverage
  check. When bars are missing inside the vertical horizon, a barrier "touch" observed in
  a later bar may in fact have happened inside the unseen window, so the emitted
  ``first_touch``/``outcome``/``status=VALID`` was untrustworthy evidence presented as a
  settled label. Such a label must be EXCLUDED with ``INTERIOR_BAR_GAP``.

Acceptance criterion LABEL-02-AC1 is deliberately preserved: a single bar whose range
straddles both barriers is *not* ambiguous-by-coverage, and the documented conservative
choice (LOWER, outcome -1) still applies. These tests guard that boundary.

opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from indodax_lab.labels.triple_barrier import (
    BarrierTouch,
    TripleBarrierConfig,
    build_triple_barrier_label,
    compute_concurrency_weights,
)

DECISION_TS = datetime(2024, 6, 1, 10, 0, tzinfo=UTC)


def _config(horizon_hours: int) -> TripleBarrierConfig:
    return TripleBarrierConfig(
        label_set_id="triple_barrier",
        version="1.0.0",
        pt_multiplier=Decimal("2.0"),
        sl_multiplier=Decimal("1.5"),
        vertical_horizon=timedelta(hours=horizon_hours),
    )


def _make_bar(
    open_time: datetime,
    open_p: str,
    high_p: str,
    low_p: str,
    close_p: str,
) -> dict[str, Any]:
    return {
        "pair": "btc_idr",
        "open_time": open_time,
        "close_time": open_time + timedelta(hours=1),
        "open": Decimal(open_p),
        "high": Decimal(high_p),
        "low": Decimal(low_p),
        "close": Decimal(close_p),
        "base_volume": Decimal("10"),
        "quote_volume": Decimal("10000000"),
    }


def _label(
    bars: list[dict[str, Any]],
    sample_id: str,
    horizon_hours: int = 5,
):
    return build_triple_barrier_label(
        sample_id=sample_id,
        pair="btc_idr",
        decision_ts=DECISION_TS,
        decision_volatility=Decimal("0.01"),
        bars=bars,
        config=_config(horizon_hours),
    )


def _gapped_bars() -> list[dict[str, Any]]:
    """10:00 and 11:00 bars, then the 12:00 bar is missing and 13:00 touches the upper barrier.

    Barriers are upper=102m / lower=98.5m, so the 13:00 bar (high 102.5m) would be read as
    an UPPER touch. The unseen 12:00 window is exactly where that touch may have happened.
    """
    return [
        _make_bar(DECISION_TS, "100000000", "100500000", "99500000", "100000000"),
        _make_bar(
            datetime(2024, 6, 1, 11, 0, tzinfo=UTC), "100000000", "101000000", "99800000", "100800000"
        ),
        # 12:00 bar is absent.
        _make_bar(
            datetime(2024, 6, 1, 13, 0, tzinfo=UTC), "100800000", "102500000", "100500000", "102200000"
        ),
        _make_bar(
            datetime(2024, 6, 1, 14, 0, tzinfo=UTC), "102200000", "103000000", "101900000", "102800000"
        ),
    ]


def test_label_02_interior_bar_gap_is_excluded_not_a_touch() -> None:
    """LABEL-02-F1: a missing bar inside the horizon invalidates any later observed touch."""
    label = _label(_gapped_bars(), "s_interior_gap")

    assert label.status == "EXCLUDED"
    assert label.exclusion_reason == "INTERIOR_BAR_GAP"
    assert label.first_touch is None
    assert label.outcome is None


def test_label_02_interior_gap_emits_no_class_signal() -> None:
    """LABEL-02-F1: the excluded row must never be handed a +1/0/-1 training class."""
    label = _label(_gapped_bars(), "s_no_signal")

    assert label.outcome not in (-1, 0, 1)
    assert label.first_touch is not BarrierTouch.UPPER
    # Barriers stay recorded for audit; only the class signal is withheld.
    assert label.upper_barrier == Decimal("102000000")
    assert label.lower_barrier == Decimal("98500000")


def test_label_02_touch_resolved_before_the_gap_stands() -> None:
    """LABEL-02-F1 guard: a gap after an already-resolved touch does not invalidate it."""
    bars = [
        _make_bar(DECISION_TS, "100000000", "100500000", "99500000", "100000000"),
        # Upper barrier touched at 11:00, before the 12:00 gap.
        _make_bar(
            datetime(2024, 6, 1, 11, 0, tzinfo=UTC), "100000000", "102500000", "99800000", "102200000"
        ),
        _make_bar(
            datetime(2024, 6, 1, 13, 0, tzinfo=UTC), "102200000", "103000000", "101900000", "102800000"
        ),
    ]
    label = _label(bars, "s_touch_before_gap")

    assert label.status == "VALID"
    assert label.first_touch == BarrierTouch.UPPER
    assert label.outcome == 1


def test_label_02_both_barriers_in_one_bar_still_selects_lower() -> None:
    """LABEL-02-AC1 guard: full coverage keeps the documented conservative LOWER choice."""
    bars = [
        _make_bar(DECISION_TS, "100000000", "100500000", "99500000", "100000000"),
        _make_bar(
            datetime(2024, 6, 1, 11, 0, tzinfo=UTC), "100000000", "103000000", "97000000", "100000000"
        ),
        _make_bar(
            datetime(2024, 6, 1, 12, 0, tzinfo=UTC), "100000000", "101000000", "99500000", "100500000"
        ),
    ]
    label = _label(bars, "s_both", horizon_hours=4)

    assert label.status == "VALID"
    assert label.first_touch == BarrierTouch.LOWER
    assert label.outcome == -1


def test_label_02_contiguous_bars_are_unaffected() -> None:
    """LABEL-02-F1 guard: gap-free coverage produces the unchanged upper/lower/vertical labels."""
    upper = _label(
        [
            _make_bar(DECISION_TS, "100000000", "100500000", "99500000", "100000000"),
            _make_bar(
                datetime(2024, 6, 1, 11, 0, tzinfo=UTC),
                "100000000", "102500000", "99500000", "102200000",
            ),
        ],
        "s_upper",
    )
    assert (upper.status, upper.first_touch, upper.outcome) == (
        "VALID", BarrierTouch.UPPER, 1,
    )

    lower = _label(
        [
            _make_bar(DECISION_TS, "100000000", "100500000", "99500000", "100000000"),
            _make_bar(
                datetime(2024, 6, 1, 11, 0, tzinfo=UTC),
                "100000000", "100500000", "98000000", "98300000",
            ),
        ],
        "s_lower",
    )
    assert (lower.status, lower.first_touch, lower.outcome) == (
        "VALID", BarrierTouch.LOWER, -1,
    )

    vertical_bars = [
        _make_bar(DECISION_TS, "100000000", "100500000", "99500000", "100000000"),
        _make_bar(
            datetime(2024, 6, 1, 11, 0, tzinfo=UTC),
            "100000000", "100900000", "99600000", "100500000",
        ),
        _make_bar(
            datetime(2024, 6, 1, 12, 0, tzinfo=UTC),
            "100500000", "100900000", "99600000", "100700000",
        ),
        _make_bar(
            datetime(2024, 6, 1, 13, 0, tzinfo=UTC),
            "100700000", "100900000", "99600000", "100800000",
        ),
        _make_bar(
            datetime(2024, 6, 1, 14, 0, tzinfo=UTC),
            "100800000", "100900000", "99600000", "100900000",
        ),
    ]
    vertical = _label(vertical_bars, "s_vertical")
    assert (vertical.status, vertical.first_touch, vertical.outcome) == (
        "VALID", BarrierTouch.VERTICAL, 0,
    )


def test_label_02_gap_excluded_row_is_not_weighted_as_evidence() -> None:
    """LABEL-02-F1: concurrency weighting must not treat an excluded row as evidence."""
    excluded = _label(_gapped_bars(), "s_interior_gap")
    weights = compute_concurrency_weights([excluded])
    assert weights["s_interior_gap"] == Decimal("1.0")


def test_label_02_future_bar_cannot_fill_coverage_gap_before_deadline() -> None:
    bars = [
        _make_bar(DECISION_TS, "100000000", "100500000", "99500000", "100000000"),
        _make_bar(
            datetime(2024, 6, 1, 11, 0, tzinfo=UTC),
            "100000000", "100500000", "99500000", "100000000",
        ),
        # 12:00-15:00 are missing; this bar opens at the 15:00 deadline.
        _make_bar(
            datetime(2024, 6, 1, 15, 0, tzinfo=UTC),
            "100000000", "100500000", "99500000", "100000000",
        ),
    ]

    label = _label(bars, "s_future_bar_cannot_close_gap")

    assert label.status == "EXCLUDED"
    assert label.exclusion_reason == "INCOMPLETE_BARS_BEFORE_VERTICAL_BARRIER"
    assert label.outcome is None


def test_label_02_bar_crossing_vertical_deadline_is_excluded() -> None:
    bars = [
        _make_bar(DECISION_TS, "100000000", "100500000", "99500000", "100000000"),
        # Its upper touch may have occurred after the 11:30 vertical deadline.
        _make_bar(
            datetime(2024, 6, 1, 11, 0, tzinfo=UTC),
            "100000000", "102500000", "99500000", "102200000",
        ),
    ]
    config = _config(1).model_copy(
        update={"vertical_horizon": timedelta(hours=1, minutes=30)}
    )

    label = build_triple_barrier_label(
        sample_id="s_crossing_deadline",
        pair="btc_idr",
        decision_ts=DECISION_TS,
        decision_volatility=Decimal("0.01"),
        bars=bars,
        config=config,
    )

    assert label.status == "EXCLUDED"
    assert label.exclusion_reason == "BAR_CROSSES_VERTICAL_BARRIER"
    assert label.outcome is None


# Actor for every line this file contributes to review evidence:
# opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
