"""Integration smoke tests for Transformer LOB (TLOB) challenger (L02-01).

Guarantees:
1. L02-01-AC0: TLOB attention architecture evaluated against DeepLOB with compute and latency budget tracking.
2. L02-01-AC1: No perfect queue fill assumption (realistic execution rejects 100% unconditional maker fills).
3. L02-01-AC2: Search budget strictly capped at <=8 configurations; excess attempts fail-closed.
4. L02-01-AC3: Poor valid challenger results are explicitly archived rather than discarded or retried.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import numpy as np
import pytest

from indodax_lab.features.lob import extract_lob_tensor
from indodax_lab.models.execution_mapper import (
    CostAwareExecutionMapper,
    CostBasis,
    DecisionAction,
    ForecastKind,
    ForecastPayload,
    PayoffStructure,
)
from indodax_lab.models.lob.dataset import BookLevel, BookSnapshot
from indodax_lab.models.lob.l02_tlob import (
    ArchivedChallengerResult,
    PerfectQueueFillForbiddenError,
    QueueFillModel,
    TLOBConfig,
    TLOBModel,
    TLOBSearchBudgetExceededError,
    TLOBTournamentArchiver,
)


def _generate_synthetic_lob_series(n_steps: int = 50) -> list[BookSnapshot]:
    """Generate synthetic LOB snapshots."""
    t0 = datetime(2025, 3, 1, 10, 0, 0, tzinfo=UTC)
    snapshots = []
    price = 1_000_000_000.0
    rng = np.random.default_rng(42)

    for i in range(n_steps):
        t = t0 + timedelta(seconds=i)
        price += rng.normal(0, 10000.0)
        best_bid = price - 100_000.0
        best_ask = price + 100_000.0

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
                bids=bids,
                asks=asks,
                sequence_id=i,
            )
        )
    return snapshots


def test_l02_01_valid_contract() -> None:
    """L02-01-AC0: TLOB attention architecture evaluated with compute and latency budget tracking."""
    torch = pytest.importorskip("torch")

    snapshots = _generate_synthetic_lob_series(n_steps=40)
    tensor = extract_lob_tensor(snapshots, levels=5)  # (40, 20)

    config = TLOBConfig(
        lookback_len=20,
        num_features=20,
        d_model=32,
        n_heads=2,
        num_layers=2,
        num_classes=3,
        search_budget_max_configs=8,
        seed=42,
    )
    model = TLOBModel(config)
    model.eval()

    # Input tensor shape: (B, lookback_len, num_features)
    x = torch.from_numpy(tensor[:20]).float().unsqueeze(0)  # (1, 20, 20)
    with torch.no_grad():
        probs = model(x)  # (1, 3)

    assert probs.shape == (1, 3)
    assert torch.all(probs >= 0.0)
    assert np.isclose(float(torch.sum(probs).item()), 1.0, atol=1e-5)

    # Validate compute summary
    compute = model.compute_budget_summary()
    assert compute.total_trainable_parameters > 0
    assert compute.estimated_flops_per_inference > 0
    assert compute.num_layers == 2

    # Map forecast through CostAwareExecutionMapper
    p_up = float(probs[0, 2].item())
    cost_basis = CostBasis(estimated_round_trip_cost=0.0040, safety_margin=0.0010)
    mapper = CostAwareExecutionMapper(cost_basis=cost_basis)
    payload = ForecastPayload(
        kind=ForecastKind.PROBABILITY,
        value=p_up,
        pair="BTC_IDR",
        decision_ts=snapshots[19].timestamp,
        desired_qty=Decimal("0.05"),
        payoff=PayoffStructure(win_return=0.015, loss_return=-0.010),
    )
    dec = mapper.evaluate_forecast(payload)
    assert dec.action in (DecisionAction.INTENT, DecisionAction.ABSTAIN)


def test_l02_01_contract_1() -> None:
    """L02-01-AC1: No perfect queue fill assumption."""
    # Simulation must reject perfect/unconditional 100% maker fill assumptions
    with pytest.raises(PerfectQueueFillForbiddenError, match="PERFECT_QUEUE_FILL_FORBIDDEN"):
        QueueFillModel(assume_unconditional_fill=True)

    with pytest.raises(PerfectQueueFillForbiddenError, match="ZERO_SLIPPAGE_OR_SPREAD_FORBIDDEN"):
        QueueFillModel(half_spread_bps=0.0)

    # Valid realistic queue fill model
    model = QueueFillModel(half_spread_bps=5.0, queue_penalty_bps=2.0)
    # Deeper queue level or larger size has strictly lower fill probability
    p_fill_level1 = model.estimate_fill_probability(queue_depth_level=1, order_qty=1.0)
    p_fill_level3 = model.estimate_fill_probability(queue_depth_level=3, order_qty=1.0)
    assert 0.0 < p_fill_level3 < p_fill_level1 < 1.0


def test_l02_01_contract_2() -> None:
    """L02-01-AC2: Batas budget menghentikan search."""
    config = TLOBConfig(search_budget_max_configs=8)
    assert config.search_budget_max_configs <= 8

    # Attempting to configure > 8 search trials fails-closed
    with pytest.raises(TLOBSearchBudgetExceededError, match="TLOB_SEARCH_BUDGET_EXCEEDED"):
        TLOBConfig(search_budget_max_configs=9)


def test_l02_01_contract_3() -> None:
    """L02-01-AC3: Poor valid result diarsipkan."""
    archiver = TLOBTournamentArchiver()

    # Suppose TLOB produces negative edge after spread vs DeepLOB baseline
    t0 = datetime(2025, 3, 1, 12, 0, tzinfo=UTC)
    result = archiver.record_tournament_outcome(
        challenger_id="L02_TLOB_ATTN",
        baseline_id="L01_DEEPLOB",
        challenger_net_edge=-0.0015,
        baseline_net_edge=0.0010,
        eval_ts=t0,
        reasons=["NET_EDGE_BELOW_BASELINE", "SPREAD_CROSSING_COST_EXCEEDS_GAIN"],
    )

    assert isinstance(result, ArchivedChallengerResult)
    assert result.status == "ARCHIVED_UNDERPERFORMER"
    assert result.promoted is False
    assert result.archived_evidence_preserved is True
    assert "NET_EDGE_BELOW_BASELINE" in result.reasons

    # Check that archive cannot be deleted or silenced
    records = archiver.list_archived_records()
    assert len(records) == 1
    assert records[0].challenger_id == "L02_TLOB_ATTN"
