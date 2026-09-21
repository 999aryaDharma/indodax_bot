"""Unit tests for DurableModeStore persistence, transition graph, and SHADOW venue isolation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from indodax_lab.control.mode import (
    DurableModeStore,
    ExecutionMode,
    InvalidModeTransitionError,
)
from indodax_lab.control.pipeline import TradingPipeline
from indodax_lab.execution.indodax_trading import IndodaxTradingClient
from indodax_lab.execution.oms import OmsStore
from indodax_lab.execution.order_router import OrderRouter
from indodax_lab.market.gateway import MarketGateway
from indodax_lab.portfolio.constructor import PortfolioConstructor
from indodax_lab.risk.engine import RiskEngine

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


def test_durable_mode_store_persistence_and_transitions(tmp_path: Path) -> None:
    mode_file = tmp_path / "mode.json"
    store = DurableModeStore(mode_file, initial_mode=ExecutionMode.DISABLED)
    assert store.get_mode() == ExecutionMode.DISABLED

    # Valid transition to READ_ONLY
    store.transition_to(ExecutionMode.READ_ONLY, reason="OPERATOR_ENABLING_READS")
    assert store.get_mode() == ExecutionMode.READ_ONLY
    assert mode_file.exists()

    # Reload from disk into fresh store instance
    reloaded_store = DurableModeStore(mode_file)
    assert reloaded_store.get_mode() == ExecutionMode.READ_ONLY

    # Transition to SHADOW
    reloaded_store.transition_to(ExecutionMode.SHADOW, reason="COMMENCING_SHADOW")
    assert reloaded_store.get_mode() == ExecutionMode.SHADOW

    # Invalid transition: SHADOW to AUTONOMOUS_LIMITED directly is forbidden
    with pytest.raises(InvalidModeTransitionError):
        reloaded_store.transition_to(ExecutionMode.AUTONOMOUS_LIMITED, reason="UNAUTHORIZED_JUMP")

    # Emergency halt is always permitted
    reloaded_store.transition_to(ExecutionMode.HALTED, reason="EMERGENCY_STOP")
    assert reloaded_store.get_mode() == ExecutionMode.HALTED

    # From HALTED, must transition to RECOVERY first
    with pytest.raises(InvalidModeTransitionError):
        reloaded_store.transition_to(ExecutionMode.SHADOW, reason="DIRECT_RESTART")

    reloaded_store.transition_to(ExecutionMode.RECOVERY, reason="OPERATOR_INVESTIGATION")
    assert reloaded_store.get_mode() == ExecutionMode.RECOVERY

    # From RECOVERY, can safely return to DISABLED or READ_ONLY or SHADOW
    reloaded_store.transition_to(ExecutionMode.DISABLED, reason="SYSTEM_RESET")
    assert reloaded_store.get_mode() == ExecutionMode.DISABLED


def test_shadow_mode_structurally_forbids_live_venue(tmp_path: Path) -> None:
    live_venue = IndodaxTradingClient(api_key="live_key", secret_key="live_secret")
    oms_store = OmsStore(tmp_path / "oms.db")
    router = OrderRouter(oms_store=oms_store, venue=live_venue)
    risk_engine = MagicMock(spec=RiskEngine)
    risk_engine.is_kill_switch_active = False

    # Invariant: Pipeline initialized in SHADOW mode with live IndodaxTradingClient must fail closed
    with pytest.raises(RuntimeError, match="SHADOW_MODE_FORBIDS_LIVE_VENUE"):
        TradingPipeline(
            mode=ExecutionMode.SHADOW,
            gateway=MagicMock(spec=MarketGateway),
            constructor=MagicMock(spec=PortfolioConstructor),
            risk_engine=risk_engine,
            oms_store=oms_store,
            order_router=router,
        )
