"""Regression tests for SHADOW-01 review findings (ops-shadow batch).

Findings covered (spec: docs/specs/14-shadow-portfolios-and-promotion.md,
acceptance boundary SHADOW-01: "Stale data atau model mismatch menolak entry"):

- S01-F1 (Critical): ``PaperDecisionStore.record_decision`` takes
  ``expected_bundle_hash: str | None = None`` and *skips* the model-mismatch check
  entirely when it is omitted. The AC2 guard therefore fails open whenever the
  caller forgets the argument: a decision produced by a completely different
  frozen model bundle is recorded as a valid PENDING entry.
- S01-F2 (Critical): ``ForwardDecision.feature_snapshot_age_seconds`` and
  ``max_staleness_seconds`` are unconstrained floats. The staleness guard is
  ``age > max_age``; a NaN or negative age (clock skew, a forged record, a
  mis-scaled unit) compares False and silently bypasses the AC2 rejection.
- S01-F3 (Important): ``probability`` is unconstrained, so NaN / out-of-range
  forecast values are stored in an immutable audit record.
- S01-F4 (Important): a rejected (stale or mismatched) entry leaves no trace.
  The store must report the blocked decision, per spec 14 "Record counts of
  rejected inputs and blocked outputs, not only successful rows."

Isolation: every test is in-memory only. No filesystem, no network, no real
ledger, no live credentials, no real orders.
"""

from __future__ import annotations

from datetime import UTC, datetime

from indodax_lab.paper.contracts import ForwardDecision, PaperDecisionStore, StaleDataError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


ACTIVE_BUNDLE_HASH = "a" * 64


def _decision(
    decision_id: str = "dec_001",
    *,
    bundle_hash: str = ACTIVE_BUNDLE_HASH,
    feature_snapshot_age_seconds: float = 30.0,
    max_staleness_seconds: float = 300.0,
    probability: float = 0.72,
) -> ForwardDecision:
    return ForwardDecision(
        decision_id=decision_id,
        candidate_id="cand_001",
        bundle_hash=bundle_hash,
        snapshot_id="snap_20260901",
        feature_snapshot_age_seconds=feature_snapshot_age_seconds,
        max_staleness_seconds=max_staleness_seconds,
        probability=probability,
        action="ENTER",
        is_manual_intent=False,
        decided_at_utc=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# S01-F1: the model-mismatch guard must never be skippable
# ---------------------------------------------------------------------------


def test_shadow_01_mismatched_bundle_hash_without_explicit_expectation_is_rejected() -> None:
    """S01-F1: a decision from another frozen bundle must not be accepted."""
    store = PaperDecisionStore()

    try:
        store.record_decision(_decision(bundle_hash="b" * 64))
    except Exception:
        return

    stored = store.get_decision("dec_001")
    assert stored is None, (
        "A forward decision from a different model bundle was accepted because the "
        "expected-bundle-hash guard is skipped when the argument is omitted"
    )


def test_shadow_01_matching_bundle_hash_is_recorded() -> None:
    """Positive control: the matching frozen bundle is accepted."""
    store = PaperDecisionStore()

    record = store.record_decision(
        _decision(), expected_bundle_hash=ACTIVE_BUNDLE_HASH
    )

    assert record.decision_id == "dec_001"


# ---------------------------------------------------------------------------
# S01-F2: the staleness guard must fail closed on nonsense measurements
# ---------------------------------------------------------------------------


def test_shadow_01_nan_feature_age_cannot_bypass_staleness_gate() -> None:
    """S01-F2: NaN snapshot age compares False against every threshold."""
    store = PaperDecisionStore()

    stored = store.get_decision("dec_nan_age")
    assert stored is None

    try:
        store.record_decision(
            _decision("dec_nan_age", feature_snapshot_age_seconds=float("nan")),
            expected_bundle_hash=ACTIVE_BUNDLE_HASH,
        )
    except Exception:
        return

    assert store.get_decision("dec_nan_age") is None, (
        "A NaN feature snapshot age silently bypassed the AC2 staleness rejection"
    )


def test_shadow_01_negative_feature_age_cannot_bypass_staleness_gate() -> None:
    """S01-F2: a negative (impossible) snapshot age also compares False."""
    store = PaperDecisionStore()

    try:
        store.record_decision(
            _decision("dec_neg_age", feature_snapshot_age_seconds=-99999.0),
            expected_bundle_hash=ACTIVE_BUNDLE_HASH,
        )
    except Exception:
        return

    assert store.get_decision("dec_neg_age") is None, (
        "A negative feature snapshot age silently bypassed the AC2 staleness rejection"
    )


def test_shadow_01_nan_probability_cannot_be_stored() -> None:
    """S01-F2/S01-F3: a NaN forecast must not enter the immutable audit record."""
    store = PaperDecisionStore()

    try:
        store.record_decision(
            _decision("dec_nan_prob", probability=float("nan")),
            expected_bundle_hash=ACTIVE_BUNDLE_HASH,
        )
    except Exception:
        return

    assert store.get_decision("dec_nan_prob") is None, (
        "A NaN probability was stored in an immutable forward decision record"
    )


# ---------------------------------------------------------------------------
# S01-F4: blocked decisions must be observable
# ---------------------------------------------------------------------------


def test_shadow_01_rejected_decisions_are_counted() -> None:
    """S01-F4: rejected entries must be observable, not silently dropped."""
    store = PaperDecisionStore(expected_bundle_hash=ACTIVE_BUNDLE_HASH)

    try:
        store.record_decision(
            _decision("dec_stale", feature_snapshot_age_seconds=400.0)
        )
    except StaleDataError:
        pass

    rejected = getattr(store, "rejected_decision_count", None)
    assert rejected == 1, (
        "A stale entry was rejected but not counted; blocked outputs must be recorded"
    )
