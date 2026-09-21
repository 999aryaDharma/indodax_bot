"""Tests for verified venue-fill normalization into ledger accounting."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.execution.fill_normalizer import (
    VenueFillNormalizationError,
    normalize_venue_fill,
)
from indodax_lab.execution.indodax_readonly import VenueFill


NOW = datetime(2026, 9, 21, 8, 0, tzinfo=UTC)


def _fill(**overrides):
    values = {
        "fill_id": "trade-1",
        "order_id": "order-1",
        "client_order_id": "bot-1",
        "pair": "btc_idr",
        "side": OrderSide.BUY,
        "role": OrderRole.TAKER,
        "qty": Decimal("0.00005"),
        "quote_qty": Decimal("50000"),
        "price": Decimal("1000000000"),
        "commission": Decimal("150"),
        "commission_asset": "idr",
        "timestamp": NOW,
    }
    values.update(overrides)
    return VenueFill(**values)


def test_real_venue_commission_becomes_ledger_fee_without_recalculation():
    normalized = normalize_venue_fill(_fill())

    assert normalized.fill_id == "trade-1"
    assert normalized.event_id == "venue-fill:trade-1"
    assert normalized.fees == Decimal("150")
    assert normalized.fee_components == {"venue_commission": Decimal("150")}
    assert normalized.gross == Decimal("50000")


def test_non_quote_commission_fails_closed_until_explicit_valuation_exists():
    with pytest.raises(
        VenueFillNormalizationError,
        match="NON_QUOTE_COMMISSION_REQUIRES_EXPLICIT_VALUATION",
    ):
        normalize_venue_fill(
            _fill(
                commission=Decimal("0.00000015"),
                commission_asset="btc",
            )
        )


def test_inconsistent_venue_quote_notional_fails_closed():
    with pytest.raises(
        VenueFillNormalizationError,
        match="VENUE_QUOTE_QTY_MISMATCH",
    ):
        normalize_venue_fill(_fill(quote_qty=Decimal("49999")))
