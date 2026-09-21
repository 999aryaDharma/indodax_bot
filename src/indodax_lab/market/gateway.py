"""Canonical market gateway orchestrating clock verification, data quality, and feed health."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import requests

from indodax_lab.contracts import CandleRecord
from indodax_lab.market.clock import ClockGuard, ClockReport
from indodax_lab.market.health import (
    MarketHealthReport,
    MarketHealthState,
)
from indodax_lab.market.quality import (
    DataQualityGuard,
    QualityValidationResult,
    TickerSnapshot,
)

logger = logging.getLogger("market.gateway")


@dataclass(frozen=True)
class MarketSnapshot:
    """Verified point-in-time market snapshot with attached health authority."""

    pair: str
    as_of_utc: datetime
    last_price: Decimal
    bid: Decimal
    ask: Decimal
    health: MarketHealthReport
    latest_closed_bar: CandleRecord | None = None
    high_24h: Decimal | None = None
    low_24h: Decimal | None = None
    volume_24h: Decimal | None = None

    @property
    def is_safe_for_trading(self) -> bool:
        """Determines whether this snapshot can authorize downstream trading decisions."""
        return not self.health.should_halt_new_orders


class MarketGateway:
    """Institutional-discipline market data gateway.

    Connects to exchange market endpoints, applies clock and quality guards,
    and returns authoritative MarketSnapshots with explicit health states.
    """

    def __init__(
        self,
        clock_guard: ClockGuard | None = None,
        quality_guard: DataQualityGuard | None = None,
        http_session: requests.Session | None = None,
        base_url: str = "https://indodax.com",
        request_timeout_seconds: float = 10.0,
        max_retries: int = 2,
    ) -> None:
        self.clock_guard = clock_guard or ClockGuard()
        self.quality_guard = quality_guard or DataQualityGuard()
        self.session = http_session or requests.Session()
        self.base_url = base_url.rstrip("/")
        self.request_timeout = float(request_timeout_seconds)
        self.max_retries = int(max_retries)

    def fetch_ticker_raw(
        self, pair: str
    ) -> tuple[dict[str, Any] | None, datetime, datetime | None]:
        """Fetch raw ticker from exchange with bounded retries and response header timestamp.

        Returns (payload, local_req_utc, venue_server_utc).
        """
        clean_pair = pair.replace("_", "").lower()
        url = f"{self.base_url}/api/ticker/{clean_pair}"
        local_utc = datetime.now(UTC)

        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=self.request_timeout)
                # Attempt to extract server date from HTTP header
                venue_server_utc = None
                date_hdr = resp.headers.get("Date")
                if date_hdr:
                    try:
                        from email.utils import parsedate_to_datetime
                        venue_server_utc = parsedate_to_datetime(date_hdr).astimezone(UTC)
                    except Exception:
                        venue_server_utc = None

                if resp.status_code == 200:
                    data = resp.json()
                    return data, local_utc, venue_server_utc
                elif resp.status_code == 429:
                    logger.warning("MarketGateway: Rate limited (429) fetching ticker for %s", pair)
                    return None, local_utc, venue_server_utc
                else:
                    logger.warning(
                        "MarketGateway: HTTP %d fetching ticker for %s", resp.status_code, pair
                    )
            except Exception as exc:
                logger.warning(
                    "MarketGateway: Attempt %d failed for %s: %s", attempt + 1, pair, exc
                )

        return None, local_utc, None

    def get_market_snapshot(
        self,
        pair: str,
        as_of_utc: datetime | None = None,
        ticker_override: TickerSnapshot | None = None,
        bar_override: CandleRecord | None = None,
    ) -> MarketSnapshot:
        """Produce an authoritative MarketSnapshot for a pair with comprehensive health analysis."""
        now_utc = as_of_utc or datetime.now(UTC)
        findings: list[str] = []

        # 1. Clock evaluation
        venue_time: datetime | None = None
        ticker_data: dict[str, Any] | None = None

        if ticker_override is None:
            ticker_data, local_time, venue_time = self.fetch_ticker_raw(pair)

        clock_report: ClockReport = self.clock_guard.check_clock(now_utc, reference_utc=venue_time)
        if not clock_report.is_safe:
            findings.append(clock_report.finding_code or "CLOCK_UNSAFE")
            health = MarketHealthReport(
                pair=pair,
                state=MarketHealthState.CLOCK_UNSAFE,
                as_of_utc=now_utc,
                clock_offset_ms=clock_report.offset_ms,
                findings=tuple(findings),
            )
            return MarketSnapshot(
                pair=pair,
                as_of_utc=now_utc,
                last_price=Decimal("0"),
                bid=Decimal("0"),
                ask=Decimal("0"),
                health=health,
            )

        # 2. Ticker resolution & validation
        ticker: TickerSnapshot | None = ticker_override
        if ticker is None:
            if ticker_data is None or "ticker" not in ticker_data:
                findings.append("VENUE_TICKER_UNAVAILABLE")
                health = MarketHealthReport(
                    pair=pair,
                    state=MarketHealthState.UNAVAILABLE,
                    as_of_utc=now_utc,
                    findings=tuple(findings),
                )
                return MarketSnapshot(
                    pair=pair,
                    as_of_utc=now_utc,
                    last_price=Decimal("0"),
                    bid=Decimal("0"),
                    ask=Decimal("0"),
                    health=health,
                )

            raw_t = ticker_data["ticker"]
            try:
                server_ts_int = int(raw_t.get("server_time", int(now_utc.timestamp())))
                ticker_ts = datetime.fromtimestamp(server_ts_int, tz=UTC)
                ticker = TickerSnapshot(
                    pair=pair,
                    bid=Decimal(str(raw_t["buy"])),
                    ask=Decimal(str(raw_t["sell"])),
                    last_price=Decimal(str(raw_t["last"])),
                    timestamp_utc=ticker_ts,
                    high_24h=Decimal(str(raw_t["high"])) if "high" in raw_t else None,
                    low_24h=Decimal(str(raw_t["low"])) if "low" in raw_t else None,
                    volume_24h=Decimal(str(raw_t.get("vol_idr", "0"))),
                )
            except Exception as exc:
                findings.append(f"TICKER_PARSE_ERROR_{exc}")
                health = MarketHealthReport(
                    pair=pair,
                    state=MarketHealthState.DEGRADED,
                    as_of_utc=now_utc,
                    findings=tuple(findings),
                )
                return MarketSnapshot(
                    pair=pair,
                    as_of_utc=now_utc,
                    last_price=Decimal("0"),
                    bid=Decimal("0"),
                    ask=Decimal("0"),
                    health=health,
                )

        # 3. Quality Guard validation of Ticker
        ticker_val: QualityValidationResult = self.quality_guard.validate_ticker(
            ticker, as_of_utc=now_utc
        )
        for finding in ticker_val.findings:
            findings.append(finding)

        # 4. Optional candle validation
        if bar_override is not None:
            bar_val: QualityValidationResult = self.quality_guard.validate_closed_bar(
                bar_override, as_of_utc=now_utc
            )
            for finding in bar_val.findings:
                findings.append(finding)

        # 5. Classify overall health state
        has_stale = any("STALE" in f for f in findings)
        has_critical = any(
            f in (
                "INVALID_BID_NON_POSITIVE",
                "INVALID_ASK_NON_POSITIVE",
                "CROSSED_MARKET_ASK_LESS_THAN_BID",
            )
            for f in findings
        )

        if has_stale:
            state = MarketHealthState.STALE
        elif has_critical:
            state = MarketHealthState.DEGRADED
        elif any(f.startswith("SPREAD_EXCEEDED") for f in findings):
            state = MarketHealthState.DEGRADED
        else:
            state = MarketHealthState.HEALTHY

        age_sec = (now_utc - ticker.timestamp_utc).total_seconds()
        health = MarketHealthReport(
            pair=pair,
            state=state,
            as_of_utc=now_utc,
            last_event_time_utc=ticker.timestamp_utc,
            age_seconds=max(0.0, age_sec),
            clock_offset_ms=clock_report.offset_ms,
            findings=tuple(findings),
        )

        return MarketSnapshot(
            pair=pair,
            as_of_utc=now_utc,
            last_price=ticker.last_price,
            bid=ticker.bid,
            ask=ticker.ask,
            health=health,
            latest_closed_bar=bar_override,
            high_24h=ticker.high_24h,
            low_24h=ticker.low_24h,
            volume_24h=ticker.volume_24h,
        )
