import copy
import json
from pathlib import Path

import pytest

import indodax_api

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "indodax" / "my_trades_v2.json"


def _load_payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def test_parse_my_trades_v2_preserves_official_trade_contract() -> None:
    """A parser that reads legacy type/amount fields loses official V2 trade data."""
    trades = indodax_api._parse_my_trades_v2(_load_payload(), "aave_idr")

    assert len(trades) == 1
    trade = trades[0]
    assert trade.pair == "aave_idr"
    assert trade.trade_id == "72057594037936570"
    assert trade.order_id == "aaveidr-limit-3568"
    assert trade.trade_type == "sell"
    assert trade.price == 1_564_455.0
    assert trade.amount == 0.1
    assert trade.quote_amount == 156_445.5
    assert trade.commission == 468.0
    assert trade.commission_asset == "idr"
    assert trade.is_buyer is False
    assert trade.is_maker is False
    assert trade.timestamp_ms == 1_723_442_692_520
    assert trade.timestamp == 1_723_442_692.52


def test_parse_my_trades_v2_skips_string_boolean_flags() -> None:
    """String flags must not turn a malformed sell into a buy."""
    payload = _load_payload()
    payload["data"][0].update({"isBuyer": "false", "isMaker": "true"})

    assert indodax_api._parse_my_trades_v2(payload, "aave_idr") == []


@pytest.mark.parametrize("payload", [None, []])
def test_parse_my_trades_v2_returns_empty_for_non_mapping_payloads(payload) -> None:
    """Malformed top-level API values are safely treated as no trade records."""
    assert indodax_api._parse_my_trades_v2(payload, "aave_idr") == []


def test_is_pair_already_held_uses_newest_buy_by_millisecond_timestamp(monkeypatch) -> None:
    """Second-level timestamp compatibility must not choose an older sell as newest."""
    payload = _load_payload()
    newest_buy = copy.deepcopy(payload["data"][0])
    newest_buy.update({"tradeId": "72057594037936571", "isBuyer": True, "time": 1723442692999})
    payload["data"].append(newest_buy)
    trades = indodax_api._parse_my_trades_v2(payload, "aave_idr")

    monkeypatch.setattr(indodax_api, "fetch_recent_trades", lambda _pair, limit: trades)

    assert indodax_api.is_pair_already_held("aave_idr") is True


def test_is_pair_already_held_uses_newest_sell_by_millisecond_timestamp(monkeypatch) -> None:
    """A newer sell closes the pair even when both trades share a whole second."""
    payload = _load_payload()
    oldest_buy = copy.deepcopy(payload["data"][0])
    oldest_buy.update({"tradeId": "72057594037936571", "isBuyer": True, "time": 1723442692001})
    payload["data"].append(oldest_buy)
    trades = indodax_api._parse_my_trades_v2(payload, "aave_idr")

    monkeypatch.setattr(indodax_api, "fetch_recent_trades", lambda _pair, limit: trades)

    assert indodax_api.is_pair_already_held("aave_idr") is False
