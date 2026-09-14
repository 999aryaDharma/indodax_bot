"""Pure, offline adapter and reliability state for Indodax public streams."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from indodax_lab.contracts import (
    AggressorSide,
    CanonicalPair,
    QualityStatus,
    TradeEvent,
)
from indodax_lab.contracts.common import UtcTimestamp

from .checksums import sha256_bytes
from .manifest import canonical_json_bytes


class InvalidPublicStreamMessage(ValueError):
    """A public payload does not match an official supported message shape."""


class ConflictingSequenceError(InvalidPublicStreamMessage):
    """A previously-seen publication offset contains different content."""


class SequenceRegressionError(InvalidPublicStreamMessage):
    """A publication offset moved backwards or wrapped to a lower value."""

    def __init__(self, *, previous_offset: int, observed_offset: int) -> None:
        self.previous_offset = previous_offset
        self.observed_offset = observed_offset
        super().__init__(
            f"book offset regressed from {previous_offset} to {observed_offset}"
        )


class StreamState(StrEnum):
    """Fail-closed order-book reliability state."""

    DISCONNECTED = "DISCONNECTED"
    SYNCING = "SYNCING"
    RELIABLE = "RELIABLE"
    GAP = "GAP"
    RECOVERING = "RECOVERING"


class BookSide(StrEnum):
    ASK = "ASK"
    BID = "BID"


class BookEvent(BaseModel):
    """One canonical level from an official full-book publication."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0.0"
    pair: CanonicalPair
    venue_symbol: str = Field(min_length=1)
    event_ts: UtcTimestamp
    ingested_at: UtcTimestamp
    available_at: UtcTimestamp
    book_session_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    event_type: Literal["SNAPSHOT", "UPDATE"]
    side: BookSide
    level: int = Field(ge=0)
    price: Decimal
    base_qty: Decimal
    quote_qty: Decimal
    source_event_id: str = Field(min_length=1)
    source: str = "indodax_public_websocket"
    quality_status: QualityStatus
    quality_flags: list[str]

    @field_validator("price", "base_qty", "quote_qty", mode="before")
    @classmethod
    def require_decimal(cls, value: object) -> Decimal:
        if not isinstance(value, Decimal):
            raise ValueError("book price and quantities must be Decimal")
        if value < 0:
            raise ValueError("book price and quantities must be non-negative")
        return value


class ParsedPublicMessage(BaseModel):
    """Canonical events and publication offset from one public message."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    kind: Literal["TRADE", "BOOK", "HEARTBEAT", "CONTROL", "SUBSCRIPTION"]
    channel: str | None = None
    offset: int | None = Field(default=None, ge=0)
    trades: tuple[TradeEvent, ...] = ()
    books: tuple[BookEvent, ...] = ()


class ProtocolResult(BaseModel):
    """One state-machine outcome, including whether downstream LOB use is safe."""

    model_config = ConfigDict(frozen=True)

    trades: tuple[TradeEvent, ...] = ()
    books: tuple[BookEvent, ...] = ()
    feature_eligible: bool
    duplicate: bool = False
    missing_offsets: tuple[int, int] | None = None


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise InvalidPublicStreamMessage(f"{name} must be an object")
    return value


def _sequence(value: object, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise InvalidPublicStreamMessage(f"{name} must be an array")
    return value


def _decimal(value: object, name: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise InvalidPublicStreamMessage(f"{name} must be a decimal") from error
    if not parsed.is_finite():
        raise InvalidPublicStreamMessage(f"{name} must be finite")
    return parsed


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise InvalidPublicStreamMessage("ingested_at must use timezone-aware UTC")
    return value.astimezone(UTC)


def parse_public_message(
    payload: object,
    *,
    ingested_at: datetime,
    book_session_id: str | None = None,
    book_event_type: Literal["SNAPSHOT", "UPDATE"] = "UPDATE",
    expected_pair: str | None = None,
) -> ParsedPublicMessage:
    """Parse one official public envelope without any I/O or ambient clock use."""
    ingested_at = _require_utc(ingested_at)
    envelope = _mapping(payload, "payload")
    if set(envelope) == {"id"}:
        return ParsedPublicMessage(
            kind="HEARTBEAT" if envelope["id"] == 3 else "CONTROL"
        )
    result = _mapping(envelope.get("result"), "result")
    if "channel" not in result:
        if "recoverable" in result:
            return ParsedPublicMessage(
                kind="SUBSCRIPTION",
                offset=int(result["offset"]) if "offset" in result else None,
            )
        if "id" in envelope:
            return ParsedPublicMessage(kind="CONTROL")
        raise InvalidPublicStreamMessage("result channel is missing")
    channel = str(result["channel"])
    expected_symbol = (
        CanonicalPair(pair=expected_pair).pair.replace("_", "")
        if expected_pair is not None
        else None
    )
    if expected_symbol is not None and channel not in {
        f"market:trade-activity-{expected_symbol}",
        f"market:order-book-{expected_symbol}",
    }:
        raise InvalidPublicStreamMessage("message channel does not match configured pair")
    publication = _mapping(result.get("data"), "result.data")
    try:
        offset = int(publication["offset"])
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidPublicStreamMessage("publication offset is invalid") from error
    if offset < 0:
        raise InvalidPublicStreamMessage("publication offset must be non-negative")

    if channel.startswith("market:trade-activity-"):
        channel_symbol = channel.removeprefix("market:trade-activity-")
        trades = _parse_trades(
            publication.get("data"),
            ingested_at,
            expected_symbol=expected_symbol or channel_symbol,
        )
        return ParsedPublicMessage(
            kind="TRADE", channel=channel, offset=offset, trades=trades
        )
    if channel.startswith("market:order-book-"):
        if not book_session_id:
            raise InvalidPublicStreamMessage("book_session_id is required for book data")
        books = _parse_book(
            publication.get("data"),
            offset=offset,
            ingested_at=ingested_at,
            book_session_id=book_session_id,
            event_type=book_event_type,
            expected_symbol=(
                expected_symbol or channel.removeprefix("market:order-book-")
            ),
        )
        return ParsedPublicMessage(kind="BOOK", channel=channel, offset=offset, books=books)
    raise InvalidPublicStreamMessage("unsupported public channel")


def _parse_trades(
    data: object, ingested_at: datetime, *, expected_symbol: str
) -> tuple[TradeEvent, ...]:
    trades: list[TradeEvent] = []
    for raw_row in _sequence(data, "trade data"):
        row = _sequence(raw_row, "trade row")
        if len(row) != 7:
            raise InvalidPublicStreamMessage("trade row must contain seven fields")
        symbol, epoch, sequence, side, price, quote_qty, base_qty = row
        symbol = str(symbol).lower()
        if symbol != expected_symbol:
            raise InvalidPublicStreamMessage("trade payload does not match configured pair")
        try:
            event_ts = datetime.fromtimestamp(int(epoch), tz=UTC)
            trade_sequence = int(sequence)
            aggressor = AggressorSide(str(side).upper())
        except (OSError, OverflowError, TypeError, ValueError) as error:
            raise InvalidPublicStreamMessage("trade identity or timestamp is invalid") from error
        trades.append(
            TradeEvent(
                schema_version="1.0.0",
                pair=CanonicalPair.from_venue_symbol(symbol),
                venue_symbol=symbol.upper(),
                event_ts=event_ts,
                ingested_at=ingested_at,
                available_at=ingested_at,
                price=_decimal(price, "trade price"),
                base_qty=_decimal(base_qty, "trade base quantity"),
                quote_qty=_decimal(quote_qty, "trade quote quantity"),
                source_event_id=f"indodax:public-trade:{symbol}:{trade_sequence}",
                source="indodax_public_websocket",
                sequence=trade_sequence,
                aggressor_side=aggressor,
                quality_status=QualityStatus.PASS,
                quality_flags=[],
            )
        )
    return tuple(trades)


def _parse_book(
    data: object,
    *,
    offset: int,
    ingested_at: datetime,
    book_session_id: str,
    event_type: Literal["SNAPSHOT", "UPDATE"],
    expected_symbol: str,
) -> tuple[BookEvent, ...]:
    book = _mapping(data, "book data")
    symbol = str(book.get("pair", "")).lower()
    if symbol != expected_symbol:
        raise InvalidPublicStreamMessage("book payload does not match configured pair")
    pair = CanonicalPair.from_venue_symbol(symbol)
    events: list[BookEvent] = []
    for source_side, side in (("ask", BookSide.ASK), ("bid", BookSide.BID)):
        for level, raw_level in enumerate(_sequence(book.get(source_side), source_side)):
            values = _mapping(raw_level, f"{source_side} level")
            price = _decimal(values.get("price"), "book price")
            base_qty = _decimal(values.get("btc_volume"), "book base quantity")
            quote_qty = _decimal(values.get("idr_volume"), "book quote quantity")
            events.append(
                BookEvent(
                    pair=pair,
                    venue_symbol=symbol.upper(),
                    event_ts=ingested_at,
                    ingested_at=ingested_at,
                    available_at=ingested_at,
                    book_session_id=book_session_id,
                    sequence=offset,
                    event_type=event_type,
                    side=side,
                    level=level,
                    price=price,
                    base_qty=base_qty,
                    quote_qty=quote_qty,
                    source_event_id=(
                        f"indodax:book:{symbol}:{book_session_id}:{offset}:{side.value}:{level}"
                    ),
                    quality_status=QualityStatus.PASS,
                    quality_flags=["SOURCE_TIMESTAMP_UNAVAILABLE"],
                )
            )
    return tuple(events)


class BookSessionProtocol:
    """Order-book session state that never bridges an observed offset gap."""

    def __init__(self, *, pair: str, session_id_factory: Callable[[], str]) -> None:
        self.pair = CanonicalPair(pair=pair)
        self._session_id_factory = session_id_factory
        self.state = StreamState.DISCONNECTED
        self.book_session_id: str | None = None
        self.last_offset: int | None = None
        self._last_digest: str | None = None
        self._pending_gap: tuple[int, int] | None = None
        self.gap_reason: str | None = None
        self.gap_observed_offset: int | None = None

    @property
    def feature_eligible(self) -> bool:
        return self.state is StreamState.RELIABLE

    def connected(self) -> None:
        if self._pending_gap is not None:
            raise RuntimeError("pending book gap must be durably quarantined before reconnect")
        self.state = StreamState.SYNCING
        self.book_session_id = self._session_id_factory()
        if not self.book_session_id:
            raise ValueError("session_id_factory returned an empty ID")
        self.last_offset = None
        self._last_digest = None
        self._pending_gap = None
        self.gap_reason = None
        self.gap_observed_offset = None

    def disconnected(self) -> None:
        self.state = StreamState.DISCONNECTED

    @property
    def pending_gap(self) -> tuple[int, int] | None:
        return self._pending_gap

    def start_recovery(self) -> None:
        if self.state is not StreamState.GAP or self._pending_gap is None:
            raise RuntimeError("recovery requires an observed sequence gap")
        self.state = StreamState.RECOVERING

    def apply_recovery(self, payload: object, *, ingested_at: datetime) -> ProtocolResult:
        """Atomically validate a complete official offset replay before restoring eligibility."""
        if self.state is not StreamState.RECOVERING:
            raise RuntimeError("official replay requires RECOVERING state")
        if self.book_session_id is None or self.last_offset is None:
            raise RuntimeError("book recovery has no reliable checkpoint")
        envelope = _mapping(payload, "recovery payload")
        result = _mapping(envelope.get("result"), "recovery result")
        if result.get("recoverable") is not True:
            raise InvalidPublicStreamMessage("official offset recovery is unavailable")
        publications = _sequence(result.get("publications"), "recovery publications")
        expected = self.last_offset + 1
        accepted: list[BookEvent] = []
        final_digest = self._last_digest
        for publication_object in publications:
            publication = _mapping(publication_object, "recovery publication")
            try:
                offset = int(publication["offset"])
            except (KeyError, TypeError, ValueError) as error:
                raise InvalidPublicStreamMessage("recovery offset is invalid") from error
            if offset != expected:
                raise InvalidPublicStreamMessage(
                    f"recovery expected offset {expected}, received {offset}"
                )
            synthetic = {
                "result": {
                    "channel": f"market:order-book-{self.pair.pair.replace('_', '')}",
                    "data": publication,
                }
            }
            parsed = parse_public_message(
                synthetic,
                ingested_at=ingested_at,
                book_session_id=self.book_session_id,
                book_event_type="UPDATE",
                expected_pair=self.pair.pair,
            )
            accepted.extend(parsed.books)
            final_digest = sha256_bytes(canonical_json_bytes(synthetic))
            expected += 1
        try:
            claimed_final = int(result["offset"])
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidPublicStreamMessage("recovery final offset is invalid") from error
        if not publications or claimed_final != expected - 1:
            raise InvalidPublicStreamMessage("recovery did not end at its claimed offset")
        if self._pending_gap is None or claimed_final < self._pending_gap[1] + 1:
            raise InvalidPublicStreamMessage("recovery did not replay through the observed gap")
        self.last_offset = claimed_final
        self._last_digest = final_digest
        self._pending_gap = None
        self.gap_reason = None
        self.gap_observed_offset = None
        self.state = StreamState.RELIABLE
        return ProtocolResult(books=tuple(accepted), feature_eligible=True)

    def abandon_gap(self) -> tuple[str, tuple[int, int]]:
        """Close an unreliable session and begin a new, ineligible synchronization session."""
        if self.state not in {StreamState.GAP, StreamState.RECOVERING}:
            raise RuntimeError("only a gapped session can be abandoned")
        if self.book_session_id is None or self._pending_gap is None:
            raise RuntimeError("gap identity is unavailable")
        closed_session = self.book_session_id
        exact_gap = self._pending_gap
        self._pending_gap = None
        self.gap_reason = None
        self.gap_observed_offset = None
        self.connected()
        return closed_session, exact_gap

    def handle(self, payload: object, *, ingested_at: datetime) -> ProtocolResult:
        if self.state not in {StreamState.SYNCING, StreamState.RELIABLE}:
            raise RuntimeError(f"cannot accept book publication while {self.state}")
        if self.book_session_id is None:
            raise RuntimeError("book session is not initialized")
        event_type: Literal["SNAPSHOT", "UPDATE"] = (
            "SNAPSHOT" if self.state is StreamState.SYNCING else "UPDATE"
        )
        parsed = parse_public_message(
            payload,
            ingested_at=ingested_at,
            book_session_id=self.book_session_id,
            book_event_type=event_type,
            expected_pair=self.pair.pair,
        )
        if parsed.kind != "BOOK" or parsed.offset is None:
            return ProtocolResult(feature_eligible=self.feature_eligible)
        digest = sha256_bytes(canonical_json_bytes(payload))
        if self.last_offset is not None:
            if parsed.offset == self.last_offset:
                if digest != self._last_digest:
                    self._pending_gap = (parsed.offset, parsed.offset)
                    self.gap_reason = "CONFLICTING_DUPLICATE"
                    self.gap_observed_offset = parsed.offset
                    self.state = StreamState.GAP
                    raise ConflictingSequenceError(
                        f"offset {parsed.offset} was replayed with conflicting content"
                    )
                return ProtocolResult(feature_eligible=self.feature_eligible, duplicate=True)
            if parsed.offset < self.last_offset:
                self._pending_gap = (parsed.offset, parsed.offset)
                self.gap_reason = "OFFSET_REGRESSION"
                self.gap_observed_offset = parsed.offset
                self.state = StreamState.GAP
                raise SequenceRegressionError(
                    previous_offset=self.last_offset,
                    observed_offset=parsed.offset,
                )
            if parsed.offset != self.last_offset + 1:
                missing_start = self.last_offset + 1
                missing_end = parsed.offset - 1
                self._pending_gap = (missing_start, missing_end)
                self.gap_reason = "OFFSET_GAP"
                self.gap_observed_offset = parsed.offset
                self.state = StreamState.GAP
                return ProtocolResult(
                    feature_eligible=False,
                    missing_offsets=self._pending_gap,
                )
        self.last_offset = parsed.offset
        self._last_digest = digest
        self.state = StreamState.RELIABLE
        return ProtocolResult(books=parsed.books, feature_eligible=True)
