"""Offline behavioral tests for the public market-stream protocol adapter."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.contracts import AggressorSide, QualityStatus
from indodax_lab.data.stream_protocol import (
    BookSessionProtocol,
    ConflictingSequenceError,
    InvalidPublicStreamMessage,
    SequenceRegressionError,
    StreamState,
    parse_public_message,
)

FIXTURES = Path(__file__).parents[3] / "fixtures" / "indodax" / "stream"
INGESTED_AT = datetime(2024, 8, 6, 0, 0, 1, tzinfo=UTC)


def _fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_public_trade_parser_preserves_official_identity_decimal_and_utc_contracts():
    """Casting exchange values to floats or inventing an account identity corrupts replay."""
    parsed = parse_public_message(_fixture("public_trade.json"), ingested_at=INGESTED_AT)

    assert parsed.channel == "market:trade-activity-btcidr"
    assert parsed.offset == 243556
    assert len(parsed.trades) == 1
    trade = parsed.trades[0]
    assert trade.pair.pair == "btc_idr"
    assert trade.venue_symbol == "BTCIDR"
    assert trade.event_ts == datetime(2024, 8, 6, tzinfo=UTC)
    assert trade.price == Decimal("881991000")
    assert trade.base_qty == Decimal("0.00003372")
    assert trade.quote_qty == Decimal("29740")
    assert trade.sequence == 21999427
    assert trade.aggressor_side is AggressorSide.BUY
    assert trade.quality_status is QualityStatus.PASS
    assert trade.source_event_id == "indodax:public-trade:btcidr:21999427"


def test_book_protocol_reaches_reliable_only_after_a_valid_snapshot():
    """Marking a just-connected stream eligible would expose a book without a baseline."""
    protocol = BookSessionProtocol(
        pair="btc_idr", session_id_factory=lambda: "book-session-1"
    )

    protocol.connected()
    assert protocol.state is StreamState.SYNCING
    assert protocol.feature_eligible is False

    result = protocol.handle(_fixture("book_snapshot.json"), ingested_at=INGESTED_AT)

    assert protocol.state is StreamState.RELIABLE
    assert protocol.feature_eligible is True
    assert result.feature_eligible is True
    assert {event.book_session_id for event in result.books} == {"book-session-1"}
    assert [(event.side.value, event.level) for event in result.books] == [
        ("ASK", 0),
        ("BID", 0),
    ]
    assert all(event.sequence == 67409 for event in result.books)


def test_identical_duplicate_offset_is_idempotent_and_emits_no_book_rows():
    """Persisting an identical replay twice would double-count one official publication."""
    protocol = BookSessionProtocol(
        pair="btc_idr", session_id_factory=lambda: "book-session-1"
    )
    protocol.connected()
    protocol.handle(_fixture("book_snapshot.json"), ingested_at=INGESTED_AT)
    first = protocol.handle(_fixture("book_update.json"), ingested_at=INGESTED_AT)

    duplicate = protocol.handle(
        _fixture("duplicate_sequence.json"), ingested_at=INGESTED_AT
    )

    assert len(first.books) == 2
    assert duplicate.duplicate is True
    assert duplicate.books == ()
    assert protocol.last_offset == 67410
    assert protocol.state is StreamState.RELIABLE


def test_conflicting_duplicate_offset_fails_closed():
    """Accepting changed content under an acknowledged offset would make replay ambiguous."""
    protocol = BookSessionProtocol(
        pair="btc_idr", session_id_factory=lambda: "book-session-1"
    )
    protocol.connected()
    protocol.handle(_fixture("book_snapshot.json"), ingested_at=INGESTED_AT)
    protocol.handle(_fixture("book_update.json"), ingested_at=INGESTED_AT)
    conflict = copy.deepcopy(_fixture("duplicate_sequence.json"))
    conflict["result"]["data"]["data"]["bid"][0]["btc_volume"] = "0.49999999"

    with pytest.raises(ConflictingSequenceError):
        protocol.handle(conflict, ingested_at=INGESTED_AT)

    assert protocol.state is StreamState.GAP
    assert protocol.feature_eligible is False


def test_heartbeat_is_recognized_without_becoming_market_data():
    """Treating a pong acknowledgement as a publication would advance a data checkpoint."""
    parsed = parse_public_message(_fixture("heartbeat.json"), ingested_at=INGESTED_AT)

    assert parsed.kind == "HEARTBEAT"
    assert parsed.offset is None
    assert parsed.trades == ()
    assert parsed.books == ()


def test_unrelated_bare_control_id_is_not_a_recognized_heartbeat():
    """Refreshing freshness from any bare ID lets unrelated replies mask a missed pong."""
    parsed = parse_public_message({"id": 99}, ingested_at=INGESTED_AT)

    assert parsed.kind == "CONTROL"


def test_public_authentication_ack_is_control_data_not_a_protocol_failure():
    """Rejecting the documented public authentication reply would force a reconnect loop."""
    payload = {
        "id": 1,
        "result": {
            "client": "public-client-id",
            "version": "2.8.6",
            "expires": True,
            "ttl": 100,
        },
    }

    parsed = parse_public_message(payload, ingested_at=INGESTED_AT)

    assert parsed.kind == "CONTROL"
    assert parsed.offset is None


@pytest.mark.parametrize("mutation", ["channel", "payload_pair"])
def test_configured_book_pair_mismatch_fails_before_state_mutation(mutation):
    """Accepting another market under a configured session would contaminate its LOB lineage."""
    protocol = BookSessionProtocol(
        pair="btc_idr", session_id_factory=lambda: "book-session-1"
    )
    protocol.connected()
    payload = copy.deepcopy(_fixture("book_snapshot.json"))
    if mutation == "channel":
        payload["result"]["channel"] = "market:order-book-ethidr"
    else:
        payload["result"]["data"]["data"]["pair"] = "ethidr"

    with pytest.raises(InvalidPublicStreamMessage, match="configured pair"):
        protocol.handle(payload, ingested_at=INGESTED_AT)

    assert protocol.state is StreamState.SYNCING
    assert protocol.last_offset is None
    assert protocol.pending_gap is None


def test_offset_regression_is_structured_without_an_inverted_missing_window():
    """Computing last+1 through observed-1 for a wrap creates an impossible inverted gap."""
    protocol = BookSessionProtocol(
        pair="btc_idr", session_id_factory=lambda: "book-session-1"
    )
    protocol.connected()
    protocol.handle(_fixture("book_snapshot.json"), ingested_at=INGESTED_AT)
    protocol.handle(_fixture("book_update.json"), ingested_at=INGESTED_AT)
    regressed = copy.deepcopy(_fixture("book_update.json"))
    regressed["result"]["data"]["offset"] = 0

    with pytest.raises(SequenceRegressionError) as raised:
        protocol.handle(regressed, ingested_at=INGESTED_AT)

    assert raised.value.previous_offset == 67410
    assert raised.value.observed_offset == 0
    assert protocol.state is StreamState.GAP
    assert protocol.pending_gap == (0, 0)
    assert protocol.gap_reason == "OFFSET_REGRESSION"
    assert protocol.gap_observed_offset == 0


def test_reconnect_cannot_clear_an_unquarantined_pending_gap():
    """A direct reconnect must not bypass the collector's durable quarantine commit."""
    protocol = BookSessionProtocol(
        pair="btc_idr", session_id_factory=lambda: "book-session-1"
    )
    protocol.connected()
    protocol.handle(_fixture("book_snapshot.json"), ingested_at=INGESTED_AT)
    protocol.handle(_fixture("book_update.json"), ingested_at=INGESTED_AT)
    protocol.handle(_fixture("gap_sequence.json"), ingested_at=INGESTED_AT)
    protocol.disconnected()

    with pytest.raises(RuntimeError, match="quarantined"):
        protocol.connected()

    assert protocol.pending_gap == (67411, 67411)
    assert protocol.book_session_id == "book-session-1"
