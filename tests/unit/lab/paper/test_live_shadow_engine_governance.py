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

import json
import sqlite3
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import CostScheduleTable
from indodax_lab.paper.live_shadow_engine import (
    ClosedTrade,
    LiveShadowEngine,
    ShadowPosition,
    UnauthorizedPortfolioResetError,
)

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


def test_shadow_new_risk_period_preserves_breaches_and_closed_trades(engine) -> None:
    _trip_hard_halt(engine)
    engine.save_state(
        event_type="RISK_HALT",
        event_payload={"reason": engine.risk_manager.halt_reason},
    )
    old_period_id = engine.risk_period_id
    engine.closed_trades.append(
        ClosedTrade(
            trade_id="closed-before-reset",
            position_id="position-before-reset",
            pair="btc_idr",
            strategy_id="test-strategy",
            entry_ts="2026-01-01T00:00:00+00:00",
            exit_ts="2026-01-01T01:00:00+00:00",
            entry_price=100.0,
            exit_price=90.0,
            qty=1.0,
            cash_debited=100.0,
            cash_credited=90.0,
            buy_fee=0.0,
            sell_fee=0.0,
            gross_pnl=-10.0,
            net_pnl=-10.0,
            pnl_pct=-0.1,
            exit_reason="STOP_LOSS",
            bars_held=1,
            risk_period_id=old_period_id,
        )
    )

    engine.reset_portfolio(**_AUTH_KWARGS)

    assert engine.risk_period_id != old_period_id
    assert [trade.trade_id for trade in engine.closed_trades] == ["closed-before-reset"]
    restarted = LiveShadowEngine(
        state_file=engine.state_file,
        initial_cash=Decimal("500000.00"),
        max_positions=2,
        fixed_risk_pct=0.015,
        max_cash_per_trade_pct=0.25,
        min_order_idr=Decimal("10000.00"),
    )
    assert restarted.risk_period_id == engine.risk_period_id
    assert [trade.trade_id for trade in restarted.closed_trades] == ["closed-before-reset"]
    assert restarted.closed_trades[0].risk_period_id == old_period_id

    with sqlite3.connect(engine.state_file) as conn:
        events = conn.execute(
            "SELECT event_type, payload FROM shadow_events ORDER BY seq"
        ).fetchall()
    halt_payloads = [json.loads(payload) for kind, payload in events if kind == "RISK_HALT"]
    reset_payloads = [json.loads(payload) for kind, payload in events if kind == "RESET"]
    assert halt_payloads and halt_payloads[-1]["risk_period_id"] == old_period_id
    assert reset_payloads and reset_payloads[-1]["previous_period_id"] == old_period_id
    assert reset_payloads[-1]["risk_period_id"] == engine.risk_period_id
    assert reset_payloads[-1]["previous_halt_reason"] == "DRAWDOWN_BREACH:0.4000"


def test_shadow_risk_period_reset_requires_closed_portfolio(engine) -> None:
    engine.open_positions["position-open"] = ShadowPosition(
        position_id="position-open",
        pair="btc_idr",
        strategy_id="test-strategy",
        entry_ts="2026-01-01T00:00:00+00:00",
        entry_price=100.0,
        qty=1.0,
        cash_debited=100.0,
        buy_fee_paid=0.0,
        stop_loss=90.0,
        take_profit=110.0,
        entry_atr=1.0,
        highest_price=100.0,
    )
    old_period_id = engine.risk_period_id
    old_cash = engine.available_cash

    with pytest.raises(UnauthorizedPortfolioResetError, match="PORTFOLIO_NOT_CLOSED"):
        engine.reset_portfolio(**_AUTH_KWARGS)

    assert engine.risk_period_id == old_period_id
    assert "position-open" in engine.open_positions
    assert engine.available_cash == old_cash


def test_shadow_failed_period_reset_restores_in_memory_state(engine, monkeypatch) -> None:
    _trip_hard_halt(engine)
    old_period_id = engine.risk_period_id
    old_risk_manager = engine.risk_manager
    old_audit_log = list(engine.audit_log)
    old_cash = engine.available_cash

    def fail_save(*args, **kwargs):
        raise OSError("simulated checkpoint failure")

    monkeypatch.setattr(engine.state_store, "save_checkpoint", fail_save)
    with pytest.raises(OSError, match="simulated checkpoint failure"):
        engine.reset_portfolio(**_AUTH_KWARGS)

    assert engine.risk_period_id == old_period_id
    assert engine.risk_manager is old_risk_manager
    assert engine.risk_manager.is_halted
    assert engine.audit_log == old_audit_log
    assert engine.available_cash == old_cash
