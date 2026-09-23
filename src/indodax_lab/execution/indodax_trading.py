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
from indodax_lab.execution.indodax_readonly import IndodaxReadOnlyClient, VenueOrder
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
        if order.limit_price is None or order.limit_price <= Decimal("0"):
            raise ValueError(
                f"UNSUPPORTED_ORDER_SEMANTICS:ORDER_LIMIT_PRICE_REQUIRED:"
                f"{order.client_order_id} - "
                "Production Indodax venue requires order_type=limit and positive limit_price"
            )
        if order.order_type.lower() != "limit" or str(order.time_in_force).upper() != "GTC":
            raise ValueError(
                f"UNSUPPORTED_ORDER_SEMANTICS:{order.order_type}:{order.time_in_force} - "
                "Production Indodax venue requires order_type=limit and time_in_force=GTC"
            )

        pair_parts = order.pair.split("_")
        base_asset = pair_parts[0]
        side_str = "buy" if order.side == OrderSide.BUY else "sell"
        price_str = str(order.limit_price)

        params = {
            "method": "trade",
            "timestamp": int(time.time() * 1000),
            "recvWindow": self._recv_window_ms,
            "pair": order.pair,
            "type": side_str,
            "price": price_str,
            base_asset: str(order.desired_qty),
            "order_type": "limit",
            "time_in_force": "GTC",
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
        side: OrderSide | str | None = None,
    ) -> VenueOrder:
        """Cancel an open order on Indodax with exact side and ID routing."""
        if not venue_order_id and not client_order_id:
            raise ValueError("VENUE_ORDER_ID_OR_CLIENT_ORDER_ID_REQUIRED")

        side_str = (
            "buy"
            if (side == OrderSide.BUY or str(side).lower() == "buy")
            else ("sell" if (side == OrderSide.SELL or str(side).lower() == "sell") else None)
        )

        if side_str is None:
            existing = None
            if venue_order_id:
                existing = self.get_order(pair, venue_order_id)
            if existing is None and client_order_id:
                existing = self.get_order_by_client_order_id(pair, client_order_id)
            if existing is not None:
                side_str = "buy" if existing.side == OrderSide.BUY else "sell"
            else:
                side_str = "buy"

        if venue_order_id:
            params = {
                "method": "cancelOrder",
                "timestamp": int(time.time() * 1000),
                "recvWindow": self._recv_window_ms,
                "pair": pair,
                "order_id": venue_order_id,
                "type": side_str,
            }
        else:
            params = {
                "method": "cancelByClientOrderId",
                "timestamp": int(time.time() * 1000),
                "recvWindow": self._recv_window_ms,
                "pair": pair,
                "client_order_id": client_order_id or "",
                "type": side_str,
            }

        body, signature = self._sign_payload(params)
        headers = {
            "Key": self._api_key,
            "Sign": signature,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        target_id = venue_order_id or client_order_id
        try:
            resp = self._session.post(
                self.LEGACY_TAPI_URL,
                data=body,
                headers=headers,
                timeout=self._timeout,
            )
        except requests.Timeout as exc:
            raise UncertainVenueSubmissionError(f"CANCEL_TIMEOUT:{target_id}") from exc
        except requests.RequestException as exc:
            raise UncertainVenueSubmissionError(f"CANCEL_TRANSPORT_ERROR:{target_id}") from exc

        if resp.status_code != 200:
            raise UncertainVenueSubmissionError(f"CANCEL_HTTP_ERROR_{resp.status_code}")

        try:
            data = resp.json()
        except Exception as exc:
            raise UncertainVenueSubmissionError("CANCEL_INVALID_JSON_RESPONSE") from exc

        if data.get("success") != 1:
            raise VenueRejectError(f"CANCEL_REJECT:{data.get('error', 'UNKNOWN')}")

        # Query ground truth after cancel to capture partial fills during race
        final_order = None
        if venue_order_id:
            final_order = self.get_order(pair, venue_order_id)
        if final_order is None and client_order_id:
            final_order = self.get_order_by_client_order_id(pair, client_order_id)

        if final_order is not None:
            return final_order

        # Fail-closed: If cancel succeeded on exchange but post-cancel lookup is inconclusive,
        # DO NOT synthesize a fake 0-fill CANCELLED order. Raise UncertainVenueSubmissionError
        # so OMS transitions to UNKNOWN until exchange truth is reconciled.
        raise UncertainVenueSubmissionError(
            f"CANCEL_ACKNOWLEDGED_BUT_STATE_INCONCLUSIVE:{target_id}"
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
        try:
            resp = self._session.post(
                self.LEGACY_TAPI_URL, data=body, headers=headers, timeout=self._timeout
            )
        except Exception as exc:
            logger.warning("getOrder transport error: %s", exc)
            return None

        if resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except Exception:
            return None
        if data.get("success") != 1:
            return None
        ret = data.get("return", {}).get("order", {})
        if not ret:
            return None

        try:
            return IndodaxReadOnlyClient._parse_legacy_order(pair, ret)
        except Exception as exc:
            logger.warning("getOrder parsing error: %s", exc)
            return None

    def get_order_by_client_order_id(self, pair: str, client_order_id: str) -> VenueOrder | None:
        """Lookup order state on Indodax by client_order_id."""
        if not client_order_id:
            return None
        params = {
            "method": "getOrderByClientOrderId",
            "timestamp": int(time.time() * 1000),
            "recvWindow": self._recv_window_ms,
            "pair": pair,
            "client_order_id": client_order_id,
        }
        body, signature = self._sign_payload(params)
        headers = {
            "Key": self._api_key,
            "Sign": signature,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            resp = self._session.post(
                self.LEGACY_TAPI_URL, data=body, headers=headers, timeout=self._timeout
            )
        except Exception as exc:
            logger.warning("getOrderByClientOrderId transport error: %s", exc)
            return None

        if resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except Exception:
            return None
        if data.get("success") != 1:
            return None
        ret = data.get("return", {}).get("order", {})
        if not ret:
            return None

        try:
            return IndodaxReadOnlyClient._parse_legacy_order(pair, ret)
        except Exception as exc:
            logger.warning("getOrderByClientOrderId parsing error: %s", exc)
            return None


IndodaxTradingClient = IndodaxTradingVenue
