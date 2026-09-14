"""Strict contracts for point-in-time universe policy, inputs, and decisions."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from indodax_lab.contracts import QualityStatus, UtcTimestamp
from indodax_lab.data.checksums import sha256_bytes

_PAIR = re.compile(r"^[a-z0-9]+_[a-z0-9]+$")
_ASSET = re.compile(r"^[a-z0-9]+$")
_IDENTITY = re.compile(r"^sha256:[0-9a-f]{64}$")


class UniverseTier(StrEnum):
    """Eligible point-in-time cap label, with an explicit cap-unavailable fallback."""

    BIG_CAP = "BIG_CAP"
    SMALL_CAP = "SMALL_CAP"
    LIQUIDITY_ONLY = "LIQUIDITY_ONLY"


class ReasonCode(StrEnum):
    """Stable audit reasons emitted by the pure eligibility classifier."""

    LISTING_TOO_YOUNG = "LISTING_TOO_YOUNG"
    ZERO_VOLUME_TOO_HIGH = "ZERO_VOLUME_TOO_HIGH"
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"
    DEPTH_TOO_LOW = "DEPTH_TOO_LOW"
    CAP_HISTORY_MISSING = "CAP_HISTORY_MISSING"
    DATA_QUALITY_FAIL = "DATA_QUALITY_FAIL"
    PAIR_INACTIVE = "PAIR_INACTIVE"
    PAIR_UNTRADABLE = "PAIR_UNTRADABLE"
    SOURCE_STALE = "SOURCE_STALE"
    SOURCE_AFTER_CUTOFF = "SOURCE_AFTER_CUTOFF"


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("decimal thresholds and metrics must not use binary float")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (str, int)):
        return Decimal(str(value))
    raise ValueError("value must be representable exactly as Decimal")


class TierPolicy(BaseModel):
    """One tier's complete listing and liquidity gates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    listing_age_days_min: int = Field(ge=1)
    zero_volume_ratio_30d_max: Decimal = Field(ge=0, le=1)
    median_spread_bps_7d_max: Decimal = Field(gt=0)
    depth_band_bps: Literal[10, 50]
    depth_to_order_multiple_min: Decimal = Field(gt=0)

    @field_validator(
        "zero_volume_ratio_30d_max",
        "median_spread_bps_7d_max",
        "depth_to_order_multiple_min",
        mode="before",
    )
    @classmethod
    def validate_decimal_threshold(cls, value: object) -> Decimal:
        return _decimal(value)


class UniversePolicy(BaseModel):
    """Versioned, fail-closed universe configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    cap_rank_boundary: int = Field(gt=0)
    cap_source: str = Field(min_length=1)
    cap_source_ttl_seconds: int = Field(gt=0)
    fallback_tier: Literal[UniverseTier.LIQUIDITY_ONLY]
    big: TierPolicy
    small: TierPolicy


class LoadedUniversePolicy(BaseModel):
    """Validated policy plus the exact YAML byte identity used by a snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy: UniversePolicy
    source_id: str

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        if not _IDENTITY.fullmatch(value):
            raise ValueError("policy source_id must be a sha256 identity")
        return value


class UniverseMetrics(BaseModel):
    """All point-in-time facts needed by the pure classifier; no provider calls."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    as_of_date: date
    pair: str
    asset: str
    quote_asset: str
    listed_at: UtcTimestamp
    active: bool
    tradable: bool
    median_quote_volume_30d: Decimal = Field(ge=0)
    median_spread_bps_7d: Decimal = Field(ge=0)
    depth_10bps: Decimal = Field(ge=0)
    depth_50bps: Decimal = Field(ge=0)
    simulated_order_quote: Decimal = Field(gt=0)
    zero_volume_ratio_30d: Decimal = Field(ge=0, le=1)
    quality_status: QualityStatus
    liquidity_available_at: UtcTimestamp
    source: str = Field(min_length=1)
    source_input_id: str
    additional_source_input_ids: tuple[str, ...] = ()
    market_cap_usd: Decimal | None = Field(default=None, gt=0)
    market_cap_rank: int | None = Field(default=None, gt=0)
    cap_source_ts: UtcTimestamp | None = None
    cap_available_at: UtcTimestamp | None = None
    cap_expires_at: UtcTimestamp | None = None
    cap_source: str | None = None
    cap_input_id: str | None = None

    @field_validator("pair")
    @classmethod
    def validate_pair(cls, value: str) -> str:
        if not _PAIR.fullmatch(value):
            raise ValueError("pair must use canonical lowercase underscore form")
        return value

    @field_validator("asset", "quote_asset")
    @classmethod
    def validate_asset(cls, value: str) -> str:
        if not _ASSET.fullmatch(value):
            raise ValueError("asset must be lowercase alphanumeric")
        return value

    @field_validator(
        "median_quote_volume_30d",
        "median_spread_bps_7d",
        "depth_10bps",
        "depth_50bps",
        "simulated_order_quote",
        "zero_volume_ratio_30d",
        "market_cap_usd",
        mode="before",
    )
    @classmethod
    def validate_decimal_metric(cls, value: object) -> Decimal | None:
        if value is None:
            return None
        return _decimal(value)

    @field_validator("source_input_id", "cap_input_id", mode="before")
    @classmethod
    def validate_input_id(cls, value: str | None) -> str | None:
        if value is not None and not _IDENTITY.fullmatch(value):
            raise ValueError("input IDs must use sha256:<64 lowercase hex>")
        return value

    @field_validator("additional_source_input_ids")
    @classmethod
    def validate_additional_input_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)) or any(not _IDENTITY.fullmatch(item) for item in value):
            raise ValueError("additional input IDs must be unique sha256 identities")
        return tuple(sorted(value))


class UniverseDecision(BaseModel):
    """One immutable `silver_universe_v1` decision row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    as_of_date: date
    pair: str
    asset: str
    quote_asset: str
    listed_at: UtcTimestamp
    listing_age_days: int
    market_cap_usd: Decimal | None
    market_cap_rank: int | None
    cap_source_ts: UtcTimestamp | None
    median_quote_volume_30d: Decimal
    median_spread_bps_7d: Decimal
    depth_10bps: Decimal
    depth_50bps: Decimal
    zero_volume_ratio_30d: Decimal
    tier: UniverseTier | None
    eligible: bool
    reason_codes: tuple[ReasonCode, ...]
    available_at: UtcTimestamp
    source: str
    source_input_ids: tuple[str, ...]


def load_universe_policy(path: Path) -> LoadedUniversePolicy:
    """Parse exact YAML bytes with strict unknown-field and threshold validation."""
    raw = Path(path).read_bytes()
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict):
        raise ValueError("universe policy YAML must contain one mapping")
    policy = UniversePolicy.model_validate(parsed)
    return LoadedUniversePolicy(policy=policy, source_id=f"sha256:{sha256_bytes(raw)}")
