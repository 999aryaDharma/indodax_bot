"""Forward paper trading and shadow portfolio management (SHADOW-01, SHADOW-02)."""

from indodax_lab.paper.contracts import (
    DuplicateDecisionError,
    ForwardDecision,
    ForwardDecisionRecord,
    ForwardDecisionStatus,
    ManualIntentRecord,
    ModelMismatchError,
    PaperDecisionStore,
    RejectedDecision,
    StaleDataError,
)
from indodax_lab.paper.portfolio import (
    CheckpointIntegrityError,
    InsufficientCashError,
    IntentProcessingResult,
    MaxPositionsExceededError,
    PaperOrderIntent,
    PaperPosition,
    SharedCapitalLedger,
    SharedLedgerCheckpoint,
)
from indodax_lab.paper.promotion import (
    ChallengerEvidence,
    ChampionRegistry,
    InsufficientForwardDurationError,
    InsufficientForwardTradesError,
    InsufficientQualityPromotionError,
    MissingPromotionApprovalError,
    NoPromotedChampionError,
    PolicyBreachPromotionError,
    PromotionApproval,
    PromotionDecision,
    SelfApprovedPromotionError,
    StalePromotionEvidenceError,
    UnsealedCandidatePromotionError,
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
    "RejectedDecision",
    "StaleDataError",
    # SHADOW-02
    "CheckpointIntegrityError",
    "InsufficientCashError",
    "IntentProcessingResult",
    "MaxPositionsExceededError",
    "PaperOrderIntent",
    "PaperPosition",
    "SharedCapitalLedger",
    "SharedLedgerCheckpoint",
    # SHADOW-03
    "ChallengerEvidence",
    "ChampionRegistry",
    "InsufficientForwardDurationError",
    "InsufficientForwardTradesError",
    "InsufficientQualityPromotionError",
    "MissingPromotionApprovalError",
    "NoPromotedChampionError",
    "PolicyBreachPromotionError",
    "PromotionApproval",
    "PromotionDecision",
    "SelfApprovedPromotionError",
    "StalePromotionEvidenceError",
    "UnsealedCandidatePromotionError",
]
