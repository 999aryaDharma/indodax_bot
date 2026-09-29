"""Shared candidate runtime: verified plan/candidate evaluation (RP-02)."""

from __future__ import annotations

from indodax_lab.runtime.candidate import (
    CandidateRuntime,
    CandidateRuntimeError,
    CanonicalMarketEvent,
    FeatureState,
    MarketCursor,
    PortfolioSnapshot,
    PositionSnapshot,
    RuntimeState,
    feature_state_digest,
    intent_id,
)
from indodax_lab.runtime.composition import ResearchBoundaryError, build_research_runtime
from indodax_lab.runtime.exits import (
    ExitDecision,
    ExitState,
    PositionExitState,
    advance_exit_state,
    exit_decisions,
    open_position,
)
from indodax_lab.runtime.kernel import (
    KernelBlockedError,
    KernelNotWiredError,
    RuntimeKernel,
    deny_all_stage,
)

__all__ = [
    "CandidateRuntime",
    "CandidateRuntimeError",
    "CanonicalMarketEvent",
    "ExitDecision",
    "ExitState",
    "FeatureState",
    "KernelBlockedError",
    "KernelNotWiredError",
    "MarketCursor",
    "PortfolioSnapshot",
    "PositionExitState",
    "PositionSnapshot",
    "ResearchBoundaryError",
    "RuntimeKernel",
    "RuntimeState",
    "advance_exit_state",
    "build_research_runtime",
    "deny_all_stage",
    "exit_decisions",
    "feature_state_digest",
    "intent_id",
    "open_position",
]
