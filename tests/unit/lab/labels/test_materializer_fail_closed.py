"""Fail-closed regression tests for TRAIN-01 training dataset materialization.

Review findings covered:
- TRAIN-01-F1 (Critical): the prohibited-name set was built from the raw ``target_column``
  while the membership test ran against ``col.lower()``. Any target column that was not
  already lowercase therefore escaped its own leakage guard, so the target itself could be
  declared as an inference feature.
- TRAIN-01-F2 (Critical): the leakage guard only inspected the *declared*
  ``inference_feature_columns``. The materializer then merges the entire ``features_df``,
  so a future-looking or outcome-shaped column that was never declared still rode into
  the persisted training artifact, where a model could consume it.

These are the only guards touched; checksum verification, identity binding, availability
and fold-boundary checks are unchanged and are exercised by the existing suite.

opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
from typing import Any

import pandas as pd
import pytest

from indodax_lab.labels.materializer import (
    TargetLeakageError,
    materialize_training_dataset,
)
from indodax_lab.labels.splits import (
    FoldAssignment,
    SampleRole,
    SplitManifest,
)

BASE_TS = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
SAMPLE_IDS = [f"sample_{i:03d}" for i in range(4)]
TIMESTAMPS = [BASE_TS + timedelta(days=i * 30) for i in range(4)]

BOUNDS = {
    SampleRole.TRAIN: (datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 3, 1, tzinfo=UTC)),
    SampleRole.VALIDATION: (datetime(2024, 3, 1, tzinfo=UTC), datetime(2024, 3, 31, tzinfo=UTC)),
    SampleRole.SEALED_TEST: (datetime(2024, 3, 31, tzinfo=UTC), datetime(2024, 5, 1, tzinfo=UTC)),
}
ROLES = [
    SampleRole.TRAIN,
    SampleRole.TRAIN,
    SampleRole.VALIDATION,
    SampleRole.SEALED_TEST,
]


def _features(extra: dict[str, Any] | None = None) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "sample_id": SAMPLE_IDS,
            "decision_ts": TIMESTAMPS,
            "pair": ["btc_idr"] * 4,
            "ret_12": [0.01, -0.02, 0.03, 0.015],
            "rsi_14": [55.0, 42.0, 68.0, 50.0],
            "eligible": [True, True, True, True],
            "row_ready_at": TIMESTAMPS,
        }
    )
    for name, values in (extra or {}).items():
        frame[name] = values
    return frame


def _labels(target_column: str = "net_return") -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "sample_id": SAMPLE_IDS,
            "decision_ts": TIMESTAMPS,
            "pair": ["btc_idr"] * 4,
            "label_end_ts": [ts + timedelta(hours=24) for ts in TIMESTAMPS],
            "label_available_at": [ts + timedelta(hours=24) for ts in TIMESTAMPS],
            "net_return": [0.02, -0.01, 0.04, 0.005],
            "binary_label": [1, 0, 1, 1],
        }
    )
    if target_column not in frame.columns:
        frame[target_column] = frame["net_return"]
    return frame


def _manifest() -> SplitManifest:
    assignments = {
        SAMPLE_IDS[i]: FoldAssignment(
            sample_id=SAMPLE_IDS[i],
            role=ROLES[i],
            fold_role=ROLES[i],
            purge_reason=None,
            fold_start_ts=BOUNDS[ROLES[i]][0],
            fold_end_ts=BOUNDS[ROLES[i]][1],
        )
        for i in range(4)
    }
    return SplitManifest(
        split_id="split_annual_2024",
        policy_id="annual_v1",
        policy_version="1.0.0",
        total_samples=4,
        train_count=2,
        validation_count=1,
        sealed_test_count=1,
        purged_count=0,
        embargoed_count=0,
        assignments=assignments,
        policy_content_sha256=hashlib.sha256(
            json.dumps(
                {
                    "policy_id": "annual_v1",
                    "version": "1.0.0",
                    "folds": {
                        str(role): [start.isoformat(), end.isoformat()]
                        for role, (start, end) in BOUNDS.items()
                    },
                    "embargo_hours": 24,
                    "max_horizon_hours": 24,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest(),
    )


def _materialize(
    features: pd.DataFrame,
    labels: pd.DataFrame,
    target_column: str,
    inference: list[str],
):
    return materialize_training_dataset(
        features, labels, _manifest(), target_column, inference,
        "snapshot", "1", "cost",
    )


# --- TRAIN-01-F1: the target column must not escape its own guard via letter case ---


@pytest.mark.parametrize("target", ["netReturn", "NetReturn", "NETRETURN", "Binary_Label"])
def test_train_01_mixed_case_target_column_cannot_be_a_declared_feature(target: str) -> None:
    """TRAIN-01-F1: a non-lowercase target escaped the lowercased membership test."""
    labels = _labels(target)

    with pytest.raises(TargetLeakageError):
        _materialize(
            _features(), labels, target, ["ret_12", "rsi_14", target]
        )


def test_train_01_mixed_case_target_column_is_rejected_in_any_case_form() -> None:
    """TRAIN-01-F1: the guard compares case-insensitively in both directions."""
    labels = _labels("netReturn")

    with pytest.raises(TargetLeakageError):
        _materialize(_features(), labels, "netReturn", ["ret_12", "NETRETURN"])


# --- TRAIN-01-F2: undeclared leaky columns in the frame are still leaks ---


def test_train_01_undeclared_future_column_in_features_is_rejected() -> None:
    """TRAIN-01-F2: the whole features_df is merged, so an undeclared leak still ships."""
    features = _features({"future_return_1": [0.02, -0.01, 0.04, 0.005]})

    with pytest.raises(TargetLeakageError):
        _materialize(features, _labels(), "net_return", ["ret_12", "rsi_14"])


@pytest.mark.parametrize(
    "column", ["label_end_ts", "outcome_class", "exit_price", "target_mean", "entry_fill"]
)
def test_train_01_undeclared_outcome_shaped_column_is_rejected(column: str) -> None:
    """TRAIN-01-F2: outcome-shaped column names are prohibited wherever they appear."""
    features = _features({column: [1.0, 2.0, 3.0, 4.0]})

    with pytest.raises(TargetLeakageError):
        _materialize(features, _labels(), "net_return", ["ret_12", "rsi_14"])


def test_train_01_target_column_physically_present_in_features_is_rejected() -> None:
    """TRAIN-01-F2: the target must not be smuggled in through the feature frame."""
    features = _features({"net_return": [0.02, -0.01, 0.04, 0.005]})

    with pytest.raises(TargetLeakageError):
        _materialize(features, _labels(), "net_return", ["ret_12", "rsi_14"])


# --- Guards: a clean frame must still materialize ---


def test_train_01_clean_frame_still_materializes() -> None:
    """TRAIN-01-F1/F2 guard: the widened scan must not reject legitimate features."""
    artifact = _materialize(
        _features(), _labels(), "net_return", ["ret_12", "rsi_14"]
    )

    assert artifact.manifest.sample_counts_by_role["TRAIN"] == 2
    assert artifact.get_role_data("TRAIN")["sample_id"].tolist() == SAMPLE_IDS[:2]
    assert "ret_12" in artifact.data.columns


def test_train_01_legitimate_metadata_columns_are_not_treated_as_leaks() -> None:
    """TRAIN-01-F2 guard: identity/eligibility columns are not outcome-shaped."""
    artifact = _materialize(
        _features(), _labels(), "net_return", ["ret_12", "rsi_14"]
    )
    for column in ("sample_id", "decision_ts", "pair", "eligible", "row_ready_at"):
        assert column in artifact.data.columns


# Actor for every line this file contributes to review evidence:
# opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
