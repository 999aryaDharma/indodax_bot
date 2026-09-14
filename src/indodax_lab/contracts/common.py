"""Common canonical identity, time, and quality contracts."""

import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, field_validator

_CANONICAL_PAIR = re.compile(r"^[a-z0-9]+_[a-z0-9]+$")


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must use UTC")
    return value.astimezone(UTC)


UtcTimestamp = Annotated[datetime, AfterValidator(_require_utc)]


class QualityStatus(StrEnum):
    """Quality gate outcome attached to every curated market record."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    QUARANTINED = "QUARANTINED"


class AggressorSide(StrEnum):
    """Source-provided direction of a public trade; adapters must not infer it."""

    BUY = "BUY"
    SELL = "SELL"
    UNKNOWN = "UNKNOWN"


class CanonicalPair(BaseModel):
    """Internal market identity, always lowercase and separated by an underscore."""

    model_config = ConfigDict(frozen=True)

    pair: str

    @field_validator("pair")
    @classmethod
    def validate_pair(cls, value: str) -> str:
        if not _CANONICAL_PAIR.fullmatch(value):
            raise ValueError("pair must use lowercase underscore form, for example btc_idr")
        return value

    @classmethod
    def from_venue_symbol(cls, venue_symbol: str, *, quote_asset: str = "idr") -> "CanonicalPair":
        """Adapt an exchange symbol at the boundary without weakening core validation."""
        compact_symbol = venue_symbol.strip().lower().replace("_", "").replace("-", "")
        quote = quote_asset.lower()
        if not quote or not compact_symbol.endswith(quote) or compact_symbol == quote:
            raise ValueError("venue symbol must contain a base asset followed by the quote asset")
        return cls(pair=f"{compact_symbol[: -len(quote)]}_{quote}")
