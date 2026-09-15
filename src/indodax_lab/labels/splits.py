"""Sealed purged chronological fold assignment and manifest generator (SPLIT-01).

Contract:
sample IDs + label_end_ts + declared exposure history -> versioned roles, purge and embargo manifest.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
import hashlib
import json
from typing import Any, Sequence, Literal
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
        if self.max_horizon_hours <= 0 or self.embargo_hours < 0:
            raise ValueError("POSITIVE_HORIZON_NONNEGATIVE_EMBARGO_REQUIRED")
        ordered = sorted(self.folds, key=lambda f: f.start_ts)
        if any(left.end_ts > right.start_ts for left, right in zip(ordered, ordered[1:])):
            raise ValueError("OVERLAPPING_FOLDS_FORBIDDEN")
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
    label_available_at: datetime | None = None

    @field_validator("decision_ts", "label_end_ts", "label_available_at", mode="after")
    @classmethod
    def validate_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _ensure_utc(value, "sample_timestamp")


class FoldAssignment(BaseModel):
    """Sample assignment to fold role with purge/embargo rationale."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str
    role: SampleRole
    fold_role: SampleRole | None = None
    purge_reason: str | None = None
    fold_start_ts: datetime | None = None
    fold_end_ts: datetime | None = None

    @field_validator("fold_start_ts", "fold_end_ts")
    @classmethod
    def validate_boundary(cls, value: datetime | None) -> datetime | None:
        return _ensure_utc(value, "fold_boundary") if value is not None else None


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
    identity_version: Literal["split-v2"] = "split-v2"
    policy_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


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
    identities = [s.sample_id for s in samples]
    if any(not identity.strip() for identity in identities):
        raise ValueError("SAMPLE_ID_REQUIRED")
    if len(set(identities)) != len(identities):
        raise ValueError("DUPLICATE_SAMPLE_ID")
    policy_payload = split_policy.model_dump(mode="json")
    policy_payload["enforce_inter_fold_embargo"] = enforce_inter_fold_embargo
    policy_digest = hashlib.sha256(json.dumps(policy_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if exposure_log:
        for fold in split_policy.folds:
            if fold.role == SampleRole.SEALED_TEST:
                for exp in exposure_log:
                    exp_start = _ensure_utc(exp["exposed_start"], "exposed_start")
                    exp_end = _ensure_utc(exp["exposed_end"], "exposed_end")
                    # Check for temporal overlap
                    if fold.start_ts < exp_end and exp_start < fold.end_ts:
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
            if fold.start_ts <= s.decision_ts < fold.end_ts:
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

        if s.label_available_at is None:
            assignments[s.sample_id] = FoldAssignment(
                sample_id=s.sample_id, role=SampleRole.EXCLUDED,
                fold_role=matched_fold.role, purge_reason="LABEL_AVAILABILITY_UNKNOWN",
            )
            continue

        # Check inter-fold embargo
        if enforce_inter_fold_embargo:
            is_embargoed = False
            for prior_fold in split_policy.folds:
                if prior_fold.end_ts <= matched_fold.start_ts:
                    embargo_boundary = prior_fold.end_ts + embargo_delta
                    if prior_fold.end_ts <= s.decision_ts < embargo_boundary:
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
        if max(s.label_end_ts, s.label_available_at) >= matched_fold.end_ts:
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
            fold_start_ts=matched_fold.start_ts,
            fold_end_ts=matched_fold.end_ts,
        )
        assignments[s.sample_id] = assignment

        if role == SampleRole.TRAIN:
            train_c += 1
        elif role == SampleRole.VALIDATION:
            val_c += 1
        elif role == SampleRole.SEALED_TEST:
            test_c += 1

    identity_payload = {
        "domain": "split-v2", "policy": policy_digest,
        "samples": [s.model_dump(mode="json") for s in sorted(samples, key=lambda s: s.sample_id)],
        "assignments": {k: v.model_dump(mode="json") for k, v in sorted(assignments.items())},
        "exposure": sorted([json.dumps(e, sort_keys=True, default=lambda v: v.isoformat()) for e in (exposure_log or [])]),
    }
    split_digest = hashlib.sha256(json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return SplitManifest(
        split_id=f"split_v2_{split_digest}",
        policy_content_sha256=policy_digest,
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
