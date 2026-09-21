"""Normalize venue executions into the canonical double-entry ledger Fill contract."""

from __future__ import annotations

from decimal import Decimal

from indodax_lab.backtest.orders import Fill
from indodax_lab.execution.indodax_readonly import VenueFill


class VenueFillNormalizationError(ValueError):
    """A venue fill cannot be represented safely in the quote-valued ledger."""


def normalize_venue_fill(
    venue_fill: VenueFill,
    *,
    valuation_currency: str = "IDR",
    quote_notional_tolerance: Decimal = Decimal("0.00000001"),
) -> Fill:
    """Convert one verified venue execution into a canonical ledger fill.

    Runtime fee estimates are intentionally ignored. Real accounting uses venue
    evidence. Until multi-currency fee valuation exists, non-valuation-currency
    commissions fail closed rather than being silently converted.
    """

    valuation = valuation_currency.strip().lower()
    if not valuation:
        raise ValueError("VALUATION_CURRENCY_REQUIRED")
    tolerance = Decimal(str(quote_notional_tolerance))
    if not tolerance.is_finite() or tolerance < 0:
        raise ValueError("INVALID_QUOTE_NOTIONAL_TOLERANCE")

    pair_parts = venue_fill.pair.lower().split("_")
    if len(pair_parts) != 2 or pair_parts[1] != valuation:
        raise VenueFillNormalizationError(
            f"UNSUPPORTED_LEDGER_QUOTE:{venue_fill.pair}:{valuation}"
        )
    if venue_fill.commission_asset.lower() != valuation:
        raise VenueFillNormalizationError(
            "NON_QUOTE_COMMISSION_REQUIRES_EXPLICIT_VALUATION"
        )

    calculated_quote = venue_fill.qty * venue_fill.price
    if abs(calculated_quote - venue_fill.quote_qty) > tolerance:
        raise VenueFillNormalizationError(
            "VENUE_QUOTE_QTY_MISMATCH"
        )

    return Fill(
        fill_id=venue_fill.fill_id,
        order_id=venue_fill.order_id,
        event_id=f"venue-fill:{venue_fill.fill_id}",
        pair=venue_fill.pair,
        side=venue_fill.side,
        role=venue_fill.role,
        qty=venue_fill.qty,
        price=venue_fill.price,
        fees=venue_fill.commission,
        timestamp=venue_fill.timestamp,
        fee_components={"venue_commission": venue_fill.commission},
    )
