"""Regression tests for SHADOW-02 review findings (ops-shadow batch).

Findings covered (spec: docs/specs/14-shadow-portfolios-and-promotion.md,
acceptance boundary SHADOW-02: "Maksimum dua posisi shared" and "Restart
menghasilkan equity dan checkpoint sama"):

- S02-F1 (Important): ``SharedLedgerCheckpoint`` records neither the original
  capital basis nor the active ``max_open_positions`` cap, and
  ``from_checkpoint`` rebuilds the ledger with the *default* cap. A ledger
  running under a stricter shared cap therefore silently gains capacity after a
  restart: the AC2 max-positions gate stops being enforced across the restart
  boundary. This is a risk-cap bypass, not a reporting nit.
- S02-F2 (Important): ``from_checkpoint`` rebuilds the ledger positionally with
  ``initial_cash=checkpoint.available_cash``, so the restored ledger's capital
  basis is the *remaining* cash and its reported equity is structurally wrong.
- S02-F3 (Important): the checkpoint carries no integrity fingerprint, so a
  tampered or forged checkpoint is restored silently as if it were authentic --
  a restore that reports success without verifying the restored content.

Isolation: every test is in-memory only. No filesystem, no network, no real
ledger, no live credentials, no real orders.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from indodax_lab.paper.portfolio import (
    PaperOrderIntent,
    SharedCapitalLedger,
    SharedLedgerCheckpoint,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _intent(
    event_id: str,
    *,
    candidate_id: str = "cand_01",
    pair: str = "btc_idr",
    allocated_cash: str = "200000.00",
) -> PaperOrderIntent:
    return PaperOrderIntent(
        event_id=event_id,
        candidate_id=candidate_id,
        pair=pair,
        side="BUY",
        allocated_cash=Decimal(allocated_cash),
        entry_price=Decimal("1000000000.00"),
        timestamp=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# S02-F1: the shared position cap must survive a restart
# ---------------------------------------------------------------------------


def test_shadow_02_max_position_cap_survives_restart() -> None:
    """S02-F1: a stricter shared cap must still be in force after a restart."""
    ledger = SharedCapitalLedger(
        initial_cash=Decimal("500000.00"), max_open_positions=1
    )
    ledger.process_intent(_intent("evt_1", allocated_cash="100000.00"))
    checkpoint = ledger.create_checkpoint()

    restored = SharedCapitalLedger.from_checkpoint(checkpoint)

    assert restored.max_open_positions == 1, (
        "The shared max-positions cap reverted to the default after a restart; the "
        "AC2 gate is no longer enforced across the restart boundary"
    )


def test_shadow_02_restarted_ledger_refuses_capacity_breach() -> None:
    """S02-F1: behaviour, not just state -- the breach must actually be refused."""
    ledger = SharedCapitalLedger(
        initial_cash=Decimal("500000.00"), max_open_positions=1
    )
    ledger.process_intent(_intent("evt_1", pair="btc_idr", allocated_cash="100000.00"))
    restored = SharedCapitalLedger.from_checkpoint(ledger.create_checkpoint())

    second = _intent("evt_2", pair="eth_idr", allocated_cash="100000.00")
    try:
        result = restored.process_intent(second)
    except Exception:
        result = None

    if result is not None and result.approved is True:
        raise AssertionError(
            "A restarted ledger approved a position beyond the shared cap that was "
            "in force before the restart; the risk cap was silently widened"
        )
    assert restored.open_position_count == 1


# ---------------------------------------------------------------------------
# S02-F2: the restored capital basis must be correct
# ---------------------------------------------------------------------------


def test_shadow_02_restart_preserves_capital_basis() -> None:
    """S02-F2: the restored ledger must report the original Rp500,000 basis."""
    ledger = SharedCapitalLedger(initial_cash=Decimal("500000.00"))
    ledger.process_intent(_intent("evt_1", allocated_cash="200000.00"))
    ledger.process_intent(_intent("evt_2", allocated_cash="150000.00"))

    restored = SharedCapitalLedger.from_checkpoint(ledger.create_checkpoint())

    basis = getattr(restored, "initial_cash", None)
    assert basis == Decimal("500000.00"), (
        f"Restored capital basis is {basis} instead of the original Rp500,000; "
        "equity computed from a restored ledger is structurally wrong"
    )


# ---------------------------------------------------------------------------
# S02-F3: a tampered checkpoint must be refused
# ---------------------------------------------------------------------------


def test_shadow_02_tampered_checkpoint_is_refused() -> None:
    """S02-F3: inflating restored cash must not be silently accepted."""
    ledger = SharedCapitalLedger(initial_cash=Decimal("500000.00"))
    ledger.process_intent(_intent("evt_1", allocated_cash="200000.00"))
    honest = ledger.create_checkpoint()

    tampered = honest.model_copy(update={"available_cash": Decimal("900000.00")})

    try:
        restored = SharedCapitalLedger.from_checkpoint(tampered)
    except Exception:
        return

    assert restored.available_cash == Decimal("300000.00"), (
        "A checkpoint with an inflated cash balance was restored as authentic; "
        "a restore reported success without verifying the restored content"
    )


def test_shadow_02_honest_checkpoint_round_trips_unchanged() -> None:
    """Positive control: an untampered checkpoint still restores exactly."""
    ledger = SharedCapitalLedger(initial_cash=Decimal("500000.00"))
    ledger.process_intent(_intent("evt_1", allocated_cash="200000.00"))
    ledger.process_intent(_intent("evt_2", allocated_cash="150000.00"))
    checkpoint = ledger.create_checkpoint()

    restored = SharedCapitalLedger.from_checkpoint(checkpoint)

    assert isinstance(checkpoint, SharedLedgerCheckpoint)
    assert restored.available_cash == ledger.available_cash
    assert restored.open_position_count == ledger.open_position_count
    assert restored.processed_event_ids == ledger.processed_event_ids
