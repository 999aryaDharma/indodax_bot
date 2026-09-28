"""Unit tests for C12 Relative strength rotation strategy (C12-01)."""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, create_decision_frame
from indodax_lab.strategies.c04 import c04_decide, load_c04_specification
from indodax_lab.strategies.c12 import c12_decide, c12_decision_history, load_c12_specification

AS_OF = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
CASH = Decimal("100000")


def _build_c12_pair_bars(
    as_of: datetime,
    pair: str,
    n_bars: int = 25,
    return_pct: float = 0.05,
    ends_at: datetime | None = None,
    atr: float = 1500.0,
    listed_at: datetime | None = None,
    starts_at: datetime | None = None,
) -> pd.DataFrame:
    """Build causal hourly feature rows ending at `ends_at` (default: as_of).

    `ends_at` earlier than as_of models a delisted pair whose history stops.
    `listed_at` attaches canonical listing evidence (C04-style). `starts_at`
    places the first bar after as_of, modeling rows entirely in the future.
    """
    end = ends_at if ends_at is not None else as_of
    start_dt = starts_at if starts_at is not None else end - timedelta(hours=n_bars - 1)
    base_price = 100000.0
    rows = []
    for i in range(n_bars):
        bar_dt = start_dt + timedelta(hours=i)
        price = base_price * (1.0 + return_pct * (i / (n_bars - 1)))
        row = {
            "pair": pair,
            "decision_ts": bar_dt,
            "row_ready_at": bar_dt,
            "close": price,
            "atr_14": atr,
            "volume": 1000.0,
            "eligible": True,
        }
        if listed_at is not None:
            row["listed_at"] = listed_at
        rows.append(row)
    df = pd.DataFrame(rows)
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    return df


def _frame(pair_bars: list[pd.DataFrame], cash: Decimal | None = CASH) -> DecisionFrame:
    combined = pd.concat(pair_bars, ignore_index=True)
    return create_decision_frame(features=combined, as_of=AS_OF, available_cash_idr=cash)


def test_c12_01_valid_contract() -> None:
    """C12-01-AC0: candidate C12 produces intents comparable with baseline on same judge."""
    spec = load_c12_specification()
    frame = _frame(
        [
            _build_c12_pair_bars(AS_OF, "btc_idr", return_pct=0.05),
            _build_c12_pair_bars(AS_OF, "eth_idr", return_pct=0.10),
            _build_c12_pair_bars(AS_OF, "sol_idr", return_pct=0.15),
        ]
    )

    intents = c12_decide(frame, spec)

    # Independent expectation: universe median return is 10%; strengths are
    # btc -5pp (FLAT), eth 0pp (>= 0, LONG), sol +5pp (LONG); top_k = 2.
    assert [intent.pair for intent in intents] == ["sol_idr", "eth_idr"]
    for intent in intents:
        assert isinstance(intent, SignalIntent)
        assert intent.side == OrderSide.BUY
        assert intent.strategy_id == "C12"
        assert intent.decision_ts == AS_OF
        # Versioned intent identity: registry version is embedded in intent_id.
        assert intent.intent_id.startswith("c12_1.0.0_")
        assert intent.desired_qty > Decimal("0")
        # Independent turnover sizing: per-slot cap = cash * 0.50 / 2 = 25000 IDR,
        # quantity rounds down to 0.0001 base units.
        expected_qty = (Decimal("25000") / intent.limit_price).quantize(
            Decimal("0.0001"), rounding=ROUND_DOWN
        )
        assert intent.desired_qty == expected_qty
        assert intent.desired_qty * intent.limit_price <= Decimal("25000")
        # Registered ATR stop: close - 2.0 * 1500, within float rounding tolerance.
        assert intent.stop_loss is not None
        assert intent.stop_loss < intent.limit_price
        assert abs((intent.limit_price - intent.stop_loss) - Decimal("3000")) < Decimal(
            "0.00001"
        )

    total_notional = sum(
        (intent.desired_qty * intent.limit_price for intent in intents), start=Decimal("0")
    )
    assert total_notional <= CASH * Decimal("0.50")

    # Same judge: dependency baseline C04 on the identical frame selects the same
    # rotation candidates, so C12 output is comparable with the baseline run.
    baseline = c04_decide(frame, load_c04_specification())
    assert [intent.pair for intent in baseline] == ["sol_idr", "eth_idr"]

    # Diagnostics: every eligible pair is accounted for with an explicit status.
    history = c12_decision_history(frame, spec)
    assert [record.pair for record in history] == ["btc_idr", "eth_idr", "sol_idr"]
    by_pair = {record.pair: record for record in history}
    assert by_pair["sol_idr"].status == "LONG"
    assert by_pair["sol_idr"].rank == 1
    assert by_pair["eth_idr"].status == "LONG"
    assert by_pair["eth_idr"].rank == 2
    assert by_pair["btc_idr"].status == "FLAT"
    assert by_pair["btc_idr"].reason_code == "C12_STRENGTH_BELOW_MINIMUM"
    assert all(record.reason_code.startswith("C12_") for record in history)
    long_records = sorted(
        (record for record in history if record.status == "LONG"), key=lambda record: record.rank
    )
    assert [record.intent for record in long_records] == intents


def test_c12_01_contract_1() -> None:
    """C12-01-AC1: delisted pair tetap ada dalam histori."""
    spec = load_c12_specification()
    delisted = _build_c12_pair_bars(
        AS_OF,
        "old_idr",
        return_pct=0.50,
        ends_at=AS_OF - timedelta(hours=12),
    )
    frame = _frame(
        [
            delisted,
            _build_c12_pair_bars(AS_OF, "ada_idr", return_pct=0.10),
            _build_c12_pair_bars(AS_OF, "dot_idr", return_pct=0.10),
        ]
    )

    # The approved frame keeps the delisted pair's historical rows (no erase, no bfill).
    assert not frame.get_pair_features("old_idr").empty

    intents = c12_decide(frame, spec)
    # Rotation continues over the two live pairs; the delisted pair never re-enters.
    assert [intent.pair for intent in intents] == ["ada_idr", "dot_idr"]
    assert "old_idr" not in [intent.pair for intent in intents]

    history = c12_decision_history(frame, spec)
    by_pair = {record.pair: record for record in history}
    # The delisted pair remains present in the decision history with an explicit reason.
    assert set(by_pair) == {"ada_idr", "dot_idr", "old_idr"}
    record = by_pair["old_idr"]
    assert record.status == "EXCLUDED"
    assert record.reason_code == "C12_STALE_OR_DELISTED_NO_CURRENT_ROW"
    assert record.rank is None
    assert record.relative_strength is None
    assert record.intent is None
    assert by_pair["ada_idr"].status == "LONG"
    assert by_pair["ada_idr"].rank == 1
    assert by_pair["dot_idr"].status == "LONG"
    assert by_pair["dot_idr"].rank == 2


def test_c12_01_contract_2() -> None:
    """C12-01-AC2: cash regime memblokir reentry."""
    spec = load_c12_specification()
    frame = _frame(
        [
            # Strongest pair would be the reentry candidate, but breadth is 1/3 positive.
            _build_c12_pair_bars(AS_OF, "sol_idr", return_pct=0.20),
            _build_c12_pair_bars(AS_OF, "btc_idr", return_pct=-0.10),
            _build_c12_pair_bars(AS_OF, "doge_idr", return_pct=-0.15),
        ]
    )

    # breadth = 1/3 <= cash_breadth_threshold 0.50 -> cash regime: no LONG intents.
    assert c12_decide(frame, spec) == []

    history = c12_decision_history(frame, spec)
    assert [record.pair for record in history] == ["btc_idr", "doge_idr", "sol_idr"]
    assert all(
        record.status == "BLOCKED"
        and record.reason_code == "C12_CASH_REGIME_BLOCKS_REENTRY"
        for record in history
    )
    statuses = {(record.pair, record.status, record.reason_code) for record in history}
    assert ("sol_idr", "BLOCKED", "C12_CASH_REGIME_BLOCKS_REENTRY") in statuses
    strong = next(record for record in history if record.pair == "sol_idr")
    # The blocked candidate is ranked first with positive strength, so the regime
    # gate (not missing evidence) is what blocked the reentry.
    assert strong.rank == 1
    assert strong.relative_strength is not None
    assert strong.relative_strength > 0
    assert strong.intent is None


def test_c12_01_contract_3() -> None:
    """C12-01-AC3: tie rank stable."""
    spec = load_c12_specification()
    trio = [
        _build_c12_pair_bars(AS_OF, "ada_idr", return_pct=0.10),
        _build_c12_pair_bars(AS_OF, "dot_idr", return_pct=0.10),
        _build_c12_pair_bars(AS_OF, "trx_idr", return_pct=0.10),
    ]
    frame1 = _frame(trio)
    frame2 = _frame(list(reversed(trio)))

    intents1 = c12_decide(frame1, spec)
    intents2 = c12_decide(frame2, spec)

    # Identical strength ties resolve to canonical pair order, independent of
    # input row order: ada, dot fill top_k = 2; trx stays FLAT.
    assert [intent.pair for intent in intents1] == ["ada_idr", "dot_idr"]
    assert [intent.pair for intent in intents2] == ["ada_idr", "dot_idr"]
    assert intents1 == intents2

    history1 = {record.pair: record for record in c12_decision_history(frame1, spec)}
    history2 = {record.pair: record for record in c12_decision_history(frame2, spec)}
    assert history1 == history2
    assert history1["ada_idr"].rank == 1
    assert history1["dot_idr"].rank == 2
    assert history1["trx_idr"].rank == 3
    assert history1["trx_idr"].status == "FLAT"
    assert history1["trx_idr"].reason_code == "C12_BELOW_TOP_K"


def test_c12_unknown_cash_abstains_with_explicit_reason() -> None:
    """Unknown cash cannot bound turnover: fail-closed with an explicit diagnostic."""
    spec = load_c12_specification()
    frame = _frame(
        [
            _build_c12_pair_bars(AS_OF, "ada_idr", return_pct=0.10),
            _build_c12_pair_bars(AS_OF, "dot_idr", return_pct=0.12),
        ],
        cash=None,
    )

    assert c12_decide(frame, spec) == []
    history = c12_decision_history(frame, spec)
    statuses = {(record.pair, record.status, record.reason_code) for record in history}
    assert ("ada_idr", "BLOCKED", "C12_CASH_UNAVAILABLE_BLOCKS_TURNOVER") in statuses
    assert ("dot_idr", "BLOCKED", "C12_CASH_UNAVAILABLE_BLOCKS_TURNOVER") in statuses


def test_c12_missing_atr_pair_excluded_fail_closed() -> None:
    """A pair without a usable ATR stop is excluded from ranking, never traded."""
    spec = load_c12_specification()
    frame = _frame(
        [
            _build_c12_pair_bars(AS_OF, "sol_idr", return_pct=0.15, atr=float("nan")),
            _build_c12_pair_bars(AS_OF, "ada_idr", return_pct=0.10),
            _build_c12_pair_bars(AS_OF, "dot_idr", return_pct=0.10),
        ]
    )

    intents = c12_decide(frame, spec)
    assert [intent.pair for intent in intents] == ["ada_idr", "dot_idr"]

    history = c12_decision_history(frame, spec)
    by_pair = {record.pair: record for record in history}
    assert "sol_idr" in by_pair
    record = by_pair["sol_idr"]
    assert record.status == "EXCLUDED"
    assert record.reason_code == "C12_INVALID_MARKET_DATA"
    assert record.rank is None
    assert record.intent is None


def test_c12_fail_closed_edge_guards() -> None:
    """Short history, sub-floor universe and unbuyable turnover stay fail-closed."""
    spec = load_c12_specification()

    # Only one pair has a full lookback window, so universe evidence is below
    # minimum_valid_pairs and the short-history pair is explicitly excluded.
    frame = _frame(
        [
            _build_c12_pair_bars(AS_OF, "short_idr", return_pct=0.10, n_bars=5),
            _build_c12_pair_bars(AS_OF, "full_idr", return_pct=0.12),
        ]
    )
    assert c12_decide(frame, spec) == []
    by_pair = {record.pair: record for record in c12_decision_history(frame, spec)}
    assert by_pair["short_idr"].status == "EXCLUDED"
    assert by_pair["short_idr"].reason_code == "C12_INSUFFICIENT_LOOKBACK"
    assert by_pair["full_idr"].status == "BLOCKED"
    assert by_pair["full_idr"].reason_code == "C12_INSUFFICIENT_UNIVERSE_EVIDENCE"

    # Cash below the smallest tradable quantity rounds every slot to zero.
    # Equal returns put both pairs above the strength gate so sizing is reached.
    tiny_cash_frame = _frame(
        [
            _build_c12_pair_bars(AS_OF, "ada_idr", return_pct=0.10),
            _build_c12_pair_bars(AS_OF, "dot_idr", return_pct=0.10),
        ],
        cash=Decimal("1"),
    )
    assert c12_decide(tiny_cash_frame, spec) == []
    assert all(
        record.status == "FLAT"
        and record.reason_code == "C12_TURNOVER_BELOW_MIN_QUANTITY"
        for record in c12_decision_history(tiny_cash_frame, spec)
    )


def test_c12_rejects_invalid_rotation_parameters() -> None:
    """Unsafe or non-finite rotation parameters are rejected before any decision."""
    spec = load_c12_specification()
    frame = _frame(
        [
            _build_c12_pair_bars(AS_OF, "ada_idr", return_pct=0.10),
            _build_c12_pair_bars(AS_OF, "dot_idr", return_pct=0.12),
        ]
    )

    for key, value in (
        ("lookback_bars", 0),
        ("top_k", 0),
        ("minimum_valid_pairs", 1),
        ("cash_breadth_threshold", -0.1),
        ("cash_breadth_threshold", 1.1),
        ("cash_breadth_threshold", "NaN"),
        ("min_relative_strength", "Infinity"),
        ("max_turnover_fraction", "0"),
        ("max_turnover_fraction", "1.5"),
        ("max_turnover_fraction", "NaN"),
        ("atr_multiplier", 0),
        ("atr_multiplier", "NaN"),
    ):
        invalid = spec.model_copy(update={"parameters": spec.parameters | {key: value}})
        try:
            c12_decide(frame, invalid)
        except ValueError as exc:
            assert str(exc) == "INVALID_C12_ROTATION_PARAMETERS"
        else:
            raise AssertionError(f"accepted unsafe {key}={value}")


def test_c12_01_negative_min_relative_strength_rejected_fail_closed(tmp_path: Path) -> None:
    """M1: a negative min_relative_strength is rejected, never silently misattributed.

    Constructed case (hand-computed): returns aaa +10%, bbb +8%, ccc -1% give
    universe median +8% and breadth 2/3 > 0.50, so the cash-regime gate passes.
    With `min_relative_strength = -0.10` the ccc_idr strength is
    -0.01 - 0.08 = -0.09, which is AT OR ABOVE the configured floor, while its
    lookback return is non-positive. Pre-fix, ccc_idr was reported FLAT with
    `C12_STRENGTH_BELOW_MINIMUM` even though the strength gate passed: the
    positive-return (breadth) criterion was what actually failed.
    """
    spec = load_c12_specification()
    frame = _frame(
        [
            _build_c12_pair_bars(AS_OF, "aaa_idr", return_pct=0.10),
            _build_c12_pair_bars(AS_OF, "bbb_idr", return_pct=0.08),
            _build_c12_pair_bars(AS_OF, "ccc_idr", return_pct=-0.01),
        ]
    )
    invalid = spec.model_copy(
        update={"parameters": spec.parameters | {"min_relative_strength": -0.10}}
    )

    # Config/load time: the canonical config with a negative floor must not load.
    canonical = Path("configs/strategies/C12_v1.yaml").read_text(encoding="utf-8")
    negative_config = tmp_path / "C12_negative_min_strength.yaml"
    negative_config.write_text(
        canonical.replace("min_relative_strength: 0.0", "min_relative_strength: -0.10"),
        encoding="utf-8",
    )
    try:
        load_c12_specification(negative_config)
    except ValueError as exc:
        assert str(exc) == "INVALID_C12_ROTATION_PARAMETERS"
    else:
        raise AssertionError("load_c12_specification accepted negative min_relative_strength")

    # Decision time: a directly injected spec must also fail closed before deciding.
    for decide in (c12_decide, c12_decision_history):
        try:
            decide(frame, invalid)
        except ValueError as exc:
            assert str(exc) == "INVALID_C12_ROTATION_PARAMETERS"
        else:
            raise AssertionError("negative min_relative_strength accepted by decision path")


def test_c12_01_not_yet_listed_and_delisted_cannot_enter_rotation() -> None:
    """M2: dedicated proof that delisted and not-yet-listed pairs cannot rotate.

    Both representations are pinned because the inherited claim that
    DecisionFrame "structurally covers" this was not proven:
    - rows entirely after as_of (pair listed only later) are dropped by the
      causal DecisionFrame, so the pair never reaches the eligible universe;
    - a not-yet-listed pair with eligible rows at as_of and canonical
      `listed_at` in the future is NOT covered by the frame (it only checks
      decision_ts/row_ready_at/eligible), so C12 itself must exclude it,
      mirroring C04's explicit listed_at guard.
    """
    spec = load_c12_specification()
    delisted = _build_c12_pair_bars(
        AS_OF, "old_idr", return_pct=0.90, ends_at=AS_OF - timedelta(hours=6)
    )
    not_yet_listed = _build_c12_pair_bars(
        AS_OF, "future_idr", return_pct=0.90, listed_at=AS_OF + timedelta(days=1)
    )
    future_only_rows = _build_c12_pair_bars(
        AS_OF, "late_idr", return_pct=0.90, starts_at=AS_OF + timedelta(hours=1)
    )
    frame = _frame(
        [
            _build_c12_pair_bars(AS_OF, "ada_idr", return_pct=0.10),
            _build_c12_pair_bars(AS_OF, "dot_idr", return_pct=0.10),
            delisted,
            not_yet_listed,
            future_only_rows,
        ]
    )

    # Frame boundary: rows after as_of never enter the eligible universe at all.
    assert set(frame.eligible_pairs) == {"ada_idr", "dot_idr", "old_idr", "future_idr"}

    # Both intruders carry the strongest lookback return (+90%) yet may not rotate.
    intents = c12_decide(frame, spec)
    assert [intent.pair for intent in intents] == ["ada_idr", "dot_idr"]

    history = {record.pair: record for record in c12_decision_history(frame, spec)}
    assert set(history) == {"ada_idr", "dot_idr", "old_idr", "future_idr"}
    delisted_record = history["old_idr"]
    assert delisted_record.status == "EXCLUDED"
    assert delisted_record.reason_code == "C12_STALE_OR_DELISTED_NO_CURRENT_ROW"
    assert delisted_record.intent is None
    future_record = history["future_idr"]
    assert future_record.status == "EXCLUDED"
    assert future_record.reason_code == "C12_NOT_YET_LISTED"
    assert future_record.intent is None
    assert history["ada_idr"].status == "LONG"
    assert history["dot_idr"].status == "LONG"
