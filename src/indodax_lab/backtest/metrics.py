"""Net-cost risk, performance reporting, and capacity metrics (SIM-04)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
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
    breakeven_count: int = 0
    win_rate: Decimal | None = None
    profit_factor: ProfitFactorResult
    max_drawdown_amount: Decimal | None
    max_drawdown_pct: Decimal | None
    drawdown_status: str = "MISSING_EQUITY_CURVE"
    stress_1_5x: CostStressMetrics
    stress_2_0x: CostStressMetrics
    by_year: dict[str, dict[str, Any]]
    by_asset: dict[str, dict[str, Any]]
    by_regime: dict[str, dict[str, Any]] | None = None
    by_tier: dict[str, dict[str, Any]] | None = None
    regime_status: str = "MISSING_CLASSIFICATION"
    tier_status: str = "MISSING_CLASSIFICATION"
    unclassified_regime_event_count: int = 0
    unclassified_tier_event_count: int = 0
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
    transaction_classifications: Mapping[str, Mapping[str, str]] | None = None,
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
    breakeven_count = 0
    trade_count = 0

    by_year: dict[str, dict[str, Any]] = {}
    by_asset: dict[str, dict[str, Any]] = {}
    by_regime: dict[str, dict[str, Any]] = {}
    by_tier: dict[str, dict[str, Any]] = {}
    dimension_groups = {"regime": by_regime, "tier": by_tier}
    relevant_transactions = {"regime": 0, "tier": 0}
    classified_transactions = {"regime": 0, "tier": 0}

    for tx in ledger.transactions:
        tx_year = str(tx.timestamp.year)
        if tx_year not in by_year:
            by_year[tx_year] = {
                "gross_pnl": Decimal("0"),
                "fees": Decimal("0"),
                "net_pnl": Decimal("0"),
                "trade_count": 0,
                "breakeven_count": 0,
            }

        tx_fees = Decimal("0")
        tx_gross_pnl = Decimal("0")
        tx_trade_count = 0
        for p in tx.postings:
            if p.account == AccountType.FEE:
                by_year[tx_year]["fees"] += p.amount
                tx_fees += p.amount

            if p.account == AccountType.PNL:
                # Credit in double-entry PNL account is negative amount; profit is positive
                trade_pnl = -p.amount
                tx_gross_pnl += trade_pnl
                tx_trade_count += 1
                trade_count += 1
                by_year[tx_year]["gross_pnl"] += trade_pnl
                by_year[tx_year]["trade_count"] += 1

                # Asset tracking
                pair = tx.pair or "UNKNOWN"
                if pair not in by_asset:
                    by_asset[pair] = {
                        "gross_pnl": Decimal("0"),
                        "fees": Decimal("0"),
                        "net_pnl": Decimal("0"),
                        "trade_count": 0,
                        "breakeven_count": 0,
                    }
                by_asset[pair]["gross_pnl"] += trade_pnl
                by_asset[pair]["trade_count"] += 1

                if trade_pnl > Decimal("0"):
                    gross_profit += trade_pnl
                    win_count += 1
                elif trade_pnl < Decimal("0"):
                    gross_loss += abs(trade_pnl)
                    loss_count += 1
                else:
                    breakeven_count += 1
                    by_year[tx_year]["breakeven_count"] += 1
                    by_asset[pair]["breakeven_count"] += 1

        pair = tx.pair or "UNKNOWN"
        if tx_fees and pair not in by_asset:
            by_asset[pair] = {
                "gross_pnl": Decimal("0"), "fees": Decimal("0"),
                "net_pnl": Decimal("0"), "trade_count": 0, "breakeven_count": 0,
            }
        if tx_fees:
            by_asset[pair]["fees"] += tx_fees

        if tx_fees or tx_trade_count:
            context = (
                transaction_classifications.get(tx.transaction_id, {})
                if transaction_classifications
                else {}
            )
            if not isinstance(context, Mapping):
                context = {}
            for dimension, groups in dimension_groups.items():
                relevant_transactions[dimension] += 1
                category = context.get(dimension)
                if not isinstance(category, str) or not category.strip():
                    continue
                category = category.strip()
                classified_transactions[dimension] += 1
                group = groups.setdefault(category, {
                    "gross_pnl": Decimal("0"), "fees": Decimal("0"),
                    "net_pnl": Decimal("0"), "trade_count": 0, "breakeven_count": 0,
                })
                group["gross_pnl"] += tx_gross_pnl
                group["fees"] += tx_fees
                group["trade_count"] += tx_trade_count
                group["breakeven_count"] += sum(
                    1 for p in tx.postings if p.account == AccountType.PNL and p.amount == 0
                )

    for y in by_year:
        by_year[y]["net_pnl"] = by_year[y]["gross_pnl"] - by_year[y]["fees"]
    for group in (*by_asset.values(), *by_regime.values(), *by_tier.values()):
        group["net_pnl"] = group["gross_pnl"] - group["fees"]

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
    max_dd_amount: Decimal | None = None
    max_dd_pct: Decimal | None = None
    drawdown_status = "MISSING_EQUITY_CURVE"

    if equity_curve:
        max_dd_amount = Decimal("0")
        max_dd_pct = Decimal("0")
        drawdown_status = "AVAILABLE"
        peak = equity_curve[0][1]
        prior_ts: datetime | None = None
        for timestamp, eq in equity_curve:
            if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
                raise ValueError("EQUITY_CURVE_UTC_TIMESTAMPS_REQUIRED")
            if prior_ts is not None and timestamp <= prior_ts:
                raise ValueError("EQUITY_CURVE_MUST_BE_STRICTLY_CHRONOLOGICAL")
            if not eq.is_finite():
                raise ValueError("EQUITY_CURVE_FINITE_VALUES_REQUIRED")
            prior_ts = timestamp
            if eq > peak:
                peak = eq
            dd = peak - eq
            if dd > max_dd_amount:
                max_dd_amount = dd
            if peak > Decimal("0"):
                dd_pct = dd / peak
                if max_dd_pct is None or dd_pct > max_dd_pct:
                    max_dd_pct = dd_pct
                if drawdown_status == "NONPOSITIVE_PEAK":
                    drawdown_status = "AVAILABLE"
            elif max_dd_pct is not None:
                max_dd_pct = None
                drawdown_status = "NONPOSITIVE_PEAK"

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
    if not spread_data:
        spread_cost = None
        spread_status = "MISSING_SPREAD"
        capacity_notes.append(
            "MISSING_SPREAD: Cost and capacity estimate requires empirical spread data"
        )
    else:
        try:
            spread_values = [Decimal(str(value)) for value in spread_data.values()]
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("INVALID_SPREAD_DATA") from exc
        if any(not value.is_finite() or value < 0 for value in spread_values):
            raise ValueError("INVALID_SPREAD_DATA")
        spread_status = "AVAILABLE"
        spread_cost = sum(spread_values, Decimal("0"))

    rejected_count = len(rejected_orders) if rejected_orders else 0
    if rejected_count > 0:
        capacity_notes.append(
            f"REJECTED_ORDERS: {rejected_count} orders rejected by risk or execution barriers"
        )

    def classification_status(dimension: str) -> str:
        total = relevant_transactions[dimension]
        known = classified_transactions[dimension]
        if total == 0 or known == 0:
            return "MISSING_CLASSIFICATION"
        return "AVAILABLE" if known == total else "PARTIAL_CLASSIFICATION"

    regime_status = classification_status("regime")
    tier_status = classification_status("tier")

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
        breakeven_count=breakeven_count,
        win_rate=win_rate,
        profit_factor=profit_factor,
        max_drawdown_amount=max_dd_amount,
        max_drawdown_pct=max_dd_pct,
        drawdown_status=drawdown_status,
        stress_1_5x=stress_1_5x,
        stress_2_0x=stress_2_0x,
        by_year=by_year,
        by_asset=by_asset,
        by_regime=by_regime or None,
        by_tier=by_tier or None,
        regime_status=regime_status,
        tier_status=tier_status,
        unclassified_regime_event_count=(
            relevant_transactions["regime"] - classified_transactions["regime"]
        ),
        unclassified_tier_event_count=(
            relevant_transactions["tier"] - classified_transactions["tier"]
        ),
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
