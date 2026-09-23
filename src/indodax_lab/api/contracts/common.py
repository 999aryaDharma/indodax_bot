"""Shared, immutable API response and request contracts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from indodax_lab.api.capabilities import Capability

T = TypeVar("T")


def _reject_non_finite_decimals(value: Any) -> None:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("decimal values must be finite")
    elif isinstance(value, BaseModel):
        _reject_non_finite_decimals(value.model_dump(mode="python"))
    elif isinstance(value, Mapping):
        for nested in value.values():
            _reject_non_finite_decimals(nested)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for nested in value:
            _reject_non_finite_decimals(nested)


class Provenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(min_length=1)
    revision: str = Field(min_length=1)


class ApiError(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(min_length=1, pattern=r"^[A-Z][A-Z0-9_]*$")
    message: str = Field(min_length=1)
    retryable: bool
    details: dict[str, Any] | None = None


class ApiEnvelope(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(min_length=1)
    as_of: datetime
    source_revision: str = Field(min_length=1)
    status: str = Field(min_length=1)
    data: T
    provenance: Provenance

    @field_validator("as_of")
    @classmethod
    def normalize_aware_utc(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("data", mode="before")
    @classmethod
    def reject_non_finite_decimal(cls, value: Any) -> Any:
        _reject_non_finite_decimals(value)
        return value


class RequestContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(min_length=1)
    actor: str | None = None
    capabilities: frozenset[Capability] = frozenset()


class IdempotencyKey(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    value: str = Field(min_length=1, max_length=255)

    @field_validator("value")
    @classmethod
    def normalize_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("idempotency key must not be blank")
        return value


__all__ = ["ApiEnvelope", "ApiError", "IdempotencyKey", "Provenance", "RequestContext"]
