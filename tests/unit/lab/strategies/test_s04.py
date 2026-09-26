import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd

from indodax_lab.strategies.base import create_decision_frame
from indodax_lab.strategies.s04 import load_s04_specification, s04_decide

AS_OF = datetime(2025, 1, 1, tzinfo=UTC)


def _frame(**overrides):
    row = {
        "pair": "btc_idr",
        "decision_ts": AS_OF,
        "row_ready_at": AS_OF,
        "eligible": True,
        "close": 100_000_000.0,
        "book_imbalance_l5": 0.2,
        "trade_imbalance_10s": 0.15,
        "book_event_ts": AS_OF - timedelta(seconds=1),
        "book_available_at": AS_OF - timedelta(milliseconds=500),
        "book_session_id": "session-1",
        "book_sequence_contiguous": True,
    } | overrides
    return create_decision_frame(
        pd.DataFrame([row]),
        AS_OF,
        feature_set_id="lob_v1",
        feature_set_version="1.0.0",
    )


def test_s04_valid_causal_order_flow_emits_candidate_sized_intent():
    intent, = s04_decide(_frame(), load_s04_specification())
    assert intent.side.value == "buy"
    assert intent.desired_qty * intent.limit_price == Decimal("10000.0000000000")
    assert intent.stop_loss == Decimal("98000000.000000000000")
    assert intent.strategy_id == "S04"


def test_s04_imbalance_thresholds_are_inclusive():
    assert len(s04_decide(_frame(book_imbalance_l5=0.10, trade_imbalance_10s=0.10))) == 1
    assert s04_decide(_frame(book_imbalance_l5=0.0999)) == []
    assert s04_decide(_frame(trade_imbalance_10s=0.0999)) == []


def test_s04_missing_unknown_or_invalid_session_sequence_abstains():
    assert s04_decide(_frame(book_sequence_contiguous=None)) == []
    assert s04_decide(_frame(book_sequence_contiguous=False)) == []
    assert s04_decide(_frame(book_session_id="  ")) == []
    assert s04_decide(_frame(book_imbalance_l5=math.nan)) == []


def test_s04_stale_or_future_book_timestamps_abstain():
    assert len(s04_decide(_frame(book_event_ts=AS_OF - timedelta(seconds=5)))) == 1
    assert s04_decide(_frame(book_event_ts=AS_OF - timedelta(milliseconds=5001))) == []
    assert s04_decide(_frame(book_event_ts=AS_OF + timedelta(milliseconds=1))) == []
    assert s04_decide(_frame(book_available_at=AS_OF + timedelta(milliseconds=1))) == []
    assert s04_decide(
        _frame(book_available_at=AS_OF - timedelta(seconds=2))
    ) == []


def test_s04_rejects_wrong_version_and_invalid_causal_timestamps():
    frame = create_decision_frame(
        pd.DataFrame([{
            "pair": "btc_idr", "decision_ts": AS_OF, "row_ready_at": AS_OF,
            "eligible": True, "close": 100_000_000, "book_imbalance_l5": 0.2,
            "trade_imbalance_10s": 0.2, "book_event_ts": "2025-01-01T00:00:00",
            "book_available_at": AS_OF, "book_session_id": "session-1",
            "book_sequence_contiguous": True,
        }]), AS_OF, feature_set_id="lob_v1", feature_set_version="1.0.0",
    )
    assert s04_decide(frame) == []
    wrong_version = create_decision_frame(
        _frame().features, AS_OF, feature_set_id="lob_v1", feature_set_version="2.0.0"
    )
    assert s04_decide(wrong_version) == []
