"""Job definitions, records, and status enums for durable research queue (JOB-01).

Contract:
SQLite WAL local queue: PENDING/RUNNING/SUCCESS/FAILED_RETRYABLE/FAILED_FINAL/BLOCKED_DATA/BLOCKED_POLICY/CANCELLED/STALE.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class JobStatus(StrEnum):
    """Lifecycle statuses for background research jobs."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"
    BLOCKED_DATA = "BLOCKED_DATA"
    BLOCKED_POLICY = "BLOCKED_POLICY"
    CANCELLED = "CANCELLED"
    STALE = "STALE"


class LeaseFencingError(RuntimeError):
    """Raised when a worker attempts to update a job with an obsolete/fenced lease generation."""


class PartialArtifactError(ValueError):
    """Raised when a job result artifact is missing, empty, or checksum fails."""


class JobDefinition(BaseModel):
    """Immutable submission definition for a durable background job."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str
    job_type: str
    recipe_hash: str
    input_ids: list[str]
    cadence_window: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = 3
    lease_duration_seconds: int = 60
    created_at: datetime

    @field_validator("created_at", mode="after")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "created_at")


class JobRecord(BaseModel):
    """Persisted job state in SQLite queue with generation lease fencing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str
    job_type: str
    status: JobStatus
    owner_id: str | None = None
    generation: int = 0
    attempts: int = 0
    max_attempts: int = 3
    lease_duration_seconds: int = 60
    lease_expires_at: datetime | None = None
    result_artifact_path: str | None = None
    result_artifact_hash: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", mode="after")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "timestamp")

    @field_validator("lease_expires_at", mode="after")
    @classmethod
    def validate_lease_expires(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            return _ensure_utc(value, "lease_expires_at")
        return None
