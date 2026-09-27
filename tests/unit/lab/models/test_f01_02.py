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
    StagedFoundationAdapter,
    StagePreconditionNotMetError,
)
from indodax_lab.models.foundation.provenance import (
    FakeFoundationModelAdapter,
    FoundationModelProvenance,
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


# ---------------------------------------------------------------------------
# Independent-review regression coverage
# ---------------------------------------------------------------------------


def _mapper() -> CostAwareExecutionMapper:
    return CostAwareExecutionMapper(
        cost_basis=CostBasis(estimated_round_trip_cost=0.0040, safety_margin=0.0015)
    )


def test_f01_02_unknown_cutoff_blocks_every_stage() -> None:
    """Critical: an unknown cutoff silently disabled the AC3 contamination guard.

    `_validate_timestamps` returned early when `training_cutoff_date is None`, so the exact
    artifacts F01-01 restricts to EXPLORATORY were scored on pre-cutoff (contaminated) data
    and produced a sealed `StageEvaluationResult`.
    """
    fake_adapter = FakeFoundationModelAdapter()
    weights, provenance = fake_adapter.get_test_weights_and_provenance()
    unknown_cutoff = FoundationModelProvenance.model_validate(
        {
            **provenance.model_dump(),
            "training_cutoff_date": None,
        }
    )

    test_x, test_y, contaminated_ts = _generate_synthetic_foundation_features(
        n_samples=20, start_dt=datetime(2023, 10, 1, 0, 0, tzinfo=UTC)
    )
    adapter = StagedFoundationAdapter(provenance=unknown_cutoff)

    with pytest.raises(
        ContaminatedDatesClaimError, match="UNKNOWN_CUTOFF_CANNOT_CERTIFY_POST_CUTOFF"
    ):
        adapter.run_zero_shot(test_x=test_x, test_y=test_y, test_timestamps=contaminated_ts)

    # Even clean-looking post-"cutoff" data cannot be certified without a known cutoff.
    clean_x, clean_y, clean_ts = _generate_synthetic_foundation_features(
        n_samples=10, start_dt=datetime(2024, 7, 1, 0, 0, tzinfo=UTC)
    )
    with pytest.raises(
        ContaminatedDatesClaimError, match="UNKNOWN_CUTOFF_CANNOT_CERTIFY_POST_CUTOFF"
    ):
        adapter.run_zero_shot(test_x=clean_x, test_y=clean_y, test_timestamps=clean_ts)

    assert weights  # provenance identity under test


def test_f01_02_forecast_without_stage_evidence_is_blocked() -> None:
    """Critical: predict_forecasts used to emit decisions from an untrained zero-shot fallback.

    With no stage executed and no fitted probe, the old code fell back to
    `sigmoid(mean(test_x))` and returned one `ExecutionDecision` per row.
    """
    fake_adapter = FakeFoundationModelAdapter()
    _, provenance = fake_adapter.get_test_weights_and_provenance()
    test_x, _, _ = _generate_synthetic_foundation_features(
        n_samples=20, start_dt=datetime(2024, 7, 1, 0, 0, tzinfo=UTC), seed=43
    )
    adapter = StagedFoundationAdapter(provenance=provenance)

    with pytest.raises(StagePreconditionNotMetError, match="NO_STAGE_EVIDENCE_FORECAST_FORBIDDEN"):
        adapter.predict_forecasts(
            test_x=test_x,
            pair="BTC_IDR",
            decision_ts=datetime(2024, 7, 1, 12, 0, tzinfo=UTC),
            mapper=_mapper(),
            desired_qty=Decimal("0.05"),
        )


def test_f01_02_bounded_adapter_decision_path_matches_scored_probabilities() -> None:
    """Important: the bounded-adapter transform was dropped at decision time (train/serve skew).

    The stage scored `probe(test_x + relu(test_x @ W_down) @ W_up)` but `predict_forecasts`
    ran `probe(test_x)`, so the executed decisions used different features than the reported
    metrics. The mean probability the stage scored must equal what the decision path produces.
    """
    fake_adapter = FakeFoundationModelAdapter()
    _, provenance = fake_adapter.get_test_weights_and_provenance()
    train_x, train_y, _ = _generate_synthetic_foundation_features(n_samples=60, seed=42)
    test_x, test_y, test_ts = _generate_synthetic_foundation_features(
        n_samples=20, start_dt=datetime(2024, 7, 1, 0, 0, tzinfo=UTC), seed=43
    )

    adapter = StagedFoundationAdapter(provenance=provenance)
    adapter.run_zero_shot(test_x=test_x, test_y=test_y, test_timestamps=test_ts)
    adapter.run_frozen_probe(
        train_x=train_x, train_y=train_y, test_x=test_x, test_y=test_y, test_timestamps=test_ts
    )
    adapter_res = adapter.run_bounded_adapter(
        train_x=train_x, train_y=train_y, test_x=test_x, test_y=test_y, test_timestamps=test_ts
    )

    probs = adapter.predict_proba(test_x)
    assert probs.shape == (len(test_x),)
    assert float(np.mean(probs)) == pytest.approx(adapter_res.metrics["mean_prob"], abs=1e-12)

    # The same probabilities must drive the decisions handed to the common mapper.
    decisions = adapter.predict_forecasts(
        test_x=test_x,
        pair="BTC_IDR",
        decision_ts=datetime(2024, 7, 1, 12, 0, tzinfo=UTC),
        mapper=_mapper(),
        desired_qty=Decimal("0.05"),
    )
    assert len(decisions) == len(test_x)


def test_f01_02_stage_result_reports_compute_budget() -> None:
    """Important: no parameter/compute budget was reported (sibling modules expose one)."""
    fake_adapter = FakeFoundationModelAdapter()
    _, provenance = fake_adapter.get_test_weights_and_provenance()
    train_x, train_y, _ = _generate_synthetic_foundation_features(n_samples=60, seed=42)
    test_x, test_y, test_ts = _generate_synthetic_foundation_features(
        n_samples=20, start_dt=datetime(2024, 7, 1, 0, 0, tzinfo=UTC), seed=43
    )

    adapter = StagedFoundationAdapter(provenance=provenance)
    zero = adapter.run_zero_shot(test_x=test_x, test_y=test_y, test_timestamps=test_ts)
    budget = getattr(zero, "compute_budget", None)
    assert budget is not None, "StageEvaluationResult exposes no compute_budget summary"
    assert budget.stage == AdaptationStage.ZERO_SHOT
    assert budget.total_learned_parameters == 0
    assert budget.input_dim == 16

    adapter.run_frozen_probe(
        train_x=train_x, train_y=train_y, test_x=test_x, test_y=test_y, test_timestamps=test_ts
    )
    adapter_res = adapter.run_bounded_adapter(
        train_x=train_x, train_y=train_y, test_x=test_x, test_y=test_y, test_timestamps=test_ts
    )
    assert adapter_res.compute_budget.adapter_parameters == 16 * 16 * 2
    assert adapter_res.compute_budget.probe_parameters == (16 + 1) * 2
    assert adapter_res.compute_budget.total_learned_parameters > 0
    assert adapter_res.compute_budget.estimated_flops_per_inference > 0


def test_f01_02_full_fine_tune_never_reports_success_without_evidence() -> None:
    """Important: an authorized full fine tune returned None while doing nothing.

    A stage method that reports success without producing a result makes a downstream
    "stage completed" belief false, so the authorized path must fail closed too.
    """
    fake_adapter = FakeFoundationModelAdapter()
    _, provenance = fake_adapter.get_test_weights_and_provenance()
    train_x, train_y, _ = _generate_synthetic_foundation_features(n_samples=40)
    test_x, test_y, _ = _generate_synthetic_foundation_features(
        n_samples=20, start_dt=datetime(2024, 7, 1, 0, 0, tzinfo=UTC)
    )

    authorized_no_owner = StagedFoundationAdapter(
        provenance=provenance, config=FoundationAdaptationConfig(allow_full_fine_tune=True)
    )
    with pytest.raises(FullFineTuneForbiddenError, match="FULL_FINE_TUNE_FORBIDDEN"):
        authorized_no_owner.run_full_fine_tune(
            train_x=train_x, train_y=train_y, test_x=test_x, test_y=test_y
        )

    authorized = StagedFoundationAdapter(
        provenance=provenance,
        config=FoundationAdaptationConfig(
            allow_full_fine_tune=True, full_fine_tune_authorization="research-owner"
        ),
    )
    with pytest.raises(StagePreconditionNotMetError, match="BOUNDED_ADAPTER required"):
        authorized.run_full_fine_tune(
            train_x=train_x, train_y=train_y, test_x=test_x, test_y=test_y
        )

    _, _, test_ts = _generate_synthetic_foundation_features(
        n_samples=20, start_dt=datetime(2024, 7, 1, 0, 0, tzinfo=UTC)
    )
    authorized.run_zero_shot(test_x=test_x, test_y=test_y, test_timestamps=test_ts)
    authorized.run_frozen_probe(
        train_x=train_x, train_y=train_y, test_x=test_x, test_y=test_y, test_timestamps=test_ts
    )
    authorized.run_bounded_adapter(
        train_x=train_x, train_y=train_y, test_x=test_x, test_y=test_y, test_timestamps=test_ts
    )
    with pytest.raises(FullFineTuneForbiddenError, match="FULL_FINE_TUNE_UNIMPLEMENTED"):
        authorized.run_full_fine_tune(
            train_x=train_x, train_y=train_y, test_x=test_x, test_y=test_y
        )


def test_f01_02_decision_ts_must_be_post_cutoff() -> None:
    """Important: predict_forecasts performed no cutoff check at all."""
    fake_adapter = FakeFoundationModelAdapter()
    _, provenance = fake_adapter.get_test_weights_and_provenance()
    train_x, train_y, _ = _generate_synthetic_foundation_features(n_samples=40)
    test_x, test_y, test_ts = _generate_synthetic_foundation_features(
        n_samples=20, start_dt=datetime(2024, 7, 1, 0, 0, tzinfo=UTC)
    )
    adapter = StagedFoundationAdapter(provenance=provenance)
    adapter.run_zero_shot(test_x=test_x, test_y=test_y, test_timestamps=test_ts)

    with pytest.raises(ContaminatedDatesClaimError, match="CONTAMINATED_DATES_FORBIDDEN"):
        adapter.predict_forecasts(
            test_x=test_x,
            pair="BTC_IDR",
            decision_ts=datetime(2023, 6, 1, 12, 0, tzinfo=UTC),
            mapper=_mapper(),
            desired_qty=Decimal("0.05"),
        )

    # And a contaminated row timestamp is rejected when supplied.
    adapter.run_zero_shot(test_x=test_x, test_y=test_y, test_timestamps=test_ts)
    with pytest.raises(ContaminatedDatesClaimError, match="CONTAMINATED_DATES_FORBIDDEN"):
        adapter.predict_forecasts(
            test_x=test_x,
            pair="BTC_IDR",
            decision_ts=datetime(2024, 7, 1, 12, 0, tzinfo=UTC),
            mapper=_mapper(),
            desired_qty=Decimal("0.05"),
            test_timestamps=[datetime(2023, 6, 1, 0, 0, tzinfo=UTC)] * len(test_x),
        )


def test_f01_02_timestamp_count_mismatch_rejected() -> None:
    """IMPORTANT: _validate_timestamps must enforce len(timestamps)==len(test_x).

    Empty/short timestamp lists must not seal a certified StageEvaluationResult.
    """
    fake_adapter = FakeFoundationModelAdapter()
    _, provenance = fake_adapter.get_test_weights_and_provenance()
    train_x, train_y, _ = _generate_synthetic_foundation_features(n_samples=40)
    test_x, test_y, test_ts = _generate_synthetic_foundation_features(
        n_samples=20, start_dt=datetime(2024, 7, 1, 0, 0, tzinfo=UTC)
    )

    adapter = StagedFoundationAdapter(provenance=provenance)

    with pytest.raises(ContaminatedDatesClaimError, match="CONTAMINATED_DATES_FORBIDDEN"):
        adapter.run_zero_shot(test_x=test_x, test_y=test_y, test_timestamps=[])

    short_ts = test_ts[:5]
    with pytest.raises(ContaminatedDatesClaimError, match="CONTAMINATED_DATES_FORBIDDEN"):
        adapter.run_zero_shot(test_x=test_x, test_y=test_y, test_timestamps=short_ts)
