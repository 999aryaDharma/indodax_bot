"""Balanced double-entry research ledger with exact cost basis (LED-01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.orders import Fill


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class AccountType(StrEnum):
    """Canonical double-entry accounts in research valuation currency."""

    CASH = "cash"
    ASSET = "asset"
    FEE = "fee"
    PNL = "pnl"
    CAPITAL = "capital"


class DuplicateFillError(ValueError):
    """Raised when a fill has already been processed by the ledger."""


class InsufficientQuantityError(ValueError):
    """Raised when selling more base quantity than held."""


class Posting(BaseModel):
    """A signed valued posting in quote valuation currency."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    account: AccountType | str
    amount: Decimal
    currency: str = "IDR"


class Position(BaseModel):
    """Position inventory tracking for a single trading pair."""

    model_config = ConfigDict(extra="forbid")

    pair: str
    base_qty: Decimal = Field(default=Decimal("0"))
    cost_basis: Decimal = Field(default=Decimal("0"))

    @property
    def average_entry_price(self) -> Decimal:
        if self.base_qty > Decimal("0"):
            return self.cost_basis / self.base_qty
        return Decimal("0")


class LedgerTransaction(BaseModel):
    """A collection of balanced postings produced by an event or fill."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: str
    fill_id: str | None
    timestamp: datetime
    postings: tuple[Posting, ...]
    base_qty_delta: Decimal = Decimal("0")
    pair: str | None = None

    @property
    def is_balanced(self) -> bool:
        """Double-entry invariant: sum of valued postings equals zero."""
        return sum(p.amount for p in self.postings) == Decimal("0")


class ResearchLedger:
    """Balanced research journal for cash, positions, exact costs and PnL."""

    def __init__(
        self,
        initial_cash: Decimal = Decimal("0"),
        valuation_currency: str = "IDR",
        init_timestamp: datetime | None = None,
    ) -> None:
        self.valuation_currency = valuation_currency
        self._cash = Decimal(str(initial_cash))
        self.transactions: list[LedgerTransaction] = []
        self._positions: dict[str, Position] = {}
        self._processed_fill_ids: set[str] = set()
        self._total_fees_paid = Decimal("0")
        self._total_net_pnl = Decimal("0")
        self._total_realized_gross_pnl = Decimal("0")

        if self._cash > Decimal("0"):
            ts = init_timestamp or datetime.now(UTC)
            p_cash = Posting(
                account=AccountType.CASH,
                amount=self._cash,
                currency=self.valuation_currency,
            )
            p_cap = Posting(
                account=AccountType.CAPITAL,
                amount=-self._cash,
                currency=self.valuation_currency,
            )
            init_tx = LedgerTransaction(
                transaction_id="tx-init",
                fill_id=None,
                timestamp=ts,
                postings=(p_cash, p_cap),
                base_qty_delta=Decimal("0"),
                pair=None,
            )
            self.transactions.append(init_tx)

    @property
    def cash(self) -> Decimal:
        """Current quote-currency cash balance."""
        return self._cash

    @property
    def total_fees_paid(self) -> Decimal:
        """Total cumulative fees paid across all fills."""
        return self._total_fees_paid

    @property
    def total_net_pnl(self) -> Decimal:
        """Total cumulative realized net PnL (gross trading profit minus all fees paid)."""
        return self._total_realized_gross_pnl - self._total_fees_paid

    @property
    def total_realized_gross_pnl(self) -> Decimal:
        """Total cumulative realized gross PnL (gross sell proceeds minus gross buy basis)."""
        return self._total_realized_gross_pnl

    @property
    def positions(self) -> Mapping[str, Position]:
        """Read-only view of open and closed positions."""
        return self._positions

    def get_position(self, pair: str) -> Position:
        """Get or initialize position for a pair."""
        if pair not in self._positions:
            self._positions[pair] = Position(pair=pair)
        return self._positions[pair]

    def equity(self, mark_prices: Mapping[str, Decimal]) -> Decimal:
        """Calculate total portfolio equity: cash + marked open positions.

        Per ADR-002: Cash equity already reflects paid fees. Equity = cash + marked assets;
        subtracting fee expense again double counts.
        """
        asset_value = Decimal("0")
        for pair, pos in self._positions.items():
            if pos.base_qty > Decimal("0"):
                if pair not in mark_prices:
                    raise ValueError(f"MISSING_MARK_PRICE:{pair}")
                mark_price = Decimal(str(mark_prices[pair]))
                asset_value += pos.base_qty * mark_price
        return self._cash + asset_value

    def process_fill(self, fill: Fill) -> LedgerTransaction:
        """Process an executed order fill and post balanced double-entry entries."""
        # LED-01-AC3: Duplicate fill ID tidak menggandakan posting
        if fill.fill_id in self._processed_fill_ids:
            raise DuplicateFillError(f"DUPLICATE_FILL_ID:{fill.fill_id}")

        pos = self.get_position(fill.pair)
        gross = fill.gross
        fee = fill.fees

        if fill.side == OrderSide.BUY:
            # buy_cash_debit = gross_buy_notional + quote-denominated costs
            cash_debit = gross + fee
            self._cash -= cash_debit

            pos.base_qty += fill.qty
            pos.cost_basis += gross

            self._total_fees_paid += fee

            p_cash = Posting(
                account=AccountType.CASH,
                amount=-cash_debit,
                currency=self.valuation_currency,
            )
            p_asset = Posting(
                account=AccountType.ASSET,
                amount=gross,
                currency=self.valuation_currency,
            )
            p_fee = Posting(
                account=AccountType.FEE,
                amount=fee,
                currency=self.valuation_currency,
            )
            postings = (p_cash, p_asset, p_fee)
            qty_delta = fill.qty

        elif fill.side == OrderSide.SELL:
            # LED-01-AC1: Buy partial sell final sell menjaga quantity nonnegative
            if fill.qty > pos.base_qty:
                raise InsufficientQuantityError(
                    f"INSUFFICIENT_BASE_QUANTITY: attempted to sell {fill.qty} "
                    f"but held {pos.base_qty} for {fill.pair}"
                )

            # net_sell_credit = gross_sell_notional - quote-denominated costs
            net_credit = gross - fee
            self._cash += net_credit

            # Exact cost basis allocation
            if fill.qty == pos.base_qty:
                allocated_basis = pos.cost_basis
                pos.base_qty = Decimal("0")
                pos.cost_basis = Decimal("0")
            else:
                allocated_basis = (fill.qty / pos.base_qty) * pos.cost_basis
                pos.base_qty -= fill.qty
                pos.cost_basis -= allocated_basis

            gross_pnl = gross - allocated_basis
            # net_pnl = net_sell_credit - allocated_basis = gross_pnl - fee
            net_pnl = net_credit - allocated_basis

            self._total_fees_paid += fee
            self._total_net_pnl += net_pnl
            self._total_realized_gross_pnl += gross_pnl

            p_cash = Posting(
                account=AccountType.CASH,
                amount=net_credit,
                currency=self.valuation_currency,
            )
            p_asset = Posting(
                account=AccountType.ASSET,
                amount=-allocated_basis,
                currency=self.valuation_currency,
            )
            p_fee = Posting(
                account=AccountType.FEE,
                amount=fee,
                currency=self.valuation_currency,
            )
            p_pnl = Posting(
                account=AccountType.PNL,
                amount=-gross_pnl,
                currency=self.valuation_currency,
            )
            postings = (p_cash, p_asset, p_fee, p_pnl)
            qty_delta = -fill.qty

        else:
            raise ValueError(f"UNSUPPORTED_ORDER_SIDE:{fill.side}")

        tx = LedgerTransaction(
            transaction_id=f"tx-{fill.fill_id}",
            fill_id=fill.fill_id,
            timestamp=fill.timestamp,
            postings=postings,
            base_qty_delta=qty_delta,
            pair=fill.pair,
        )

        # Invariant check: transaction must balance
        if not tx.is_balanced:
            raise RuntimeError(f"UNBALANCED_TRANSACTION:{tx.transaction_id}")

        self.transactions.append(tx)
        self._processed_fill_ids.add(fill.fill_id)
        return tx
