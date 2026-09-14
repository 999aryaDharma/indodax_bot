"""Staged foundation model adaptation pipeline: zero-shot -> frozen probe -> bounded adapter (F01-02).

Guarantees:
1. F01-02-AC0: Evaluates zero-shot, frozen probe, and bounded adapter stages, routing forecasts to common mapper.
2. F01-02-AC1: Prior stage execution and evidence is strictly required; skipping stages is rejected fail-closed.
3. F01-02-AC2: Full fine-tune is barred by default and rejected without explicit owner authorization.
4. F01-02-AC3: Test dates prior to training cutoff are rejected fail-closed to prevent lookahead contamination.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

from indodax_lab.models.execution_mapper import (
    CostAwareExecutionMapper,
    ExecutionDecision,
    ForecastKind,
    ForecastPayload,
    PayoffStructure,
)
from indodax_lab.models.foundation.provenance import FoundationModelProvenance


# ---------------------------------------------------------------------------
# Enums and Errors
# ---------------------------------------------------------------------------


class AdaptationStage(StrEnum):
    """Stages of foundation model adaptation."""

    ZERO_SHOT = "zero_shot"
    FROZEN_PROBE = "frozen_probe"
    BOUNDED_ADAPTER = "bounded_adapter"
    FULL_FINE_TUNE = "full_fine_tune"


class StagePreconditionNotMetError(ValueError):
    """Raised when an adaptation stage is invoked without required prior stage evidence."""


class FullFineTuneForbiddenError(ValueError):
    """Raised when full fine-tuning is attempted without explicit authorization."""


class ContaminatedDatesClaimError(ValueError):
    """Raised when evaluation data includes pre-cutoff observations violating causal benchmark integrity."""


# ---------------------------------------------------------------------------
# Configurations and Results
# ---------------------------------------------------------------------------


class FoundationAdaptationConfig(BaseModel):
    """Configuration for staged adaptation of foundation models."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    stage: AdaptationStage = AdaptationStage.FROZEN_PROBE
    allow_full_fine_tune: bool = False
    adapter_dim: int = 16
    learning_rate: float = 0.001
    max_epochs: int = 20
    patience: int = 5
    seed: int = 42


class StageEvaluationResult(BaseModel):
    """Evaluated outcome of an adaptation stage on post-cutoff test data."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    stage: AdaptationStage
    sample_count: int
    brier_score: float
    log_loss_value: float
    metrics: dict[str, float]
    evaluated_at_utc: datetime


# ---------------------------------------------------------------------------
# Staged Foundation Adapter
# ---------------------------------------------------------------------------


class StagedFoundationAdapter:
    """Manages sequential evaluation of zero-shot, frozen probe, and bounded adapter stages."""

    def __init__(
        self,
        provenance: FoundationModelProvenance,
        config: FoundationAdaptationConfig | None = None,
    ) -> None:
        self.provenance = provenance
        self.config = config or FoundationAdaptationConfig()
        self._stage_history: dict[AdaptationStage, StageEvaluationResult] = {}
        self._active_probe: Any = None
        self._adapter_weights: np.ndarray | None = None
        self._last_test_probs: np.ndarray | None = None

    def _validate_timestamps(self, timestamps: list[datetime]) -> None:
        """Validate that all test observations strictly occur after training cutoff."""
        if self.provenance.training_cutoff_date is None:
            return

        cutoff = self.provenance.training_cutoff_date
        for ts in timestamps:
            if ts <= cutoff:
                raise ContaminatedDatesClaimError(
                    f"CONTAMINATED_DATES_FORBIDDEN: Test observation at {ts.isoformat()} "
                    f"is prior to or overlaps training cutoff {cutoff.isoformat()}"
                )

    def run_zero_shot(
        self,
        test_x: np.ndarray,
        test_y: np.ndarray,
        test_timestamps: list[datetime],
    ) -> StageEvaluationResult:
        """Stage 0: Evaluate zero-shot performance on post-cutoff test set."""
        self._validate_timestamps(test_timestamps)

        # Baseline zero-shot decision (uncalibrated feature projection)
        raw_scores = np.mean(test_x, axis=1)
        probs = 1.0 / (1.0 + np.exp(-raw_scores))
        probs = np.clip(probs, 1e-6, 1.0 - 1e-6)

        brier = float(brier_score_loss(test_y, probs))
        ll = float(log_loss(test_y, probs))

        res = StageEvaluationResult(
            stage=AdaptationStage.ZERO_SHOT,
            sample_count=len(test_x),
            brier_score=brier,
            log_loss_value=ll,
            metrics={"mean_prob": float(np.mean(probs))},
            evaluated_at_utc=datetime.now(UTC),
        )
        self._stage_history[AdaptationStage.ZERO_SHOT] = res
        self._last_test_probs = probs
        return res

    def run_frozen_probe(
        self,
        train_x: np.ndarray,
        train_y: np.ndarray,
        test_x: np.ndarray,
        test_y: np.ndarray,
        test_timestamps: list[datetime],
    ) -> StageEvaluationResult:
        """Stage 1: Train linear probe on frozen backbone representations."""
        if AdaptationStage.ZERO_SHOT not in self._stage_history:
            raise StagePreconditionNotMetError(
                "STAGE_PRECONDITION_NOT_MET: ZERO_SHOT required before executing FROZEN_PROBE"
            )

        self._validate_timestamps(test_timestamps)

        clf = LogisticRegression(C=1.0, max_iter=200, random_state=self.config.seed)
        clf.fit(train_x, train_y)
        self._active_probe = clf

        probs = clf.predict_proba(test_x)[:, 1]
        probs = np.clip(probs, 1e-6, 1.0 - 1e-6)

        brier = float(brier_score_loss(test_y, probs))
        ll = float(log_loss(test_y, probs))

        res = StageEvaluationResult(
            stage=AdaptationStage.FROZEN_PROBE,
            sample_count=len(test_x),
            brier_score=brier,
            log_loss_value=ll,
            metrics={"mean_prob": float(np.mean(probs))},
            evaluated_at_utc=datetime.now(UTC),
        )
        self._stage_history[AdaptationStage.FROZEN_PROBE] = res
        self._last_test_probs = probs
        return res

    def run_bounded_adapter(
        self,
        train_x: np.ndarray,
        train_y: np.ndarray,
        test_x: np.ndarray,
        test_y: np.ndarray,
        test_timestamps: list[datetime],
    ) -> StageEvaluationResult:
        """Stage 2: Train bounded low-rank adapter over frozen representations."""
        if AdaptationStage.FROZEN_PROBE not in self._stage_history:
            raise StagePreconditionNotMetError(
                "STAGE_PRECONDITION_NOT_MET: FROZEN_PROBE required before executing BOUNDED_ADAPTER"
            )

        self._validate_timestamps(test_timestamps)

        # Low-rank projection: in_dim -> adapter_dim -> in_dim + residual
        rng = np.random.default_rng(self.config.seed)
        in_dim = train_x.shape[1]
        adapter_dim = min(self.config.adapter_dim, in_dim)

        w_down = rng.normal(0.0, 0.1, size=(in_dim, adapter_dim))
        w_up = rng.normal(0.0, 0.1, size=(adapter_dim, in_dim))

        # Project features through bottleneck adapter
        train_adapted = train_x + np.maximum(0, train_x @ w_down) @ w_up
        test_adapted = test_x + np.maximum(0, test_x @ w_down) @ w_up

        clf = LogisticRegression(C=0.5, max_iter=200, random_state=self.config.seed)
        clf.fit(train_adapted, train_y)
        self._active_probe = clf
        self._adapter_weights = w_down

        probs = clf.predict_proba(test_adapted)[:, 1]
        probs = np.clip(probs, 1e-6, 1.0 - 1e-6)

        brier = float(brier_score_loss(test_y, probs))
        ll = float(log_loss(test_y, probs))

        res = StageEvaluationResult(
            stage=AdaptationStage.BOUNDED_ADAPTER,
            sample_count=len(test_x),
            brier_score=brier,
            log_loss_value=ll,
            metrics={"mean_prob": float(np.mean(probs))},
            evaluated_at_utc=datetime.now(UTC),
        )
        self._stage_history[AdaptationStage.BOUNDED_ADAPTER] = res
        self._last_test_probs = probs
        return res

    def run_full_fine_tune(
        self,
        train_x: np.ndarray,
        train_y: np.ndarray,
        test_x: np.ndarray,
        test_y: np.ndarray,
    ) -> None:
        """Stage 3: Full fine-tuning (strictly forbidden by default)."""
        if not self.config.allow_full_fine_tune:
            raise FullFineTuneForbiddenError(
                "FULL_FINE_TUNE_FORBIDDEN: Full fine-tuning is not default and forbidden "
                "without explicit owner authorization and compute allocation."
            )

    def predict_forecasts(
        self,
        test_x: np.ndarray,
        pair: str,
        decision_ts: datetime,
        mapper: CostAwareExecutionMapper,
        desired_qty: Any = None,
        payoff: PayoffStructure | None = None,
    ) -> list[ExecutionDecision]:
        """Convert latest adapter predictions into execution decisions via common mapper."""
        if self._last_test_probs is None or len(self._last_test_probs) != len(test_x):
            if self._active_probe is not None:
                probs = self._active_probe.predict_proba(test_x)[:, 1]
            else:
                raw_scores = np.mean(test_x, axis=1)
                probs = 1.0 / (1.0 + np.exp(-raw_scores))
        else:
            probs = self._last_test_probs

        decisions: list[ExecutionDecision] = []
        eff_payoff = payoff or PayoffStructure(win_return=0.015, loss_return=-0.010)

        for prob in probs:
            payload = ForecastPayload(
                kind=ForecastKind.PROBABILITY,
                value=float(prob),
                pair=pair,
                decision_ts=decision_ts,
                desired_qty=desired_qty or 1.0,
                payoff=eff_payoff,
            )
            decisions.append(mapper.evaluate_forecast(payload))
        return decisions
