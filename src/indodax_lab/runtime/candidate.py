"""Shared candidate runtime evaluator (RP-02).

One verified evaluator independent of venue, training and ambient clock.
``CandidateRuntime`` consumes a verified ``RuntimePlan`` (historical
bootstrap) or ``VerifiedCandidate`` (forward shadow/production) and
evaluates canonical market events into deterministic ``SignalIntent``
tuples.

Guarantees (CONTRACTS.md / ADR-002):
- Same candidate/event/state gives identical intent bytes (content-derived
  intent IDs; no ambient clock, no dict-order dependence).
- Future rows cannot alter past decisions (causal availability; no bfill).
- Feature/model mismatch rejects before any decision is emitted.
- Missing declared model artifacts BLOCK; the evaluator never degrades to a
  TA-only intent.
- Candidate stop and exit state share identical semantics before
  environment-specific venue effects.

Clock, data and model inference are injected through declared ports; the
evaluator never submits an order and never reads a wall clock.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from datetime import timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.contracts.identity import ArtifactRef, canonical_bytes, manifest_digest
from indodax_lab.contracts.workbench import (
    PipelineManifest,
    VerifiedCandidate,
    VerifiedRuntimePlan,
)
from indodax_lab.models.registry import ModelRegistry, ModelRegistryError
from indodax_lab.runtime.exits import (
    ExitDecision,
    ExitState,
    exit_decisions,
)
from indodax_lab.strategies.base import RegisteredStrategy, create_decision_frame

# ---------------------------------------------------------------------------
# Errors — fail-closed, ``<CODE>: <detail>`` messages
# ---------------------------------------------------------------------------


class CandidateRuntimeError(Exception):
    """Base error for candidate runtime rejections."""

    code: str = "CANDIDATE_RUNTIME_ERROR"

    def __init__(self, detail: str) -> None:
        super().__init__(f"{self.code}: {detail}")


# ---------------------------------------------------------------------------
# Canonical market event (fields fixed in CONTRACTS.md)
# ---------------------------------------------------------------------------


def _ensure_utc(dt: object, field_name: str) -> object:
    if not hasattr(dt, "tzinfo") or dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class CanonicalMarketEvent(BaseModel):
    """Immutable canonical market event with content-derived identity.

    ``available_at`` may not exceed ``event_time`` (UTC availability cannot
    exceed evaluation time). ``sequence`` is the durable local feed position.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str
    feed_id: str
    sequence: int
    pair: str
    event_time: object
    available_at: object
    observation: Any
    quality_ref: str | None = None

    @field_validator("event_time", "available_at")
    @classmethod
    def _utc(cls, value: object, info: Any) -> object:
        return _ensure_utc(value, str(info.field_name))

    @field_validator("sequence")
    @classmethod
    def _positive_sequence(cls, value: int) -> int:
        if value < 1:
            raise ValueError("EVENT_SEQUENCE_MUST_BE_POSITIVE")
        return value


# ---------------------------------------------------------------------------
# Runtime state (fields fixed in CONTRACTS.md)
# ---------------------------------------------------------------------------


class PositionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pair: str
    qty: Decimal


class PortfolioSnapshot(BaseModel):
    """Minimal portfolio snapshot carried by the runtime state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cash: Decimal
    positions: tuple[PositionSnapshot, ...] = ()
    revision: int = 0


class MarketCursor(BaseModel):
    """Durable local feed cursor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feed_id: str
    last_event_id: str
    last_sequence: int


class FeatureState(BaseModel):
    """Bounded causal closed-bar window backing feature evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bars: tuple[Any, ...] = ()
    digest: str = ""


class RuntimeState(BaseModel):
    """Immutable runtime state consumed by ``CandidateRuntime.evaluate``.

    Contains runtime-plan digest, optional candidate digest (required in
    forward shadow/production), portfolio snapshot/revision, feature/exit
    state, risk snapshot/revision, market cursor and runtime policy digests.
    It carries no API credentials and no concrete live client.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime_plan_digest: str
    candidate_digest: str | None = None
    portfolio: PortfolioSnapshot | None = None
    feature_state: FeatureState | None = None
    exit_state: ExitState | None = None
    risk_snapshot_digest: str | None = None
    risk_revision: int = 0
    market_cursor: MarketCursor | None = None
    runtime_policy_digests: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Content-derived identity
# ---------------------------------------------------------------------------


def intent_id(plan_digest: str, event_id: str, output_node: str, ordinal: int) -> str:
    """Deterministic intent ID: runtime-plan digest + event ID + output node + ordinal.

    The candidate digest is deliberately NOT part of intent identity, so
    packaging completed evidence cannot change decision identity.
    """
    payload = {
        "plan_digest": plan_digest,
        "event_id": event_id,
        "output_node": output_node,
        "ordinal": ordinal,
    }
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def feature_state_digest(bars: Sequence[Any]) -> str:
    """Content digest of the causal closed-bar feature window."""
    return hashlib.sha256(canonical_bytes(tuple(bars))).hexdigest()


# C02 feature columns produced by the feature replay extension.
_C02_FEATURE_COLUMNS = ("ema_fast", "ema_slow", "atr_14")


# ---------------------------------------------------------------------------
# Candidate runtime
# ---------------------------------------------------------------------------


class CandidateRuntime:
    """Verified evaluator bound to one runtime plan (and optional candidate).

    Immutable and stateless: ``evaluate`` is a pure function of ``(event,
    state)``. Strategy and model inference are injected through declared
    ports at construction time.
    """

    def __init__(
        self,
        *,
        plan: VerifiedRuntimePlan,
        candidate: VerifiedCandidate | None = None,
        pipeline: PipelineManifest | None = None,
        strategy_resolver: Callable[[ArtifactRef], RegisteredStrategy] | None = None,
        models: ModelRegistry | None = None,
    ) -> None:
        self._plan = plan
        self._candidate = candidate
        self._pipeline = pipeline
        self._models = models

        # Verify candidate/package linkage before any evaluation.
        if candidate is not None:
            if candidate.candidate_digest != manifest_digest(candidate.candidate):
                raise CandidateRuntimeError(
                    "CANDIDATE_DIGEST_MISMATCH: candidate wrapper digest does not match "
                    "candidate manifest bytes"
                )
            ref = candidate.candidate.runtime_plan_ref
            if (
                ref.sha256 != plan.plan_digest
                or ref.id != plan.plan.plan_id
                or ref.version != plan.plan.version
            ):
                raise CandidateRuntimeError(
                    "CANDIDATE_PLAN_LINKAGE_MISMATCH: candidate runtime_plan_ref does not "
                    "bind the verified runtime plan"
                )

        # Resolve registered pipeline nodes once by digest (strategy + models).
        self._strategy = self._resolve_strategy(pipeline, strategy_resolver)
        self._model_refs = self._verify_models(pipeline, models)

    # -- loading ------------------------------------------------------------

    @classmethod
    def load_plan(
        cls,
        plan: VerifiedRuntimePlan,
        **dependencies: Any,
    ) -> CandidateRuntime:
        """Historical bootstrap entry: evaluate from a verified RuntimePlan."""
        return cls(plan=plan, candidate=None, **dependencies)

    @classmethod
    def load(
        cls,
        candidate: VerifiedCandidate,
        *,
        plan: VerifiedRuntimePlan | None = None,
        plan_resolver: Callable[[ArtifactRef], VerifiedRuntimePlan] | None = None,
        **dependencies: Any,
    ) -> CandidateRuntime:
        """Forward/production entry: verify the candidate wrapper, then delegate.

        The candidate's ``runtime_plan_ref`` must resolve to the same verified
        runtime plan; linkage is verified before the evaluator is constructed.
        """
        if candidate.candidate_digest != manifest_digest(candidate.candidate):
            raise CandidateRuntimeError(
                "CANDIDATE_DIGEST_MISMATCH: candidate wrapper digest does not match "
                "candidate manifest bytes"
            )
        ref = candidate.candidate.runtime_plan_ref
        resolved = plan
        if resolved is None and plan_resolver is not None:
            resolved = plan_resolver(ref)
        if resolved is None:
            raise CandidateRuntimeError(
                "CANDIDATE_PLAN_UNRESOLVED: candidate runtime_plan_ref cannot be resolved "
                "to a verified runtime plan"
            )
        if (
            resolved.plan_digest != ref.sha256
            or resolved.plan.plan_id != ref.id
            or resolved.plan.version != ref.version
        ):
            raise CandidateRuntimeError(
                "CANDIDATE_PLAN_LINKAGE_MISMATCH: resolved plan does not match the "
                "candidate runtime_plan_ref"
            )
        return cls(plan=resolved, candidate=candidate, **dependencies)

    # -- component resolution -------------------------------------------------

    def _resolve_strategy(
        self,
        pipeline: PipelineManifest | None,
        strategy_resolver: Callable[[ArtifactRef], RegisteredStrategy] | None,
    ) -> RegisteredStrategy | None:
        if pipeline is None:
            return None
        for node in pipeline.nodes:
            if node.kind != "ta":
                continue
            ref = self._component_ref(pipeline, node.node_id, "strategy_manifest")
            if ref is None:
                raise CandidateRuntimeError(
                    f"PIPELINE_STRATEGY_REF_MISSING: no strategy_manifest reference for ta "
                    f"node {node.node_id!r}"
                )
            if strategy_resolver is None:
                raise CandidateRuntimeError(
                    "PIPELINE_STRATEGY_UNRESOLVED: no strategy resolver was provided"
                )
            try:
                return strategy_resolver(ref)
            except Exception as exc:
                raise CandidateRuntimeError(
                    f"PIPELINE_STRATEGY_UNRESOLVED: strategy {ref.id}:{ref.version} does not "
                    f"resolve ({exc})"
                ) from exc
        return None

    def _verify_models(
        self,
        pipeline: PipelineManifest | None,
        models: ModelRegistry | None,
    ) -> tuple[ArtifactRef, ...]:
        """Verify every declared model artifact; missing artifacts BLOCK.

        A declared M02/D04 (or any model) artifact that does not resolve in
        the model registry blocks the evaluator at load time — the runtime
        never silently degrades to a TA-only intent.
        """
        if pipeline is None:
            return ()
        refs = tuple(
            self._component_ref(pipeline, node.node_id, "model")
            for node in pipeline.nodes
            if node.kind in ("ml", "dl")
        )
        refs = tuple(ref for ref in refs if ref is not None)
        for ref in refs:
            if models is None:
                raise CandidateRuntimeError(
                    f"RUNTIME_MODEL_ARTIFACT_MISSING: no model registry was provided to "
                    f"resolve declared model {ref.id}:{ref.version}"
                )
            try:
                models.load_verified(ref)
            except (ModelRegistryError, KeyError, ValueError) as exc:
                raise CandidateRuntimeError(
                    f"RUNTIME_MODEL_ARTIFACT_MISSING: declared model artifact "
                    f"{ref.id}:{ref.version} is unavailable ({exc})"
                ) from exc
        return refs

    @staticmethod
    def _component_ref(
        pipeline: PipelineManifest, node_id: str, kind: str
    ) -> ArtifactRef | None:
        for ref in pipeline.component_refs:
            if ref.id == node_id and ref.kind == kind:
                return ref
        return None

    # -- evaluation -------------------------------------------------------------

    def evaluate(
        self, event: CanonicalMarketEvent, state: RuntimeState
    ) -> tuple[SignalIntent, ...]:
        """Evaluate one canonical event into a deterministic intent tuple.

        Verifies candidate and feature identity before evaluation; rejects
        with a specific reason code on any mismatch. Never submits an order.
        """
        self._verify_state(state)
        self._verify_availability(event)

        observation = event.observation
        if not hasattr(observation, "close_time") or not hasattr(observation, "pair"):
            raise CandidateRuntimeError(
                "RUNTIME_OBSERVATION_INVALID: event observation is not a closed-bar market "
                "observation"
            )

        # Causal availability: state bars and the event observation must not
        # exceed the event time (no future rows, no bfill).
        self._verify_causal_window(event, state)

        # Build the causal feature frame and verify feature identity.
        feature_frame = self._build_feature_frame(event, state)
        self._verify_feature_identity(feature_frame)

        intents: list[SignalIntent] = []

        # Entry decisions from the registered strategy (TA path).
        if self._strategy is not None and feature_frame is not None:
            frame = create_decision_frame(
                features=feature_frame,
                as_of=event.event_time,
            )
            for ordinal, raw in enumerate(self._strategy.decide(frame)):
                intents.append(self._assemble_entry_intent(event, raw, ordinal))

        # Exit decisions from the persistible exit state (stop-first).
        exit_state = state.exit_state or ExitState()
        for decision in exit_decisions(exit_state, observation):
            intents.append(self._assemble_exit_intent(event, decision, len(intents)))

        return tuple(intents)

    # -- verification helpers ---------------------------------------------------

    def _verify_state(self, state: RuntimeState) -> None:
        if state.runtime_plan_digest != self._plan.plan_digest:
            raise CandidateRuntimeError(
                "RUNTIME_PLAN_DIGEST_MISMATCH: state does not bind the verified runtime plan"
            )
        expected = self._candidate.candidate_digest if self._candidate is not None else None
        if state.candidate_digest != expected:
            raise CandidateRuntimeError(
                "RUNTIME_CANDIDATE_DIGEST_MISMATCH: state candidate digest does not match "
                "the candidate binding"
            )

    @staticmethod
    def _verify_availability(event: CanonicalMarketEvent) -> None:
        if event.available_at > event.event_time:
            raise CandidateRuntimeError(
                "RUNTIME_AVAILABILITY_VIOLATION: available_at exceeds event_time"
            )

    @staticmethod
    def _verify_causal_window(event: CanonicalMarketEvent, state: RuntimeState) -> None:
        observation = event.observation
        if observation.close_time > event.event_time:
            raise CandidateRuntimeError(
                "RUNTIME_FUTURE_EVIDENCE: event observation closes after event_time"
            )
        feature_state = state.feature_state
        if feature_state is not None:
            for bar in feature_state.bars:
                if bar.close_time > observation.close_time:
                    raise CandidateRuntimeError(
                        "RUNTIME_FUTURE_EVIDENCE: feature state contains a bar closing "
                        "after the event observation"
                    )

    @staticmethod
    def _build_feature_frame(event: CanonicalMarketEvent, state: RuntimeState) -> Any:
        from indodax_lab.backtest.feature_replay import build_c02_feature_rows

        window = state.feature_state
        bars = list(window.bars) if window is not None else []
        bars.append(event.observation)
        return build_c02_feature_rows(bars)

    def _verify_feature_identity(self, feature_frame: Any) -> None:
        computed = tuple(
            column for column in feature_frame.columns if column in _C02_FEATURE_COLUMNS
        )
        expected = tuple(self._plan.plan.ordered_feature_names)
        if computed != expected:
            raise CandidateRuntimeError(
                f"RUNTIME_FEATURE_SCHEMA_MISMATCH: computed feature schema {computed} does "
                f"not match plan ordered feature schema {expected}"
            )

    # -- intent assembly ---------------------------------------------------------

    def _assemble_entry_intent(
        self, event: CanonicalMarketEvent, raw: SignalIntent, ordinal: int
    ) -> SignalIntent:
        output_node = f"sizing:{self._plan.plan.sizing_policy_ref.id}"
        return SignalIntent(
            intent_id=intent_id(self._plan.plan_digest, event.event_id, output_node, ordinal),
            decision_ts=event.event_time,
            pair=raw.pair,
            side=raw.side,
            desired_qty=raw.desired_qty,
            limit_price=raw.limit_price,
            stop_loss=raw.stop_loss,
            take_profit=raw.take_profit,
            role_preference=raw.role_preference,
            strategy_id=raw.strategy_id,
            time_in_force=raw.time_in_force,
        )

    def _assemble_exit_intent(
        self, event: CanonicalMarketEvent, decision: ExitDecision, ordinal: int
    ) -> SignalIntent:
        output_node = f"exits:{self._plan.plan.exit_policy_ref.id}"
        return SignalIntent(
            intent_id=intent_id(self._plan.plan_digest, event.event_id, output_node, ordinal),
            decision_ts=event.event_time,
            pair=decision.pair,
            side=OrderSide.SELL,
            desired_qty=decision.qty,
            limit_price=decision.price,
            strategy_id=decision.strategy_id,
        )

    # -- properties -----------------------------------------------------------------

    @property
    def plan_digest(self) -> str:
        return self._plan.plan_digest

    @property
    def candidate_digest(self) -> str | None:
        return self._candidate.candidate_digest if self._candidate is not None else None


__all__ = [
    "CandidateRuntime",
    "CandidateRuntimeError",
    "CanonicalMarketEvent",
    "FeatureState",
    "MarketCursor",
    "PortfolioSnapshot",
    "PositionSnapshot",
    "RuntimeState",
    "feature_state_digest",
    "intent_id",
]
