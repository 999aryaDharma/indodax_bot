"""Pure Indodax candle parsing and a wire-first public HTTP boundary."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol

from pydantic import ValidationError

from indodax_lab.contracts import CandleRecord, CanonicalPair, QualityStatus

from .checksums import sha256_bytes
from .manifest import canonical_json_bytes
from .wire_store import WireArtifact, WireRequest, WireStore

HISTORY_V2_ENDPOINT = "https://indodax.com/tradingview/history_v2"
SOURCE = "indodax-history-v2"
PAIR_TO_VENUE_SYMBOL = {"btc_idr": "BTCIDR", "eth_idr": "ETHIDR", "sol_idr": "SOLIDR"}
INTERVAL_TO_SECONDS = {
    "1m": 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "1d": 24 * 60 * 60,
}
INTERVAL_TO_ENDPOINT = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "1h": "60",
    "4h": "240",
    "1d": "1D",
}


class InvalidCandlePayload(ValueError):
    """The top-level wire shape is unsupported and must not be treated as empty data."""


class CandleHttpError(RuntimeError):
    """A non-success HTTP response that has already been stored as wire evidence."""


@dataclass(frozen=True)
class CandleReject:
    """Stable parser rejection outcome for one malformed or conflicting source row."""

    row_index: int
    reason: str
    source_event_id: str | None
    wire_metadata: Mapping[str, object]
    detail: str


@dataclass(frozen=True)
class ParsedCandle:
    """Canonical candle plus lineage that is not part of bronze_candles_v1."""

    candle: CandleRecord
    source_event_id: str
    wire_metadata: Mapping[str, object]
    row_index: int


@dataclass(frozen=True)
class ParseBatch:
    """Accepted canonical candles and every explicit row-level rejection."""

    items: tuple[ParsedCandle, ...]
    rejects: tuple[CandleReject, ...]

    @property
    def records(self) -> tuple[CandleRecord, ...]:
        return tuple(item.candle for item in self.items)

    @property
    def candles(self) -> tuple[CandleRecord, ...]:
        return self.records


@dataclass(frozen=True)
class HttpResponse:
    """Transport-neutral public HTTP response."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes


class HttpTransport(Protocol):
    """Injected HTTP surface; tests never need sockets or credentials."""

    def get(self, url: str, *, params: Mapping[str, object], timeout: float) -> HttpResponse: ...


@dataclass(frozen=True)
class CandleFetch:
    """Wire artifact and its deterministic parser outcome."""

    wire: WireArtifact
    batch: ParseBatch


class IndodaxCandleAdapter:
    """Parse only the two documented history_v2 wire response shapes."""

    def parse(
        self,
        payload: object,
        *,
        pair: str,
        interval: str,
        ingested_at: datetime,
    ) -> ParseBatch:
        if isinstance(payload, list):
            return parse_pascal_rows(
                payload, pair=pair, interval=interval, ingested_at=ingested_at
            )
        elif isinstance(payload, dict):
            return parse_columnar(
                payload, pair=pair, interval=interval, ingested_at=ingested_at
            )
        else:
            raise InvalidCandlePayload(type(payload).__name__)


def parse_pascal_rows(
    payload: object, *, pair: str, interval: str, ingested_at: datetime
) -> ParseBatch:
    """Parse the documented list-of-PascalCase-objects response without I/O."""
    if not isinstance(payload, list):
        raise InvalidCandlePayload("pascal_shape_must_be_list")
    return _parse_rows(payload, pair=pair, interval=interval, ingested_at=ingested_at)


def parse_columnar(
    payload: object, *, pair: str, interval: str, ingested_at: datetime
) -> ParseBatch:
    """Parse the documented t/o/h/l/c/v response without I/O."""
    if not isinstance(payload, dict):
        raise InvalidCandlePayload("columnar_shape_must_be_object")
    return _parse_rows(
        _columnar_rows(payload), pair=pair, interval=interval, ingested_at=ingested_at
    )


class IndodaxCandleClient:
    """Fetch public history and persist exact response bytes before parsing."""

    def __init__(
        self,
        *,
        transport: HttpTransport,
        wire_store: WireStore,
        adapter: IndodaxCandleAdapter | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        self._transport = transport
        self._wire_store = wire_store
        self._adapter = adapter or IndodaxCandleAdapter()
        self._timeout_seconds = timeout_seconds

    def fetch_window(
        self,
        *,
        pair: str,
        interval: str,
        start: datetime,
        end: datetime,
        received_at: datetime,
    ) -> CandleFetch:
        venue_symbol = _venue_symbol(pair)
        _interval_seconds(interval)
        _require_utc(start, "start")
        _require_utc(end, "end")
        if end <= start:
            raise ValueError("backfill window end must be after start")
        start_epoch = int(start.timestamp())
        end_epoch = int(end.timestamp())
        request = WireRequest(
            endpoint=HISTORY_V2_ENDPOINT,
            pair=pair,
            venue_symbol=venue_symbol,
            interval=interval,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
        )
        response = self._transport.get(
            HISTORY_V2_ENDPOINT,
            params={
                "symbol": venue_symbol,
                "tf": INTERVAL_TO_ENDPOINT[interval],
                "from": start_epoch,
                "to": end_epoch,
            },
            timeout=self._timeout_seconds,
        )
        wire = self._wire_store.write_response(
            request=request,
            status_code=response.status_code,
            headers=response.headers,
            body=response.body,
            received_at=received_at,
        )
        if not 200 <= response.status_code < 300:
            raise CandleHttpError(f"history_v2 returned HTTP {response.status_code}")
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise InvalidCandlePayload("invalid_json") from error
        batch = self._adapter.parse(
            payload, pair=pair, interval=interval, ingested_at=wire.received_at
        )
        return CandleFetch(wire=wire, batch=_constrain_to_window(batch, start=start, end=end))


def _columnar_rows(payload: Mapping[object, object]) -> list[object]:
    fields = ("t", "o", "h", "l", "c", "v")
    if not all(field in payload for field in fields):
        raise InvalidCandlePayload("columnar_missing_fields")
    columns = {field: payload[field] for field in fields}
    if any(
        not isinstance(column, list)
        for column in columns.values()
    ):
        raise InvalidCandlePayload("columnar_fields_must_be_lists")
    length = max((len(column) for column in columns.values()), default=0)
    rows: list[object] = []
    for index in range(length):
        rows.append(
            {
                "Time": columns["t"][index] if index < len(columns["t"]) else None,
                "Open": columns["o"][index] if index < len(columns["o"]) else None,
                "High": columns["h"][index] if index < len(columns["h"]) else None,
                "Low": columns["l"][index] if index < len(columns["l"]) else None,
                "Close": columns["c"][index] if index < len(columns["c"]) else None,
                "Volume": columns["v"][index] if index < len(columns["v"]) else None,
            }
        )
    return rows


def _parse_rows(
    rows: Sequence[object], *, pair: str, interval: str, ingested_at: datetime
) -> ParseBatch:
    canonical_pair = CanonicalPair(pair=pair)
    venue_symbol = _venue_symbol(pair)
    interval_seconds = _interval_seconds(interval)
    _require_utc(ingested_at, "ingested_at")
    parsed: dict[str, list[tuple[int, ParsedCandle, tuple[Decimal, ...]]]] = {}
    rejects: list[CandleReject] = []
    for index, row in enumerate(rows):
        try:
            item, signature = _parse_row(
                row,
                row_index=index,
                pair=canonical_pair,
                venue_symbol=venue_symbol,
                interval=interval,
                interval_seconds=interval_seconds,
                ingested_at=ingested_at,
            )
        except (
            InvalidOperation,
            KeyError,
            OSError,
            OverflowError,
            TypeError,
            ValueError,
            ValidationError,
        ) as error:
            metadata = _row_metadata(row)
            rejects.append(
                CandleReject(
                    row_index=index,
                    reason="INVALID_ROW",
                    source_event_id=None,
                    wire_metadata=metadata,
                    detail=type(error).__name__,
                )
            )
            continue
        parsed.setdefault(item.source_event_id, []).append((index, item, signature))

    accepted: list[ParsedCandle] = []
    for source_event_id, candidates in parsed.items():
        signatures = {candidate[2] for candidate in candidates}
        if len(signatures) == 1:
            accepted.append(candidates[0][1])
            continue
        for index, item, _signature in candidates:
            rejects.append(
                CandleReject(
                    row_index=index,
                    reason="CONFLICTING_DUPLICATE_SOURCE_EVENT_ID",
                    source_event_id=source_event_id,
                    wire_metadata=item.wire_metadata,
                    detail="same candle identity has different OHLCV values",
                )
            )

    accepted.sort(key=lambda item: (item.candle.open_time, item.source_event_id))
    rejects.sort(key=lambda reject: reject.row_index)
    return ParseBatch(items=tuple(accepted), rejects=tuple(rejects))


def _parse_row(
    row: object,
    *,
    row_index: int,
    pair: CanonicalPair,
    venue_symbol: str,
    interval: str,
    interval_seconds: int,
    ingested_at: datetime,
) -> tuple[ParsedCandle, tuple[Decimal, ...]]:
    if not isinstance(row, Mapping):
        raise TypeError("Pascal row must be an object")
    epoch_value = row["Time"]
    if isinstance(epoch_value, bool) or not isinstance(epoch_value, int):
        raise TypeError("Time must be an integer epoch in seconds")
    open_time = datetime.fromtimestamp(epoch_value, tz=UTC)
    close_time = open_time + timedelta(seconds=interval_seconds)
    values = tuple(
        _decimal(row[field], field)
        for field in ("Open", "High", "Low", "Close", "Volume")
    )
    open_price, high, low, close, volume = values
    source_event_id = _source_event_id(
        pair=pair.pair,
        venue_symbol=venue_symbol,
        interval=interval,
        open_epoch=epoch_value,
    )
    metadata = {"original_epoch": epoch_value, "epoch_unit": "seconds"}
    candle = CandleRecord(
        schema_version="1.0.0",
        pair=pair,
        venue_symbol=venue_symbol,
        interval=interval,
        open_time=open_time,
        close_time=close_time,
        open=open_price,
        high=high,
        low=low,
        close=close,
        base_volume=volume,
        quote_volume=None,
        trade_count=None,
        is_closed=ingested_at >= close_time,
        available_at=max(ingested_at, close_time),
        source=SOURCE,
        ingested_at=ingested_at,
        quality_status=QualityStatus.PASS,
        quality_flags=[],
    )
    return ParsedCandle(candle, source_event_id, metadata, row_index), values


def _constrain_to_window(
    batch: ParseBatch, *, start: datetime, end: datetime
) -> ParseBatch:
    accepted: list[ParsedCandle] = []
    rejects = list(batch.rejects)
    for item in batch.items:
        if start <= item.candle.open_time < end:
            accepted.append(item)
            continue
        rejects.append(
            CandleReject(
                row_index=item.row_index,
                reason="OUTSIDE_REQUEST_WINDOW",
                source_event_id=item.source_event_id,
                wire_metadata=item.wire_metadata,
                detail="candle open_time is outside end-exclusive request window",
            )
        )
    rejects.sort(key=lambda reject: reject.row_index)
    return ParseBatch(items=tuple(accepted), rejects=tuple(rejects))


def _decimal(value: object, field: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise TypeError(f"{field} must be a decimal value")
    decimal = Decimal(str(value))
    if not decimal.is_finite():
        raise ValueError(f"{field} must be finite")
    return decimal


def _source_event_id(
    *, pair: str, venue_symbol: str, interval: str, open_epoch: int
) -> str:
    identity = {
        "interval": interval,
        "open_epoch": open_epoch,
        "pair": pair,
        "source": SOURCE,
        "venue_symbol": venue_symbol,
    }
    return f"sha256:{sha256_bytes(canonical_json_bytes(identity))}"


def _row_metadata(row: object) -> dict[str, object]:
    if isinstance(row, Mapping):
        epoch = row.get("Time")
        return {"original_epoch": epoch, "epoch_unit": "seconds"}
    return {"original_epoch": None, "epoch_unit": "seconds"}


def _venue_symbol(pair: str) -> str:
    try:
        return PAIR_TO_VENUE_SYMBOL[pair]
    except KeyError as error:
        raise ValueError(f"unsupported Indodax candle pair: {pair}") from error


def _interval_seconds(interval: str) -> int:
    try:
        return INTERVAL_TO_SECONDS[interval]
    except KeyError as error:
        raise ValueError(f"unsupported candle interval: {interval}") from error


def _require_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be timezone-aware UTC")
