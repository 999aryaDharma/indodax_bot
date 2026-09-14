from decimal import Decimal

import pytest

from paper_accounting import account_buy, account_sell, realized_pnl


def test_round_trip_uses_gross_cash_debit_as_cost_basis() -> None:
    buy = account_buy(
        cash_budget=Decimal("100000"),
        price=Decimal("10000"),
        fee_rate=Decimal("0.002"),
    )
    sell = account_sell(
        base_qty=buy.base_qty,
        price=Decimal("11000"),
        fee_rate=Decimal("0.004"),
    )

    assert buy.cash_debit == Decimal("100000")
    assert buy.fee == Decimal("200")
    assert buy.notional == Decimal("99800")
    assert buy.base_qty == Decimal("9.98")
    assert sell.notional == Decimal("109780")
    assert sell.fee == Decimal("439.120")
    assert sell.net_credit == Decimal("109340.880")
    assert realized_pnl(buy, sell) == Decimal("9340.880")


@pytest.mark.parametrize(
    ("function", "arguments"),
    [
        (account_buy, (Decimal("0"), Decimal("10000"), Decimal("0.002"))),
        (account_buy, (Decimal("-1"), Decimal("10000"), Decimal("0.002"))),
        (account_buy, (Decimal("100000"), Decimal("0"), Decimal("0.002"))),
        (account_buy, (Decimal("100000"), Decimal("NaN"), Decimal("0.002"))),
        (account_buy, (Decimal("Infinity"), Decimal("10000"), Decimal("0.002"))),
        (account_buy, (Decimal("100000"), Decimal("10000"), Decimal("-0.1"))),
        (account_buy, (Decimal("100000"), Decimal("10000"), Decimal("1"))),
        (account_sell, (Decimal("0"), Decimal("11000"), Decimal("0.004"))),
        (account_sell, (Decimal("9.98"), Decimal("-1"), Decimal("0.004"))),
        (account_sell, (Decimal("9.98"), Decimal("11000"), Decimal("NaN"))),
    ],
)
def test_accounting_rejects_invalid_or_non_finite_inputs(function, arguments) -> None:
    with pytest.raises(ValueError):
        function(*arguments)
