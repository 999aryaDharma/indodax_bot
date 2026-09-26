"""Fail-closed regression tests for SPLIT-01 sealed purged chronological folds.

Review finding covered:
- SPLIT-01-F1 (Important): ``assign_folds(..., enforce_inter_fold_embargo: bool = False)``
  made the safe behaviour opt-in, so any caller that forgot the argument silently received
  no inter-fold embargo and training data leaked across the fold boundary. Enforcement must
  be the default, and any opt-out must carry an explicit, named, auditable reason.

opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
"""

from __future__ import annotations

from datetime import UTC, datetime
import inspect

import pytest

from indodax_lab.labels.splits import (
    FoldWindow,
    SampleRecord,
    SampleRole,
    SplitPolicy,
    assign_folds,
)

FOLD_1_END = datetime(2024, 1, 2, tzinfo=UTC)
FOLD_2_END = datetime(2024, 1, 6, tzinfo=UTC)


def _policy() -> SplitPolicy:
    return SplitPolicy(
        policy_id="adjacent",
        version="1",
        embargo_hours=24,
        max_horizon_hours=24,
        folds=[
            FoldWindow(
                role=SampleRole.TRAIN,
                start_ts=datetime(2024, 1, 1, tzinfo=UTC),
                end_ts=FOLD_1_END,
            ),
            FoldWindow(
                role=SampleRole.VALIDATION,
                start_ts=FOLD_1_END,
                end_ts=FOLD_2_END,
            ),
        ],
    )


def _record(sample_id: str, decision_ts: datetime) -> SampleRecord:
    return SampleRecord(
        sample_id=sample_id,
        pair="btc_idr",
        decision_ts=decision_ts,
        label_end_ts=decision_ts.replace(hour=23),
        label_available_at=decision_ts.replace(hour=23),
    )


def test_split_01_inter_fold_embargo_is_enforced_by_default() -> None:
    """SPLIT-01-F1: a caller who forgets the argument must still get the embargo."""
    # 01:30 sits 1.5h after the TRAIN fold closes, i.e. inside the 24h embargo window.
    sample = _record("s_default", datetime(2024, 1, 2, 1, 30, tzinfo=UTC))

    manifest = assign_folds([sample], _policy())

    assert manifest.assignments["s_default"].role == SampleRole.EMBARGOED
    assert manifest.embargoed_count == 1


def test_split_01_embargo_enforcement_default_is_true_in_the_signature() -> None:
    """SPLIT-01-F1: the default itself must be the safe value."""
    default = inspect.signature(assign_folds).parameters["enforce_inter_fold_embargo"].default
    assert default is True, (
        "enforce_inter_fold_embargo must default to True; a False default silently disables "
        "the inter-fold embargo for every caller that omits the argument"
    )


def test_split_01_opt_out_requires_a_named_auditable_reason() -> None:
    """SPLIT-01-F1: an embargo opt-out must not be silent."""
    sample = _record("s_optout", datetime(2024, 1, 2, 1, 30, tzinfo=UTC))
    policy = _policy()

    with pytest.raises(ValueError) as exc_info:
        assign_folds([sample], policy, enforce_inter_fold_embargo=False)
    message = str(exc_info.value)
    assert "EMBARGO_OPT_OUT_REASON_REQUIRED" in message
    assert "enforce_inter_fold_embargo" in message

    # Blank / whitespace-only reasons are not a reason either.
    with pytest.raises(ValueError, match="EMBARGO_OPT_OUT_REASON_REQUIRED"):
        assign_folds([sample], policy, enforce_inter_fold_embargo=False,
                     embargo_opt_out_reason="   ")


def test_split_01_named_opt_out_reason_still_disables_the_embargo() -> None:
    """SPLIT-01-F1: an explicit, reasoned opt-out remains possible and is auditable."""
    sample = _record("s_optout_ok", datetime(2024, 1, 2, 1, 30, tzinfo=UTC))

    manifest = assign_folds(
        [sample],
        _policy(),
        enforce_inter_fold_embargo=False,
        embargo_opt_out_reason="single-fold diagnostic fixture; no inter-fold boundary exists",
    )

    assert manifest.assignments["s_optout_ok"].role == SampleRole.VALIDATION
    assert manifest.embargoed_count == 0


def test_split_01_opt_out_changes_the_split_identity() -> None:
    """SPLIT-01-F1: the opt-out is content-addressed, so it is visible in the manifest."""
    sample = _record("s_identity", datetime(2024, 1, 2, 1, 30, tzinfo=UTC))
    policy = _policy()

    enforced = assign_folds([sample], policy)
    opted_out = assign_folds(
        [sample],
        policy,
        enforce_inter_fold_embargo=False,
        embargo_opt_out_reason="single-fold diagnostic fixture; no inter-fold boundary exists",
    )

    assert enforced.split_id != opted_out.split_id
    assert enforced.policy_content_sha256 != opted_out.policy_content_sha256


def test_split_01_second_fold_also_gets_an_embargo_window() -> None:
    """SPLIT-01-F1: enforcement applies to every fold boundary, not just the first."""
    sample = _record("s_second", datetime(2024, 1, 6, 3, 0, tzinfo=UTC))
    policy = SplitPolicy(
        policy_id="three",
        version="1",
        embargo_hours=24,
        max_horizon_hours=24,
        folds=[
            FoldWindow(role=SampleRole.TRAIN,
                       start_ts=datetime(2024, 1, 1, tzinfo=UTC), end_ts=FOLD_1_END),
            FoldWindow(role=SampleRole.VALIDATION, start_ts=FOLD_1_END, end_ts=FOLD_2_END),
            FoldWindow(role=SampleRole.SEALED_TEST, start_ts=FOLD_2_END,
                       end_ts=datetime(2024, 1, 10, tzinfo=UTC)),
        ],
    )

    manifest = assign_folds([sample], policy)
    assert manifest.assignments["s_second"].role == SampleRole.EMBARGOED


# Actor for every line this file contributes to review evidence:
# opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
