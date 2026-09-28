"""Unit tests for S07 Small cap rotation strategy (S07-01)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, create_decision_frame
from indodax_lab.strategies.s07 import load_s07_specification, s07_decide, s07_evaluate

_AS_OF = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
_BASE_PRICE = 100000.0
_DEFAULT_CASH = Decimal("10000000")


def _build_s07_bars(
    pair: str,
    *,
    n_bars: int = 25,
    return_pct: float = 0.05,
    volume: float = 1000.0,
    spread_bps: float | None = 15.0,
    depth: float | None = 40000000.0,
    atr_14: float | None = 1500.0,
) -> pd.DataFrame:
    """Build causal 1h feature rows for one pair over the S07 lookback window.

    Fixture numbers are test-only and never production defaults. Liquidity fields
    (``spread_bps`` / ``depth_50bps``) follow the S01 convention: quote-IDR depth and
    spread in bps on the decision rows.
    """
    start_dt = _AS_OF - timedelta(hours=n_bars - 1)
    rows = []
    for i in range(n_bars):
        bar_dt = start_dt + timedelta(hours=i)
        price = _BASE_PRICE * (1.0 + return_pct * (i / (n_bars - 1)))
        rows.append(
            {
                "pair": pair,
                "decision_ts": bar_dt,
                "row_ready_at": bar_dt,
                "close": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "volume": volume,
                "spread_bps": spread_bps,
                "depth_50bps": depth,
                "atr_14": atr_14 if atr_14 is not None else float("nan"),
                "eligible": True,
                "missing_feature_count": 0,
                "reason_codes": (),
            }
        )
    df = pd.DataFrame(rows)
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    return df


def _frame(features: pd.DataFrame, cash: Decimal | None = _DEFAULT_CASH) -> DecisionFrame:
    return create_decision_frame(
        features=features,
        as_of=_AS_OF,
        universe_snapshot_id="snap_s07_test",
        feature_set_id="feat_s07_v1",
        available_cash_idr=cash,
    )


def test_s07_01_valid_contract() -> None:
    """S07-01-AC0: candidate S07 emits judge-comparable LONG intents via public inputs."""
    spec = load_s07_specification()
    assert spec.strategy_id == "S07"
    assert spec.version == "1.0.0"

    features = pd.concat(
        [
            _build_s07_bars("btc_idr", return_pct=0.05),
            _build_s07_bars("eth_idr", return_pct=0.10),
            _build_s07_bars("sol_idr", return_pct=0.15),
        ],
        ignore_index=True,
    )
    frame = _frame(features)

    intents = s07_decide(frame, spec)
    assert len(intents) == 2, f"top-2 rotation must emit 2 intents, got {intents}"
    assert intents == s07_evaluate(frame, spec)[0], "decide must wrap evaluate exactly"

    pairs = [intent.pair for intent in intents]
    assert pairs == ["sol_idr", "eth_idr"], f"rank order wrong: {pairs}"

    for intent in intents:
        assert isinstance(intent, SignalIntent)
        assert intent.side == OrderSide.BUY
        assert intent.desired_qty > Decimal("0")
        assert intent.strategy_id == "S07"
        assert intent.decision_ts == _AS_OF
        assert intent.intent_id.startswith("s07_")
        assert intent.limit_price is not None and intent.limit_price > 0
        assert intent.stop_loss is not None and intent.stop_loss < intent.limit_price


def test_s07_01_contract_1() -> None:
    """S07-01-AC1: illiquid top rank is never automatically eligible for a slot."""
    spec = load_s07_specification()

    # Case A: rank-1 momentum with volume far below min_volume (100.0).
    features_a = pd.concat(
        [
            _build_s07_bars("illiquid_idr", return_pct=0.30, volume=5.0),
            _build_s07_bars("eth_idr", return_pct=0.10),
            _build_s07_bars("sol_idr", return_pct=0.05),
        ],
        ignore_index=True,
    )
    intents_a, rejections_a = s07_evaluate(_frame(features_a), spec)
    pairs_a = [intent.pair for intent in intents_a]
    assert "illiquid_idr" not in pairs_a, (
        f"illiquid top rank must not be eligible, got {pairs_a}"
    )
    assert pairs_a == ["eth_idr", "sol_idr"], f"liquid names must fill slots: {pairs_a}"
    assert "S07_ILLIQUID_VOLUME:illiquid_idr" in rejections_a, rejections_a

    # Case B: rank-1 momentum with a spread wider than max_spread_bps (30.0).
    features_b = pd.concat(
        [
            _build_s07_bars("illiquid_idr", return_pct=0.30, spread_bps=60.0),
            _build_s07_bars("eth_idr", return_pct=0.10),
            _build_s07_bars("sol_idr", return_pct=0.05),
        ],
        ignore_index=True,
    )
    intents_b, rejections_b = s07_evaluate(_frame(features_b), spec)
    pairs_b = [intent.pair for intent in intents_b]
    assert "illiquid_idr" not in pairs_b, f"wide spread must be rejected, got {pairs_b}"
    assert "S07_WIDE_SPREAD:illiquid_idr" in rejections_b, rejections_b

    # Case C: rank-1 momentum with missing depth (fail-closed, never zero-filled).
    features_c = pd.concat(
        [
            _build_s07_bars("illiquid_idr", return_pct=0.30, depth=None),
            _build_s07_bars("eth_idr", return_pct=0.10),
            _build_s07_bars("sol_idr", return_pct=0.05),
        ],
        ignore_index=True,
    )
    intents_c, rejections_c = s07_evaluate(_frame(features_c), spec)
    pairs_c = [intent.pair for intent in intents_c]
    assert "illiquid_idr" not in pairs_c, f"missing depth must abstain, got {pairs_c}"
    assert "S07_MISSING_LIQUIDITY:illiquid_idr" in rejections_c, rejections_c

    # Positive control: same fixture fully liquid -> rank 1 takes slot 1.
    features_ok = pd.concat(
        [
            _build_s07_bars("illiquid_idr", return_pct=0.30),
            _build_s07_bars("eth_idr", return_pct=0.10),
            _build_s07_bars("sol_idr", return_pct=0.05),
        ],
        ignore_index=True,
    )
    intents_ok, _ = s07_evaluate(_frame(features_ok), spec)
    assert [intent.pair for intent in intents_ok] == ["illiquid_idr", "eth_idr"]


def test_s07_01_contract_2() -> None:
    """S07-01-AC2: an order sized above the pair's liquidity capacity is rejected."""
    spec = load_s07_specification()

    # Rank-1 pair shows only 1,000,000 IDR of 50bps depth while the shared-cash slot
    # is 4,000,000 IDR (10,000,000 cash x 0.80 deployable / 2 slots).
    features = pd.concat(
        [
            _build_s07_bars("topcap_idr", return_pct=0.15, depth=1000000.0),
            _build_s07_bars("eth_idr", return_pct=0.10),
        ],
        ignore_index=True,
    )
    intents, rejections = s07_evaluate(_frame(features), spec)
    pairs = [intent.pair for intent in intents]
    assert "topcap_idr" not in pairs, (
        f"order above capacity must be rejected, not shrunk or filled: {pairs}"
    )
    assert pairs == ["eth_idr"], f"remaining liquid slot must still emit: {pairs}"
    assert "S07_OVER_CAPACITY:topcap_idr" in rejections, rejections

    # Positive control: same fixture with ample depth -> both slots emit.
    control = pd.concat(
        [
            _build_s07_bars("topcap_idr", return_pct=0.15),
            _build_s07_bars("eth_idr", return_pct=0.10),
        ],
        ignore_index=True,
    )
    control_intents, control_rejections = s07_evaluate(_frame(control), spec)
    assert [intent.pair for intent in control_intents] == ["topcap_idr", "eth_idr"]
    assert not any("OVER_CAPACITY" in code for code in control_rejections), (
        control_rejections
    )


def test_s07_01_contract_3() -> None:
    """S07-01-AC3: rotation slot sizing respects the shared cash pool (Decimal)."""
    spec = load_s07_specification()
    features = pd.concat(
        [
            _build_s07_bars("btc_idr", return_pct=0.05),
            _build_s07_bars("eth_idr", return_pct=0.10),
            _build_s07_bars("sol_idr", return_pct=0.15),
        ],
        ignore_index=True,
    )

    # Case A: shared cash 10,000,000 IDR with cash_reserve_pct 0.20 -> deployable
    # 8,000,000 IDR split over top_k=2 slots.
    intents_a = s07_decide(_frame(features, cash=Decimal("10000000")), spec)
    assert len(intents_a) == 2, f"expected 2 rotation intents, got {intents_a}"
    total_a = sum(
        (intent.desired_qty * intent.limit_price for intent in intents_a),
        start=Decimal("0"),
    )
    assert total_a <= Decimal("8000000"), (
        f"rotation must reserve 20% of shared cash, deployed {total_a}"
    )
    for intent in intents_a:
        notional = intent.desired_qty * intent.limit_price
        assert notional <= Decimal("4000000"), f"slot exceeded shared cash: {notional}"

    # Case B: a smaller shared pool scales the whole rotation down proportionally.
    intents_b = s07_decide(_frame(features, cash=Decimal("1000000")), spec)
    assert len(intents_b) == 2, f"expected 2 rotation intents, got {intents_b}"
    total_b = sum(
        (intent.desired_qty * intent.limit_price for intent in intents_b),
        start=Decimal("0"),
    )
    assert total_b <= Decimal("800000"), f"deployed {total_b} from shared 1,000,000"

    # Case C: unknown shared cash fails closed with an explicit diagnostic.
    intents_c, rejections_c = s07_evaluate(_frame(features, cash=None), spec)
    assert intents_c == [], f"missing shared cash must abstain, got {intents_c}"
    assert rejections_c == ["S07_SHARED_CASH_UNAVAILABLE"], rejections_c


def test_s07_01_missing_atr_abstains() -> None:
    """REGRESSION: missing ATR fails closed instead of degenerate stop-at-entry."""
    spec = load_s07_specification()
    features = _build_s07_bars("btc_idr", return_pct=0.05, atr_14=None)

    intents, rejections = s07_evaluate(_frame(features), spec)

    assert intents == [], f"missing ATR must abstain, got {intents}"
    assert "S07_ATR_INVALID:btc_idr" in rejections, rejections
