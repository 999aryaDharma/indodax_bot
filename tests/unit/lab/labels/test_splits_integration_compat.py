"""Pyarrow-free regression guard for the SPLIT-01 inter-fold embargo default change.

Context
-------
``tests/integration/lab/test_training_materialization.py`` cannot execute in this
environment (``pyarrow``/``fastparquet`` are not installed), so the interaction
between the corrected ``enforce_inter_fold_embargo=True`` default and that
module's fold-cutoff fixture is unverifiable by execution there.

This module reproduces the *exact* ``assign_folds`` inputs of
``test_generated_fold_cutoffs_exclude_delayed_labels_from_training`` without any
parquet round-trip, so the boundary behaviour is execution-verified here.

Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from indodax_lab.labels.splits import (
    FoldWindow,
    SampleRecord,
    SampleRole,
    SplitPolicy,
    assign_folds,
)

# Mirrors _build_test_data() in tests/integration/lab/test_training_materialization.py
BASE_TS = datetime(2024, 1, 1, tzinfo=UTC)
TIMESTAMPS = [BASE_TS + timedelta(days=i * 30) for i in range(4)]
SAMPLE_IDS = [f"sample_{i:03d}" for i in range(4)]


def _policy() -> SplitPolicy:
    """The exact SplitPolicy built at test_training_materialization.py:305-312.

    embargo_hours and max_horizon_hours are left at their defaults (24), which is
    what makes sample_002 sit inside the post-TRAIN embargo window.
    """
    return SplitPolicy(
        policy_id="chronological",
        version="2",
        folds=[
            FoldWindow(
                role=SampleRole.TRAIN,
                start_ts=datetime(2024, 1, 1, tzinfo=UTC),
                end_ts=datetime(2024, 3, 1, tzinfo=UTC),
            ),
            FoldWindow(
                role=SampleRole.VALIDATION,
                start_ts=datetime(2024, 3, 1, tzinfo=UTC),
                end_ts=datetime(2024, 3, 31, tzinfo=UTC),
            ),
            FoldWindow(
                role=SampleRole.SEALED_TEST,
                start_ts=datetime(2024, 3, 31, tzinfo=UTC),
                end_ts=datetime(2024, 5, 1, tzinfo=UTC),
            ),
        ],
    )


def _records() -> list[SampleRecord]:
    """The exact SampleRecords built at test_training_materialization.py:313-315.

    sample_001's label_available_at is delayed to 2024-03-02, which is the
    subject of the integration test.
    """
    label_available = [ts + timedelta(hours=24) for ts in TIMESTAMPS]
    label_available[1] = datetime(2024, 3, 2, tzinfo=UTC)
    return [
        SampleRecord(
            sample_id=sample_id,
            pair="btc_idr",
            decision_ts=decision_ts,
            label_end_ts=decision_ts + timedelta(hours=24),
            label_available_at=available_at,
        )
        for sample_id, decision_ts, available_at in zip(
            SAMPLE_IDS, TIMESTAMPS, label_available
        )
    ]


def test_fixture_timestamps_straddle_the_declared_fold_boundaries() -> None:
    """Guard the premise: the fixture's sample_002 sits exactly on the boundary.

    If this ever changes, the embargo interaction below is no longer the thing
    the integration test is exercising.
    """
    assert TIMESTAMPS[0] == datetime(2024, 1, 1, tzinfo=UTC)
    assert TIMESTAMPS[2] == datetime(2024, 3, 1, tzinfo=UTC)
    assert TIMESTAMPS[3] == datetime(2024, 3, 31, tzinfo=UTC)


def test_corrected_default_embargoes_the_boundary_sample() -> None:
    """RED (pre-compat-fix): the corrected default embargoes sample_002.

    This is the behaviour that broke
    test_generated_fold_cutoffs_exclude_delayed_labels_from_training, which
    asserted sample_002 -> VALIDATION.
    """
    manifest = assign_folds(_records(), _policy())
    roles = {sid: a.role for sid, a in manifest.assignments.items()}
    assert roles["sample_000"] is SampleRole.TRAIN
    assert roles["sample_001"] is SampleRole.PURGED
    # sample_002 (2024-03-01) and sample_003 (2024-03-31) each sit exactly on a
    # fold start, and the preceding fold closed less than embargo_hours (24)
    # earlier, so both fall inside a post-fold embargo window.
    assert roles["sample_002"] is SampleRole.EMBARGOED
    assert roles["sample_003"] is SampleRole.EMBARGOED


def test_named_opt_out_restores_the_fold_cutoff_expectation() -> None:
    """The integration test's actual subject: delayed labels are purged.

    With an explicit, named embargo opt-out (as the integration test now passes),
    the fold-cutoff behaviour the test was written to verify is preserved.
    """
    manifest = assign_folds(
        _records(),
        _policy(),
        enforce_inter_fold_embargo=False,
        embargo_opt_out_reason=(
            "fold-cutoff/delayed-label fixture; embargo semantics are covered by "
            "test_splits.py and not the subject of this assertion"
        ),
    )
    roles = {sid: a.role for sid, a in manifest.assignments.items()}
    assert roles["sample_000"] is SampleRole.TRAIN
    assert roles["sample_001"] is SampleRole.PURGED
    assert roles["sample_002"] is SampleRole.VALIDATION
    assert roles["sample_003"] is SampleRole.SEALED_TEST


def test_opt_out_without_a_named_reason_is_rejected() -> None:
    """The opt-out must be auditable, not silent."""
    with pytest.raises(ValueError, match="EMBARGO_OPT_OUT_REASON_REQUIRED"):
        assign_folds(_records(), _policy(), enforce_inter_fold_embargo=False)
