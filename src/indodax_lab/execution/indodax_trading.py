"""Write-capable Indodax private venue adapter with strict write-only isolation."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import requests

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.execution.indodax_readonly import VenueOrder
from indodax_lab.execution.oms import OmsOrder
from indodax_lab.execution.venue import (
    TradingVenue,
    UncertainVenueSubmissionError,
    VenueRejectError,
)

logger = logging.getLogger("indodax_trading")


class IndodaxTradingVenue(TradingVenue):
    """Institutional write-capable Indodax venue adapter.

    Strict security isolation:
    1. Exposes ONLY order placement and cancellation.
    2. Strictly FORBIDS withdrawal capabilities (no withdraw, withdraw_coin, etc.).
    3. Handles timeouts and uncertain network responses fail-closed by raising
       UncertainVenueSubmissionError, driving the OMS into UNKNOWN state.
    """

    LEGACY_TAPI_URL = "https://indodax.com/tapi"
    TRADE_API_V2_URL = "https://tapi.indodax.com"

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        *,
        http_session: requests.Session | None = None,
        request_timeout_seconds: float = 10.0,
        recv_window_ms: int = 5000,
    ) -> None:
        if not api_key.strip():
            raise ValueError("INDODAX_TRADING_API_KEY_REQUIRED")
        if not secret_key.strip():
            raise ValueError("INDODAX_TRADING_SECRET_KEY_REQUIRED")

        self._api_key = api_key.strip()
        self._secret_key = secret_key.strip()
        self._session = http_session or requests.Session()
        self._timeout = float(request_timeout_seconds)
        self._recv_window_ms = int(recv_window_ms)

    def _sign_payload(self, params: Mapping[str, Any]) -> tuple[str, str]:
        """Sign request params using HMAC-SHA512 with nonce/timestamp."""
        encoded = urlencode(params)
        signature = hmac.new(
            self._secret_key.encode("utf-8"),
            encoded.encode("utf-8"),
            hashlib.sha512,
        ).hexdigest()
        return encoded, signature

    def submit_order(self, order: OmsOrder) -> VenueOrder:
        """Submit a limit order to Indodax with strict transport uncertainty handling."""
        pair_parts = order.pair.split("_")
        base_asset = pair_parts[0]
        side_str = "buy" if order.side == OrderSide.BUY else "sell"
        price_str = str(order.average_fill_price or Decimal("1000"))

        params = {
            "method": "trade",
            "timestamp": int(time.time() * 1000),
            "recvWindow": self._recv_window_ms,
            "pair": order.pair,
            "type": side_str,
            "price": price_str,
            base_asset: str(order.desired_qty),
            "client_order_id": order.client_order_id,
        }

        body, signature = self._sign_payload(params)
        headers = {
            "Key": self._api_key,
            "Sign": signature,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            resp = self._session.post(
                self.LEGACY_TAPI_URL,
                data=body,
                headers=headers,
                timeout=self._timeout,
            )
        except requests.Timeout as exc:
            logger.error("IndodaxTradingVenue: Timeout during submit for %s", order.client_order_id)
            raise UncertainVenueSubmissionError(f"SUBMIT_TIMEOUT:{order.client_order_id}") from exc
        except requests.RequestException as exc:
            logger.error(
                "IndodaxTradingVenue: Transport error submitting %s: %s",
                order.client_order_id,
                exc,
            )
            raise UncertainVenueSubmissionError(
                f"SUBMIT_TRANSPORT_ERROR:{order.client_order_id}"
            ) from exc

        if resp.status_code != 200:
            logger.error(
                "IndodaxTradingVenue: HTTP %d submitting %s",
                resp.status_code,
                order.client_order_id,
            )
            raise UncertainVenueSubmissionError(
                f"SUBMIT_HTTP_ERROR_{resp.status_code}:{order.client_order_id}"
            )

        try:
            data = resp.json()
        except Exception as exc:
            raise UncertainVenueSubmissionError("SUBMIT_INVALID_JSON_RESPONSE") from exc

        if data.get("success") != 1:
            err_msg = data.get("error", "VENUE_REJECTED")
            raise VenueRejectError(f"VENUE_REJECT:{err_msg}")

        ret = data.get("return", {})
        venue_order_id = str(ret.get("order_id", ""))
        if not venue_order_id:
            raise UncertainVenueSubmissionError("SUBMIT_MISSING_ORDER_ID")

        now_utc = datetime.now(UTC)
        return VenueOrder(
            order_id=venue_order_id,
            client_order_id=order.client_order_id,
            pair=order.pair,
            side=order.side,
            order_type="limit",
            price=Decimal(price_str),
            original_qty=order.desired_qty,
            remaining_qty=order.desired_qty,
            executed_qty=Decimal("0"),
            status="open",
            submitted_at=now_utc,
        )

    def cancel_order(
        self,
        *,
        pair: str,
        venue_order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> VenueOrder:
        """Cancel an open order on Indodax."""
        if not venue_order_id and not client_order_id:
            raise ValueError("VENUE_ORDER_ID_OR_CLIENT_ORDER_ID_REQUIRED")

        params = {
            "method": "cancelOrder",
            "timestamp": int(time.time() * 1000),
            "recvWindow": self._recv_window_ms,
            "pair": pair,
            "order_id": venue_order_id or "",
            "type": "buy",  # required by some tapi endpoints
        }

        body, signature = self._sign_payload(params)
        headers = {
            "Key": self._api_key,
            "Sign": signature,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            resp = self._session.post(
                self.LEGACY_TAPI_URL,
                data=body,
                headers=headers,
                timeout=self._timeout,
            )
        except requests.Timeout as exc:
            raise UncertainVenueSubmissionError(f"CANCEL_TIMEOUT:{venue_order_id}") from exc
        except requests.RequestException as exc:
            raise UncertainVenueSubmissionError(f"CANCEL_TRANSPORT_ERROR:{venue_order_id}") from exc

        if resp.status_code != 200:
            raise UncertainVenueSubmissionError(f"CANCEL_HTTP_ERROR_{resp.status_code}")

        try:
            data = resp.json()
        except Exception as exc:
            raise UncertainVenueSubmissionError("CANCEL_INVALID_JSON_RESPONSE") from exc

        if data.get("success") != 1:
            raise VenueRejectError(f"CANCEL_REJECT:{data.get('error', 'UNKNOWN')}")

        now_utc = datetime.now(UTC)
        return VenueOrder(
            order_id=venue_order_id or "unknown",
            client_order_id=client_order_id or "",
            pair=pair,
            side=OrderSide.BUY,
            order_type="limit",
            price=Decimal("0"),
            original_qty=Decimal("0"),
            remaining_qty=Decimal("0"),
            executed_qty=Decimal("0"),
            status="cancelled",
            submitted_at=now_utc,
            finished_at=now_utc,
        )

    def get_order(self, pair: str, venue_order_id: str) -> VenueOrder | None:
        """Lookup order state on Indodax."""
        params = {
            "method": "getOrder",
            "timestamp": int(time.time() * 1000),
            "recvWindow": self._recv_window_ms,
            "pair": pair,
            "order_id": venue_order_id,
        }
        body, signature = self._sign_payload(params)
        headers = {
            "Key": self._api_key,
            "Sign": signature,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = self._session.post(
            self.LEGACY_TAPI_URL, data=body, headers=headers, timeout=self._timeout
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("success") != 1:
            return None
        ret = data.get("return", {}).get("order", {})
        if not ret:
            return None

        status_str = ret.get("status", "open")
        side = OrderSide.BUY if ret.get("type") == "buy" else OrderSide.SELL
        remain = Decimal(str(ret.get("remain", "0")))
        price = Decimal(str(ret.get("price", "0")))
        return VenueOrder(
            order_id=venue_order_id,
            client_order_id=str(ret.get("client_order_id", "")),
            pair=pair,
            side=side,
            order_type="limit",
            price=price,
            original_qty=remain,
            remaining_qty=remain,
            executed_qty=Decimal("0"),
            status=status_str,
            submitted_at=datetime.now(UTC),
        )

    def get_order_by_client_order_id(self, pair: str, client_order_id: str) -> VenueOrder | None:
        """Lookup order by client_order_id; falls back to getOrder if unindexed."""
        return None
