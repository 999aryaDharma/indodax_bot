"""Unit tests for F01-02 Staged foundation adaptation.

Guarantees:
1. F01-02-AC0: Zero-shot -> frozen probe -> bounded adapter menghasilkan forecast teruji via common mapper (test_f01_02_valid_contract).
2. F01-02-AC1: Stage sebelumnya harus terdokumentasi; loncat stage ditolak fail-closed (test_f01_02_contract_1).
3. F01-02-AC2: Full fine-tune bukan default; ditolak tanpa otorisasi eksplisit (test_f01_02_contract_2).
4. F01-02-AC3: Contaminated pre-cutoff dates tidak boleh menjadi sealed benchmark claim (test_f01_02_contract_3).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import numpy as np
import pytest

from indodax_lab.models.execution_mapper import (
    CostAwareExecutionMapper,
    CostBasis,
    DecisionAction,
)
from indodax_lab.models.foundation.f01_kronos import (
    AdaptationStage,
    ContaminatedDatesClaimError,
    FoundationAdaptationConfig,
    FullFineTuneForbiddenError,
    StagePreconditionNotMetError,
    StagedFoundationAdapter,
)
from indodax_lab.models.foundation.provenance import (
    FakeFoundationModelAdapter,
)


def _generate_synthetic_foundation_features(
    n_samples: int = 50,
    feature_dim: int = 16,
    start_dt: datetime | None = None,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, list[datetime]]:
    rng = np.random.default_rng(seed)
    X = rng.normal(0.0, 1.0, size=(n_samples, feature_dim))
    y = (X[:, 0] * 0.5 - X[:, 1] * 0.3 + rng.normal(0.0, 0.1, size=n_samples) > 0.0).astype(float)

    start = start_dt or datetime(2024, 6, 1, 0, 0, tzinfo=UTC)
    timestamps = [start + timedelta(hours=i) for i in range(n_samples)]
    return X, y, timestamps


def test_f01_02_valid_contract() -> None:
    """F01-02-AC0: Zero-shot -> frozen probe -> bounded adapter menghasilkan forecast via common mapper."""
    fake_adapter = FakeFoundationModelAdapter()
    _, provenance = fake_adapter.get_test_weights_and_provenance()

    # Post-cutoff dataset (cutoff is 2023-12-01, dataset is from 2024-06-01)
    train_x, train_y, _ = _generate_synthetic_foundation_features(n_samples=60, seed=42)
    test_x, test_y, test_ts = _generate_synthetic_foundation_features(
        n_samples=20, start_dt=datetime(2024, 7, 1, 0, 0, tzinfo=UTC), seed=43
    )

    adapter = StagedFoundationAdapter(provenance=provenance)

    # 1. Execute Zero-shot stage
    zs_res = adapter.run_zero_shot(test_x=test_x, test_y=test_y, test_timestamps=test_ts)
    assert zs_res.stage == AdaptationStage.ZERO_SHOT
    assert zs_res.brier_score >= 0.0

    # 2. Execute Frozen Probe stage
    fp_res = adapter.run_frozen_probe(
        train_x=train_x,
        train_y=train_y,
        test_x=test_x,
        test_y=test_y,
        test_timestamps=test_ts,
    )
    assert fp_res.stage == AdaptationStage.FROZEN_PROBE
    assert fp_res.brier_score >= 0.0

    # 3. Execute Bounded Adapter stage
    ba_res = adapter.run_bounded_adapter(
        train_x=train_x,
        train_y=train_y,
        test_x=test_x,
        test_y=test_y,
        test_timestamps=test_ts,
    )
    assert ba_res.stage == AdaptationStage.BOUNDED_ADAPTER

    # Connect to common CostAwareExecutionMapper
    cost_basis = CostBasis(estimated_round_trip_cost=0.0040, safety_margin=0.0015)
    mapper = CostAwareExecutionMapper(cost_basis=cost_basis)
    decisions = adapter.predict_forecasts(
        test_x=test_x,
        pair="BTC_IDR",
        decision_ts=datetime(2024, 7, 1, 12, 0, tzinfo=UTC),
        mapper=mapper,
        desired_qty=Decimal("0.05"),
    )

    assert len(decisions) == len(test_x)
    for d in decisions:
        assert d.action in (DecisionAction.INTENT, DecisionAction.ABSTAIN)


def test_f01_02_contract_1() -> None:
    """F01-02-AC1: Stage sebelumnya harus terdokumentasi; loncat stage ditolak fail-closed."""
    fake_adapter = FakeFoundationModelAdapter()
    _, provenance = fake_adapter.get_test_weights_and_provenance()

    train_x, train_y, _ = _generate_synthetic_foundation_features(n_samples=40)
    test_x, test_y, test_ts = _generate_synthetic_foundation_features(
        n_samples=20, start_dt=datetime(2024, 7, 1, 0, 0, tzinfo=UTC)
    )

    adapter = StagedFoundationAdapter(provenance=provenance)

    # Attempting to run Frozen Probe without Zero-Shot must fail
    with pytest.raises(StagePreconditionNotMetError, match="STAGE_PRECONDITION_NOT_MET: ZERO_SHOT required"):
        adapter.run_frozen_probe(
            train_x=train_x,
            train_y=train_y,
            test_x=test_x,
            test_y=test_y,
            test_timestamps=test_ts,
        )

    # Attempting to run Bounded Adapter without Frozen Probe must fail
    adapter.run_zero_shot(test_x=test_x, test_y=test_y, test_timestamps=test_ts)
    with pytest.raises(StagePreconditionNotMetError, match="STAGE_PRECONDITION_NOT_MET: FROZEN_PROBE required"):
        adapter.run_bounded_adapter(
            train_x=train_x,
            train_y=train_y,
            test_x=test_x,
            test_y=test_y,
            test_timestamps=test_ts,
        )


def test_f01_02_contract_2() -> None:
    """F01-02-AC2: Full fine tune bukan default; ditolak tanpa otorisasi eksplisit."""
    fake_adapter = FakeFoundationModelAdapter()
    _, provenance = fake_adapter.get_test_weights_and_provenance()

    # Default config has allow_full_fine_tune = False
    default_config = FoundationAdaptationConfig(stage=AdaptationStage.FULL_FINE_TUNE)
    adapter = StagedFoundationAdapter(provenance=provenance, config=default_config)

    train_x, train_y, _ = _generate_synthetic_foundation_features(n_samples=40)
    test_x, test_y, test_ts = _generate_synthetic_foundation_features(
        n_samples=20, start_dt=datetime(2024, 7, 1, 0, 0, tzinfo=UTC)
    )

    with pytest.raises(FullFineTuneForbiddenError, match="FULL_FINE_TUNE_FORBIDDEN"):
        adapter.run_full_fine_tune(train_x=train_x, train_y=train_y, test_x=test_x, test_y=test_y)


def test_f01_02_contract_3() -> None:
    """F01-02-AC3: Contaminated dates tidak menjadi sealed claim."""
    fake_adapter = FakeFoundationModelAdapter()
    _, provenance = fake_adapter.get_test_weights_and_provenance()
    # Provenance cutoff is 2023-12-01

    # Contaminated test dataset containing dates prior to cutoff (e.g. 2023-10-01)
    test_x, test_y, contaminated_ts = _generate_synthetic_foundation_features(
        n_samples=20, start_dt=datetime(2023, 10, 1, 0, 0, tzinfo=UTC)
    )

    adapter = StagedFoundationAdapter(provenance=provenance)

    # Attempting to claim benchmark on contaminated dates must fail
    with pytest.raises(ContaminatedDatesClaimError, match="CONTAMINATED_DATES_FORBIDDEN"):
        adapter.run_zero_shot(test_x=test_x, test_y=test_y, test_timestamps=contaminated_ts)
