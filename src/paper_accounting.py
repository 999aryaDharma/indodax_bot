from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BuyFill:
    cash_debit: Decimal
    fee: Decimal
    notional: Decimal
    base_qty: Decimal


@dataclass(frozen=True)
class SellFill:
    notional: Decimal
    fee: Decimal
    net_credit: Decimal


def _require_positive_finite(value: Decimal, name: str) -> None:
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{name} must be positive and finite")


def _require_fee_rate(value: Decimal) -> None:
    if not value.is_finite() or value < 0 or value >= 1:
        raise ValueError("fee_rate must be finite and in the range [0, 1)")


def account_buy(cash_budget: Decimal, price: Decimal, fee_rate: Decimal) -> BuyFill:
    _require_positive_finite(cash_budget, "cash_budget")
    _require_positive_finite(price, "price")
    _require_fee_rate(fee_rate)
    fee = cash_budget * fee_rate
    notional = cash_budget - fee
    return BuyFill(cash_budget, fee, notional, notional / price)


def account_sell(base_qty: Decimal, price: Decimal, fee_rate: Decimal) -> SellFill:
    _require_positive_finite(base_qty, "base_qty")
    _require_positive_finite(price, "price")
    _require_fee_rate(fee_rate)
    notional = base_qty * price
    fee = notional * fee_rate
    return SellFill(notional, fee, notional - fee)


def realized_pnl(buy: BuyFill, sell: SellFill) -> Decimal:
    return sell.net_credit - buy.cash_debit
