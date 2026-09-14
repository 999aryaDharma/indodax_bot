"""Unit tests for C04 Cross sectional momentum strategy (C04-01)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pandas as pd
import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, create_decision_frame
from indodax_lab.strategies.c04 import c04_decide, load_c04_specification


def _build_c04_pair_bars(
    as_of: datetime,
    pair: str,
    n_bars: int = 25,
    return_pct: float = 0.05,
    volume: float = 500.0,
    eligible: bool = True,
    listing_date: datetime | None = None,
) -> pd.DataFrame:
    """Build causal feature frame for a single pair with specified return over lookback."""
    start_dt = as_of - timedelta(hours=n_bars - 1)
    rows = []
    base_price = 100000.0

    for i in range(n_bars):
        bar_dt = start_dt + timedelta(hours=i)
        # Price smoothly progresses to achieve target return_pct over the window
        p = base_price * (1.0 + (return_pct * (i / (n_bars - 1))))

        row = {
            "pair": pair,
            "decision_ts": bar_dt,
            "row_ready_at": bar_dt,
            "close": p,
            "high": p * 1.01,
            "low": p * 0.99,
            "volume": volume,
            "atr_14": 1500.0,
            "eligible": eligible,
            "missing_feature_count": 0,
            "reason_codes": (),
        }
        if listing_date is not None:
            row["listing_date"] = listing_date
        rows.append(row)

    df = pd.DataFrame(rows)
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    return df


def test_c04_01_valid_contract() -> None:
    """C04-01-AC0: Candidate C04 produces intents comparable with baseline on same judge."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c04_specification()

    # Three assets with different positive returns: sol (15%) > eth (10%) > btc (5%)
    btc_df = _build_c04_pair_bars(as_of, "btc_idr", return_pct=0.05, volume=1000.0)
    eth_df = _build_c04_pair_bars(as_of, "eth_idr", return_pct=0.10, volume=1000.0)
    sol_df = _build_c04_pair_bars(as_of, "sol_idr", return_pct=0.15, volume=1000.0)

    combined_df = pd.concat([btc_df, eth_df, sol_df], ignore_index=True)
    frame = create_decision_frame(
        features=combined_df,
        as_of=as_of,
        universe_snapshot_id="snap_c04_test",
        feature_set_id="feat_c04_v1",
    )

    intents = c04_decide(frame, spec)

    # Top-k is 2: sol_idr and eth_idr should be selected
    assert len(intents) == 2
    selected_pairs = [intent.pair for intent in intents]
    assert "sol_idr" in selected_pairs
    assert "eth_idr" in selected_pairs
    assert "btc_idr" not in selected_pairs

    for intent in intents:
        assert isinstance(intent, SignalIntent)
        assert intent.side == OrderSide.BUY
        assert intent.desired_qty > Decimal("0")
        assert intent.strategy_id == "C04"
        assert intent.decision_ts == as_of
        assert intent.limit_price is not None
        assert intent.stop_loss is not None
        assert intent.stop_loss < intent.limit_price


def test_c04_01_contract_1() -> None:
    """C04-01-AC1: Future listing does not enter rank."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c04_specification()

    # btc and eth are legitimately listed before as_of
    btc_df = _build_c04_pair_bars(as_of, "btc_idr", return_pct=0.05, volume=1000.0)
    eth_df = _build_c04_pair_bars(as_of, "eth_idr", return_pct=0.08, volume=1000.0)

    # future_coin has high return (50%) but its listing_date is in the future relative to as_of
    future_listing_dt = as_of + timedelta(days=5)
    future_df = _build_c04_pair_bars(
        as_of,
        "future_idr",
        return_pct=0.50,
        volume=5000.0,
        eligible=False,
        listing_date=future_listing_dt,
    )

    # Ineligible or future listing rows must not be ranked
    combined_df = pd.concat([btc_df, eth_df, future_df], ignore_index=True)
    frame = create_decision_frame(
        features=combined_df,
        as_of=as_of,
        universe_snapshot_id="snap_c04_test",
        feature_set_id="feat_c04_v1",
    )

    intents = c04_decide(frame, spec)

    # future_idr must strictly NOT be included
    selected_pairs = [intent.pair for intent in intents]
    assert "future_idr" not in selected_pairs
    assert len(intents) == 2
    assert "eth_idr" in selected_pairs
    assert "btc_idr" in selected_pairs


def test_c04_01_contract_2() -> None:
    """C04-01-AC2: Rank tie is consistent across runs."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c04_specification()

    # Three assets with identical return of 10% and top_k=2
    # Deterministic tie-breaking must consistently choose alphabetical canonical pairs
    ada_df = _build_c04_pair_bars(as_of, "ada_idr", return_pct=0.10, volume=1000.0)
    dot_df = _build_c04_pair_bars(as_of, "dot_idr", return_pct=0.10, volume=1000.0)
    trx_df = _build_c04_pair_bars(as_of, "trx_idr", return_pct=0.10, volume=1000.0)

    # Run 1: ada, dot, trx order
    df1 = pd.concat([ada_df, dot_df, trx_df], ignore_index=True)
    frame1 = create_decision_frame(features=df1, as_of=as_of)
    intents1 = c04_decide(frame1, spec)

    # Run 2: reversed trx, dot, ada order
    df2 = pd.concat([trx_df, dot_df, ada_df], ignore_index=True)
    frame2 = create_decision_frame(features=df2, as_of=as_of)
    intents2 = c04_decide(frame2, spec)

    # Both runs must produce the exact same pairs and exact same order
    pairs1 = [intent.pair for intent in intents1]
    pairs2 = [intent.pair for intent in intents2]

    assert pairs1 == pairs2
    assert len(pairs1) == 2
    # Alphabetical order: ada_idr then dot_idr (trx_idr is ranked 3rd and excluded)
    assert pairs1 == ["ada_idr", "dot_idr"]


def test_c04_01_contract_3() -> None:
    """C04-01-AC3: Cash is reserved once on rotation."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c04_specification()

    # Spec has base_qty = "0.1", top_k = 2, cash_reserve_pct = 0.20
    # Reserved cash is 20%, deployable is 80% (0.08 total)
    # Each slot gets 0.08 / 2 = 0.04
    btc_df = _build_c04_pair_bars(as_of, "btc_idr", return_pct=0.08, volume=1000.0)
    eth_df = _build_c04_pair_bars(as_of, "eth_idr", return_pct=0.12, volume=1000.0)

    combined_df = pd.concat([btc_df, eth_df], ignore_index=True)
    frame = create_decision_frame(features=combined_df, as_of=as_of)
    intents = c04_decide(frame, spec)

    assert len(intents) == 2
    total_deployed_qty = sum((intent.desired_qty for intent in intents), start=Decimal("0"))
    expected_deployed = Decimal("0.1") * (Decimal("1") - Decimal("0.20"))
    assert total_deployed_qty == expected_deployed
    for intent in intents:
        assert intent.desired_qty == expected_deployed / Decimal("2")
