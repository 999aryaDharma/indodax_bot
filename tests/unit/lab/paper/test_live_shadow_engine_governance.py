"""Regression tests for the live shadow engine review findings (ops-shadow batch).

Spec: docs/specs/14-shadow-portfolios-and-promotion.md, "Security and privacy":
"Paper only; authorized operator may pause/reset hard halt via audited control,
never through untrusted callback."

Findings covered:

- LS-F1 (Critical): ``LiveShadowEngine.reset_portfolio()`` takes no authorization
  argument and no audit record. Any holder of the engine object -- an untrusted
  callback, a scheduler tick, a replay driver -- can call it, which rebuilds
  ``PortfolioRiskManager`` and therefore silently clears an active risk hard
  halt.
- LS-F2 (Critical): the same method executes ``self.audit_log = []``, destroying
  the audit trail of the very positions being wiped, and records no reason for
  clearing the halt.

Isolation: every test uses a ``tmp_path`` SQLite state file and a synthetic cost
schedule. No network, no real ledger, no live credentials, no real orders.
``fetch_live_market_data`` is never called.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import CostScheduleTable

from indodax_lab.paper.live_shadow_engine import LiveShadowEngine


# The audited-control arguments a governed reset must require.
_AUTH_KWARGS = {
    "operator_id": "operator_root",
    "reason": "Operator-authorized portfolio reset after incident review",
    "authorization_ref": "CHG-2026-0042",
}


@pytest.fixture
def engine(tmp_path: Path):
    state_file = tmp_path / "shadow_state.sqlite3"
    instance = LiveShadowEngine(
        state_file=state_file,
        initial_cash=Decimal("500000.00"),
        max_positions=2,
        fixed_risk_pct=0.015,
        max_cash_per_trade_pct=0.25,
        min_order_idr=Decimal("10000.00"),
    )
    instance.cost_table = CostScheduleTable(
        schedule_set_id="paper-test-fixture",
        version="1",
        intervals=tuple(
            interval.model_copy(update={"evidence_verified": True})
            for interval in instance.cost_table.intervals
        ),
    )
    return instance


def _trip_hard_halt(instance: LiveShadowEngine) -> None:
    """Drive the risk manager into a real hard halt through its public surface."""
    # max_drawdown_halt_fraction is 0.08; observe equity far below the halt band.
    start = instance.risk_manager.start_time
    instance.risk_manager.observe_equity(Decimal("300000.00"), start)
    instance.risk_manager.observe_equity(
        Decimal("300000.00"), start + timedelta(minutes=1)
    )
    assert instance.risk_manager.is_halted is True, "fixture failed to trip the hard halt"


def _reset(engine: LiveShadowEngine, **overrides) -> None:
    """Attempt a reset through the governed API, falling back to the unhardened one.

    Before the fix the engine exposes no authorization arguments at all, so the
    bare call is the only reachable path -- and it is exactly the defect.
    """
    kwargs = {**_AUTH_KWARGS, **overrides}
    try:
        engine.reset_portfolio(**kwargs)
    except TypeError:
        engine.reset_portfolio()


# ---------------------------------------------------------------------------
# LS-F1: resetting a hard halt requires an audited, authorized control
# ---------------------------------------------------------------------------


def test_shadow_reset_requires_authorization(engine) -> None:
    """LS-F1: a reset with no authorization must not clear an active hard halt."""
    _trip_hard_halt(engine)

    # A bare call carries no operator identity, reason or change reference. This
    # is the exact shape an untrusted callback or scheduler tick has available.
    try:
        engine.reset_portfolio()
    except TypeError:
        pass  # correctly refuses a call with no authorization at all

    assert engine.risk_manager.is_halted is True, (
        "reset_portfolio() cleared an active risk hard halt with no authorization "
        "requirement; an untrusted caller can silently lift the risk governor"
    )


def test_shadow_blank_operator_cannot_authorize_reset(engine) -> None:
    """LS-F1: an empty operator identity must not satisfy the authorization gate."""
    _trip_hard_halt(engine)

    for blank in ("", "   "):
        try:
            engine.reset_portfolio(
                operator_id=blank, reason="test", authorization_ref="CHG-X"
            )
        except Exception:
            continue  # correctly refused

    assert engine.risk_manager.is_halted is True, (
        "A blank operator identity was accepted as authorization for a hard-halt reset"
    )


def test_shadow_authorized_reset_clears_halt_and_records_audit(engine) -> None:
    """Positive control: a fully authorized, audited reset does clear the halt."""
    _trip_hard_halt(engine)
    engine.audit_log.append({"action": "PRIOR_ENTRY", "pair": "btc_idr"})

    _reset(engine)

    assert engine.risk_manager.is_halted is False
    assert engine.available_cash == Decimal("500000.00")

    recorded = [
        entry
        for entry in engine.audit_log
        if entry.get("action") == "PORTFOLIO_RESET_AUTHORIZED"
    ]
    assert recorded, "An authorized hard-halt reset left no audit record"
    assert recorded[0]["operator_id"] == "operator_root"
    assert recorded[0]["authorization_ref"] == "CHG-2026-0042"
    assert "hard_halt_cleared" in recorded[0]["detail"]


# ---------------------------------------------------------------------------
# LS-F2: the audit trail must survive the reset
# ---------------------------------------------------------------------------


def test_shadow_reset_does_not_destroy_audit_trail(engine) -> None:
    """LS-F2: prior audit entries must survive a reset, not be wiped with it."""
    prior = [{"action": "PRIOR_ENTRY", "seq": index} for index in range(3)]
    engine.audit_log.extend(prior)

    _reset(engine)

    assert [e for e in engine.audit_log if e.get("action") == "PRIOR_ENTRY"] == prior, (
        "reset_portfolio() destroyed the audit trail of the positions it wiped"
    )


def test_shadow_reset_appends_one_recorded_reason(engine) -> None:
    """LS-F2/LS-F3: each reset appends exactly one recorded reason."""
    for index in range(3):
        engine.audit_log.append({"action": "ENTRY", "seq": index})
        before = len(engine.audit_log)

        engine.reset_portfolio(
            operator_id=_AUTH_KWARGS["operator_id"],
            reason=f"reset {index}",
            authorization_ref=f"CHG-{index}",
        )

        assert len(engine.audit_log) == before + 1, (
            "reset_portfolio truncated the audit log instead of appending to it"
        )

    assert sum(1 for e in engine.audit_log if e.get("action") == "ENTRY") == 3


def test_shadow_reset_without_authorization_leaves_no_audit_entry(engine) -> None:
    """LS-F3: a refused reset must not touch the ledger, risk state or audit log."""
    _trip_hard_halt(engine)
    engine.audit_log.append({"action": "PRIOR_ENTRY", "pair": "btc_idr"})
    before_audit = list(engine.audit_log)
    before_cash = engine.available_cash

    for kwargs in (
        {"operator_id": "  ", "reason": "no identity", "authorization_ref": "CHG-1"},
        {"operator_id": "operator_root", "reason": "  ", "authorization_ref": "CHG-1"},
        {"operator_id": "operator_root", "reason": "no ref", "authorization_ref": " "},
    ):
        try:
            engine.reset_portfolio(**kwargs)
        except Exception:
            continue  # correctly refused

    assert list(engine.audit_log) == before_audit, (
        "A refused/unauthorized reset still mutated the audit log"
    )
    assert engine.risk_manager.is_halted is True, (
        "A refused/unauthorized reset still cleared the risk hard halt"
    )
    assert engine.available_cash == before_cash
