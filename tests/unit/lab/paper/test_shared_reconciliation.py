"""Tests for SHADOW-02: Shared capital reconciliation.

RED tests written before implementation.

Contract: durable event IDs + risk policy -> reconciled postings, independent vs shared reports.

AC boundaries:
- AC0: Single shared ledger of Rp500,000 resolves cash allocation across multiple candidates.
- AC1: Duplicate event ID does not create a second entry (idempotency guard).
- AC2: Maximum of two shared open positions enforced strictly across all candidates.
- AC3: Restart from checkpoint or event replay produces identical equity and position state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import pytest

# These imports will fail until implementation exists — RED phase
from indodax_lab.paper.portfolio import (
    MaxPositionsExceededError,
    PaperOrderIntent,
    SharedCapitalLedger,
    SharedLedgerCheckpoint,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_intent(
    event_id: str,
    candidate_id: str = "cand_01",
    pair: str = "btc_idr",
    side: str = "BUY",
    allocated_cash: Decimal = Decimal("200000.00"),
    entry_price: Decimal = Decimal("1000000000.00"),
) -> PaperOrderIntent:
    return PaperOrderIntent(
        event_id=event_id,
        candidate_id=candidate_id,
        pair=pair,
        side=side,
        allocated_cash=allocated_cash,
        entry_price=entry_price,
        timestamp=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# AC0: Single shared ledger of Rp500,000 resolves cash allocation
# ---------------------------------------------------------------------------

def test_shadow_02_valid_contract():
    """SHADOW-02-AC0: Rp500,000 shared ledger allocates cash and maintains exact decimal balances."""
    ledger = SharedCapitalLedger(initial_cash=Decimal("500000.00"))

    assert ledger.available_cash == Decimal("500000.00")
    assert ledger.open_position_count == 0

    intent = _make_intent(event_id="evt_01", allocated_cash=Decimal("200000.00"))
    result = ledger.process_intent(intent)

    assert result.approved is True
    assert ledger.available_cash == Decimal("300000.00")
    assert ledger.open_position_count == 1


# ---------------------------------------------------------------------------
# AC1: Duplicate event ID does not create a second entry
# ---------------------------------------------------------------------------

def test_shadow_02_contract_1():
    """SHADOW-02-AC1: Submitting an intent with an already-processed event_id is rejected as DUPLICATE."""
    ledger = SharedCapitalLedger(initial_cash=Decimal("500000.00"))
    intent = _make_intent(event_id="evt_dup", allocated_cash=Decimal("150000.00"))

    res1 = ledger.process_intent(intent)
    assert res1.approved is True
    cash_after_first = ledger.available_cash

    # Second submission with the exact same event_id
    res2 = ledger.process_intent(intent)
    assert res2.approved is False
    assert res2.reason == "DUPLICATE_EVENT_ID"

    # Cash must remain exactly what it was after the first processing
    assert ledger.available_cash == cash_after_first
    assert ledger.open_position_count == 1


# ---------------------------------------------------------------------------
# AC2: Maximum two shared open positions
# ---------------------------------------------------------------------------

def test_shadow_02_contract_2():
    """SHADOW-02-AC2: Maximum two shared open positions enforced across all candidates."""
    ledger = SharedCapitalLedger(
        initial_cash=Decimal("500000.00"),
        max_open_positions=2,
    )

    # Position 1: candidate A
    intent1 = _make_intent(event_id="evt_p1", candidate_id="cand_A", pair="btc_idr", allocated_cash=Decimal("100000.00"))
    res1 = ledger.process_intent(intent1)
    assert res1.approved is True
    assert ledger.open_position_count == 1

    # Position 2: candidate B
    intent2 = _make_intent(event_id="evt_p2", candidate_id="cand_B", pair="eth_idr", allocated_cash=Decimal("100000.00"))
    res2 = ledger.process_intent(intent2)
    assert res2.approved is True
    assert ledger.open_position_count == 2

    # Position 3: candidate C (must be rejected because max 2 positions reached)
    intent3 = _make_intent(event_id="evt_p3", candidate_id="cand_C", pair="sol_idr", allocated_cash=Decimal("100000.00"))
    with pytest.raises(MaxPositionsExceededError):
        ledger.process_intent(intent3)

    assert ledger.open_position_count == 2


# ---------------------------------------------------------------------------
# AC3: Restart produces identical equity and checkpoint state
# ---------------------------------------------------------------------------

def test_shadow_02_contract_3():
    """SHADOW-02-AC3: Restart from checkpoint yields identical cash, equity, and position state."""
    ledger = SharedCapitalLedger(initial_cash=Decimal("500000.00"))
    intent1 = _make_intent(event_id="evt_r1", allocated_cash=Decimal("200000.00"))
    intent2 = _make_intent(event_id="evt_r2", allocated_cash=Decimal("150000.00"))

    ledger.process_intent(intent1)
    ledger.process_intent(intent2)

    # Export checkpoint
    checkpoint = ledger.create_checkpoint()
    assert isinstance(checkpoint, SharedLedgerCheckpoint)

    # Restore in a fresh ledger
    restored_ledger = SharedCapitalLedger.from_checkpoint(checkpoint)

    assert restored_ledger.available_cash == ledger.available_cash
    assert restored_ledger.open_position_count == ledger.open_position_count
    assert restored_ledger.processed_event_ids == ledger.processed_event_ids

    # Attempting to process evt_r1 in restored ledger should still be detected as DUPLICATE
    res_dup = restored_ledger.process_intent(intent1)
    assert res_dup.approved is False
    assert res_dup.reason == "DUPLICATE_EVENT_ID"
