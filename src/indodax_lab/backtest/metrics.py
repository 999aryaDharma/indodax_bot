"""Net-cost risk, performance reporting, and capacity metrics (SIM-04)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.backtest.ledger import AccountType, LedgerTransaction, ResearchLedger


class ProfitFactorResult(BaseModel):
    """Profit factor outcome with explicit failure reason for undefined cases."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Decimal | None = None
    defined: bool
    reason: str | None = None


class CostStressMetrics(BaseModel):
    """Performance outcome under stressed execution cost schedules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    multiplier: Decimal
    stressed_fees: Decimal
    stressed_net_pnl: Decimal


class PerformanceMetrics(BaseModel):
    """Comprehensive performance and capacity metrics derived from ledger postings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    initial_cash: Decimal
    ending_cash: Decimal
    ending_equity: Decimal
    total_net_pnl: Decimal
    total_gross_pnl: Decimal
    total_fees_paid: Decimal
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: Decimal | None = None
    profit_factor: ProfitFactorResult
    max_drawdown_amount: Decimal
    max_drawdown_pct: Decimal
    stress_1_5x: CostStressMetrics
    stress_2_0x: CostStressMetrics
    by_year: dict[str, dict[str, Any]]
    by_asset: dict[str, dict[str, Any]]
    spread_cost: Decimal | None = None
    spread_status: str
    rejected_order_count: int
    capacity_notes: list[str] = Field(default_factory=list)


def calculate_equity(cash: Decimal, marked_asset_value: Decimal) -> Decimal:
    """Calculate portfolio equity without double-subtracting transaction fees.

    Because cash postings in the research ledger already reflect all fee debits,
    equity is simply cash plus current marked asset valuation.
    """
    return cash + marked_asset_value


def compute_performance_metrics(
    ledger: ResearchLedger,
    equity_curve: Sequence[tuple[datetime, Decimal]] | None = None,
    rejected_orders: Sequence[Any] | None = None,
    spread_data: Mapping[str, Decimal] | None = None,
    mark_prices: Mapping[str, Decimal] | None = None,
) -> PerformanceMetrics:
    """Compute performance, risk, and cost metrics directly from the research ledger."""
    initial_cash = ledger.initial_cash
    ending_cash = ledger.cash
    ending_equity = ledger.equity(mark_prices=mark_prices)

    total_gross_pnl = ledger.total_realized_gross_pnl
    total_fees_paid = ledger.total_fees_paid
    total_net_pnl = ledger.total_net_pnl

    # Analyze trades from transactions containing PnL postings
    gross_profit = Decimal("0")
    gross_loss = Decimal("0")
    win_count = 0
    loss_count = 0

    by_year: dict[str, dict[str, Any]] = {}
    by_asset: dict[str, dict[str, Any]] = {}

    for tx in ledger.transactions:
        tx_year = str(tx.timestamp.year)
        if tx_year not in by_year:
            by_year[tx_year] = {
                "gross_pnl": Decimal("0"),
                "fees": Decimal("0"),
                "net_pnl": Decimal("0"),
                "trade_count": 0,
            }

        # Check for fee postings in this tx
        for p in tx.postings:
            if p.account == AccountType.FEE:
                by_year[tx_year]["fees"] += p.amount

            if p.account == AccountType.PNL:
                # Credit in double-entry PNL account is negative amount; profit is positive
                trade_pnl = -p.amount
                by_year[tx_year]["gross_pnl"] += trade_pnl
                by_year[tx_year]["trade_count"] += 1

                # Asset tracking
                pair = tx.pair or "UNKNOWN"
                if pair not in by_asset:
                    by_asset[pair] = {
                        "gross_pnl": Decimal("0"),
                        "trade_count": 0,
                    }
                by_asset[pair]["gross_pnl"] += trade_pnl
                by_asset[pair]["trade_count"] += 1

                if trade_pnl > Decimal("0"):
                    gross_profit += trade_pnl
                    win_count += 1
                elif trade_pnl < Decimal("0"):
                    gross_loss += abs(trade_pnl)
                    loss_count += 1

    for y in by_year:
        by_year[y]["net_pnl"] = by_year[y]["gross_pnl"] - by_year[y]["fees"]

    trade_count = win_count + loss_count
    win_rate = (
        Decimal(win_count) / Decimal(trade_count) if trade_count > 0 else None
    )

    # Compute profit factor
    if trade_count == 0:
        profit_factor = ProfitFactorResult(
            value=None, defined=False, reason="NO_TRADES"
        )
    elif gross_loss == Decimal("0"):
        if gross_profit > Decimal("0"):
            profit_factor = ProfitFactorResult(
                value=None, defined=False, reason="ZERO_LOSS"
            )
        else:
            profit_factor = ProfitFactorResult(
                value=None, defined=False, reason="NO_PROFIT_OR_LOSS"
            )
    else:
        profit_factor = ProfitFactorResult(
            value=gross_profit / gross_loss, defined=True, reason=None
        )

    # Drawdown calculation
    max_dd_amount = Decimal("0")
    max_dd_pct = Decimal("0")

    if equity_curve and len(equity_curve) > 0:
        peak = equity_curve[0][1]
        for _, eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = peak - eq
            if dd > max_dd_amount:
                max_dd_amount = dd
            if peak > Decimal("0"):
                dd_pct = dd / peak
                if dd_pct > max_dd_pct:
                    max_dd_pct = dd_pct

    # Cost stress tests (1.5x and 2.0x)
    stress_1_5_fees = total_fees_paid * Decimal("1.5")
    stress_1_5_net = total_gross_pnl - stress_1_5_fees
    stress_1_5x = CostStressMetrics(
        multiplier=Decimal("1.5"),
        stressed_fees=stress_1_5_fees,
        stressed_net_pnl=stress_1_5_net,
    )

    stress_2_0_fees = total_fees_paid * Decimal("2.0")
    stress_2_0_net = total_gross_pnl - stress_2_0_fees
    stress_2_0x = CostStressMetrics(
        multiplier=Decimal("2.0"),
        stressed_fees=stress_2_0_fees,
        stressed_net_pnl=stress_2_0_net,
    )

    # Capacity and spread handling (SIM-04-FR3)
    capacity_notes: list[str] = []
    if spread_data is None:
        spread_cost = None
        spread_status = "MISSING_SPREAD"
        capacity_notes.append(
            "MISSING_SPREAD: Cost and capacity estimate requires empirical spread data"
        )
    else:
        spread_status = "AVAILABLE"
        spread_cost = sum(spread_data.values(), Decimal("0"))

    rejected_count = len(rejected_orders) if rejected_orders else 0
    if rejected_count > 0:
        capacity_notes.append(
            f"REJECTED_ORDERS: {rejected_count} orders rejected by risk or execution barriers"
        )

    return PerformanceMetrics(
        initial_cash=initial_cash,
        ending_cash=ending_cash,
        ending_equity=ending_equity,
        total_net_pnl=total_net_pnl,
        total_gross_pnl=total_gross_pnl,
        total_fees_paid=total_fees_paid,
        trade_count=trade_count,
        win_count=win_count,
        loss_count=loss_count,
        win_rate=win_rate,
        profit_factor=profit_factor,
        max_drawdown_amount=max_dd_amount,
        max_drawdown_pct=max_dd_pct,
        stress_1_5x=stress_1_5x,
        stress_2_0x=stress_2_0x,
        by_year=by_year,
        by_asset=by_asset,
        spread_cost=spread_cost,
        spread_status=spread_status,
        rejected_order_count=rejected_count,
        capacity_notes=capacity_notes,
    )


__all__ = [
    "CostStressMetrics",
    "PerformanceMetrics",
    "ProfitFactorResult",
    "calculate_equity",
    "compute_performance_metrics",
]
