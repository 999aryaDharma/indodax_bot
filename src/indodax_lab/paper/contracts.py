"""Forward paper decision contracts and in-memory store (SHADOW-01).

Contract: frozen candidate + live available features -> immutable prediction/decision with paper intent only.

Guarantees:
1. SHADOW-01-AC0: ForwardDecision stored before outcome; immutable; no callback selection bias.
2. SHADOW-01-AC1: Telegram failure does NOT delete or void the stored decision.
3. SHADOW-01-AC2: Stale feature data or model bundle hash mismatch rejects entry fail-closed.
4. SHADOW-01-AC3: Manual intent flag preserved; manual decisions cannot become ground truth.

Security: Paper-only intent; no real-money execution; no shell injection; decisions are immutable after recording.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class StaleDataError(ValueError):
    """Raised when a forward decision is attempted with feature data beyond the staleness threshold."""


class ModelMismatchError(ValueError):
    """Raised when the bundle hash in a forward decision does not match the expected hash."""


class DuplicateDecisionError(ValueError):
    """Raised when a decision with the same ID is recorded more than once."""


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class ForwardDecisionStatus(StrEnum):
    """Lifecycle status of a forward paper decision."""

    PENDING = "PENDING"       # Recorded, outcome not yet observed
    CLOSED = "CLOSED"         # Outcome observed and recorded
    VOIDED = "VOIDED"         # Explicitly voided by operator (audited, not auto)


class ForwardDecision(BaseModel):
    """Immutable forward paper decision capturing prediction and risk intent before outcome.

    Decisions are recorded *before* any market outcome is observed. This prevents
    look-ahead bias and callback selection bias (SHADOW-01-AC0).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str
    candidate_id: str
    bundle_hash: str
    snapshot_id: str
    feature_snapshot_age_seconds: float
    max_staleness_seconds: float
    probability: float
    action: str  # e.g. "ENTER", "HOLD", "EXIT"
    is_manual_intent: bool = False
    decided_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    parameters: dict[str, Any] = {}


class ForwardDecisionRecord(BaseModel):
    """Stored record of a forward decision with notification and status metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str
    candidate_id: str
    bundle_hash: str
    snapshot_id: str
    probability: float
    action: str
    is_manual_intent: bool
    status: ForwardDecisionStatus
    decided_at_utc: datetime
    telegram_notified: bool = False
    telegram_error: str | None = None
    recorded_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ManualIntentRecord(BaseModel):
    """Record of a human operator intent — NOT ground truth, paper-only signal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intent_id: str
    decision_id: str
    operator_note: str
    recorded_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# PaperDecisionStore — in-memory guarded store
# ---------------------------------------------------------------------------


class PaperDecisionStore:
    """In-memory store for forward paper decisions with staleness and hash guards.

    Designed to be dependency-injected; real persistence adapters use the same interface.
    No real-money execution, no HTTP, no external I/O in this pure domain layer.
    """

    def __init__(self) -> None:
        self._decisions: dict[str, ForwardDecisionRecord] = {}

    def record_decision(
        self,
        decision: ForwardDecision,
        expected_bundle_hash: str | None = None,
    ) -> ForwardDecisionRecord:
        """Record a forward paper decision after validating staleness and hash constraints.

        Args:
            decision: The ``ForwardDecision`` to store.
            expected_bundle_hash: If provided, the stored ``bundle_hash`` must match this
                value. Mismatch raises ``ModelMismatchError`` (SHADOW-01-AC2).

        Returns:
            A ``ForwardDecisionRecord`` with ``status=PENDING``.

        Raises:
            DuplicateDecisionError: If ``decision.decision_id`` already exists (idempotency guard).
            StaleDataError: If ``feature_snapshot_age_seconds > max_staleness_seconds`` (SHADOW-01-AC2).
            ModelMismatchError: If ``expected_bundle_hash`` is provided and does not match (SHADOW-01-AC2).
        """
        # Idempotency guard
        if decision.decision_id in self._decisions:
            raise DuplicateDecisionError(
                f"DUPLICATE_DECISION_ID: Decision '{decision.decision_id}' is already recorded. "
                "Forward decisions are immutable once stored; re-submission is not permitted."
            )

        # AC2: Staleness check
        if decision.feature_snapshot_age_seconds > decision.max_staleness_seconds:
            raise StaleDataError(
                f"STALE_DATA_REJECTED: Feature snapshot age {decision.feature_snapshot_age_seconds:.1f}s "
                f"exceeds maximum allowed staleness {decision.max_staleness_seconds:.1f}s. "
                "Entry blocked to prevent decisions on outdated market information."
            )

        # AC2: Bundle hash mismatch check
        if expected_bundle_hash is not None and decision.bundle_hash != expected_bundle_hash:
            raise ModelMismatchError(
                f"MODEL_HASH_MISMATCH: Decision bundle_hash='{decision.bundle_hash}' "
                f"does not match expected_bundle_hash='{expected_bundle_hash}'. "
                "Entry rejected to prevent decisions from a mismatched or stale model version."
            )

        # AC0: Store decision BEFORE any notification attempt
        record = ForwardDecisionRecord(
            decision_id=decision.decision_id,
            candidate_id=decision.candidate_id,
            bundle_hash=decision.bundle_hash,
            snapshot_id=decision.snapshot_id,
            probability=decision.probability,
            action=decision.action,
            is_manual_intent=decision.is_manual_intent,
            status=ForwardDecisionStatus.PENDING,
            decided_at_utc=decision.decided_at_utc,
            telegram_notified=False,
        )
        self._decisions[decision.decision_id] = record
        return record

    def notify_telegram(
        self,
        decision_id: str,
        telegram_error: Exception | None = None,
    ) -> ForwardDecisionRecord:
        """Attempt to send Telegram notification; failure preserves the decision (SHADOW-01-AC1).

        The decision is already persisted before this call. A Telegram failure records
        the error reason but does NOT change decision status to VOIDED or FAILED.

        Args:
            decision_id: ID of the decision to notify about.
            telegram_error: If not None, notification failed with this exception.

        Returns:
            Updated ``ForwardDecisionRecord`` (telegram_notified reflects outcome).
        """
        record = self._decisions.get(decision_id)
        if record is None:
            raise KeyError(f"DECISION_NOT_FOUND: No decision with id='{decision_id}'")

        if telegram_error is not None:
            # AC1: Decision status remains PENDING — Telegram failure does NOT void/delete it
            updated = ForwardDecisionRecord(
                decision_id=record.decision_id,
                candidate_id=record.candidate_id,
                bundle_hash=record.bundle_hash,
                snapshot_id=record.snapshot_id,
                probability=record.probability,
                action=record.action,
                is_manual_intent=record.is_manual_intent,
                status=record.status,  # unchanged: still PENDING
                decided_at_utc=record.decided_at_utc,
                telegram_notified=False,
                telegram_error=str(telegram_error),
                recorded_at_utc=record.recorded_at_utc,
            )
        else:
            updated = ForwardDecisionRecord(
                decision_id=record.decision_id,
                candidate_id=record.candidate_id,
                bundle_hash=record.bundle_hash,
                snapshot_id=record.snapshot_id,
                probability=record.probability,
                action=record.action,
                is_manual_intent=record.is_manual_intent,
                status=record.status,
                decided_at_utc=record.decided_at_utc,
                telegram_notified=True,
                telegram_error=None,
                recorded_at_utc=record.recorded_at_utc,
            )

        self._decisions[decision_id] = updated
        return updated

    def get_decision(self, decision_id: str) -> ForwardDecisionRecord | None:
        """Retrieve a stored forward decision by ID."""
        return self._decisions.get(decision_id)

    def mark_as_ground_truth(self, decision_id: str) -> None:
        """Attempt to promote a decision to ground truth status.

        Always raises for manual intent decisions (SHADOW-01-AC3).
        Manual intent is paper-only and cannot be authoritative ground truth.
        """
        record = self._decisions.get(decision_id)
        if record is None:
            raise KeyError(f"DECISION_NOT_FOUND: No decision with id='{decision_id}'")

        if record.is_manual_intent:
            raise ValueError(
                f"MANUAL_INTENT_NOT_GROUND_TRUTH: Decision '{decision_id}' was recorded "
                "as manual intent (human override). Manual intent is paper-only and cannot "
                "be designated as authoritative ground truth. Outcomes must be observed from "
                "market events, not operator overrides."
            )
