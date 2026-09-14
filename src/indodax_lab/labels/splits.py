"""Sealed purged chronological fold assignment and manifest generator (SPLIT-01).

Contract:
sample IDs + label_end_ts + declared exposure history -> versioned roles, purge and embargo manifest.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Sequence
import pandas as pd
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def _ensure_utc(dt: datetime, field_name: str = "timestamp") -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class SampleRole(StrEnum):
    """Assignment roles for chronological dataset splits."""

    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    CALIBRATION = "CALIBRATION"
    SEALED_TEST = "SEALED_TEST"
    PURGED = "PURGED"
    EMBARGOED = "EMBARGOED"
    EXCLUDED = "EXCLUDED"


class ExposedPeriodViolationError(ValueError):
    """Raised when an evaluation period that was previously exposed is claimed as sealed test."""


class FoldWindow(BaseModel):
    """Definition of a single chronological fold window."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: SampleRole
    start_ts: datetime
    end_ts: datetime

    @field_validator("start_ts", "end_ts", mode="after")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "fold_timestamp")

    @model_validator(mode="after")
    def validate_bounds(self) -> FoldWindow:
        if self.start_ts >= self.end_ts:
            raise ValueError(f"START_TS_MUST_PRECEDE_END_TS:{self.start_ts} >= {self.end_ts}")
        return self


class SplitPolicy(BaseModel):
    """Versioned split policy with max horizon and embargo validation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str
    version: str
    max_horizon_hours: int = 24
    embargo_hours: int = 24
    folds: list[FoldWindow]

    @model_validator(mode="after")
    def validate_embargo(self) -> SplitPolicy:
        # SPLIT-01-AC2: Embargo must be at least max horizon
        if self.embargo_hours < self.max_horizon_hours:
            raise ValueError(
                f"EMBARGO_LESS_THAN_MAX_HORIZON: embargo ({self.embargo_hours}h) < max horizon ({self.max_horizon_hours}h)"
            )
        return self


class SampleRecord(BaseModel):
    """Point-in-time sample record with decision and label availability boundaries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str
    decision_ts: datetime
    label_end_ts: datetime
    pair: str

    @field_validator("decision_ts", "label_end_ts", mode="after")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "sample_timestamp")


class FoldAssignment(BaseModel):
    """Sample assignment to fold role with purge/embargo rationale."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str
    role: SampleRole
    fold_role: SampleRole | None = None
    purge_reason: str | None = None


class SplitManifest(BaseModel):
    """Immutable audit manifest of chronological fold assignment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    split_id: str
    policy_id: str
    policy_version: str
    total_samples: int
    train_count: int
    validation_count: int
    sealed_test_count: int
    purged_count: int
    embargoed_count: int
    assignments: dict[str, FoldAssignment]


def assign_folds(
    samples: Sequence[SampleRecord],
    split_policy: SplitPolicy,
    exposure_log: Sequence[dict[str, Any]] | None = None,
    enforce_inter_fold_embargo: bool = False,
) -> SplitManifest:
    """Assign chronological roles to samples, purging boundary crossers and embargoing overlap.

    Invariants:
    - SPLIT-01-AC1: Samples whose label_end_ts crosses fold boundaries are PURGED.
    - SPLIT-01-AC2: Embargo windows following fold closures are marked EMBARGOED.
    - SPLIT-01-AC3: Any sealed test fold overlapping previous exposure is strictly rejected.
    """
    # 1. SPLIT-01-AC3: Check exposure log against sealed test folds
    if exposure_log:
        for fold in split_policy.folds:
            if fold.role == SampleRole.SEALED_TEST:
                for exp in exposure_log:
                    exp_start = _ensure_utc(exp["exposed_start"], "exposed_start")
                    exp_end = _ensure_utc(exp["exposed_end"], "exposed_end")
                    # Check for temporal overlap
                    if not (fold.end_ts < exp_start or fold.start_ts > exp_end):
                        raise ExposedPeriodViolationError(
                            f"EXPOSED_PERIOD_CANNOT_BE_SEALED: fold [{fold.start_ts} .. {fold.end_ts}] "
                            f"overlaps prior exposure [{exp_start} .. {exp_end}] (run_id: {exp.get('run_id')})"
                        )

    assignments: dict[str, FoldAssignment] = {}
    train_c = 0
    val_c = 0
    test_c = 0
    purged_c = 0
    embargoed_c = 0

    embargo_delta = timedelta(hours=split_policy.embargo_hours)

    for s in samples:
        # Find matching fold window
        matched_fold: FoldWindow | None = None
        for fold in split_policy.folds:
            if fold.start_ts <= s.decision_ts <= fold.end_ts:
                matched_fold = fold
                break

        if matched_fold is None:
            assignment = FoldAssignment(
                sample_id=s.sample_id,
                role=SampleRole.EXCLUDED,
                purge_reason="OUTSIDE_ALL_FOLDS",
            )
            assignments[s.sample_id] = assignment
            continue

        # Check inter-fold embargo
        if enforce_inter_fold_embargo:
            is_embargoed = False
            for prior_fold in split_policy.folds:
                if prior_fold.end_ts < matched_fold.start_ts:
                    embargo_boundary = prior_fold.end_ts + embargo_delta
                    if prior_fold.end_ts < s.decision_ts <= embargo_boundary:
                        is_embargoed = True
                        break
            if is_embargoed:
                assignment = FoldAssignment(
                    sample_id=s.sample_id,
                    role=SampleRole.EMBARGOED,
                    fold_role=matched_fold.role,
                    purge_reason="WITHIN_EMBARGO_WINDOW",
                )
                assignments[s.sample_id] = assignment
                embargoed_c += 1
                continue

        # SPLIT-01-AC1: Boundary purge check
        if s.label_end_ts > matched_fold.end_ts:
            assignment = FoldAssignment(
                sample_id=s.sample_id,
                role=SampleRole.PURGED,
                fold_role=matched_fold.role,
                purge_reason="LABEL_OVERLAPS_FOLD_BOUNDARY",
            )
            assignments[s.sample_id] = assignment
            purged_c += 1
            continue

        # Assigned cleanly to fold role
        role = matched_fold.role
        assignment = FoldAssignment(
            sample_id=s.sample_id,
            role=role,
            fold_role=role,
        )
        assignments[s.sample_id] = assignment

        if role == SampleRole.TRAIN:
            train_c += 1
        elif role == SampleRole.VALIDATION:
            val_c += 1
        elif role == SampleRole.SEALED_TEST:
            test_c += 1

    return SplitManifest(
        split_id=f"{split_policy.policy_id}_{int(datetime.now(UTC).timestamp())}",
        policy_id=split_policy.policy_id,
        policy_version=split_policy.version,
        total_samples=len(samples),
        train_count=train_c,
        validation_count=val_c,
        sealed_test_count=test_c,
        purged_count=purged_c,
        embargoed_count=embargoed_c,
        assignments=assignments,
    )
