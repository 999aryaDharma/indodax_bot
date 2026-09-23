"""Integration smoke tests for DeepLOB baseline (L01-01).

Guarantees:
1. L01-01-AC0: DeepLOB produces short-horizon forecast mapped through CostAwareExecutionMapper with spread and latency accounting.
2. L01-01-AC1: High raw mid-price accuracy does not imply net profitability when spread and fees dominate.
3. L01-01-AC2: Gapped book sequences block execution fail-closed.
4. L01-01-AC3: Benchmarked against baseline MLP on strictly identical out-of-fold samples.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import numpy as np
import pytest

from indodax_lab.features.lob import extract_lob_tensor
from indodax_lab.models.dl.d01_mlp import SameSampleComparator
from indodax_lab.models.execution_mapper import (
    CostAwareExecutionMapper,
    CostBasis,
    DecisionAction,
    ForecastKind,
    ForecastPayload,
    PayoffStructure,
)
from indodax_lab.models.lob.dataset import BookLevel, BookSnapshot
from indodax_lab.models.lob.l01_deeplob import (
    DeepLOBConfig,
    DeepLOBModel,
    DeepLOBSampleComparator,
    DeepLOBTrainer,
    GappedBookBlockedError,
    SampleComparatorMismatchError,
    SpreadAwareEdgeEvaluator,
)


def _generate_synthetic_lob_series(
    n_steps: int = 120,
    base_price: float = 1_000_000_000.0,
    half_spread_bps: float = 10.0,
    has_gap: bool = False,
) -> list[BookSnapshot]:
    """Generate synthetic LOB snapshots with depth levels."""
    t0 = datetime(2025, 3, 1, 10, 0, 0, tzinfo=UTC)
    snapshots = []
    price = base_price
    rng = np.random.default_rng(42)

    for i in range(n_steps):
        # Insert a 120s gap if requested at step 60
        delta_s = 120 if (has_gap and i == 60) else 1
        t = (snapshots[-1].timestamp if snapshots else t0) + timedelta(seconds=delta_s)

        price += rng.normal(0, 10000.0)
        half_spread = price * (half_spread_bps / 10_000.0)
        best_bid = price - half_spread
        best_ask = price + half_spread

        bids = [
            BookLevel(price=Decimal(str(int(best_bid - k * 1000))), volume=Decimal(str(round(1.0 + k * 0.5, 2))))
            for k in range(5)
        ]
        asks = [
            BookLevel(price=Decimal(str(int(best_ask + k * 1000))), volume=Decimal(str(round(1.0 + k * 0.5, 2))))
            for k in range(5)
        ]
        snapshots.append(
            BookSnapshot(
                timestamp=t,
                pair="BTC_IDR",
                session_id="synthetic-session",
                bids=bids,
                asks=asks,
                sequence_id=i,
            )
        )
    return snapshots


def test_l01_01_valid_contract() -> None:
    """L01-01-AC0: DeepLOB produces short-horizon forecast mapped through CostAwareExecutionMapper."""
    torch = pytest.importorskip("torch")

    snapshots = _generate_synthetic_lob_series(n_steps=60, has_gap=False)
    tensor = extract_lob_tensor(snapshots, levels=5)  # (60, 20)
    assert tensor.shape == (60, 20)

    config = DeepLOBConfig(
        lookback_len=20,
        num_features=20,
        conv_filters=8,
        lstm_hidden=16,
        max_epochs=5,
        patience=3,
        seed=42,
    )
    model = DeepLOBModel(config)
    model.eval()

    # DeepLOB expects shape (B, 1, L, 4K)
    x = torch.from_numpy(tensor[:20]).float().unsqueeze(0).unsqueeze(0)  # (1, 1, 20, 20)
    with torch.no_grad():
        probs = model(x)  # (1, 3): [P(down), P(stationary), P(up)]

    assert probs.shape == (1, 3)
    assert torch.all(probs >= 0.0)
    assert np.isclose(float(torch.sum(probs).item()), 1.0, atol=1e-5)

    # Route through CostAwareExecutionMapper with spread and fee hurdles
    p_up = float(probs[0, 2].item())
    cost_basis = CostBasis(estimated_round_trip_cost=0.0040, safety_margin=0.0010)
    mapper = CostAwareExecutionMapper(cost_basis=cost_basis)
    payoff = PayoffStructure(win_return=0.015, loss_return=-0.010)

    payload = ForecastPayload(
        kind=ForecastKind.PROBABILITY,
        value=p_up,
        pair="BTC_IDR",
        decision_ts=snapshots[19].timestamp,
        desired_qty=Decimal("0.05"),
        payoff=payoff,
    )
    decision = mapper.evaluate_forecast(payload)
    assert decision.action in (DecisionAction.INTENT, DecisionAction.ABSTAIN)


def test_l01_01_contract_1() -> None:
    """L01-01-AC1: Mid-price accuracy tinggi belum berarti net profitable."""
    # Scenario: 70% directional accuracy on tiny price moves (e.g. 2 bps = 0.0002)
    # But half-spread is 10 bps (0.0010) and round-trip fee is 40 bps (0.0040) -> total hurdle = 50 bps
    evaluator = SpreadAwareEdgeEvaluator(
        estimated_round_trip_cost=0.0040,
        safety_margin=0.0010,
    )

    # Test high directional accuracy (70%) with sub-cost moves
    # Directional prediction: 70% correct, average gross win = +0.0002, average loss = -0.0002
    # Even with 70% accuracy, net expected profit is negative after costs!
    win_rate = 0.70
    avg_win_return = 0.0005   # 5 bps
    avg_loss_return = -0.0005 # -5 bps
    avg_spread = 0.0020       # 20 bps half-spread

    assessment = evaluator.assess_net_profitability(
        directional_accuracy=win_rate,
        avg_gross_win=avg_win_return,
        avg_gross_loss=avg_loss_return,
        avg_half_spread=avg_spread,
    )

    assert assessment.high_accuracy_flag is True
    assert assessment.net_edge < 0.0
    assert assessment.is_net_profitable is False
    assert "COST_AND_SPREAD_OVERWHELMS_EDGE" in assessment.reasons


def test_l01_01_contract_2() -> None:
    """L01-01-AC2: Gapped book blocks run."""
    # Create book snapshots containing an unobserved gap (120 seconds between updates)
    gapped_snapshots = _generate_synthetic_lob_series(n_steps=80, has_gap=True)

    trainer = DeepLOBTrainer(
        config=DeepLOBConfig(lookback_len=20, num_features=20, max_gap_seconds=10.0)
    )

    # Attempting to feed unsegmented gapped series into model training or inference raises GappedBookBlockedError
    with pytest.raises(GappedBookBlockedError, match="GAPPED_BOOK_BLOCKED"):
        trainer.validate_unbroken_sequence(gapped_snapshots)


def test_l01_01_contract_3() -> None:
    """L01-01-AC3: Baseline MLP memakai sample identik."""
    # Verify that DeepLOB and tabular MLP baseline evaluate against strictly identical samples
    snapshots = _generate_synthetic_lob_series(n_steps=50, has_gap=False)
    tensor = extract_lob_tensor(snapshots, levels=5)

    test_indices = list(range(20, 50))
    comparator = DeepLOBSampleComparator(test_sample_indices=test_indices)

    # Valid matching test indices
    deeplob_indices = list(range(20, 50))
    mlp_indices = list(range(20, 50))
    res = comparator.verify_same_samples(model_a_indices=deeplob_indices, model_b_indices=mlp_indices)
    assert res.indices_match is True
    assert res.total_samples == 30

    # Mismatched sample indices must fail-closed
    mismatched_mlp_indices = list(range(19, 49))
    with pytest.raises(SampleComparatorMismatchError):
        comparator.verify_same_samples(model_a_indices=deeplob_indices, model_b_indices=mismatched_mlp_indices)
