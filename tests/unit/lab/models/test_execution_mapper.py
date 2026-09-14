"""Unit tests for ML-02 Held-out calibration and cost mapper.

Acceptance Criteria:
- ML-02-AC0 (test_ml_02_valid_contract): Forecast terkalibrasi hanya menjadi intent ketika net edge melampaui margin.
- ML-02-AC1 (test_ml_02_contract_1): Calibrator memakai inner held-out segment.
- ML-02-AC2 (test_ml_02_contract_2): Dataset calibration terlalu kecil memblokir.
- ML-02-AC3 (test_ml_02_contract_3): Gross dan net equivalent forecast menghasilkan keputusan sama.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import numpy as np
import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.models.calibration import (
    CalibrationSegmentError,
    FittedCalibratorArtifact,
    HeldOutCalibrator,
    InsufficientCalibrationDataError,
)
from indodax_lab.models.execution_mapper import (
    CostAwareExecutionMapper,
    CostBasis,
    DecisionAction,
    ExecutionDecision,
    ForecastKind,
    ForecastPayload,
    PayoffStructure,
)


def test_ml_02_valid_contract() -> None:
    """ML-02-AC0: Forecast terkalibrasi hanya menjadi intent ketika net edge melampaui margin."""
    cost_basis = CostBasis(
        estimated_round_trip_cost=0.0040,  # 0.40% round trip cost
        safety_margin=0.0015,  # 0.15% minimum safety edge
    )
    mapper = CostAwareExecutionMapper(cost_basis=cost_basis)

    # 1. Forecast with insufficient edge: net return = 0.0010 <= 0.0015 -> ABSTAIN
    decision_ts = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    payload_low = ForecastPayload(
        kind=ForecastKind.NET_RETURN,
        value=0.0010,
        pair="BTC_IDR",
        decision_ts=decision_ts,
        desired_qty=Decimal("0.05"),
    )
    decision_low = mapper.evaluate_forecast(payload_low)
    assert decision_low.action == DecisionAction.ABSTAIN
    assert decision_low.signal_intent is None
    assert "INSUFFICIENT_NET_EDGE" in decision_low.reasons
    assert pytest.approx(decision_low.net_edge) == 0.0010

    # 2. Forecast with sufficient edge: net return = 0.0035 > 0.0015 -> INTENT
    payload_high = ForecastPayload(
        kind=ForecastKind.NET_RETURN,
        value=0.0035,
        pair="BTC_IDR",
        decision_ts=decision_ts,
        desired_qty=Decimal("0.05"),
        stop_loss=Decimal("950000000"),
        take_profit=Decimal("1050000000"),
    )
    decision_high = mapper.evaluate_forecast(payload_high)
    assert decision_high.action == DecisionAction.INTENT
    assert decision_high.signal_intent is not None
    assert isinstance(decision_high.signal_intent, SignalIntent)
    assert decision_high.signal_intent.pair == "BTC_IDR"
    assert decision_high.signal_intent.desired_qty == Decimal("0.05")
    assert decision_high.signal_intent.stop_loss == Decimal("950000000")
    assert decision_high.signal_intent.take_profit == Decimal("1050000000")
    assert pytest.approx(decision_high.net_edge) == 0.0035

    # 3. Probability forecast with payoff mapping
    # win = +0.03, loss = -0.015. With p = 0.70:
    # gross_edge = 0.70 * 0.03 + 0.30 * (-0.015) = 0.021 - 0.0045 = 0.0165
    # net_edge = 0.0165 - 0.0040 (round trip cost applied once) = 0.0125 > 0.0015 -> INTENT
    payload_prob = ForecastPayload(
        kind=ForecastKind.PROBABILITY,
        value=0.70,
        pair="BTC_IDR",
        decision_ts=decision_ts,
        desired_qty=Decimal("0.10"),
        payoff=PayoffStructure(win_return=0.03, loss_return=-0.015),
    )
    decision_prob = mapper.evaluate_forecast(payload_prob)
    assert decision_prob.action == DecisionAction.INTENT
    assert decision_prob.signal_intent is not None
    assert pytest.approx(decision_prob.net_edge, rel=1e-4) == 0.0125


def test_ml_02_contract_1() -> None:
    """ML-02-AC1: Calibrator memakai inner held-out segment."""
    calibrator = HeldOutCalibrator(min_calibration_samples=50, min_positives=10)

    np.random.seed(42)
    scores = np.random.normal(0.0, 1.0, size=100)
    # Binary labels correlated with scores
    probs = 1.0 / (1.0 + np.exp(-scores))
    labels = (probs > 0.5).astype(int)

    # Invariant: Training segment is forbidden for calibration
    with pytest.raises(CalibrationSegmentError, match="CALIBRATOR_MUST_USE_INNER_HELDOUT_SEGMENT"):
        calibrator.fit(scores, labels, segment_type="train")

    with pytest.raises(CalibrationSegmentError, match="CALIBRATOR_MUST_USE_INNER_HELDOUT_SEGMENT"):
        calibrator.fit(scores, labels, segment_type="sealed_test")

    with pytest.raises(CalibrationSegmentError, match="CALIBRATOR_MUST_USE_INNER_HELDOUT_SEGMENT"):
        calibrator.fit(scores, labels, segment_type="test")

    # Valid inner held-out segment succeeds
    artifact = calibrator.fit(scores, labels, segment_type="inner_heldout")
    assert isinstance(artifact, FittedCalibratorArtifact)
    assert artifact.segment_type == "inner_heldout"
    assert artifact.n_samples == 100

    calibrated_probs = calibrator.predict_probability(scores[:5])
    assert len(calibrated_probs) == 5
    assert np.all((calibrated_probs >= 0.0) & (calibrated_probs <= 1.0))


def test_ml_02_contract_2() -> None:
    """ML-02-AC2: Dataset calibration terlalu kecil memblokir."""
    calibrator = HeldOutCalibrator(min_calibration_samples=50, min_positives=10)

    # 1. Less than min_calibration_samples (e.g. 20 samples)
    tiny_scores = np.linspace(-1.0, 1.0, num=20)
    tiny_labels = np.array([0] * 10 + [1] * 10)

    with pytest.raises(InsufficientCalibrationDataError, match="CALIBRATION_DATASET_TOO_SMALL"):
        calibrator.fit(tiny_scores, tiny_labels, segment_type="inner_heldout")

    # 2. Enough samples (60 samples) but insufficient positive classes (e.g. only 2 positives)
    skewed_scores = np.random.normal(0.0, 1.0, size=60)
    skewed_labels = np.array([0] * 58 + [1] * 2)

    with pytest.raises(InsufficientCalibrationDataError, match="INSUFFICIENT_CLASS_REPRESENTATION"):
        calibrator.fit(skewed_scores, skewed_labels, segment_type="inner_heldout")


def test_ml_02_contract_3() -> None:
    """ML-02-AC3: Gross dan net equivalent forecast menghasilkan keputusan sama."""
    cost_basis = CostBasis(
        estimated_round_trip_cost=0.0040,  # 0.40%
        safety_margin=0.0010,  # 0.10%
    )
    mapper = CostAwareExecutionMapper(cost_basis=cost_basis)
    decision_ts = datetime(2025, 6, 1, 14, 0, tzinfo=UTC)

    # Scenario A: Profitable / Intent
    # Gross expected return = 0.0070 (0.70%)
    # Net edge = 0.0070 - 0.0040 = 0.0030 (0.30%) > 0.0010
    # Equivalent Net expected return = 0.0030 (0.30%)
    gross_payload_high = ForecastPayload(
        kind=ForecastKind.GROSS_RETURN,
        value=0.0070,
        pair="ETH_IDR",
        decision_ts=decision_ts,
        desired_qty=Decimal("1.5"),
    )
    net_payload_high = ForecastPayload(
        kind=ForecastKind.NET_RETURN,
        value=0.0030,
        pair="ETH_IDR",
        decision_ts=decision_ts,
        desired_qty=Decimal("1.5"),
    )

    decision_gross_high = mapper.evaluate_forecast(gross_payload_high)
    decision_net_high = mapper.evaluate_forecast(net_payload_high)

    # Both must reach the EXACT same decision: INTENT
    assert decision_gross_high.action == DecisionAction.INTENT
    assert decision_net_high.action == DecisionAction.INTENT
    assert pytest.approx(decision_gross_high.net_edge) == pytest.approx(decision_net_high.net_edge)
    assert decision_gross_high.signal_intent is not None
    assert decision_net_high.signal_intent is not None
    assert decision_gross_high.signal_intent.desired_qty == decision_net_high.signal_intent.desired_qty
    assert decision_gross_high.signal_intent.pair == decision_net_high.signal_intent.pair

    # Scenario B: Unprofitable / Abstain
    # Gross expected return = 0.0045 (0.45%) -> net edge = 0.0045 - 0.0040 = 0.0005 <= 0.0010 -> ABSTAIN
    # Equivalent Net expected return = 0.0005 (0.05%) -> net edge = 0.0005 <= 0.0010 -> ABSTAIN
    gross_payload_low = ForecastPayload(
        kind=ForecastKind.GROSS_RETURN,
        value=0.0045,
        pair="ETH_IDR",
        decision_ts=decision_ts,
        desired_qty=Decimal("1.5"),
    )
    net_payload_low = ForecastPayload(
        kind=ForecastKind.NET_RETURN,
        value=0.0005,
        pair="ETH_IDR",
        decision_ts=decision_ts,
        desired_qty=Decimal("1.5"),
    )

    decision_gross_low = mapper.evaluate_forecast(gross_payload_low)
    decision_net_low = mapper.evaluate_forecast(net_payload_low)

    # Both must reach the EXACT same decision: ABSTAIN
    assert decision_gross_low.action == DecisionAction.ABSTAIN
    assert decision_net_low.action == DecisionAction.ABSTAIN
    assert pytest.approx(decision_gross_low.net_edge) == pytest.approx(decision_net_low.net_edge)
    assert decision_gross_low.signal_intent is None
    assert decision_net_low.signal_intent is None


def test_ml_02_edge_cases_and_guards() -> None:
    """Edge cases: timezone validation, payoff constraints, unfitted errors, and bounds."""
    # 1. Non-UTC naive datetime rejected
    with pytest.raises(ValueError, match="UTC_TIMEZONE_AWARE_REQUIRED"):
        ForecastPayload(
            kind=ForecastKind.NET_RETURN,
            value=0.01,
            pair="BTC_IDR",
            decision_ts=datetime(2025, 6, 1, 12, 0),  # naive
            desired_qty=Decimal("0.1"),
        )

    # 2. Probability bounds and missing payoff
    utc_now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="PROBABILITY_OUT_OF_BOUNDS"):
        ForecastPayload(
            kind=ForecastKind.PROBABILITY,
            value=1.5,  # > 1.0
            pair="BTC_IDR",
            decision_ts=utc_now,
            desired_qty=Decimal("0.1"),
            payoff=PayoffStructure(win_return=0.02, loss_return=-0.01),
        )

    with pytest.raises(ValueError, match="PAYOFF_STRUCTURE_REQUIRED_FOR_PROBABILITY_FORECAST"):
        ForecastPayload(
            kind=ForecastKind.PROBABILITY,
            value=0.6,
            pair="BTC_IDR",
            decision_ts=utc_now,
            desired_qty=Decimal("0.1"),
            payoff=None,
        )

    # 3. Payoff structure validation
    with pytest.raises(ValueError, match="WIN_RETURN_MUST_BE_POSITIVE"):
        PayoffStructure(win_return=-0.01, loss_return=-0.02)

    with pytest.raises(ValueError, match="LOSS_RETURN_MUST_BE_NEGATIVE"):
        PayoffStructure(win_return=0.02, loss_return=0.01)

    # 4. CostBasis non-negative validation
    with pytest.raises(ValueError, match="NON_NEGATIVE_VALUE_REQUIRED"):
        CostBasis(estimated_round_trip_cost=-0.001, safety_margin=0.001)

    # 5. Unfitted calibrator
    calibrator = HeldOutCalibrator()
    with pytest.raises(Exception, match="HeldOutCalibrator is not fitted"):
        _ = calibrator.is_fitted
        calibrator.predict_probability([0.5])

