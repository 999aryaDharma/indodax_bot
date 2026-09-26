"""Versioned queue evidence contract for research execution qualification."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field}")
    return value


class QueueEvidencePolicy(BaseModel):
    """Explicitly approved freshness policy; no operational default is implied."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    approval_ref: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    max_evidence_age_seconds: Decimal = Field(gt=0)


class QueueEvidence(BaseModel):
    """Point-in-time queue observation, including explicit unavailable rows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["lob_queue_v1"] = "lob_queue_v1"
    pair: str = Field(min_length=1)
    event_at: datetime
    available_at: datetime
    observed_at: datetime
    session_id: str | None
    sequence_contiguous: bool | None
    book_imbalance_l5: Decimal | None = Field(default=None, ge=-1, le=1)
    depth_bid_10bps_idr: Decimal | None = Field(default=None, ge=0)
    depth_ask_10bps_idr: Decimal | None = Field(default=None, ge=0)
    spread_bps: Decimal | None = Field(default=None, ge=0)
    queue_ahead_base_qty: Decimal | None = Field(default=None, ge=0)
    status: Literal["known", "unknown"]
    source_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("pair", mode="before")
    @classmethod
    def normalize_pair(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("QUEUE_PAIR_STRING_REQUIRED")
        return value.strip().lower()

    @field_validator("event_at", "available_at", "observed_at")
    @classmethod
    def require_utc(cls, value: datetime, info) -> datetime:
        return _utc(value, info.field_name)

    @model_validator(mode="after")
    def validate_known_evidence(self) -> QueueEvidence:
        if self.status == "known" and (
            self.session_id is None
            or self.sequence_contiguous is None
            or self.book_imbalance_l5 is None
            or self.depth_bid_10bps_idr is None
            or self.depth_ask_10bps_idr is None
            or self.spread_bps is None
            or self.queue_ahead_base_qty is None
        ):
            raise ValueError("KNOWN_QUEUE_EVIDENCE_INCOMPLETE")
        if self.available_at < self.event_at:
            raise ValueError("QUEUE_AVAILABILITY_PRECEDES_EVENT")
        if self.observed_at < self.available_at:
            raise ValueError("QUEUE_OBSERVATION_PRECEDES_AVAILABILITY")
        return self


class QueueQualificationReport(BaseModel):
    """Run-level evidence summary bound into explicit promotion approval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    report_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    candidate_version: str = Field(min_length=1)
    policy: QueueEvidencePolicy
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sample_count: int = Field(gt=0)
    unavailable_count: int = Field(ge=0)
    stale_count: int = Field(ge=0)
    future_count: int = Field(ge=0)
    sequence_invalid_count: int = Field(ge=0)
    max_observed_age_seconds: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def counts_fit_sample_total(self) -> QueueQualificationReport:
        counts = (
            self.unavailable_count
            + self.stale_count
            + self.future_count
            + self.sequence_invalid_count
        )
        if counts > self.sample_count:
            raise ValueError("QUEUE_FAILURE_COUNTS_EXCEED_SAMPLE_COUNT")
        return self

    def failure_reason(self, candidate_id: str, candidate_version: str) -> str | None:
        if (self.candidate_id, self.candidate_version) != (candidate_id, candidate_version):
            return "QUEUE_CANDIDATE_MISMATCH"
        if any((self.unavailable_count, self.stale_count, self.future_count)):
            return "QUEUE_EVIDENCE_INCOMPLETE"
        if self.sequence_invalid_count:
            return "QUEUE_SEQUENCE_INVALID"
        if self.max_observed_age_seconds > self.policy.max_evidence_age_seconds:
            return "QUEUE_EVIDENCE_STALE"
        return None


def queue_evidence_failure_reason(
    evidence: QueueEvidence | None,
    policy: QueueEvidencePolicy | None,
    *,
    decision_time: datetime,
    expected_pair: str | None = None,
) -> str | None:
    """Return a stable fail-closed reason, or None when queue evidence is usable."""
    _utc(decision_time, "decision_time")
    if evidence is None:
        return "QUEUE_UNAVAILABLE"
    if policy is None:
        return "QUEUE_POLICY_MISSING"
    if evidence.status != "known":
        return "QUEUE_UNAVAILABLE"
    if expected_pair is not None and evidence.pair != expected_pair.strip().lower():
        return "QUEUE_PAIR_MISMATCH"
    if evidence.source_id != policy.source_id or evidence.source_version != policy.source_version:
        return "QUEUE_SOURCE_MISMATCH"
    if (
        evidence.event_at > decision_time
        or evidence.available_at > decision_time
        or evidence.observed_at > decision_time
    ):
        return "QUEUE_EVIDENCE_NOT_CAUSAL"
    if evidence.sequence_contiguous is not True:
        return "QUEUE_SEQUENCE_INVALID"
    age = Decimal(str((decision_time - evidence.observed_at).total_seconds()))
    if age > policy.max_evidence_age_seconds:
        return "QUEUE_EVIDENCE_STALE"
    return None
