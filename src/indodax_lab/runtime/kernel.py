"""Shared runtime kernel sequencing candidate, OMS, venue and store (RP-04).

``RuntimeKernel.process`` drives one canonical event through the durable
protocol owned by the PM-02 execution store: prepare, evaluate, commit,
submit (claim/record per outbox row), acknowledge. Restart safety comes from
the store's idempotent envelopes; the kernel never re-drives a decided
envelope and never advances memory state before acknowledgement.

Guarantees (CONTRACTS.md):
- Duplicate same-bytes delivery after acknowledgement is a no-op replay.
- A crash between commit and acknowledgement surfaces as an explicit
  blocked error (the PM-02 ``recover()`` path owns mid-flight resumption);
  the kernel manufactures no progress and duplicates no effect.
- Portfolio/risk gating arrives through the injected ``risk_stage``. The
  default stage denies everything: an unwired kernel emits no orders.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from indodax_lab.execution.oms import OmsOrder, OmsOrderState, OmsStateMachine
from indodax_lab.execution.venue import (
    UncertainVenueSubmissionError,
    VenueRejectError,
)
from indodax_lab.runtime.candidate import (
    CanonicalMarketEvent,
    FeatureState,
    MarketCursor,
    RuntimeState,
    feature_state_digest,
)
from indodax_lab.runtime.exits import ExitState, advance_exit_state

RiskStage = Callable[[tuple[Any, ...], RuntimeState], tuple[Any, ...]]
"""Portfolio/risk admission: approved intents pass, the rest are dropped."""


def deny_all_stage(
    intents: tuple[Any, ...], _state: RuntimeState
) -> tuple[Any, ...]:
    """Default fail-closed risk stage: an unwired kernel emits no orders."""
    return ()


class KernelNotWiredError(Exception):
    """The kernel lacks candidate, store, or venue wiring for processing."""


class KernelBlockedError(Exception):
    """A decided-but-unacknowledged envelope needs store recovery first."""


class RuntimeKernel:
    """One production-shaped event coordinator over simulated adapters."""

    def __init__(
        self,
        *,
        candidate_runtime: Any | None = None,
        store: Any | None = None,
        oms_store: Any | None = None,
        venue: Any | None = None,
        venue_name: str = "unwired",
        risk_stage: RiskStage | None = None,
        feature_window: int = 50,
    ) -> None:
        self._candidate = candidate_runtime
        self._store = store
        self._oms_store = oms_store
        self._venue = venue
        self._venue_name = venue_name
        self._risk_stage = risk_stage or deny_all_stage
        self._feature_window = max(1, feature_window)
        self._bars: list[Any] = []
        self._exits = ExitState()
        self._cursor: MarketCursor | None = None
        self._risk_revision = 0

    @classmethod
    def minimal(cls, *, venue: Any = None, venue_name: str = "unwired") -> RuntimeKernel:
        """Boundary-only kernel for composition vetting (no processing wiring)."""
        return cls(venue=venue, venue_name=venue_name)

    @property
    def venue_name(self) -> str:
        return self._venue_name

    def _cursor_id(self) -> str | None:
        if self._cursor is None:
            return None
        return f"{self._cursor.feed_id}:{self._cursor.last_sequence}"

    # -- main entry ---------------------------------------------------------

    def process(self, event: CanonicalMarketEvent) -> Any:
        """Process one canonical event to a durable step result (RP-04)."""
        if self._candidate is None or self._store is None or self._venue is None:
            raise KernelNotWiredError(
                "KERNEL_NOT_WIRED: candidate_runtime, store and venue are all "
                "required to process events"
            )
        snapshot = self._store.restore()
        envelope = self._store.prepare_event(event, snapshot.revision)
        if envelope.status == "ACKNOWLEDGED":
            # Duplicate same-bytes delivery after acknowledgement: replay,
            # no re-evaluation, no new effect.
            from indodax_lab.execution.state_store import RuntimeStepResult

            return RuntimeStepResult(
                event_id=envelope.event_id,
                envelope_id=envelope.envelope_id,
                namespace=self._store.namespace,
                status="ACKNOWLEDGED",
                cursor=self._cursor_id(),
                revision=envelope.revision,
            )
        if envelope.status == "DECIDED":
            raise KernelBlockedError(
                f"KERNEL_DECIDED_UNFINISHED: envelope '{envelope.envelope_id}' "
                "is decided but unacknowledged; run store.recover() before "
                "reprocessing (no effect was duplicated)"
            )

        state = self._runtime_state(event)
        intents = tuple(self._candidate.evaluate(event, state))
        approved = tuple(self._risk_stage(intents, state))
        orders = [self._intent_to_order(intent, event) for intent in approved]

        next_state = self._next_state(event, state)
        decided = self._store.commit_decision(
            envelope.envelope_id, envelope.revision, next_state, orders, {}
        )
        revision = decided.revision
        for order in orders:
            self._mirror_oms_new(order, event)
            outbox_id = f"outbox_{order.internal_order_id}"
            attempt = self._store.claim_submission(outbox_id, revision)
            revision = attempt.revision
            outcome = self._submit(order)
            recorded = self._store.record_submission(attempt.attempt_id, outcome)
            revision = recorded.revision
            self._mirror_oms_outcome(order, outcome)

        result = self._store.acknowledge_event(envelope.envelope_id, revision)
        self._bars = list(next_state.feature_state.bars) if next_state.feature_state else []
        self._exits = next_state.exit_state or ExitState()
        if result.cursor:
            self._cursor = MarketCursor(
                feed_id=event.feed_id,
                last_event_id=event.event_id,
                last_sequence=event.sequence,
            )
        self._risk_revision += 1
        return result

    # -- state ---------------------------------------------------------------

    def _runtime_state(self, event: CanonicalMarketEvent) -> RuntimeState:
        return RuntimeState(
            runtime_plan_digest=self._candidate.plan_digest,
            candidate_digest=self._candidate.candidate_digest,
            feature_state=FeatureState(
                bars=tuple(self._bars),
                digest=feature_state_digest(self._bars),
            ),
            exit_state=self._exits,
            risk_revision=self._risk_revision,
            market_cursor=self._cursor,
        )

    def _next_state(
        self, event: CanonicalMarketEvent, state: RuntimeState
    ) -> RuntimeState:
        bars = list(state.feature_state.bars) if state.feature_state else []
        bars.append(event.observation)
        bars = bars[-self._feature_window :]
        exits = state.exit_state or ExitState()
        observation = event.observation
        if all(
            hasattr(observation, name)
            for name in ("pair", "high", "low", "close", "close_time")
        ):
            exits = advance_exit_state(exits, observation)
        return RuntimeState(
            runtime_plan_digest=state.runtime_plan_digest,
            candidate_digest=state.candidate_digest,
            portfolio=state.portfolio,
            feature_state=FeatureState(
                bars=tuple(bars), digest=feature_state_digest(bars)
            ),
            exit_state=exits,
            risk_snapshot_digest=state.risk_snapshot_digest,
            risk_revision=state.risk_revision,
            market_cursor=state.market_cursor,
            runtime_policy_digests=dict(state.runtime_policy_digests),
        )

    # -- orders -----------------------------------------------------------------

    @staticmethod
    def _intent_to_order(intent: Any, event: CanonicalMarketEvent) -> OmsOrder:
        """Deterministic NEW order per intent: restarts derive identical IDs."""
        digest = str(intent.intent_id if hasattr(intent, "intent_id") else event.event_id)
        return OmsOrder(
            internal_order_id=f"ord_{digest[:12]}",
            client_order_id=f"cl_{digest[:12]}",
            pair=str(intent.pair if hasattr(intent, "pair") else event.pair),
            side=intent.side,
            desired_qty=intent.desired_qty,
            limit_price=intent.limit_price,
            created_at=event.event_time,
            updated_at=event.event_time,
        )

    def _mirror_oms_new(self, order: OmsOrder, event: CanonicalMarketEvent) -> None:
        if self._oms_store is None:
            return
        self._oms_store.create_order(order, event_id=f"kernel_{event.event_id}")

    def _mirror_oms_outcome(self, order: OmsOrder, outcome: dict[str, Any]) -> None:
        if self._oms_store is None:
            return
        status = str(outcome.get("status", "UNKNOWN")).upper()
        target = {
            "SUBMITTED": OmsOrderState.ACKNOWLEDGED,
            "REJECTED": OmsOrderState.REJECTED,
        }.get(status, OmsOrderState.UNKNOWN)
        current = self._oms_store.load_order(order.internal_order_id)
        if current is None:
            return
        if current.state == OmsOrderState.NEW:
            submitting = OmsStateMachine.transition(
                current,
                OmsOrderState.SUBMITTING,
                at=current.updated_at,
                reason="KERNEL_DISPATCHED",
            )
            self._oms_store.apply_transition(
                current, submitting, event_id=f"kernel_{current.internal_order_id}"
            )
            current = submitting
        transitioned = OmsStateMachine.transition(
            current, target, at=current.updated_at, reason=f"KERNEL_{status}"
        )
        self._oms_store.apply_transition(
            current, transitioned, event_id=f"kernel_{current.internal_order_id}"
        )

    def _submit(self, order: OmsOrder) -> dict[str, Any]:
        """Submit through the venue; every outcome becomes durable evidence."""
        try:
            receipt = self._venue.submit_order(order)
        except VenueRejectError as exc:
            return {"status": "REJECTED", "reason": str(exc)}
        except UncertainVenueSubmissionError as exc:
            return {"status": "UNKNOWN", "reason": str(exc)}
        except ValueError as exc:
            return {"status": "REJECTED", "reason": f"VENUE_INVALID:{exc}"}
        except Exception as exc:  # timeout/crash after dispatch is UNKNOWN
            return {"status": "UNKNOWN", "reason": f"VENUE_ERROR:{exc}"}
        return {
            "status": "SUBMITTED",
            "venue_order_id": receipt.order_id,
            "executed_qty": str(receipt.executed_qty),
        }


__all__ = [
    "KernelBlockedError",
    "KernelNotWiredError",
    "RiskStage",
    "RuntimeKernel",
    "deny_all_stage",
]
