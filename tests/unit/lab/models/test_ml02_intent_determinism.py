"""Regression: ML-02 intent_id must be deterministic (sha256, not salted hash())."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from indodax_lab.models.execution_mapper import (
    CostAwareExecutionMapper,
    CostBasis,
    ForecastKind,
    ForecastPayload,
)


def _expected_intent_id(pair: str, value: float, qty: str, ts_str: str) -> str:
    payload = f"{pair}|{value!r}|{qty}|{ts_str}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]
    return f"intent_{pair}_{ts_str}_{digest}"


def test_ml02_intent_id_deterministic_sha256() -> None:
    cost_basis = CostBasis(estimated_round_trip_cost=0.0040, safety_margin=0.0010)
    mapper = CostAwareExecutionMapper(cost_basis=cost_basis)
    decision_ts = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    payload = ForecastPayload(
        kind=ForecastKind.NET_RETURN,
        value=0.005,
        pair="BTC_IDR",
        decision_ts=decision_ts,
        desired_qty=Decimal("0.05"),
    )
    d1 = mapper.evaluate_forecast(payload)
    d2 = mapper.evaluate_forecast(payload)
    assert d1.signal_intent is not None and d2.signal_intent is not None
    ts_str = decision_ts.strftime("%Y%m%d%H%M%S")
    expected = _expected_intent_id("BTC_IDR", 0.005, "0.05", ts_str)
    assert d1.signal_intent.intent_id == expected
    assert d2.signal_intent.intent_id == expected
