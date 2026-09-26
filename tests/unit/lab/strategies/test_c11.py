from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd

from indodax_lab.strategies.base import DecisionFrame
from indodax_lab.strategies.c11 import c11_decide, load_c11_specification

AS_OF = datetime(2025, 1, 1, tzinfo=UTC)


def _frame(rows, cash=Decimal("100000")):
    data = pd.DataFrame(
        [
            {
                "pair": pair,
                "decision_ts": AS_OF,
                "row_ready_at": AS_OF,
                "eligible": True,
                "close": price,
                "rv_24_1h": rv,
            }
            for pair, rv, price in rows
        ]
    )
    return DecisionFrame(AS_OF, data, data["pair"].tolist(), available_cash_idr=cash)


def test_c11_candidate_sized_inverse_volatility_respects_cash_and_pair_caps():
    frame = _frame(
        [("btc_idr", "0.1", "1000000"), ("eth_idr", "0.2", "50000"), ("sol_idr", "0.4", "1000")]
    )
    intents = c11_decide(frame, load_c11_specification())
    notionals = {intent.pair: intent.desired_qty * intent.limit_price for intent in intents}
    assert set(notionals) == {"btc_idr", "eth_idr"}
    assert sum(notionals.values()) <= Decimal("50000")
    assert all(value <= Decimal("25000") for value in notionals.values())
    assert notionals["btc_idr"] == Decimal("25000")
    assert notionals["eth_idr"] > Decimal("10000")


def test_c11_excludes_zero_and_nonfinite_volatility_and_requires_two_pairs():
    frame = _frame(
        [("btc_idr", "0", "100"), ("eth_idr", "NaN", "100"), ("sol_idr", "0.2", "100")]
    )
    assert c11_decide(frame, load_c11_specification()) == []


def test_c11_missing_cash_abstains():
    frame = _frame([("btc_idr", "0.1", "100"), ("eth_idr", "0.2", "100")], cash=None)
    assert c11_decide(frame, load_c11_specification()) == []


def test_c11_respects_indodax_minimum_notional():
    frame = _frame(
        [(f"pair{i}_idr", "0.1", "100") for i in range(6)],
        cash=Decimal("100000"),
    )
    assert c11_decide(frame, load_c11_specification()) == []


def test_c11_excludes_missing_volatility_without_crashing():
    frame = _frame(
        [("btc_idr", None, "100"), ("eth_idr", "0.1", "100"), ("sol_idr", "0.2", "100")]
    )
    intents = c11_decide(frame, load_c11_specification())
    assert {intent.pair for intent in intents} == {"eth_idr", "sol_idr"}


def test_c11_rechecks_minimum_after_decimal_quantity_rounding():
    frame = _frame(
        [("btc_idr", "0.1", "3"), ("eth_idr", "0.1", "3")],
        cash=Decimal("40000"),
    )
    assert c11_decide(frame, load_c11_specification()) == []


def test_c11_rejects_parameters_above_frozen_allocation_caps():
    frame = _frame([("btc_idr", "0.1", "100"), ("eth_idr", "0.2", "100")])
    spec = load_c11_specification()
    for key, value in (
        ("deployment_fraction", "2"),
        ("deployment_fraction", "NaN"),
        ("max_pair_fraction", "1"),
        ("max_pair_fraction", "Infinity"),
        ("min_notional_idr", "0"),
        ("min_notional_idr", "1"),
        ("min_notional_idr", "9999"),
    ):
        invalid = spec.model_copy(
            update={"parameters": spec.parameters | {key: value}}
        )
        try:
            c11_decide(frame, invalid)
        except ValueError as exc:
            assert str(exc) == "INVALID_C11_ALLOCATION_PARAMETERS"
        else:
            raise AssertionError(f"accepted unsafe {key}={value}")


def test_decision_frame_cash_contract_is_optional_decimal_only():
    features = pd.DataFrame()
    assert DecisionFrame(AS_OF, features, ()).available_cash_idr is None
    zero_cash_frame = DecisionFrame(AS_OF, features, (), available_cash_idr=Decimal("0"))
    assert zero_cash_frame.available_cash_idr == 0
    for invalid in (100, 1.0, Decimal("-1"), Decimal("Infinity")):
        try:
            DecisionFrame(AS_OF, features, (), available_cash_idr=invalid)
        except ValueError as exc:
            assert str(exc) == "INVALID_AVAILABLE_CASH_IDR"
        else:
            raise AssertionError(f"accepted invalid cash value: {invalid!r}")
