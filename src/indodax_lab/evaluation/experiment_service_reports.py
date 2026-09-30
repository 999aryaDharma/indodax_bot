"""Trade-report builder over persisted RW3-01 trial evidence (RW3-01-AC8).

Pure transform over the result-artifact document: fills, FIFO-matched
closed lifecycles, open remnants, explicit fee/win-rate markers. Missing
evidence never becomes a numeric success: win rate without closed trades
is UNAVAILABLE (never zero), fees without a bound schedule are UNKNOWN.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from indodax_lab.evaluation.experiment_service import (
    ClosedTrade,
    TradeFill,
    TradeReport,
)


def _dec(value: Any, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"TRADE_REPORT_NON_DECIMAL:{field}:{value!r}") from exc
    if not parsed.is_finite():
        raise ValueError(f"TRADE_REPORT_NON_FINITE:{field}")
    return parsed


def build_trade_report(experiment_id: str, doc: dict[str, Any]) -> TradeReport:
    fills: list[TradeFill] = []
    for child in doc.get("children", []):
        evidence = child.get("evidence", {}) if isinstance(child, dict) else {}
        for receipt in evidence.get("receipts", []) or []:
            executed = _dec(receipt.get("executed_qty", "0"), "executed_qty")
            if executed <= 0:
                continue
            fills.append(
                TradeFill(
                    fill_id=f"fill_{receipt.get('client_order_id', receipt.get('order_id'))}",
                    order_id=str(receipt.get("client_order_id", receipt.get("order_id"))),
                    pair=str(receipt.get("pair")),
                    side=str(receipt.get("side")),
                    qty=executed,
                    price=_dec(receipt.get("price", "0"), "price"),
                )
            )

    open_lots: list[dict[str, Decimal | str]] = []
    closed: list[ClosedTrade] = []
    for fill in fills:
        if "BUY" in fill.side.upper():
            open_lots.append(
                {"pair": fill.pair, "qty": fill.qty, "price": fill.price}
            )
            continue
        if "SELL" not in fill.side.upper():
            continue
        remaining = fill.qty
        while remaining > 0:
            lot = next(
                (lot for lot in open_lots if lot["pair"] == fill.pair and lot["qty"] > 0),  # type: ignore[operator]
                None,
            )
            if lot is None:
                break
            matched = min(remaining, lot["qty"])  # type: ignore[type-var]
            closed.append(
                ClosedTrade(
                    pair=fill.pair,
                    qty=matched,  # type: ignore[arg-type]
                    buy_price=lot["price"],  # type: ignore[arg-type]
                    sell_price=fill.price,
                    realized_pnl=(fill.price - lot["price"]) * matched,  # type: ignore[operator]
                )
            )
            lot["qty"] = lot["qty"] - matched  # type: ignore[operator]
            remaining = remaining - matched
    open_orders = tuple(
        {"pair": str(lot["pair"]), "open_qty": str(lot["qty"]), "price": str(lot["price"])}
        for lot in open_lots
        if lot["qty"] > 0  # type: ignore[operator]
    )

    if closed:
        wins = sum(1 for trade in closed if trade.realized_pnl > 0)
        win_rate: Decimal | None = Decimal(wins) / Decimal(len(closed))
        win_status = "AVAILABLE"
        win_reason = ""
    else:
        win_rate = None
        win_status = "UNAVAILABLE"
        win_reason = "WIN_RATE_UNAVAILABLE:no_closed_trades"
    return TradeReport(
        experiment_id=experiment_id,
        fills=tuple(fills),
        closed_trades=tuple(closed),
        open_orders=open_orders,
        fee_status="FEES_UNKNOWN",
        fee_reason="no fee schedule bound to trial",
        win_rate=win_rate,
        win_rate_status=win_status,
        win_rate_reason=win_reason,
    )
