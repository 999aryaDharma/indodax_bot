"""Balanced double-entry research ledger with exact cost basis (LED-01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from threading import RLock
from typing import Any, Mapping

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
        self._initial_cash = Decimal(str(initial_cash))
        if not self._initial_cash.is_finite() or self._initial_cash < 0:
            raise ValueError("INVALID_INITIAL_CASH")
        if init_timestamp is not None:
            _ensure_utc(init_timestamp, "init_timestamp")
        # In-process synchronization only; not a cross-process allocation lock.
        self.allocation_lock = RLock()
        self._reservations: dict[str, Decimal] = {}
        self._cash = self._initial_cash
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
    def initial_cash(self) -> Decimal:
        """Initial deposited quote-currency cash."""
        return self._initial_cash

    @property
    def reservations(self) -> Mapping[str, Decimal]:
        with self.allocation_lock:
            return dict(self._reservations)

    @property
    def available_cash(self) -> Decimal:
        with self.allocation_lock:
            return self._cash - sum(self._reservations.values(), Decimal("0"))

    def reserve_cash(self, intent_id: str, amount: Decimal) -> None:
        with self.allocation_lock:
            if not amount.is_finite() or amount <= 0:
                raise ValueError("INVALID_RESERVATION")
            if intent_id in self._reservations:
                raise ValueError("DUPLICATE_RESERVATION")
            if amount > self.available_cash:
                raise ValueError("INSUFFICIENT_UNRESERVED_CASH")
            self._reservations[intent_id] = amount

    def release_reservation(self, intent_id: str) -> Decimal:
        """Release once; repeat cancellation is harmless."""
        with self.allocation_lock:
            return self._reservations.pop(intent_id, Decimal("0"))

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
        """Get or initialize position; reacquire after a successfully posted fill.

        Successful fills replace the position with a validated staged value.
        A previously returned object does not track subsequent transactions.
        """
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
                if not mark_price.is_finite() or mark_price <= 0:
                    raise ValueError(f"INVALID_MARK_PRICE:{pair}")
                asset_value += pos.base_qty * mark_price
        return self._cash + asset_value

    def process_fill(self, fill: Fill) -> LedgerTransaction:
        """Process an executed order fill and post balanced double-entry entries."""
        with self.allocation_lock:
            return self._process_fill_locked(fill)

    def _process_fill_locked(self, fill: Fill) -> LedgerTransaction:
        # model_copy/model_construct can bypass Pydantic field validation.
        fill = Fill.model_validate(fill.model_dump())
        # LED-01-AC3: Duplicate fill ID tidak menggandakan posting
        if fill.fill_id in self._processed_fill_ids:
            raise DuplicateFillError(f"DUPLICATE_FILL_ID:{fill.fill_id}")

        # Stage all arithmetic and model validation before changing live state.
        current = self._positions.get(fill.pair)
        pos = current.model_copy(deep=True) if current else Position(pair=fill.pair)
        next_cash = self._cash
        next_fees = self._total_fees_paid
        next_net_pnl = self._total_net_pnl
        next_gross_pnl = self._total_realized_gross_pnl
        gross = fill.gross
        fee = fill.fees

        if fill.side == OrderSide.BUY:
            # buy_cash_debit = gross_buy_notional + quote-denominated costs
            cash_debit = gross + fee
            if cash_debit > self.available_cash:
                raise ValueError("INSUFFICIENT_CASH_INCLUDING_FEES")
            next_cash -= cash_debit

            pos.base_qty += fill.qty
            pos.cost_basis += gross

            next_fees += fee

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
            next_cash += net_credit
            if next_cash < 0:
                raise ValueError("INSUFFICIENT_CASH_INCLUDING_FEES")

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

            next_fees += fee
            next_net_pnl += net_pnl
            next_gross_pnl += gross_pnl

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

        self._cash = next_cash
        self._positions[fill.pair] = pos
        self._total_fees_paid = next_fees
        self._total_net_pnl = next_net_pnl
        self._total_realized_gross_pnl = next_gross_pnl
        self.transactions.append(tx)
        self._processed_fill_ids.add(fill.fill_id)
        return tx

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete ledger state for durable checkpointing."""
        with self.allocation_lock:
            return {
                "schema_version": 1,
                "valuation_currency": self.valuation_currency,
                "initial_cash": str(self._initial_cash),
                "cash": str(self._cash),
                "reservations": {key: str(value) for key, value in self._reservations.items()},
                "transactions": [
                    tx.model_dump(mode="json") for tx in self.transactions
                ],
                "positions": {
                    pair: position.model_dump(mode="json")
                    for pair, position in self._positions.items()
                },
                "processed_fill_ids": sorted(self._processed_fill_ids),
                "total_fees_paid": str(self._total_fees_paid),
                "total_realized_gross_pnl": str(self._total_realized_gross_pnl),
            }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ResearchLedger":
        """Restore and verify a previously serialized ledger fail-closed."""
        if data.get("schema_version") != 1:
            raise ValueError("LEDGER_STATE_SCHEMA_UNSUPPORTED")
        valuation_currency = str(data.get("valuation_currency", ""))
        if not valuation_currency:
            raise ValueError("LEDGER_STATE_CURRENCY_MISSING")

        ledger = cls(initial_cash=Decimal("0"), valuation_currency=valuation_currency)
        initial_cash = Decimal(str(data.get("initial_cash")))
        cash = Decimal(str(data.get("cash")))
        total_fees = Decimal(str(data.get("total_fees_paid")))
        gross_pnl = Decimal(str(data.get("total_realized_gross_pnl")))
        decimals = (initial_cash, cash, total_fees, gross_pnl)
        if any(not value.is_finite() for value in decimals):
            raise ValueError("LEDGER_STATE_NONFINITE")
        if initial_cash < 0 or cash < 0 or total_fees < 0:
            raise ValueError("LEDGER_STATE_NEGATIVE_BALANCE")

        raw_transactions = data.get("transactions")
        raw_positions = data.get("positions")
        raw_reservations = data.get("reservations")
        raw_processed = data.get("processed_fill_ids")
        if not isinstance(raw_transactions, list):
            raise ValueError("LEDGER_STATE_TRANSACTIONS_INVALID")
        if not isinstance(raw_positions, dict):
            raise ValueError("LEDGER_STATE_POSITIONS_INVALID")
        if not isinstance(raw_reservations, dict):
            raise ValueError("LEDGER_STATE_RESERVATIONS_INVALID")
        if not isinstance(raw_processed, list):
            raise ValueError("LEDGER_STATE_PROCESSED_IDS_INVALID")

        transactions = [LedgerTransaction.model_validate(row) for row in raw_transactions]
        if any(not tx.is_balanced for tx in transactions):
            raise ValueError("LEDGER_STATE_UNBALANCED_TRANSACTION")
        positions = {
            str(pair): Position.model_validate(row)
            for pair, row in raw_positions.items()
        }
        reservations = {
            str(key): Decimal(str(value))
            for key, value in raw_reservations.items()
        }
        if any(not value.is_finite() or value <= 0 for value in reservations.values()):
            raise ValueError("LEDGER_STATE_RESERVATION_INVALID")

        processed = {str(value) for value in raw_processed}
        transaction_fill_ids = {tx.fill_id for tx in transactions if tx.fill_id is not None}
        if processed != transaction_fill_ids:
            raise ValueError("LEDGER_STATE_FILL_ID_MISMATCH")

        cash_from_postings = sum(
            (
                posting.amount
                for tx in transactions
                for posting in tx.postings
                if posting.account == AccountType.CASH
            ),
            Decimal("0"),
        )
        fees_from_postings = sum(
            (
                posting.amount
                for tx in transactions
                for posting in tx.postings
                if posting.account == AccountType.FEE
            ),
            Decimal("0"),
        )
        gross_pnl_from_postings = -sum(
            (
                posting.amount
                for tx in transactions
                for posting in tx.postings
                if posting.account == AccountType.PNL
            ),
            Decimal("0"),
        )
        capital_from_postings = -sum(
            (
                posting.amount
                for tx in transactions
                for posting in tx.postings
                if posting.account == AccountType.CAPITAL
            ),
            Decimal("0"),
        )
        if capital_from_postings != initial_cash:
            raise ValueError("LEDGER_STATE_INITIAL_CAPITAL_MISMATCH")
        if cash_from_postings != cash:
            raise ValueError("LEDGER_STATE_CASH_MISMATCH")
        if fees_from_postings != total_fees:
            raise ValueError("LEDGER_STATE_FEE_MISMATCH")
        if gross_pnl_from_postings != gross_pnl:
            raise ValueError("LEDGER_STATE_PNL_MISMATCH")

        for pair, position in positions.items():
            quantity_from_postings = sum(
                (
                    tx.base_qty_delta
                    for tx in transactions
                    if tx.pair == pair
                ),
                Decimal("0"),
            )
            asset_value_from_postings = sum(
                (
                    posting.amount
                    for tx in transactions
                    if tx.pair == pair
                    for posting in tx.postings
                    if posting.account == AccountType.ASSET
                ),
                Decimal("0"),
            )
            if quantity_from_postings != position.base_qty:
                raise ValueError(f"LEDGER_STATE_QTY_MISMATCH:{pair}")
            if asset_value_from_postings != position.cost_basis:
                raise ValueError(f"LEDGER_STATE_COST_BASIS_MISMATCH:{pair}")

        ledger._initial_cash = initial_cash
        ledger._cash = cash
        ledger._reservations = reservations
        ledger.transactions = transactions
        ledger._positions = positions
        ledger._processed_fill_ids = processed
        ledger._total_fees_paid = total_fees
        ledger._total_realized_gross_pnl = gross_pnl
        ledger._total_net_pnl = gross_pnl - total_fees
        return ledger

