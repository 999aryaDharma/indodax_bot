"""Unit tests for SPLIT-01 Sealed purged chronological folds."""

from datetime import UTC, datetime, timedelta
import pytest

from indodax_lab.labels.splits import (
    ExposedPeriodViolationError,
    FoldAssignment,
    FoldWindow,
    SampleRecord,
    SampleRole,
    SplitManifest,
    SplitPolicy,
    assign_folds,
)


def _build_test_policy(
    embargo_hours: int = 24,
    max_horizon_hours: int = 24,
) -> SplitPolicy:
    """Build standard 3-fold chronological split policy: train, validation, sealed_test."""
    train_start = datetime(2023, 1, 1, 0, 0, tzinfo=UTC)
    train_end = datetime(2023, 12, 31, 23, 59, 59, tzinfo=UTC)

    val_start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    val_end = datetime(2024, 6, 30, 23, 59, 59, tzinfo=UTC)

    test_start = datetime(2024, 7, 1, 0, 0, tzinfo=UTC)
    test_end = datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC)

    return SplitPolicy(
        policy_id="annual_v1",
        version="1.0.0",
        max_horizon_hours=max_horizon_hours,
        embargo_hours=embargo_hours,
        folds=[
            FoldWindow(role=SampleRole.TRAIN, start_ts=train_start, end_ts=train_end),
            FoldWindow(role=SampleRole.VALIDATION, start_ts=val_start, end_ts=val_end),
            FoldWindow(role=SampleRole.SEALED_TEST, start_ts=test_start, end_ts=test_end),
        ],
    )


def test_split_01_valid_contract() -> None:
    """SPLIT-01-AC0: Fold assignment separates train, validation, and sealed test without overlap."""
    policy = _build_test_policy()

    # Three clean samples well inside their respective fold boundaries
    s_train = SampleRecord(
        sample_id="s_train_1",
        decision_ts=datetime(2023, 6, 1, 12, 0, tzinfo=UTC),
        label_end_ts=datetime(2023, 6, 2, 12, 0, tzinfo=UTC),
        pair="btc_idr",
    )
    s_val = SampleRecord(
        sample_id="s_val_1",
        decision_ts=datetime(2024, 3, 1, 12, 0, tzinfo=UTC),
        label_end_ts=datetime(2024, 3, 2, 12, 0, tzinfo=UTC),
        pair="btc_idr",
    )
    s_test = SampleRecord(
        sample_id="s_test_1",
        decision_ts=datetime(2024, 9, 1, 12, 0, tzinfo=UTC),
        label_end_ts=datetime(2024, 9, 2, 12, 0, tzinfo=UTC),
        pair="btc_idr",
    )

    manifest = assign_folds([s_train, s_val, s_test], policy)
    assert isinstance(manifest, SplitManifest)
    assert manifest.assignments["s_train_1"].role == SampleRole.TRAIN
    assert manifest.assignments["s_val_1"].role == SampleRole.VALIDATION
    assert manifest.assignments["s_test_1"].role == SampleRole.SEALED_TEST
    assert manifest.purged_count == 0
    assert manifest.embargoed_count == 0


def test_split_01_contract_1() -> None:
    """SPLIT-01-AC1: Sample crossing fold boundary is purged."""
    policy = _build_test_policy()

    # Sample starts in train on 2023-12-31 at 20:00, but label ends on 2024-01-01 at 20:00 (inside validation!)
    boundary_crosser = SampleRecord(
        sample_id="s_crosser",
        decision_ts=datetime(2023, 12, 31, 20, 0, tzinfo=UTC),
        label_end_ts=datetime(2024, 1, 1, 20, 0, tzinfo=UTC),
        pair="btc_idr",
    )
    # Non-crossing sample inside train
    clean_sample = SampleRecord(
        sample_id="s_clean",
        decision_ts=datetime(2023, 12, 30, 10, 0, tzinfo=UTC),
        label_end_ts=datetime(2023, 12, 30, 22, 0, tzinfo=UTC),
        pair="btc_idr",
    )

    manifest = assign_folds([boundary_crosser, clean_sample], policy)
    assert manifest.assignments["s_crosser"].role == SampleRole.PURGED
    assert manifest.assignments["s_crosser"].purge_reason == "LABEL_OVERLAPS_FOLD_BOUNDARY"
    assert manifest.assignments["s_clean"].role == SampleRole.TRAIN
    assert manifest.purged_count == 1


def test_split_01_contract_2() -> None:
    """SPLIT-01-AC2: Embargo is at least max horizon."""
    # Policy with embargo less than max horizon must be rejected
    with pytest.raises(ValueError, match="EMBARGO_LESS_THAN_MAX_HORIZON"):
        _build_test_policy(embargo_hours=12, max_horizon_hours=24)

    policy = _build_test_policy(embargo_hours=24, max_horizon_hours=24)

    # In a chronological rolling scheme or fold boundary, sample within embargo window after validation fold
    # is marked EMBARGOED
    sample_in_embargo = SampleRecord(
        sample_id="s_embargo",
        decision_ts=datetime(2024, 7, 1, 10, 0, tzinfo=UTC),  # within 24h after val_end
        label_end_ts=datetime(2024, 7, 2, 10, 0, tzinfo=UTC),
        pair="btc_idr",
    )

    # Assign with embargo enforcement between folds
    manifest = assign_folds([sample_in_embargo], policy, enforce_inter_fold_embargo=True)
    assert manifest.assignments["s_embargo"].role == SampleRole.EMBARGOED
    assert manifest.embargoed_count == 1


def test_split_01_contract_3() -> None:
    """SPLIT-01-AC3: Previously exposed year cannot be claimed as sealed again."""
    policy = _build_test_policy()

    # Exposure log indicates 2024 has already been exposed/evaluated in a prior experiment
    exposure_log = [
        {
            "run_id": "run_old_2024_eval",
            "exposed_start": datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
            "exposed_end": datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC),
            "reason": "historical_evaluation",
        }
    ]

    s_test = SampleRecord(
        sample_id="s_test_1",
        decision_ts=datetime(2024, 9, 1, 12, 0, tzinfo=UTC),
        label_end_ts=datetime(2024, 9, 2, 12, 0, tzinfo=UTC),
        pair="btc_idr",
    )

    with pytest.raises(ExposedPeriodViolationError, match="EXPOSED_PERIOD_CANNOT_BE_SEALED"):
        assign_folds([s_test], policy, exposure_log=exposure_log)
