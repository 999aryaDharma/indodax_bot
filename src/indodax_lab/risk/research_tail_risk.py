"""Versioned Research-only tail-risk policy and causal evidence contracts."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _ensure_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return value


class ResearchTailRiskPolicy(BaseModel):
    """Approved, versioned thresholds for one Research risk-gate deployment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str | None = None
    version: str | None = None
    approved_by: str | None = None
    approval_ref: str | None = None
    evidence_source_id: str | None = None
    evidence_source_version: str | None = None
    max_pump_gap_fraction: Decimal | None = None
    max_amihud_24_1h: Decimal | None = None
    max_evidence_age_seconds: int | None = Field(default=None, gt=0, strict=True)

    @field_validator(
        "policy_id",
        "version",
        "approved_by",
        "approval_ref",
        "evidence_source_id",
        "evidence_source_version",
    )
    @classmethod
    def require_nonblank_identity(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("max_pump_gap_fraction", "max_amihud_24_1h", mode="before")
    @classmethod
    def parse_nonnegative_threshold(cls, value: Any) -> Decimal | None:
        if value is None:
            return None
        result = Decimal(str(value))
        if not result.is_finite() or result < 0:
            raise ValueError("NON_NEGATIVE_FINITE_THRESHOLD_REQUIRED")
        return result

    @property
    def is_approved_and_complete(self) -> bool:
        return all(
            value is not None
            for value in (
                self.policy_id,
                self.version,
                self.approved_by,
                self.approval_ref,
                self.evidence_source_id,
                self.evidence_source_version,
                self.max_pump_gap_fraction,
                self.max_amihud_24_1h,
                self.max_evidence_age_seconds,
            )
        )


class ResearchTailRiskEvidence(BaseModel):
    """Point-in-time evidence used only by an explicitly enabled Research gate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pair: str
    decision_ts: datetime
    event_at: datetime
    available_at: datetime
    risk_period_id: str
    source_id: str
    source_version: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pump_gap_fraction: Decimal | None = None
    amihud_24_1h: Decimal | None = None

    @field_validator("decision_ts", "event_at", "available_at")
    @classmethod
    def validate_utc(cls, value: datetime, info) -> datetime:
        return _ensure_utc(value, info.field_name)

    @field_validator("pair")
    @classmethod
    def normalize_pair(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("RESEARCH_TAIL_EVIDENCE_IDENTITY_REQUIRED")
        return value.lower()

    @field_validator("risk_period_id", "source_id", "source_version")
    @classmethod
    def require_identity(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("RESEARCH_TAIL_EVIDENCE_IDENTITY_REQUIRED")
        return value

    @field_validator("pump_gap_fraction", "amihud_24_1h", mode="before")
    @classmethod
    def parse_optional_measurement(cls, value: Any) -> Decimal | None:
        if value is None:
            return None
        result = Decimal(str(value))
        if not result.is_finite() or result < 0:
            raise ValueError("NON_NEGATIVE_FINITE_EVIDENCE_REQUIRED")
        return result
