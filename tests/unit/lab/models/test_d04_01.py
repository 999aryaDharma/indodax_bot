"""Unit tests for Compact iTransformer challenger (D04-01).

Guarantees:
1. D04-01-AC0: Compact iTransformer produces panel forecasts connected to CostAwareExecutionMapper.
2. D04-01-AC1: Shape time-feature tidak tertukar (verifies inverted variate-as-token semantics & dimension validation).
3. D04-01-AC2: Missing variate masking diuji (cross-variate attention masking guarantees unobserved variate isolation).
4. D04-01-AC3: Tidak memakai future universe (point-in-time universe filtering rejects premature/future asset listings).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import numpy as np
import pytest

from indodax_lab.models.dl.d04_itransformer import (
    CompactITransformer,
    CompactITransformerConfig,
    FutureUniverseError,
    ITransformerComputeBudgetSummary,
    InvertedDimensionError,
    PointInTimePanelSnapshot,
    PointInTimeUniverseGate,
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


def test_d04_01_valid_contract() -> None:
    """D04-01-AC0: Positive contract - iTransformer produces panel forecasts consumed by CostAwareExecutionMapper."""
    torch = pytest.importorskip("torch")

    # Lookback window L=24, Variates V=4
    L = 24
    V = 4
    config = CompactITransformerConfig(
        lookback_len=L,
        num_variates=V,
        d_model=32,
        n_heads=2,
        e_layers=2,
        d_ff=64,
        horizons=(1, 4),
        seed=42,
    )

    model = CompactITransformer(config)
    model.eval()

    # Batch of 2 samples, L=24, V=4
    torch.manual_seed(42)
    x = torch.randn(2, L, V)
    variate_mask = torch.ones(2, V, dtype=torch.bool)

    with torch.no_grad():
        output = model(x, variate_mask=variate_mask)

    # Output shapes: forecasts of shape (B, V, num_horizons) and direction probabilities (B, V)
    assert output.horizon_forecasts.shape == (2, V, 2)
    assert output.probabilities.shape == (2, V)
    assert torch.all((output.probabilities >= 0.0) & (output.probabilities <= 1.0))

    # Verify connection to CostAwareExecutionMapper
    cost_basis = CostBasis(estimated_round_trip_cost=0.0040, safety_margin=0.0015)
    mapper = CostAwareExecutionMapper(cost_basis=cost_basis)
    t0 = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    pairs = ["BTC_IDR", "ETH_IDR", "SOL_IDR", "ADA_IDR"]
    payoff = PayoffStructure(win_return=0.015, loss_return=-0.010)

    decisions = []
    for v_idx, pair in enumerate(pairs):
        prob = float(output.probabilities[0, v_idx].item())
        payload = ForecastPayload(
            kind=ForecastKind.PROBABILITY,
            value=prob,
            pair=pair,
            decision_ts=t0,
            desired_qty=Decimal("0.05"),
            payoff=payoff,
        )
        decision = mapper.evaluate_forecast(payload)
        decisions.append(decision)

    assert len(decisions) == 4
    for dec in decisions:
        assert isinstance(dec, ExecutionDecision)
        assert dec.action in (DecisionAction.INTENT, DecisionAction.ABSTAIN)

    budget = model.compute_budget_summary()
    assert isinstance(budget, ITransformerComputeBudgetSummary)
    assert budget.total_trainable_parameters > 0
    assert budget.estimated_flops_per_panel > 0
    assert budget.num_layers == 2


def test_d04_01_contract_1() -> None:
    """D04-01-AC1: Shape time-feature tidak tertukar."""
    torch = pytest.importorskip("torch")

    L = 30
    V = 5
    config = CompactITransformerConfig(
        lookback_len=L,
        num_variates=V,
        d_model=32,
        n_heads=2,
        e_layers=1,
        seed=42,
    )
    model = CompactITransformer(config)

    # 1. Swapped dimensions: input is passed as (B, V, L) where dim 1 != lookback_len
    x_swapped = torch.randn(2, V, L)
    with pytest.raises(InvertedDimensionError, match="TIME_FEATURE_SHAPE_INVERTED"):
        model(x_swapped)

    # 2. Verify tokenization architecture: variates are tokens, time is embedded
    x_valid = torch.randn(2, L, V)
    # The inverted embedding maps temporal history L -> d_model
    tokens = model.embed_variates(x_valid)
    # Shape of tokens must be (B, V, d_model): V tokens, each of dimension d_model
    assert tokens.shape == (2, V, config.d_model)

    # Cross-variate attention operates on V tokens
    attn_weights = model.get_cross_variate_attention(x_valid)
    # Shape of attention map must be (B, n_heads, V, V) - attention across variates, NOT time!
    assert attn_weights.shape == (2, config.n_heads, V, V)


def test_d04_01_contract_2() -> None:
    """D04-01-AC2: Missing variate masking diuji."""
    torch = pytest.importorskip("torch")

    L = 20
    V = 4
    config = CompactITransformerConfig(
        lookback_len=L,
        num_variates=V,
        d_model=32,
        n_heads=2,
        e_layers=2,
        seed=42,
    )
    model = CompactITransformer(config)
    model.eval()

    torch.manual_seed(123)
    x = torch.randn(1, L, V)

    # Variate index 3 is missing / inactive
    variate_mask = torch.tensor([[True, True, True, False]], dtype=torch.bool)

    with torch.no_grad():
        out1 = model(x, variate_mask=variate_mask)

    # Now perturb missing variate 3 with extreme values
    x_perturbed = x.clone()
    x_perturbed[0, :, 3] = x_perturbed[0, :, 3] + 999.0

    with torch.no_grad():
        out2 = model(x_perturbed, variate_mask=variate_mask)

    # Active variates (0, 1, 2) must produce EXACT same outputs despite massive perturbation of variate 3
    for v in range(3):
        np.testing.assert_allclose(
            out1.horizon_forecasts[0, v].numpy(),
            out2.horizon_forecasts[0, v].numpy(),
            atol=1e-5,
            err_msg=f"Active variate {v} was affected by missing variate perturbation!",
        )
        assert np.isclose(
            out1.probabilities[0, v].item(),
            out2.probabilities[0, v].item(),
            atol=1e-5,
        )

    # The missing variate forecast must be flagged as masked / inactive
    assert out1.active_mask[0, 3].item() is False
    assert out2.active_mask[0, 3].item() is False


def test_d04_01_contract_3() -> None:
    """D04-01-AC3: Tidak memakai future universe."""
    # Point-in-time universe gating
    listing_registry = {
        "BTC_IDR": datetime(2014, 2, 15, tzinfo=UTC),
        "ETH_IDR": datetime(2016, 5, 1, tzinfo=UTC),
        "SOL_IDR": datetime(2021, 8, 1, tzinfo=UTC),
        "NEW_TOKEN_IDR": datetime(2026, 6, 1, tzinfo=UTC),  # Listed in future relative to t0
    }

    gate = PointInTimeUniverseGate(listing_registry=listing_registry)

    # Current evaluation timestamp: 2026-03-01
    t0 = datetime(2026, 3, 1, 0, 0, tzinfo=UTC)

    # Query active universe at t0
    active_universe = gate.get_active_universe(eval_ts=t0)
    assert "BTC_IDR" in active_universe
    assert "ETH_IDR" in active_universe
    assert "SOL_IDR" in active_universe
    assert "NEW_TOKEN_IDR" not in active_universe

    # 1. Attempting to build snapshot with future asset raises FutureUniverseError
    with pytest.raises(FutureUniverseError, match="FUTURE_UNIVERSE_LEAKAGE"):
        gate.validate_universe_snapshot(
            eval_ts=t0,
            requested_assets=["BTC_IDR", "ETH_IDR", "NEW_TOKEN_IDR"],
        )

    # 2. Lookahead temporal check: data beyond t0 raises ValueError
    future_data_ts = t0 + timedelta(hours=1)
    with pytest.raises(ValueError, match="LOOKAHEAD_DATA_DETECTED"):
        gate.validate_temporal_timestamps(eval_ts=t0, timestamps=[t0 - timedelta(hours=1), future_data_ts])

    # 3. Valid point-in-time panel snapshot construction
    snapshot = gate.create_panel_snapshot(
        eval_ts=t0,
        requested_assets=["BTC_IDR", "ETH_IDR", "SOL_IDR"],
        lookback_len=24,
    )
    assert snapshot.eval_ts == t0
    assert snapshot.active_assets == ["BTC_IDR", "ETH_IDR", "SOL_IDR"]
    assert len(snapshot.active_assets) == 3
