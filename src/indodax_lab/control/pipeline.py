"""Unified execution pipeline coordinating market data, risk, control modes, and OMS."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from indodax_lab.backtest.events import SignalIntent
from indodax_lab.backtest.ledger import Position
from indodax_lab.control.approval import ManualApprovalStore, PendingProposal, ProposalStatus
from indodax_lab.control.mode import (
    AutonomousLimits,
    DurableModeStore,
    ExecutionMode,
    InvalidModeTransitionError,
    validate_mode_transition,
)
from indodax_lab.execution.indodax_trading import IndodaxTradingClient
from indodax_lab.execution.oms import OmsOrder, OmsOrderState
from indodax_lab.execution.oms_store import OmsStore
from indodax_lab.execution.order_router import OrderRouter
from indodax_lab.market.gateway import MarketGateway
from indodax_lab.market.health import UNSAFE_TRADING_STATES, MarketHealthState
from indodax_lab.market.quality import TickerSnapshot
from indodax_lab.portfolio.constructor import PortfolioConstructor
from indodax_lab.risk.engine import RiskEngine

logger = logging.getLogger("trading_pipeline")


@dataclass(frozen=True)
class PipelineStepReport:
    """Diagnostic outcome of an execution cycle."""

    mode: ExecutionMode
    evaluated_at: datetime
    intents_evaluated: int
    approved_count: int
    rejected_reasons: tuple[str, ...]
    submitted_orders: tuple[OmsOrder, ...] = field(default_factory=tuple)
    pending_proposals: tuple[PendingProposal, ...] = field(default_factory=tuple)
    kill_switch_triggered: bool = False


class TradingPipeline:
    """Unified trading execution coordinator enforcing fail-closed mode boundaries."""

    def __init__(
        self,
        *,
        mode: ExecutionMode,
        gateway: MarketGateway,
        constructor: PortfolioConstructor,
        risk_engine: RiskEngine,
        oms_store: OmsStore,
        order_router: OrderRouter,
        approval_store: ManualApprovalStore | None = None,
        autonomous_limits: AutonomousLimits | None = None,
        mode_store: DurableModeStore | None = None,
    ) -> None:
        self.mode_store = mode_store
        self.mode = mode_store.get_mode() if mode_store is not None else mode
        self.gateway = gateway
        self.constructor = constructor
        self.risk_engine = risk_engine
        self.oms_store = oms_store
        self.order_router = order_router
        self.approval_store = approval_store or ManualApprovalStore()
        self.autonomous_limits = autonomous_limits or AutonomousLimits()

        # Structural SHADOW isolation: SHADOW mode MUST NOT use real live venue adapter
        if self.mode == ExecutionMode.SHADOW and isinstance(
            self.order_router.venue, IndodaxTradingClient
        ):
            raise RuntimeError(
                "SHADOW_MODE_FORBIDS_LIVE_VENUE: Real exchange adapter forbidden in SHADOW mode"
            )

    def set_mode(self, new_mode: ExecutionMode) -> None:
        """Switch operational execution mode with transition graph enforcement."""
        if not validate_mode_transition(self.mode, new_mode):
            raise InvalidModeTransitionError(
                f"ILLEGAL_MODE_TRANSITION:{self.mode.value}->{new_mode.value}"
            )
        if new_mode == ExecutionMode.SHADOW and isinstance(
            self.order_router.venue, IndodaxTradingClient
        ):
            raise RuntimeError(
                "SHADOW_MODE_FORBIDS_LIVE_VENUE: Real exchange adapter forbidden in SHADOW mode"
            )
        logger.info("TradingPipeline: Transitioning mode from %s to %s", self.mode, new_mode)
        self.mode = new_mode
        if self.mode_store is not None:
            self.mode_store.transition_to(new_mode)

    def step(
        self,
        intents: Sequence[SignalIntent],
        *,
        current_positions: Mapping[str, Position],
        available_cash: Decimal,
        current_equity: Decimal,
        now: datetime,
        mark_prices_override: Mapping[str, Decimal] | None = None,
        ticker_overrides: Mapping[str, TickerSnapshot] | None = None,
    ) -> PipelineStepReport:
        """Execute one complete trading cycle with strict mode isolation."""
        # 1. Check DISABLED or HALTED mode
        if self.mode in {ExecutionMode.DISABLED, ExecutionMode.HALTED}:
            logger.debug(
                "TradingPipeline: Skipped step because execution mode is %s", self.mode.value
            )
            return PipelineStepReport(
                mode=self.mode,
                evaluated_at=now,
                intents_evaluated=len(intents),
                approved_count=0,
                rejected_reasons=(f"MODE_IS_{self.mode.value}",),
            )

        # 2. Structural SHADOW isolation: SHADOW mode MUST NOT use real live venue adapter
        if self.mode == ExecutionMode.SHADOW and isinstance(
            self.order_router.venue, IndodaxTradingClient
        ):
            raise RuntimeError("SHADOW_MODE_FORBIDS_REAL_VENUE_ADAPTER: Must use simulated venue")

        # 3. Pre-write safety gates
        if self.risk_engine.is_kill_switch_active:
            logger.critical("TradingPipeline: Kill switch is active. Blocking step.")
            return PipelineStepReport(
                mode=self.mode,
                evaluated_at=now,
                intents_evaluated=len(intents),
                approved_count=0,
                rejected_reasons=("KILL_SWITCH_ACTIVE",),
                kill_switch_triggered=True,
            )

        unknown_orders = [
            o for o in self.oms_store.load_nonterminal_orders() if o.state == OmsOrderState.UNKNOWN
        ]
        if unknown_orders:
            logger.critical(
                "TradingPipeline: Found %d unresolved UNKNOWN orders in OMS. Tripping kill switch.",
                len(unknown_orders),
            )
            self.risk_engine.trigger_kill_switch("UNRESOLVED_UNKNOWN_ORDERS_IN_OMS")
            return PipelineStepReport(
                mode=self.mode,
                evaluated_at=now,
                intents_evaluated=len(intents),
                approved_count=0,
                rejected_reasons=("UNRESOLVED_UNKNOWN_ORDERS_IN_OMS",),
                kill_switch_triggered=True,
            )

        # 4. Collect mark prices and market health from gateway
        mark_prices: dict[str, Decimal] = dict(mark_prices_override or {})
        market_health = MarketHealthState.HEALTHY

        pairs_to_check = {i.pair.lower() for i in intents} | {p.lower() for p in current_positions}
        for pair in pairs_to_check:
            ticker_override = ticker_overrides.get(pair) if ticker_overrides else None
            try:
                snapshot = self.gateway.get_market_snapshot(
                    pair=pair,
                    as_of_utc=now,
                    ticker_override=ticker_override,
                )
            except Exception as exc:
                logger.warning("Failed fetching snapshot for %s: %s", pair, exc)
                snapshot = None

            if snapshot is not None:
                if pair not in mark_prices and snapshot.last_price > Decimal("0"):
                    mark_prices[pair] = snapshot.last_price
                if snapshot.health.state in UNSAFE_TRADING_STATES:
                    market_health = snapshot.health.state
            elif pair not in mark_prices:
                mark_prices[pair] = Decimal("0")

        # 3. Portfolio constructor translates intents and positions into rebalance intents
        target_exposures = self.constructor.construct_exposures(
            intents, current_positions, mark_prices
        )
        rebalance_intents = self.constructor.generate_rebalance_intents(
            target_exposures, decision_ts=now
        )

        # 4. Assess intents against RiskEngine
        approved_orders: list[OmsOrder] = []
        rejected_reasons: list[str] = []
        submitted_orders: list[OmsOrder] = []
        pending_proposals: list[PendingProposal] = []
        kill_switch_tripped = False

        for reb_intent in rebalance_intents:
            assessment = self.risk_engine.assess_intent(
                reb_intent,
                current_equity=current_equity,
                current_positions=current_positions,
                mark_prices=mark_prices,
                evaluation_time=now,
                available_cash=available_cash,
                market_health=market_health,
            )

            if not assessment.approved:
                rejected_reasons.append(f"{reb_intent.pair}:{assessment.reason_code}")
                continue

            # Create OMS order
            internal_order_id = f"ord_{uuid.uuid4().hex[:12]}"
            client_order_id = f"cl_{uuid.uuid4().hex[:12]}"

            oms_order = self.risk_engine.create_oms_order_from_assessment(
                reb_intent,
                assessment,
                internal_order_id=internal_order_id,
                client_order_id=client_order_id,
                created_at=now,
            )
            approved_orders.append(oms_order)

            # Route by execution mode:
            if self.mode == ExecutionMode.READ_ONLY:
                # In READ_ONLY: do not record in OMS store and do not submit
                logger.info(
                    "TradingPipeline [READ_ONLY]: Simulating approved order %s (%s %s)",
                    oms_order.internal_order_id,
                    oms_order.side,
                    oms_order.desired_qty,
                )
                continue

            if self.mode == ExecutionMode.SHADOW:
                # In SHADOW: save to OMS store, but route through paper/fake
                self.oms_store.create_order(
                    oms_order,
                    event_id=f"evt_init_{oms_order.internal_order_id}",
                )
                submitted = self.order_router.submit_order(oms_order, now=now)
                submitted_orders.append(submitted)
                continue

            if self.mode == ExecutionMode.MANUAL_APPROVAL:
                # In MANUAL_APPROVAL: save to OMS store as NEW, and queue in approval store
                self.oms_store.create_order(
                    oms_order,
                    event_id=f"evt_init_{oms_order.internal_order_id}",
                )
                proposal = self.approval_store.propose(oms_order, at=now)
                pending_proposals.append(proposal)
                continue

            if self.mode == ExecutionMode.AUTONOMOUS_LIMITED:
                # Check autonomous boundaries
                order_notional = oms_order.desired_qty * mark_prices.get(
                    oms_order.pair, Decimal("0")
                )
                if order_notional > self.autonomous_limits.max_single_order_notional:
                    logger.critical(
                        "TradingPipeline: Order %s notional %s exceeds limit %s. Halting.",
                        oms_order.internal_order_id,
                        order_notional,
                        self.autonomous_limits.max_single_order_notional,
                    )
                    self.risk_engine.trigger_kill_switch("AUTONOMOUS_NOTIONAL_LIMIT_BREACH")
                    kill_switch_tripped = True
                    rejected_reasons.append(f"{oms_order.pair}:AUTONOMOUS_LIMIT_EXCEEDED")
                    break

                if oms_order.pair.lower() not in self.autonomous_limits.allowed_pairs:
                    logger.critical(
                        "TradingPipeline: Pair %s not in allowed autonomous pairs %s.",
                        oms_order.pair,
                        self.autonomous_limits.allowed_pairs,
                    )
                    self.risk_engine.trigger_kill_switch("UNAUTHORIZED_AUTONOMOUS_PAIR")
                    kill_switch_tripped = True
                    rejected_reasons.append(f"{oms_order.pair}:UNAUTHORIZED_PAIR")
                    break

                # Persist order and submit
                self.oms_store.create_order(
                    oms_order,
                    event_id=f"evt_init_{oms_order.internal_order_id}",
                )
                submitted = self.order_router.submit_order(oms_order, now=now)
                submitted_orders.append(submitted)

                # If submission ended in UNKNOWN, immediately trip kill switch!
                if submitted.state == OmsOrderState.UNKNOWN:
                    logger.critical(
                        "TradingPipeline: Order %s in UNKNOWN state! Tripping kill switch.",
                        submitted.internal_order_id,
                    )
                    self.risk_engine.trigger_kill_switch("ORDER_SUBMIT_UNKNOWN")
                    kill_switch_tripped = True
                    break

        return PipelineStepReport(
            mode=self.mode,
            evaluated_at=now,
            intents_evaluated=len(intents),
            approved_count=len(approved_orders),
            rejected_reasons=tuple(rejected_reasons),
            submitted_orders=tuple(submitted_orders),
            pending_proposals=tuple(pending_proposals),
            kill_switch_triggered=kill_switch_tripped,
        )

    def execute_approved_proposal(
        self,
        proposal_id: str,
        *,
        now: datetime | None = None,
        at: datetime | None = None,
        market_snapshot: Any | None = None,
        max_slippage_bps: int = 100,
    ) -> OmsOrder:
        """Safely execute a human-approved proposal with pre-flight re-validation."""
        exec_now = now or at or datetime.now(UTC)
        if self.mode != ExecutionMode.MANUAL_APPROVAL:
            raise ValueError(f"CANNOT_EXECUTE_PROPOSAL_IN_MODE:{self.mode.value}")

        # 1. Load proposal
        proposal = self.approval_store.get(proposal_id)
        if proposal is None:
            raise KeyError(f"PROPOSAL_NOT_FOUND:{proposal_id}")
        if proposal.status != ProposalStatus.APPROVED:
            raise ValueError(f"PROPOSAL_NOT_APPROVED:{proposal.status.value}")
        if exec_now > proposal.expires_at:
            raise TimeoutError(f"PROPOSAL_EXPIRED:{proposal_id}")

        order = proposal.order

        # 2. Check pre-flight gates
        if self.risk_engine.is_kill_switch_active:
            raise RuntimeError("KILL_SWITCH_ACTIVE")
        unknown_orders = [
            o for o in self.oms_store.load_nonterminal_orders() if o.state == OmsOrderState.UNKNOWN
        ]
        if unknown_orders:
            self.risk_engine.trigger_kill_switch("UNRESOLVED_UNKNOWN_ORDERS_IN_OMS")
            raise RuntimeError("UNRESOLVED_UNKNOWN_ORDERS_IN_OMS")

        # 3. Re-validate market health & price slippage
        snapshot = market_snapshot or self.gateway.get_market_snapshot(
            pair=order.pair, as_of_utc=exec_now
        )
        if snapshot.health.state in UNSAFE_TRADING_STATES or not snapshot.health.is_clean:
            raise RuntimeError(f"UNSAFE_MARKET_HEALTH:{snapshot.health.state.value}")

        if order.limit_price is not None and snapshot.last_price > Decimal("0"):
            price_diff = abs(snapshot.last_price - order.limit_price)
            slippage_bps = int((price_diff / order.limit_price) * 10000)
            if slippage_bps > max_slippage_bps:
                raise RuntimeError(
                    f"PROPOSAL_PRICE_SLIPPAGE_EXCEEDED:{slippage_bps}bps>{max_slippage_bps}bps"
                )

        # Ensure order exists in OMS store before submit if not already saved
        if self.oms_store.load_order(order.internal_order_id) is None:
            self.oms_store.create_order(order, event_id=f"evt_init_{order.internal_order_id}")

        # 4. Submit exact approved order
        submitted = self.order_router.submit_order(order, now=exec_now)
        if submitted.state == OmsOrderState.UNKNOWN:
            self.risk_engine.trigger_kill_switch("ORDER_SUBMIT_UNKNOWN")
        return submitted
