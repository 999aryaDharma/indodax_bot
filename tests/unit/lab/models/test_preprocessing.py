"""Unit tests for ML-01 Train-only preprocessing.

Acceptance Criteria:
- ML-01-AC0 (test_ml_01_valid_contract): Preprocessor menyimpan fitted statistics dan feature order tanpa mengakses test.
- ML-01-AC1 (test_ml_01_contract_1): Test extreme value tidak memengaruhi train median.
- ML-01-AC2 (test_ml_01_contract_2): Missing extra reordered feature ditolak.
- ML-01-AC3 (test_ml_01_contract_3): Transform tidak menjalankan fit.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from indodax_lab.models.preprocessing import (
    FeatureAlignmentError,
    FittedPreprocessorArtifact,
    PreprocessorConfig,
    TabularPreprocessor,
)


def _build_sample_dfs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build small train and test feature sets."""
    train_df = pd.DataFrame(
        {
            "ret_12": [0.01, 0.02, 0.03, 0.02, np.nan],  # Median is 0.02
            "rsi_14": [40.0, 50.0, 60.0, 50.0, 50.0],   # Median is 50.0
            "vol_ratio": [1.0, 1.2, 0.8, 1.0, 1.5],     # Median is 1.0
        }
    )
    test_df = pd.DataFrame(
        {
            "ret_12": [0.015, np.nan, 0.025],
            "rsi_14": [45.0, 55.0, 65.0],
            "vol_ratio": [1.1, 0.9, 1.3],
        }
    )
    return train_df, test_df


def test_ml_01_valid_contract() -> None:
    """ML-01-AC0: Preprocessor menyimpan fitted statistics dan feature order tanpa mengakses test."""
    train_df, test_df = _build_sample_dfs()
    config = PreprocessorConfig(
        impute_strategy="median",
        scale_strategy="robust",  # (x - median) / IQR
        clip_outliers=True,
        clip_quantile_lower=0.01,
        clip_quantile_upper=0.99,
    )
    preprocessor = TabularPreprocessor(config)

    # Fit strictly on train features
    artifact = preprocessor.fit(train_df)
    assert isinstance(artifact, FittedPreprocessorArtifact)
    assert artifact.feature_names == ["ret_12", "rsi_14", "vol_ratio"]
    assert artifact.medians["ret_12"] == pytest.approx(0.02)
    assert artifact.medians["rsi_14"] == pytest.approx(50.0)
    assert artifact.medians["vol_ratio"] == pytest.approx(1.0)

    # Transform test features
    transformed_test = preprocessor.transform(test_df)
    assert list(transformed_test.columns) == ["ret_12", "rsi_14", "vol_ratio"]
    # Check that missing value in test_df["ret_12"] row 1 was imputed with train median (0.02)
    assert not transformed_test["ret_12"].isna().any()


def test_ml_01_contract_1() -> None:
    """ML-01-AC1: Test extreme value tidak memengaruhi train median."""
    train_df, _ = _build_sample_dfs()
    preprocessor = TabularPreprocessor()
    preprocessor.fit(train_df)

    initial_median_ret = preprocessor.fitted_artifact.medians["ret_12"]
    initial_median_rsi = preprocessor.fitted_artifact.medians["rsi_14"]

    # Test set containing massive outliers
    extreme_test_df = pd.DataFrame(
        {
            "ret_12": [999999.0, -888888.0, 100000.0],
            "rsi_14": [999999.0, 999999.0, 999999.0],
            "vol_ratio": [1.0, 1.0, 1.0],
        }
    )

    # Transform should not pollute or update the train medians
    _ = preprocessor.transform(extreme_test_df)

    assert preprocessor.fitted_artifact.medians["ret_12"] == initial_median_ret
    assert preprocessor.fitted_artifact.medians["rsi_14"] == initial_median_rsi


def test_ml_01_contract_2() -> None:
    """ML-01-AC2: Missing extra reordered feature ditolak."""
    train_df, _ = _build_sample_dfs()
    preprocessor = TabularPreprocessor()
    preprocessor.fit(train_df)

    # 1. Missing feature in test input
    missing_test_df = pd.DataFrame(
        {
            "ret_12": [0.01, 0.02],
            "rsi_14": [45.0, 55.0],
            # missing "vol_ratio"
        }
    )
    with pytest.raises(FeatureAlignmentError) as exc_missing:
        preprocessor.transform(missing_test_df)
    assert "MISSING_REQUIRED_FEATURES" in str(exc_missing.value)

    # 2. Extra unexpected feature in test input
    extra_test_df = pd.DataFrame(
        {
            "ret_12": [0.01, 0.02],
            "rsi_14": [45.0, 55.0],
            "vol_ratio": [1.0, 1.1],
            "unauthorized_leakage_feature": [123.0, 456.0],
        }
    )
    with pytest.raises(FeatureAlignmentError) as exc_extra:
        preprocessor.transform(extra_test_df)
    assert "UNEXPECTED_EXTRA_FEATURES" in str(exc_extra.value)

    # 3. Reordered features are rejected on the default path.
    reordered_test_df = pd.DataFrame(
        {
            "vol_ratio": [1.0, 1.1],
            "ret_12": [0.01, 0.02],
            "rsi_14": [45.0, 55.0],
        }
    )
    with pytest.raises(FeatureAlignmentError) as exc_order:
        preprocessor.transform(reordered_test_df)
    assert "FEATURE_ORDER_MISMATCH" in str(exc_order.value)

    adapter_preprocessor = TabularPreprocessor(PreprocessorConfig(strict_feature_order=False))
    adapter_preprocessor.fit(train_df)
    with pytest.raises(FeatureAlignmentError, match="FEATURE_ORDER_MISMATCH"):
        adapter_preprocessor.transform(reordered_test_df)
    restored = reordered_test_df[train_df.columns]
    assert list(adapter_preprocessor.transform(restored).columns) == list(train_df.columns)


def test_ml_01_contract_3() -> None:
    """ML-01-AC3: Transform tidak menjalankan fit."""
    train_df, test_df = _build_sample_dfs()
    preprocessor = TabularPreprocessor()
    preprocessor.fit(train_df)

    saved_state = copy.deepcopy(preprocessor.fitted_artifact.model_dump())

    # Call transform multiple times with different datasets
    for _ in range(5):
        _ = preprocessor.transform(test_df)

    current_state = preprocessor.fitted_artifact.model_dump()
    assert saved_state == current_state


def test_ml_01_ac2_duplicate_feature_column_is_rejected_on_transform() -> None:
    """Regression: the AC2 alignment guard is set-based, so it is blind to duplicated columns.

    Before the fix `transform` accepted a DataFrame carrying a repeated feature name,
    silently resolved it to the first occurrence and returned a frame whose column
    count no longer matched the fitted feature schema.
    """
    train_df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0], "b": [5.0, 6.0, 7.0, 8.0]})
    preprocessor = TabularPreprocessor()
    preprocessor.fit(train_df)

    duplicated = pd.DataFrame(
        [[1.0, 9.9, 5.0], [2.0, 8.8, 6.0]],
        columns=["a", "a", "b"],
    )
    assert list(duplicated.columns) == ["a", "a", "b"]

    with pytest.raises(FeatureAlignmentError, match="DUPLICATE_FEATURE_COLUMNS"):
        preprocessor.transform(duplicated)


def test_ml_01_ac0_duplicate_feature_column_is_rejected_on_fit() -> None:
    """Regression: a duplicated train column crashed with an unclassified pandas TypeError.

    Before the fix `fit` indexed the duplicated column by label, which pandas rejects
    with `TypeError: arg must be a list, tuple, 1-d array, or Series`.
    """
    duplicated_train = pd.DataFrame(
        [[1.0, 9.9], [2.0, 8.8], [3.0, 7.7], [4.0, 6.6]],
        columns=["a", "a"],
    )
    with pytest.raises(FeatureAlignmentError, match="DUPLICATE_FEATURE_COLUMNS"):
        TabularPreprocessor().fit(duplicated_train)


def test_ml_01_fitted_artifact_rejects_non_unique_feature_schema() -> None:
    """A fitted artifact is an immutable record of the feature schema; it must be unique."""
    train_df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]})
    artifact = TabularPreprocessor().fit(train_df)

    with pytest.raises(ValueError, match="FEATURE_SCHEMA_INVALID"):
        FittedPreprocessorArtifact(
            feature_names=["a", "a"],
            medians=artifact.medians,
            means=artifact.means,
            stds=artifact.stds,
            iqrs=artifact.iqrs,
            lower_bounds=artifact.lower_bounds,
            upper_bounds=artifact.upper_bounds,
            config=artifact.config,
        )


def test_ml_01_fitted_artifact_rejects_statistics_outside_feature_schema() -> None:
    train_df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]})
    state = TabularPreprocessor().fit(train_df).model_dump()
    state["feature_names"] = ["arbitrary"]

    with pytest.raises(ValueError, match="FEATURE_SCHEMA_INVALID"):
        FittedPreprocessorArtifact.model_validate(state)


def test_ml_01_returned_artifact_is_a_defensive_copy() -> None:
    train_df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 7.0]})
    preprocessor = TabularPreprocessor(PreprocessorConfig(clip_outliers=False))
    returned_artifact = preprocessor.fit(train_df)
    expected = preprocessor.transform(train_df)

    returned_artifact.medians["a"] = 100.0
    returned_artifact.feature_names.reverse()

    pd.testing.assert_frame_equal(preprocessor.transform(train_df), expected)
    assert preprocessor.fitted_artifact.medians["a"] == 2.0
    assert preprocessor.fitted_artifact.feature_names == ["a", "b"]


def test_ml_01_transform_uses_config_recorded_at_fit() -> None:
    train_df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 7.0]})
    preprocessor = TabularPreprocessor(PreprocessorConfig(clip_outliers=False))
    preprocessor.fit(train_df)
    expected = preprocessor.transform(train_df)

    preprocessor.config = PreprocessorConfig(
        impute_strategy="zero",
        scale_strategy="standard",
        clip_outliers=False,
        strict_feature_order=False,
    )

    pd.testing.assert_frame_equal(preprocessor.transform(train_df), expected)
    with pytest.raises(FeatureAlignmentError, match="FEATURE_ORDER_MISMATCH"):
        preprocessor.transform(train_df[["b", "a"]])
