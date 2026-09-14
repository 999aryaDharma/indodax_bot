import pytest

from signal_observer import resolve_barriers


def test_same_bar_stop_and_target_is_stop_first() -> None:
    result = resolve_barriers(
        bar_high=112, bar_low=88, stop_loss=90, take_profit=110
    )

    assert result is not None
    assert result.reason == "SL"
    assert result.fill_price == 90


@pytest.mark.parametrize(
    ("bar_high", "bar_low", "expected_reason", "expected_fill"),
    [
        (112, 91, "TP", 110),
        (109, 88, "SL", 90),
    ],
)
def test_single_barrier_touch_resolves_at_the_barrier(
    bar_high: float,
    bar_low: float,
    expected_reason: str,
    expected_fill: float,
) -> None:
    result = resolve_barriers(
        bar_high=bar_high,
        bar_low=bar_low,
        stop_loss=90,
        take_profit=110,
    )

    assert result is not None
    assert result.reason == expected_reason
    assert result.fill_price == expected_fill


def test_no_barrier_touch_has_no_resolution() -> None:
    result = resolve_barriers(
        bar_high=109,
        bar_low=91,
        stop_loss=90,
        take_profit=110,
    )

    assert result is None
