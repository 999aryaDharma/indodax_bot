"""Forward paper trading and shadow portfolio management (SHADOW-01, SHADOW-02)."""

from indodax_lab.paper.contracts import (
    DuplicateDecisionError,
    ForwardDecision,
    ForwardDecisionRecord,
    ForwardDecisionStatus,
    ManualIntentRecord,
    ModelMismatchError,
    PaperDecisionStore,
    StaleDataError,
)
from indodax_lab.paper.portfolio import (
    InsufficientCashError,
    IntentProcessingResult,
    MaxPositionsExceededError,
    PaperOrderIntent,
    PaperPosition,
    SharedCapitalLedger,
    SharedLedgerCheckpoint,
)

__all__ = [
    # SHADOW-01
    "DuplicateDecisionError",
    "ForwardDecision",
    "ForwardDecisionRecord",
    "ForwardDecisionStatus",
    "ManualIntentRecord",
    "ModelMismatchError",
    "PaperDecisionStore",
    "StaleDataError",
    # SHADOW-02
    "InsufficientCashError",
    "IntentProcessingResult",
    "MaxPositionsExceededError",
    "PaperOrderIntent",
    "PaperPosition",
    "SharedCapitalLedger",
    "SharedLedgerCheckpoint",
]
