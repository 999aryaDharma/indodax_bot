from datetime import datetime, timezone

import pandas as pd
import pytest

from indodax_lab.strategies.multitimeframe import align_closed_context


def test_context_must_be_available_at_signal_time():
    signals = pd.DataFrame({"pair": ["btc_idr"], "decision_ts": [datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc)]})
    context = pd.DataFrame({
        "pair": ["btc_idr"],
        "decision_ts": [datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)],
        "row_ready_at": [datetime(2024, 1, 1, 1, 5, tzinfo=timezone.utc)],
        "regime": ["up"],
    })
    with pytest.raises(ValueError, match="MTF_FUTURE_CONTEXT_FORBIDDEN"):
        align_closed_context(signals, context)


def test_uses_latest_closed_context_without_forward_fill():
    signals = pd.DataFrame({"pair": ["btc_idr"], "decision_ts": [datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc)]})
    context = pd.DataFrame({
        "pair": ["btc_idr", "btc_idr"],
        "decision_ts": [datetime(2023, 12, 31, 23, 0, tzinfo=timezone.utc), datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)],
        "row_ready_at": [datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, 0, 5, tzinfo=timezone.utc)],
        "regime": ["flat", "up"],
    })
    result = align_closed_context(signals, context)
    assert result.loc[0, "regime"] == "up"
