"""Train-only tabular preprocessing, feature scaling, and imputation (ML-01).

Contract:
train features -> imputer/scaler/pruner artifact; validation transform only.
Test extreme value tidak memengaruhi train median.
Missing extra reordered feature ditolak.
Transform tidak menjalankan fit.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _ensure_utc(dt: datetime, field_name: str = "timestamp") -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class FeatureAlignmentError(ValueError):
    """Raised when evaluation or inference features do not align with fitted features."""


class NotFittedError(RuntimeError):
    """Raised when transform is attempted before preprocessor is fitted."""


class PreprocessorConfig(BaseModel):
    """Configuration parameters for tabular feature preprocessing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    impute_strategy: str = "median"
    scale_strategy: str = "robust"
    clip_outliers: bool = True
    clip_quantile_lower: float = 0.01
    clip_quantile_upper: float = 0.99
    strict_feature_order: bool = False


class FittedPreprocessorArtifact(BaseModel):
    """Immutable record of fitted preprocessing statistics and feature schemas."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_names: list[str]
    medians: dict[str, float]
    means: dict[str, float]
    stds: dict[str, float]
    iqrs: dict[str, float]
    lower_bounds: dict[str, float]
    upper_bounds: dict[str, float]
    config: PreprocessorConfig
    fitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("fitted_at", mode="after")
    @classmethod
    def validate_fitted_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "fitted_at")


class TabularPreprocessor:
    """Preprocessor that fits exclusively on train data and strictly applies fixed statistics to evaluation data."""

    def __init__(self, config: PreprocessorConfig | None = None) -> None:
        self.config = config or PreprocessorConfig()
        self._fitted_artifact: FittedPreprocessorArtifact | None = None

    @property
    def fitted_artifact(self) -> FittedPreprocessorArtifact:
        if self._fitted_artifact is None:
            raise NotFittedError("TabularPreprocessor has not been fitted yet.")
        return self._fitted_artifact

    def fit(self, train_df: pd.DataFrame) -> FittedPreprocessorArtifact:
        """Fit preprocessor statistics on training features without accessing test data."""
        feature_names = list(train_df.columns)

        medians: dict[str, float] = {}
        means: dict[str, float] = {}
        stds: dict[str, float] = {}
        iqrs: dict[str, float] = {}
        lower_bounds: dict[str, float] = {}
        upper_bounds: dict[str, float] = {}

        for col in feature_names:
            series = pd.to_numeric(train_df[col], errors="coerce").dropna()
            if len(series) == 0:
                med = 0.0
                mean_val = 0.0
                std_val = 1.0
                iqr = 1.0
                lb = 0.0
                ub = 0.0
            else:
                med = float(series.median())
                mean_val = float(series.mean())
                std_val = float(series.std(ddof=1)) if len(series) > 1 else 1.0
                if std_val == 0.0 or np.isnan(std_val):
                    std_val = 1.0

                q25 = float(series.quantile(0.25))
                q75 = float(series.quantile(0.75))
                iqr = q75 - q25
                if iqr == 0.0 or np.isnan(iqr):
                    iqr = 1.0

                lb = float(series.quantile(self.config.clip_quantile_lower))
                ub = float(series.quantile(self.config.clip_quantile_upper))

            medians[col] = med
            means[col] = mean_val
            stds[col] = std_val
            iqrs[col] = iqr
            lower_bounds[col] = lb
            upper_bounds[col] = ub

        self._fitted_artifact = FittedPreprocessorArtifact(
            feature_names=feature_names,
            medians=medians,
            means=means,
            stds=stds,
            iqrs=iqrs,
            lower_bounds=lower_bounds,
            upper_bounds=upper_bounds,
            config=self.config,
            fitted_at=datetime.now(UTC),
        )
        return self._fitted_artifact

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform input features using frozen train-only statistics.

        Invariants:
        - Validates feature alignment (rejects missing or unexpected columns) (ML-01-AC2).
        - Test data does not alter fitted statistics (ML-01-AC1).
        - Does NOT execute fit (ML-01-AC3).
        """
        artifact = self.fitted_artifact
        expected_features = set(artifact.feature_names)
        actual_features = set(df.columns)

        missing = expected_features - actual_features
        if missing:
            raise FeatureAlignmentError(f"MISSING_REQUIRED_FEATURES:{sorted(missing)}")

        extra = actual_features - expected_features
        if extra:
            raise FeatureAlignmentError(f"UNEXPECTED_EXTRA_FEATURES:{sorted(extra)}")

        if self.config.strict_feature_order and list(df.columns) != artifact.feature_names:
            raise FeatureAlignmentError(
                f"FEATURE_ORDER_MISMATCH: expected {artifact.feature_names}, got {list(df.columns)}"
            )

        # Work on aligned columns copy
        out_df = df[artifact.feature_names].copy().astype(np.float64)

        for col in artifact.feature_names:
            # 1. Imputation
            if self.config.impute_strategy == "median":
                out_df[col] = out_df[col].fillna(artifact.medians[col])
            elif self.config.impute_strategy == "mean":
                out_df[col] = out_df[col].fillna(artifact.means[col])
            elif self.config.impute_strategy == "zero":
                out_df[col] = out_df[col].fillna(0.0)

            # 2. Outlier clipping using train bounds
            if self.config.clip_outliers:
                lb = artifact.lower_bounds[col]
                ub = artifact.upper_bounds[col]
                if lb <= ub:
                    out_df[col] = out_df[col].clip(lower=lb, upper=ub)

            # 3. Scaling using train statistics
            if self.config.scale_strategy == "robust":
                med = artifact.medians[col]
                iqr = artifact.iqrs[col]
                out_df[col] = (out_df[col] - med) / iqr
            elif self.config.scale_strategy == "standard":
                mean_val = artifact.means[col]
                std_val = artifact.stds[col]
                out_df[col] = (out_df[col] - mean_val) / std_val

        return out_df
