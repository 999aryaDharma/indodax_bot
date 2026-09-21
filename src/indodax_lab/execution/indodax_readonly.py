"""Read-only Indodax private venue adapter.

This module deliberately exposes only account/view operations. It has no order-create,
order-cancel, or withdrawal method. Signed requests follow the current official Indodax
Private REST and Trade API v2 contracts.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Any
from urllib.parse import urlencode

import requests

from indodax_lab.backtest.costs import OrderRole, OrderSide


class VenueReadError(RuntimeError):
    """Base error for read-only venue access."""


class VenueAuthenticationError(VenueReadError):
    """Authentication/permission failure from the venue."""


class VenueProtocolError(VenueReadError):
    """Malformed or unexpected venue response."""


@dataclass(frozen=True)
class VenueBalance:
    """One currency balance split into immediately available and held funds."""

    currency: str
    available: Decimal
    hold: Decimal

    @property
    def total(self) -> Decimal:
        return self.available + self.hold


@dataclass(frozen=True)
class VenueAccountSnapshot:
    """Private account balance snapshot returned by getInfo."""

    server_time: datetime
    balances: Mapping[str, VenueBalance]


@dataclass(frozen=True)
class VenueOrder:
    """Normalized order representation used by reconciliation/OMS recovery."""

    order_id: str
    client_order_id: str | None
    pair: str
    side: OrderSide
    order_type: str
    status: str
    price: Decimal
    original_qty: Decimal
    executed_qty: Decimal
    remaining_qty: Decimal
    submitted_at: datetime
    finished_at: datetime | None = None
    cancel_reason: str | None = None


@dataclass(frozen=True)
class VenueFill:
    """Normalized execution fill from Trade API v2."""

    fill_id: str
    order_id: str
    client_order_id: str | None
    pair: str
    side: OrderSide
    role: OrderRole
    qty: Decimal
    quote_qty: Decimal
    price: Decimal
    commission: Decimal
    commission_asset: str
    timestamp: datetime


def _decimal(value: Any, field_name: str, *, positive: bool = False) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise VenueProtocolError(f"INVALID_DECIMAL:{field_name}") from exc
    if not parsed.is_finite() or parsed < 0 or (positive and parsed <= 0):
        raise VenueProtocolError(f"INVALID_DECIMAL:{field_name}")
    return parsed


def _utc_from_epoch(value: Any, field_name: str) -> datetime:
    try:
        numeric = int(value)
    except (TypeError, ValueError) as exc:
        raise VenueProtocolError(f"INVALID_TIMESTAMP:{field_name}") from exc
    if numeric <= 0:
        raise VenueProtocolError(f"INVALID_TIMESTAMP:{field_name}")
    seconds = numeric / 1000 if numeric >= 10_000_000_000 else numeric
    try:
        return datetime.fromtimestamp(seconds, tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise VenueProtocolError(f"INVALID_TIMESTAMP:{field_name}") from exc


def _pair(pair: str) -> str:
    normalized = pair.strip().lower()
    parts = normalized.split("_")
    if len(parts) != 2 or not all(part.isalnum() for part in parts):
        raise ValueError(f"INVALID_PAIR:{pair}")
    return normalized


def _symbol(pair: str) -> str:
    return _pair(pair).replace("_", "")


def _side(value: Any, field_name: str) -> OrderSide:
    try:
        return OrderSide(str(value).lower())
    except ValueError as exc:
        raise VenueProtocolError(f"INVALID_ORDER_SIDE:{field_name}") from exc


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise VenueProtocolError(f"MISSING_TEXT:{field_name}")
    return text


def _legacy_order_quantities(
    pair: str,
    side: OrderSide,
    row: Mapping[str, Any],
    *,
    field_prefix: str,
) -> tuple[Decimal, Decimal]:
    """Normalize legacy order amount fields into base-asset quantity."""

    base, quote = pair.split("_", 1)
    base_order_key = f"order_{base}"
    base_remain_key = f"remain_{base}"
    if base_order_key in row and base_remain_key in row:
        original = _decimal(row[base_order_key], f"{field_prefix}.original_qty")
        remaining = _decimal(row[base_remain_key], f"{field_prefix}.remaining_qty")
        return original, remaining

    if side != OrderSide.BUY:
        raise VenueProtocolError(f"INDODAX_{field_prefix.upper()}_QUANTITY_MISSING")

    aliases = [quote]
    if quote == "idr":
        aliases.append("rp")
    for alias in aliases:
        order_key = f"order_{alias}"
        remain_key = f"remain_{alias}"
        if order_key not in row or remain_key not in row:
            continue
        price = _decimal(row.get("price"), f"{field_prefix}.price", positive=True)
        original_quote = _decimal(row[order_key], f"{field_prefix}.original_quote")
        remaining_quote = _decimal(row[remain_key], f"{field_prefix}.remaining_quote")
        return original_quote / price, remaining_quote / price

    raise VenueProtocolError(f"INDODAX_{field_prefix.upper()}_QUANTITY_MISSING")


def _validate_time_window(start_time_ms: int | None, end_time_ms: int | None) -> None:
    if start_time_ms is not None and start_time_ms <= 0:
        raise ValueError("INVALID_START_TIME")
    if end_time_ms is not None and end_time_ms <= 0:
        raise ValueError("INVALID_END_TIME")
    if start_time_ms is not None and end_time_ms is not None:
        if end_time_ms < start_time_ms:
            raise ValueError("INVALID_TIME_RANGE")
        if end_time_ms - start_time_ms > 7 * 24 * 60 * 60 * 1000:
            raise ValueError("TIME_RANGE_EXCEEDS_7_DAYS")


class IndodaxReadOnlyClient:
    """Signed private client intentionally incapable of mutating exchange state."""

    LEGACY_TAPI_URL = "https://indodax.com/tapi"
    TRADE_API_V2_URL = "https://tapi.indodax.com"

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        *,
        session: requests.Session | None = None,
        recv_window_ms: int = 5000,
        timeout_seconds: float = 10.0,
        max_attempts: int = 3,
        sleep_fn: Any = time.sleep,
        clock_ms: Any | None = None,
        legacy_tapi_url: str = LEGACY_TAPI_URL,
        trade_api_v2_url: str = TRADE_API_V2_URL,
    ) -> None:
        if not api_key or not secret_key:
            raise ValueError("INDODAX_READONLY_CREDENTIALS_REQUIRED")
        if recv_window_ms <= 0:
            raise ValueError("INVALID_RECV_WINDOW")
        if timeout_seconds <= 0:
            raise ValueError("INVALID_TIMEOUT")
        if max_attempts < 1:
            raise ValueError("INVALID_MAX_ATTEMPTS")

        self._api_key = api_key
        self._secret_key = secret_key
        self._session = session or requests.Session()
        self.recv_window_ms = recv_window_ms
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self._sleep_fn = sleep_fn
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self.legacy_tapi_url = legacy_tapi_url.rstrip("/")
        self.trade_api_v2_url = trade_api_v2_url.rstrip("/")
        self._timestamp_lock = Lock()
        self._last_timestamp_ms = 0

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(api_key=<redacted>, secret_key=<redacted>, "
            f"recv_window_ms={self.recv_window_ms})"
        )

    def _timestamp_ms(self) -> int:
        with self._timestamp_lock:
            current = int(self._clock_ms())
            if current <= 0:
                raise VenueReadError("INVALID_LOCAL_CLOCK")
            current = max(current, self._last_timestamp_ms + 1)
            self._last_timestamp_ms = current
            return current

    def _sign(self, encoded_params: str) -> str:
        return hmac.new(
            self._secret_key.encode("utf-8"),
            encoded_params.encode("utf-8"),
            hashlib.sha512,
        ).hexdigest()

    @staticmethod
    def _json_payload(response: Any) -> Mapping[str, Any]:
        try:
            payload = response.json()
        except (ValueError, TypeError) as exc:
            raise VenueProtocolError("INDODAX_RESPONSE_NOT_JSON") from exc
        if not isinstance(payload, Mapping):
            raise VenueProtocolError("INDODAX_RESPONSE_NOT_OBJECT")
        return payload

    @staticmethod
    def _raise_api_error(status_code: int, payload: Mapping[str, Any]) -> None:
        code = payload.get("error_code", payload.get("code", "unknown"))
        message = str(payload.get("error", payload.get("message", "request_failed")))
        marker = f"INDODAX_API_ERROR:http={status_code}:code={code}:message={message}"
        if status_code in {401, 403} or str(code) in {
            "1001",
            "1103",
            "1104",
            "1105",
            "1106",
            "invalid_credentials",
            "bad_sign",
        }:
            raise VenueAuthenticationError(marker)
        raise VenueReadError(marker)

    def _execute_request_with_retry(
        self,
        request_factory: Callable[[], tuple[str, str, Mapping[str, str], str | None]],
    ) -> Mapping[str, Any]:
        last_exception: Exception | None = None
        for attempt in range(self.max_attempts):
            method, url, headers, body = request_factory()
            try:
                response = self._session.request(
                    method,
                    url,
                    headers=dict(headers),
                    data=body,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                last_exception = exc
                if attempt + 1 < self.max_attempts:
                    self._sleep_fn(0.25 * (2**attempt))
                    continue
                raise VenueReadError("INDODAX_NETWORK_ERROR") from exc

            retryable = response.status_code == 429 or response.status_code >= 500
            try:
                payload = self._json_payload(response)
            except VenueProtocolError as exc:
                if retryable and attempt + 1 < self.max_attempts:
                    self._sleep_fn(0.25 * (2**attempt))
                    continue
                if retryable:
                    raise VenueReadError(
                        f"INDODAX_RETRYABLE_HTTP_NON_JSON:http={response.status_code}"
                    ) from exc
                raise

            if retryable and attempt + 1 < self.max_attempts:
                self._sleep_fn(0.25 * (2**attempt))
                continue
            if response.status_code >= 400:
                self._raise_api_error(response.status_code, payload)
            return payload

        raise VenueReadError("INDODAX_REQUEST_EXHAUSTED") from last_exception

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: str | None = None,
    ) -> Mapping[str, Any]:
        return self._execute_request_with_retry(lambda: (method, url, headers, body))

    def _legacy_view_call(
        self,
        method: str,
        params: Sequence[tuple[str, Any]] = (),
    ) -> Mapping[str, Any]:
        def _build_request() -> tuple[str, str, Mapping[str, str], str | None]:
            encoded = urlencode(
                [
                    ("method", method),
                    *[(key, str(value)) for key, value in params],
                    ("timestamp", str(self._timestamp_ms())),
                    ("recvWindow", str(self.recv_window_ms)),
                ]
            )
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Key": self._api_key,
                "Sign": self._sign(encoded),
            }
            return "POST", self.legacy_tapi_url, headers, encoded

        payload = self._execute_request_with_retry(_build_request)
        if payload.get("success") != 1:
            self._raise_api_error(200, payload)
        returned = payload.get("return")
        if not isinstance(returned, Mapping):
            raise VenueProtocolError("INDODAX_LEGACY_RETURN_MISSING")
        return returned

    def _v2_get(
        self,
        path: str,
        params: Sequence[tuple[str, Any]],
    ) -> list[Mapping[str, Any]]:
        def _build_request() -> tuple[str, str, Mapping[str, str], str | None]:
            encoded = urlencode(
                [
                    *[(key, str(value)) for key, value in params],
                    ("timestamp", str(self._timestamp_ms())),
                    ("recvWindow", str(self.recv_window_ms)),
                ]
            )
            url = f"{self.trade_api_v2_url}{path}?{encoded}"
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-APIKEY": self._api_key,
                "Sign": self._sign(encoded),
            }
            return "GET", url, headers, None

        payload = self._execute_request_with_retry(_build_request)
        if payload.get("error"):
            self._raise_api_error(200, payload)
        data = payload.get("data")
        if not isinstance(data, list) or any(not isinstance(row, Mapping) for row in data):
            raise VenueProtocolError("INDODAX_V2_DATA_INVALID")
        return list(data)

    def get_account_snapshot(self) -> VenueAccountSnapshot:
        """Read balances/holds using view-only getInfo."""

        returned = self._legacy_view_call("getInfo")
        available_raw = returned.get("balance")
        hold_raw = returned.get("balance_hold")
        if not isinstance(available_raw, Mapping) or not isinstance(hold_raw, Mapping):
            raise VenueProtocolError("INDODAX_BALANCE_PAYLOAD_INVALID")

        currencies = {str(key).lower() for key in available_raw} | {
            str(key).lower() for key in hold_raw
        }
        balances = {
            currency: VenueBalance(
                currency=currency,
                available=_decimal(available_raw.get(currency, 0), f"balance.{currency}"),
                hold=_decimal(hold_raw.get(currency, 0), f"balance_hold.{currency}"),
            )
            for currency in sorted(currencies)
        }
        return VenueAccountSnapshot(
            server_time=_utc_from_epoch(returned.get("server_time"), "server_time"),
            balances=balances,
        )

    def get_open_orders(self, pair: str) -> tuple[VenueOrder, ...]:
        """Read currently open orders for one canonical pair."""

        canonical_pair = _pair(pair)
        returned = self._legacy_view_call("openOrders", (("pair", canonical_pair),))
        rows = returned.get("orders")
        if not isinstance(rows, list):
            raise VenueProtocolError("INDODAX_OPEN_ORDERS_INVALID")
        return tuple(self._parse_legacy_open_order(canonical_pair, row) for row in rows)

    def get_order(self, pair: str, order_id: str) -> VenueOrder:
        """Read one order by venue order ID for UNKNOWN-state recovery."""

        canonical_pair = _pair(pair)
        if not order_id:
            raise ValueError("ORDER_ID_REQUIRED")
        returned = self._legacy_view_call(
            "getOrder",
            (("pair", canonical_pair), ("order_id", order_id)),
        )
        row = returned.get("order")
        if not isinstance(row, Mapping):
            raise VenueProtocolError("INDODAX_ORDER_INVALID")
        return self._parse_legacy_order(canonical_pair, row)

    def get_order_by_client_order_id(
        self,
        pair: str,
        client_order_id: str,
    ) -> VenueOrder:
        """Read one order by deterministic client order ID."""

        canonical_pair = _pair(pair)
        if not client_order_id:
            raise ValueError("CLIENT_ORDER_ID_REQUIRED")
        returned = self._legacy_view_call(
            "getOrderByClientOrderId",
            (("client_order_id", client_order_id),),
        )
        row = returned.get("order")
        if not isinstance(row, Mapping):
            raise VenueProtocolError("INDODAX_ORDER_INVALID")
        return self._parse_legacy_order(canonical_pair, row)

    def get_order_history(
        self,
        pair: str,
        *,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        limit: int = 100,
        sort: str = "desc",
    ) -> tuple[VenueOrder, ...]:
        """Read terminal order history from the current Trade API v2 endpoint."""

        canonical_pair = _pair(pair)
        _validate_time_window(start_time_ms, end_time_ms)
        if not 10 <= limit <= 1000:
            raise ValueError("ORDER_HISTORY_LIMIT_OUT_OF_RANGE")
        if sort not in {"asc", "desc"}:
            raise ValueError("INVALID_SORT")

        params: list[tuple[str, Any]] = [("symbol", _symbol(canonical_pair))]
        if start_time_ms is not None:
            params.append(("startTime", start_time_ms))
        if end_time_ms is not None:
            params.append(("endTime", end_time_ms))
        params.extend((("limit", limit), ("sort", sort)))

        rows = self._v2_get("/api/v2/order/histories", params)
        return tuple(self._parse_v2_order(canonical_pair, row) for row in rows)

    def get_trade_fills(
        self,
        pair: str,
        *,
        order_id: str | None = None,
        client_order_id: str | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        limit: int = 500,
        sort: str = "desc",
    ) -> tuple[VenueFill, ...]:
        """Read execution fills from the current Trade API v2 endpoint."""

        canonical_pair = _pair(pair)
        _validate_time_window(start_time_ms, end_time_ms)
        if order_id and client_order_id:
            raise ValueError("ORDER_ID_FILTERS_ARE_MUTUALLY_EXCLUSIVE")
        if not 10 <= limit <= 1000:
            raise ValueError("TRADE_HISTORY_LIMIT_OUT_OF_RANGE")
        if sort not in {"asc", "desc"}:
            raise ValueError("INVALID_SORT")

        params: list[tuple[str, Any]] = [("symbol", _symbol(canonical_pair))]
        if order_id:
            params.append(("orderId", order_id))
        if client_order_id:
            params.append(("clientOrderId", client_order_id))
        if start_time_ms is not None:
            params.append(("startTime", start_time_ms))
        if end_time_ms is not None:
            params.append(("endTime", end_time_ms))
        params.extend((("limit", limit), ("sort", sort)))

        rows = self._v2_get("/api/v2/myTrades", params)
        return tuple(self._parse_v2_fill(canonical_pair, row) for row in rows)

    @staticmethod
    def _parse_legacy_open_order(pair: str, row: Any) -> VenueOrder:
        if not isinstance(row, Mapping):
            raise VenueProtocolError("INDODAX_OPEN_ORDER_ROW_INVALID")
        side = _side(row.get("type"), "open_order.type")
        original, remaining = _legacy_order_quantities(
            pair,
            side,
            row,
            field_prefix="open_order",
        )
        if remaining > original:
            raise VenueProtocolError("INDODAX_OPEN_ORDER_REMAIN_EXCEEDS_ORIGINAL")
        return VenueOrder(
            order_id=_required_text(row.get("order_id"), "open_order.order_id"),
            client_order_id=(str(row["client_order_id"]) if row.get("client_order_id") else None),
            pair=pair,
            side=side,
            order_type=str(row.get("order_type", "limit")).lower(),
            status="OPEN",
            price=_decimal(row.get("price"), "open_order.price", positive=True),
            original_qty=original,
            executed_qty=original - remaining,
            remaining_qty=remaining,
            submitted_at=_utc_from_epoch(row.get("submit_time"), "submit_time"),
        )

    @staticmethod
    def _parse_legacy_order(pair: str, row: Mapping[str, Any]) -> VenueOrder:
        side = _side(row.get("type"), "order.type")
        original, remaining = _legacy_order_quantities(
            pair,
            side,
            row,
            field_prefix="order",
        )

        if remaining > original:
            raise VenueProtocolError("INDODAX_ORDER_REMAIN_EXCEEDS_ORIGINAL")
        finish_raw = row.get("finish_time")
        return VenueOrder(
            order_id=_required_text(row.get("order_id"), "order.order_id"),
            client_order_id=(str(row["client_order_id"]) if row.get("client_order_id") else None),
            pair=pair,
            side=side,
            order_type=str(row.get("order_type", "limit")).lower(),
            status=str(row.get("status", "UNKNOWN")).upper(),
            price=_decimal(row.get("price"), "order.price", positive=True),
            original_qty=original,
            executed_qty=original - remaining,
            remaining_qty=remaining,
            submitted_at=_utc_from_epoch(row.get("submit_time"), "submit_time"),
            finished_at=(
                _utc_from_epoch(finish_raw, "finish_time")
                if finish_raw and str(finish_raw).strip() not in ("", "0")
                else None
            ),
        )

    @staticmethod
    def _parse_v2_order(pair: str, row: Mapping[str, Any]) -> VenueOrder:
        if str(row.get("symbol", "")).lower() != _symbol(pair):
            raise VenueProtocolError("INDODAX_ORDER_SYMBOL_MISMATCH")
        original = _decimal(row.get("oriQty"), "order.oriQty")
        executed = _decimal(row.get("executedQty"), "order.executedQty")
        if executed > original:
            raise VenueProtocolError("INDODAX_ORDER_EXECUTED_EXCEEDS_ORIGINAL")
        finish_raw = row.get("finishTime")
        return VenueOrder(
            order_id=_required_text(row.get("orderId"), "order.orderId"),
            client_order_id=(str(row["clientOrderId"]) if row.get("clientOrderId") else None),
            pair=pair,
            side=_side(row.get("side"), "order.side"),
            order_type=str(row.get("type", "")).lower(),
            status=str(row.get("status", "")).upper(),
            price=_decimal(row.get("price"), "order.price"),
            original_qty=original,
            executed_qty=executed,
            remaining_qty=original - executed,
            submitted_at=_utc_from_epoch(row.get("submitTime"), "submitTime"),
            finished_at=(_utc_from_epoch(finish_raw, "finishTime") if finish_raw else None),
            cancel_reason=(str(row["cancelReason"]) if row.get("cancelReason") else None),
        )

    @staticmethod
    def _parse_v2_fill(pair: str, row: Mapping[str, Any]) -> VenueFill:
        if str(row.get("symbol", "")).lower() != _symbol(pair):
            raise VenueProtocolError("INDODAX_FILL_SYMBOL_MISMATCH")
        is_buyer = row.get("isBuyer")
        is_maker = row.get("isMaker")
        if not isinstance(is_buyer, bool) or not isinstance(is_maker, bool):
            raise VenueProtocolError("INDODAX_FILL_ROLE_INVALID")
        return VenueFill(
            fill_id=_required_text(row.get("tradeId"), "fill.tradeId"),
            order_id=_required_text(row.get("orderId"), "fill.orderId"),
            client_order_id=(str(row["clientOrderId"]) if row.get("clientOrderId") else None),
            pair=pair,
            side=OrderSide.BUY if is_buyer else OrderSide.SELL,
            role=OrderRole.MAKER if is_maker else OrderRole.TAKER,
            qty=_decimal(row.get("qty"), "fill.qty", positive=True),
            quote_qty=_decimal(row.get("quoteQty"), "fill.quoteQty"),
            price=_decimal(row.get("price"), "fill.price", positive=True),
            commission=_decimal(row.get("commission"), "fill.commission"),
            commission_asset=str(row.get("commissionAsset", "")).lower(),
            timestamp=_utc_from_epoch(row.get("time"), "fill.time"),
        )
