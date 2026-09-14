"""Public exports for the feature engineering domain (FEAT-01..FEAT-04)."""

from .builder import build_feature_frame
from .context import asof_join_features, point_in_time_market_context
from .registry import (
    FeatureAvailability,
    FeatureDefinition,
    FeatureRegistry,
    LoadedFeatureRegistry,
    MissingPolicy,
    load_feature_registry,
)

__all__ = [
    "FeatureAvailability",
    "FeatureDefinition",
    "FeatureRegistry",
    "LoadedFeatureRegistry",
    "MissingPolicy",
    "asof_join_features",
    "build_feature_frame",
    "load_feature_registry",
    "point_in_time_market_context",
]
