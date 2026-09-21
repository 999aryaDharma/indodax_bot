"""Data quality guard for market data validation and sanity checking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from indodax_lab.contracts import CandleRecord


@dataclass(frozen=True)
class TickerSnapshot:
    """Sanitized, decimal-authoritative price ticker."""

    pair: str
    bid: Decimal
    ask: Decimal
    last_price: Decimal
    timestamp_utc: datetime
    high_24h: Decimal | None = None
    low_24h: Decimal | None = None
    volume_24h: Decimal | None = None


@dataclass(frozen=True)
class QualityValidationResult:
    """Result of validating a market event or series."""

    is_valid: bool
    findings: tuple[str, ...] = field(default_factory=tuple)
    detail: str = ""


class DataQualityGuard:
    """Validates real-time market data sanity, closed-bar correctness, and gap detection."""

    def __init__(
        self,
        max_ticker_age_seconds: float = 60.0,
        max_bar_age_seconds: float = 7200.0,  # 2 hours for 1h candles
        max_spread_fraction: Decimal = Decimal("0.05"),  # 5% max bid-ask spread
    ) -> None:
        self.max_ticker_age_seconds = float(max_ticker_age_seconds)
        self.max_bar_age_seconds = float(max_bar_age_seconds)
        self.max_spread_fraction = max_spread_fraction
        self._last_bar_end_by_pair_interval: dict[tuple[str, str], datetime] = {}

    def validate_ticker(
        self,
        ticker: TickerSnapshot,
        as_of_utc: datetime,
    ) -> QualityValidationResult:
        """Sanity check ticker prices, spread, and timeliness."""
        findings: list[str] = []

        # 1. Non-negativity and strictly positive prices
        if ticker.bid <= 0:
            findings.append("INVALID_BID_NON_POSITIVE")
        if ticker.ask <= 0:
            findings.append("INVALID_ASK_NON_POSITIVE")
        if ticker.last_price <= 0:
            findings.append("INVALID_LAST_PRICE_NON_POSITIVE")

        # 2. Inverted book / crossed market
        if ticker.ask < ticker.bid:
            findings.append("CROSSED_MARKET_ASK_LESS_THAN_BID")
        elif ticker.bid > 0:
            spread = (ticker.ask - ticker.bid) / ticker.bid
            if spread > self.max_spread_fraction:
                findings.append(f"SPREAD_EXCEEDED_THRESHOLD_{spread:.4f}")

        # 3. Staleness
        age_seconds = (as_of_utc - ticker.timestamp_utc).total_seconds()
        if age_seconds < -2.0:
            findings.append("TICKER_TIMESTAMP_IN_FUTURE")
        elif age_seconds > self.max_ticker_age_seconds:
            findings.append(f"STALE_TICKER_AGE_{age_seconds:.1f}S")

        is_valid = len(findings) == 0
        return QualityValidationResult(
            is_valid=is_valid,
            findings=tuple(findings),
            detail="; ".join(findings) if findings else "Ticker valid",
        )

    def validate_closed_bar(
        self,
        bar: CandleRecord,
        as_of_utc: datetime,
        interval_seconds: int = 3600,
    ) -> QualityValidationResult:
        """Validate candle integrity, strictly enforcing closed-bar semantics."""
        findings: list[str] = []

        # 1. OHLC numeric invariants
        if bar.open <= 0 or bar.high <= 0 or bar.low <= 0 or bar.close <= 0 or bar.base_volume < 0:
            findings.append("INVALID_CANDLE_NEGATIVE_OR_ZERO_PRICE")

        if bar.high < bar.low:
            findings.append("INVALID_CANDLE_HIGH_LESS_THAN_LOW")
        if bar.high < bar.open or bar.high < bar.close:
            findings.append("INVALID_CANDLE_HIGH_NOT_SUPREMUM")
        if bar.low > bar.open or bar.low > bar.close:
            findings.append("INVALID_CANDLE_LOW_NOT_INFIMUM")

        # 2. Closed-bar correctness: bar end timestamp must not exceed as_of_utc
        bar_start = bar.open_time.astimezone(UTC)
        bar_end = bar.close_time.astimezone(UTC)
        if not bar.is_closed or bar_end > as_of_utc:
            findings.append("CANDLE_NOT_CLOSED_YET")

        # 3. Staleness
        bar_age_seconds = (as_of_utc - bar_end).total_seconds()
        if bar_age_seconds > self.max_bar_age_seconds:
            findings.append(f"STALE_CANDLE_AGE_{bar_age_seconds:.1f}S")

        # 4. Sequence checks: duplicate & out-of-order detection
        pair_key = (bar.pair.pair, bar.interval)
        last_end = self._last_bar_end_by_pair_interval.get(pair_key)
        if last_end is not None:
            if bar_end == last_end:
                findings.append("DUPLICATE_CANDLE_TIMESTAMP")
            elif bar_end < last_end:
                findings.append("OUT_OF_ORDER_CANDLE_TIMESTAMP")
            elif bar_start > last_end:
                gap_seconds = (bar_start - last_end).total_seconds()
                findings.append(f"MISSING_CANDLE_INTERVAL_GAP_{gap_seconds:.0f}S")

        has_seq_err = (
            "DUPLICATE_CANDLE_TIMESTAMP" in findings or "OUT_OF_ORDER_CANDLE_TIMESTAMP" in findings
        )
        if not has_seq_err:
            self._last_bar_end_by_pair_interval[pair_key] = bar_end

        is_valid = len(findings) == 0
        return QualityValidationResult(
            is_valid=is_valid,
            findings=tuple(findings),
            detail="; ".join(findings) if findings else "Candle valid",
        )
