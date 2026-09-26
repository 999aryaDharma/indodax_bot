"""Shared capital ledger and paper portfolio reconciliation (SHADOW-02).

Contract: durable event IDs + risk policy -> reconciled postings, independent vs shared reports.

Guarantees:
1. SHADOW-02-AC0: Single shared ledger of Rp500,000 resolves cash allocation across multiple candidates.
2. SHADOW-02-AC1: Duplicate event IDs are detected and rejected without altering balances.
3. SHADOW-02-AC2: Maximum of two shared open positions enforced strictly across all candidates.
4. SHADOW-02-AC3: Restart from checkpoint produces identical equity, cash, and position state.

Review hardening (ops-shadow batch): the checkpoint now carries the capital basis,
the active shared position cap, and a SHA-256 integrity fingerprint. Previously the
cap silently reverted to its default on restart (a risk-cap bypass) and a tampered
checkpoint was restored as if authentic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import hashlib
import json
from threading import RLock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MaxPositionsExceededError(RuntimeError):
    """Raised when an entry is attempted while the shared portfolio is at max capacity."""


class InsufficientCashError(ValueError):
    """Raised when cash allocation exceeds available ledger cash."""


class CheckpointIntegrityError(ValueError):
    """Raised when a persisted shared-ledger checkpoint cannot be trusted."""


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class PaperOrderIntent(BaseModel):
    """Order intent submitted by a candidate strategy to the shared ledger."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str
    candidate_id: str
    pair: str
    side: Literal["BUY"] = "BUY"
    allocated_cash: Decimal = Field(gt=0, allow_inf_nan=False)
    entry_price: Decimal = Field(gt=0, allow_inf_nan=False)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("timestamp")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("UTC_TIMEZONE_AWARE_REQUIRED")
        return value


class PaperPosition(BaseModel):
    """An open position recorded in the shared paper ledger."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    position_id: str
    candidate_id: str
    pair: str
    cost_basis: Decimal
    entry_price: Decimal
    quantity: Decimal
    opened_at: datetime


class IntentProcessingResult(BaseModel):
    """Result of attempting to process an order intent against the shared ledger."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approved: bool
    reason: str | None = None
    position: PaperPosition | None = None


class SharedLedgerCheckpoint(BaseModel):
    """Immutable, integrity-sealed snapshot of the shared ledger state for crash recovery."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    available_cash: Decimal
    positions: list[PaperPosition]
    processed_event_ids: list[str]
    # Review hardening: the original capital basis and the active shared cap must
    # survive the restart, otherwise equity and the AC2 gate are both wrong after it.
    initial_cash: Decimal | None = None
    max_open_positions: int = Field(default=2, ge=1)
    checkpoint_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sha256: str = ""

    @field_validator("available_cash", "initial_cash")
    @classmethod
    def require_finite_cash(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or value < 0):
            raise ValueError("SHARED_CHECKPOINT_CASH_INVALID")
        return value

    @model_validator(mode="after")
    def seal_or_verify(self) -> "SharedLedgerCheckpoint":
        digest = _checkpoint_digest(self)
        if not self.sha256:
            object.__setattr__(self, "sha256", digest)
        elif self.sha256 != digest:
            raise CheckpointIntegrityError("SHARED_CHECKPOINT_DIGEST_MISMATCH")
        return self


def _checkpoint_digest(checkpoint: SharedLedgerCheckpoint) -> str:
    """Fingerprint the reconciled state only; timestamp and digest are excluded."""
    payload = {
        "available_cash": str(checkpoint.available_cash),
        "initial_cash": None if checkpoint.initial_cash is None else str(checkpoint.initial_cash),
        "max_open_positions": checkpoint.max_open_positions,
        "processed_event_ids": sorted(checkpoint.processed_event_ids),
        "positions": sorted(
            (
                {
                    "position_id": position.position_id,
                    "candidate_id": position.candidate_id,
                    "pair": position.pair,
                    "cost_basis": str(position.cost_basis),
                    "entry_price": str(position.entry_price),
                    "quantity": str(position.quantity),
                    "opened_at": position.opened_at.isoformat(),
                }
                for position in checkpoint.positions
            ),
            key=lambda item: item["position_id"],
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# SharedCapitalLedger
# ---------------------------------------------------------------------------


class SharedCapitalLedger:
    """Shared capital ledger managing cash allocation and capacity across candidate strategies."""

    def __init__(
        self,
        initial_cash: Decimal = Decimal("500000.00"),
        max_open_positions: int = 2,
    ) -> None:
        initial_cash = Decimal(str(initial_cash))
        if not initial_cash.is_finite() or initial_cash < 0:
            raise ValueError("INVALID_INITIAL_CASH")
        if isinstance(max_open_positions, bool) or not isinstance(max_open_positions, int) or max_open_positions <= 0:
            raise ValueError("INVALID_MAX_OPEN_POSITIONS")
        self._allocation_lock = RLock()  # Threads sharing this object, not processes.
        self.initial_cash: Decimal = initial_cash
        self.available_cash: Decimal = initial_cash
        self.max_open_positions: int = max_open_positions
        self._positions: dict[str, PaperPosition] = {}
        self._processed_event_ids: set[str] = set()

    @property
    def open_position_count(self) -> int:
        return len(self._positions)

    @property
    def processed_event_ids(self) -> set[str]:
        return set(self._processed_event_ids)

    def process_intent(self, intent: PaperOrderIntent) -> IntentProcessingResult:
        with self._allocation_lock:
            return self._process_intent_locked(intent)

    def _process_intent_locked(self, intent: PaperOrderIntent) -> IntentProcessingResult:
        """Process an order intent under shared capacity and cash constraints.

        Args:
            intent: The incoming ``PaperOrderIntent``.

        Returns:
            ``IntentProcessingResult`` with approval status.

        Raises:
            MaxPositionsExceededError: If ``max_open_positions`` is reached (SHADOW-02-AC2).
        """
        intent = PaperOrderIntent.model_validate(intent.model_dump())
        # AC1: Check for duplicate event ID (idempotency guard)
        if intent.event_id in self._processed_event_ids:
            return IntentProcessingResult(
                approved=False,
                reason="DUPLICATE_EVENT_ID",
            )

        # AC2: Check max open positions
        if len(self._positions) >= self.max_open_positions:
            raise MaxPositionsExceededError(
                f"MAX_POSITIONS_REACHED: Shared portfolio has {len(self._positions)} "
                f"positions open, which meets the limit of {self.max_open_positions}."
            )

        # Cash check
        if intent.allocated_cash > self.available_cash:
            return IntentProcessingResult(
                approved=False,
                reason="INSUFFICIENT_CASH",
            )

        # Execute allocation
        next_cash = self.available_cash - intent.allocated_cash
        quantity = intent.allocated_cash / intent.entry_price

        position = PaperPosition(
            position_id=f"pos_{intent.event_id}",
            candidate_id=intent.candidate_id,
            pair=intent.pair,
            cost_basis=intent.allocated_cash,
            entry_price=intent.entry_price,
            quantity=quantity,
            opened_at=intent.timestamp,
        )

        result = IntentProcessingResult(approved=True, position=position)
        self.available_cash = next_cash
        self._positions[intent.event_id] = position
        self._processed_event_ids.add(intent.event_id)

        return result

    def create_checkpoint(self) -> SharedLedgerCheckpoint:
        """Generate an immutable, integrity-sealed checkpoint (SHADOW-02-AC3)."""
        with self._allocation_lock:
            return SharedLedgerCheckpoint(
                available_cash=self.available_cash,
                initial_cash=self.initial_cash,
                max_open_positions=self.max_open_positions,
                positions=list(self._positions.values()),
                processed_event_ids=sorted(self._processed_event_ids),
            )

    @classmethod
    def from_checkpoint(cls, checkpoint: SharedLedgerCheckpoint) -> SharedCapitalLedger:
        """Reconstruct a ledger from a verified checkpoint (SHADOW-02-AC3).

        The checkpoint fingerprint is verified before any state is adopted, so a
        tampered or forged balance is refused instead of being restored silently.
        The capital basis and the shared position cap are restored with the state.
        """
        recomputed = _checkpoint_digest(checkpoint)
        if checkpoint.sha256 and recomputed != checkpoint.sha256:
            raise CheckpointIntegrityError(
                "SHARED_CHECKPOINT_DIGEST_MISMATCH: Refusing to restore a shared-ledger "
                "checkpoint whose state does not match its recorded fingerprint."
            )
        if not checkpoint.sha256:
            raise CheckpointIntegrityError(
                "SHARED_CHECKPOINT_DIGEST_MISSING: Refusing to restore an unsealed checkpoint."
            )

        if checkpoint.initial_cash is not None:
            basis = Decimal(str(checkpoint.initial_cash))
        else:
            # Legacy checkpoints carry no basis; the only admitted movement is an entry
            # allocation, so remaining cash plus allocated cost basis is the original.
            basis = checkpoint.available_cash + sum(
                (position.cost_basis for position in checkpoint.positions),
                Decimal("0"),
            )

        ledger = cls(
            initial_cash=basis,
            max_open_positions=checkpoint.max_open_positions,
        )
        for pos in checkpoint.positions:
            # key positions by their original event_id extracted from pos_id or matching event
            event_id = pos.position_id.removeprefix("pos_")
            ledger._positions[event_id] = pos
        ledger.available_cash = checkpoint.available_cash
        ledger._processed_event_ids = set(checkpoint.processed_event_ids)
        return ledger
