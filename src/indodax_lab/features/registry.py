"""Strict, immutable contracts for versioned feature registries."""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from indodax_lab.data.checksums import sha256_bytes


_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_IMPLEMENTATION = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.]*:[a-zA-Z_][a-zA-Z0-9_]*$")
_TIMEFRAME = re.compile(r"_(5m|15m|1h|4h|1d)$")
_IDENTITY = re.compile(r"^sha256:[0-9a-f]{64}$")


class FeatureAvailability(StrEnum):
    """Stable policies describing when a feature may enter a decision row."""

    CLOSED_BAR = "closed_bar"
    ASOF_CLOSED_BAR = "asof_closed_bar"
    POINT_IN_TIME = "point_in_time"
    KNOWN_AT_TIME = "known_at_time"


class MissingPolicy(StrEnum):
    """Registered missingness behavior; backward filling is deliberately absent."""

    DROP_SAMPLE_UNTIL_WARM = "drop_sample_until_warm"
    NULLABLE_OPTIONAL = "nullable_optional"


class FeatureDefinition(BaseModel):
    """One frozen feature definition with all causal and preprocessing metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    family: str = Field(min_length=1)
    source_columns: tuple[str, ...]
    formula: str = Field(min_length=1)
    implementation: str = Field(pattern=_IMPLEMENTATION.pattern)
    params: dict[str, int | float | str | bool]
    lookback_bars: int = Field(gt=0)
    availability: FeatureAvailability
    lag_bars: int = Field(ge=0)
    dtype: str
    missing_policy: MissingPolicy
    normalization: str = Field(min_length=1)
    monotonicity: str = Field(min_length=1)

    @field_validator("source_columns")
    @classmethod
    def require_source_columns(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(value) != len(set(value)) or any(not column for column in value):
            raise ValueError("FEATURE_SOURCE_COLUMNS_INVALID")
        return value

    @field_validator("dtype")
    @classmethod
    def require_float64(cls, value: str) -> str:
        if value != "float64":
            raise ValueError("FEATURE_DTYPE_MUST_BE_FLOAT64")
        return value

    @field_validator("missing_policy", mode="before")
    @classmethod
    def forbid_bfill(cls, value: object) -> object:
        if isinstance(value, str) and value.lower() in {"bfill", "backfill", "backward_fill"}:
            raise ValueError("BFILL_FORBIDDEN")
        return value

    @model_validator(mode="after")
    def validate_lookback(self) -> Self:
        minimum = _minimum_lookback(self)
        if self.lookback_bars < minimum:
            raise ValueError(
                f"INSUFFICIENT_FEATURE_LOOKBACK:{self.name}:"
                f"required={minimum}:configured={self.lookback_bars}"
            )
        return self


class FeatureRegistry(BaseModel):
    """The immutable semantic contents of one feature-set version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_set_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: str
    decision_interval: str = Field(pattern=r"^(5m|15m|1h|4h|1d)$")
    features: tuple[FeatureDefinition, ...]

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not _SEMVER.fullmatch(value):
            raise ValueError("FEATURE_REGISTRY_VERSION_MUST_BE_SEMVER")
        return value

    @model_validator(mode="before")
    @classmethod
    def reject_duplicate_names(cls, raw: Any) -> Any:
        if isinstance(raw, dict) and isinstance(raw.get("features"), list):
            names = [row.get("name") for row in raw["features"] if isinstance(row, dict)]
            if len(names) != len(set(names)):
                raise ValueError("DUPLICATE_FEATURE_NAME")
        return raw

    @model_validator(mode="after")
    def validate_registry(self) -> Self:
        if not self.features:
            raise ValueError("FEATURE_REGISTRY_EMPTY")
        for feature in self.features:
            match = _TIMEFRAME.search(feature.name)
            if (
                match is not None
                and match.group(1) != self.decision_interval
                and feature.availability is not FeatureAvailability.ASOF_CLOSED_BAR
            ):
                raise ValueError(f"TIMEFRAME_AVAILABILITY_POLICY_REQUIRED:{feature.name}")
        return self

    def feature(self, name: str) -> FeatureDefinition:
        """Return a named definition or fail closed instead of silently omitting it."""
        for feature in self.features:
            if feature.name == name:
                return feature
        raise KeyError(f"UNKNOWN_FEATURE:{name}")


class LoadedFeatureRegistry(BaseModel):
    """Validated semantics plus the SHA identity of the exact source YAML bytes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    registry: FeatureRegistry
    source_id: str

    @field_validator("source_id")
    @classmethod
    def require_identity(cls, value: str) -> str:
        if not _IDENTITY.fullmatch(value):
            raise ValueError("FEATURE_REGISTRY_SOURCE_ID_INVALID")
        return value


def load_feature_registry(
    path: Path,
    *,
    previous: LoadedFeatureRegistry | None = None,
) -> LoadedFeatureRegistry:
    """Load exact YAML bytes and reject same-version semantic or byte changes."""
    raw = Path(path).read_bytes()
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict):
        raise ValueError("FEATURE_REGISTRY_YAML_MUST_BE_MAPPING")
    registry = FeatureRegistry.model_validate(parsed)
    loaded = LoadedFeatureRegistry(
        registry=registry,
        source_id=f"sha256:{sha256_bytes(raw)}",
    )
    if previous is not None and loaded.source_id != previous.source_id:
        if _semver_tuple(registry.version) <= _semver_tuple(previous.registry.version):
            raise ValueError("FEATURE_CONTENT_CHANGED_WITHOUT_VERSION_BUMP")
    return loaded


def _semver_tuple(value: str) -> tuple[int, int, int]:
    match = _SEMVER.fullmatch(value)
    if match is None:
        raise ValueError("FEATURE_REGISTRY_VERSION_MUST_BE_SEMVER")
    return tuple(int(part) for part in match.groups())


def _integer_param(feature: FeatureDefinition, name: str, default: int = 1) -> int:
    value = feature.params.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"FEATURE_PARAM_INVALID:{feature.name}:{name}")
    return value


def _minimum_lookback(feature: FeatureDefinition) -> int:
    function = feature.implementation.rsplit(":", maxsplit=1)[1]
    if function in {"log_return", "btc_log_return"}:
        return _integer_param(feature, "periods") + 1
    if function == "ema_ratio":
        return max(_integer_param(feature, "fast"), _integer_param(feature, "slow"))
    if function == "ema_slope_atr":
        return max(
            _integer_param(feature, "ema_period") + _integer_param(feature, "slope_bars"),
            _integer_param(feature, "atr_period"),
        )
    if function in {"rsi_centered"}:
        return _integer_param(feature, "period") + 1
    if function == "stochrsi_component":
        return (
            2 * _integer_param(feature, "period")
            + _integer_param(feature, "smooth_k")
            + _integer_param(feature, "smooth_d")
            - 2
        )
    if function == "macd_hist_atr":
        return max(
            _integer_param(feature, "slow") + _integer_param(feature, "signal"),
            _integer_param(feature, "atr_period"),
        )
    if function == "adx_di_component":
        return 2 * _integer_param(feature, "period") - 1
    if function in {"realized_volatility", "downside_volatility", "amihud"}:
        return _integer_param(feature, "period") + 1
    integer_params = [
        value for value in feature.params.values() if isinstance(value, int) and not isinstance(value, bool)
    ]
    return max(integer_params, default=1)


__all__ = [
    "FeatureAvailability",
    "FeatureDefinition",
    "FeatureRegistry",
    "LoadedFeatureRegistry",
    "MissingPolicy",
    "load_feature_registry",
]
