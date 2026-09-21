"""Immutable identities, artifact references, and canonical digest functions (RW0-01).

Guarantees:
- ArtifactRef identifies verified bytes via lowercase 64-hex SHA-256 and opaque IDs.
- Canonical JSON encoding ensures sorted keys, compact separators, finite numbers.
- manifest_digest computes lowercase SHA-256 over canonical semantic bytes.
- All manifest models are frozen, extra-forbidden, and deeply immutable.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

_SHA256_REGEX = re.compile(r"^[a-f0-9]{64}$")
_PATH_SEPARATOR_REGEX = re.compile(r"[/\\:]|\.\.")

# Audit fields excluded from semantic manifest digest
AUDIT_FIELDS = frozenset(
    {
        "created_at",
        "created_at_utc",
        "digest",
        "manifest_digest",
    }
)


def _ensure_utc(dt: datetime, field_name: str = "timestamp") -> datetime:
    """Validate timezone-aware UTC datetime."""
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class ArtifactRef(BaseModel):
    """Immutable reference identifying verified content-addressed bytes."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    kind: str
    id: str
    version: str
    sha256: str
    schema_version: str = "v1"

    @field_validator("id", "version", "kind", "schema_version")
    @classmethod
    def validate_opaque_non_path(cls, value: str, info: Any) -> str:
        if not value or not value.strip():
            raise ValueError(f"NON_EMPTY_REQUIRED:{info.field_name}")
        if _PATH_SEPARATOR_REGEX.search(value) or value.startswith(("/", "\\")):
            raise ValueError(f"PATH_SEPARATOR_FORBIDDEN:{info.field_name}")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_sha256_hex(cls, value: str) -> str:
        if not _SHA256_REGEX.fullmatch(value):
            raise ValueError("INVALID_SHA256_HEX: Must be exactly 64 lowercase hex characters")
        return value


def canonical_json_value(val: Any, exclude_audit: bool = False) -> Any:
    """Recursively convert values into canonical JSON-serializable primitives."""
    if val is None or isinstance(val, (bool, int, str)):
        return val

    if isinstance(val, float):
        if not math.isfinite(val):
            raise ValueError("NON_FINITE_NUMBER_FORBIDDEN")
        return val

    if isinstance(val, Decimal):
        if not val.is_finite():
            raise ValueError("NON_FINITE_NUMBER_FORBIDDEN")
        # Format Decimal as normalized non-exponent string
        normalized = val.normalize()
        sign, digits, exponent = normalized.as_tuple()
        if exponent > 0:
            return str(val)
        return format(val, "f")

    if isinstance(val, datetime):
        utc_dt = _ensure_utc(val)
        return utc_dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    if isinstance(val, Enum):
        return val.value

    if isinstance(val, BaseModel):
        data = {}
        for k, v in val.__dict__.items():
            if k.startswith("_"):
                continue
            if exclude_audit and k in AUDIT_FIELDS:
                continue
            data[k] = canonical_json_value(v, exclude_audit=exclude_audit)
        return {k: data[k] for k in sorted(data.keys())}

    if isinstance(val, dict):
        data = {}
        for k, v in val.items():
            if exclude_audit and str(k) in AUDIT_FIELDS:
                continue
            data[str(k)] = canonical_json_value(v, exclude_audit=exclude_audit)
        return {k: data[k] for k in sorted(data.keys())}

    if isinstance(val, (list, tuple, set, frozenset)):
        return [canonical_json_value(item, exclude_audit=exclude_audit) for item in val]

    raise TypeError(f"UNSUPPORTED_CANONICAL_TYPE:{type(val)}")


def canonical_bytes(value: Any, exclude_audit: bool = False) -> bytes:
    """Encode value into deterministic canonical UTF-8 JSON bytes."""
    primitive = canonical_json_value(value, exclude_audit=exclude_audit)
    encoded = json.dumps(
        primitive,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return encoded.encode("utf-8")


def manifest_digest(value: Any) -> str:
    """Compute lowercase 64-hex SHA-256 digest of semantic bytes (excluding audit metadata)."""
    payload_bytes = canonical_bytes(value, exclude_audit=True)
    return hashlib.sha256(payload_bytes).hexdigest()


class ImmutableManifest(BaseModel):
    """Base class for all deeply immutable domain manifests."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    def semantic_digest(self) -> str:
        """Compute content digest of semantic fields."""
        return manifest_digest(self)

    def to_artifact_ref(self, kind: str | None = None) -> ArtifactRef:
        """Derive an ArtifactRef from this manifest."""
        manifest_id = getattr(
            self,
            "manifest_id",
            getattr(
                self,
                "dataset_id",
                getattr(
                    self,
                    "strategy_id",
                    getattr(
                        self,
                        "model_id",
                        getattr(
                            self,
                            "pipeline_id",
                            getattr(
                                self,
                                "experiment_id",
                                getattr(
                                    self,
                                    "plan_id",
                                    getattr(
                                        self,
                                        "candidate_id",
                                        getattr(self, "agent_id", "manifest"),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )
        ver = getattr(self, "version", "1.0.0")
        k = kind or self.__class__.__name__.replace("Manifest", "").lower()
        return ArtifactRef(
            kind=k,
            id=manifest_id,
            version=ver,
            sha256=self.semantic_digest(),
            schema_version=getattr(self, "schema_version", "v1"),
        )
