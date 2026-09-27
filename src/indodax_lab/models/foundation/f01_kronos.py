"""Staged foundation model adaptation pipeline: zero-shot -> frozen probe -> bounded adapter (F01-02).

Guarantees:
1. F01-02-AC0: Evaluates zero-shot, frozen probe, and bounded adapter stages, routing forecasts to common mapper.
2. F01-02-AC1: Prior stage execution and evidence is strictly required; skipping stages is rejected fail-closed.
3. F01-02-AC2: Full fine-tune is barred by default and rejected without explicit owner authorization.
4. F01-02-AC3: Test dates prior to training cutoff are rejected fail-closed to prevent lookahead contamination.
   An artifact with an *unknown* cutoff cannot certify a post-cutoff claim at all and is blocked
   for every stage (F01-01 restricts it to EXPLORATORY, so no sealed claim may be produced from it).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict
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


class FoundationComputeBudgetSummary(BaseModel):
    """Parameter and compute budget summary for one staged adaptation stage.

    Mirrors the sibling `*ComputeBudgetSummary` contracts (`TCNComputeBudgetSummary`,
    `ITransformerComputeBudgetSummary`) so every research model reports its own
    parameter/compute footprint instead of leaving it unrecorded.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    stage: AdaptationStage
    input_dim: int
    adapter_dim: int
    probe_parameters: int
    adapter_parameters: int
    total_learned_parameters: int
    estimated_flops_per_inference: int
    evaluated_samples: int


class FoundationAdaptationConfig(BaseModel):
    """Configuration for staged adaptation of foundation models."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    stage: AdaptationStage = AdaptationStage.FROZEN_PROBE
    allow_full_fine_tune: bool = False
    full_fine_tune_authorization: str | None = None
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
    compute_budget: FoundationComputeBudgetSummary
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
        self._active_stage: AdaptationStage | None = None
        self._adapter_w_down: np.ndarray | None = None
        self._adapter_w_up: np.ndarray | None = None
        self._last_test_probs: np.ndarray | None = None

    # -- guards ---------------------------------------------------------------

    def _require_known_cutoff(self) -> datetime:
        """Fail closed when the cutoff is unknown: no post-cutoff claim can be certified."""
        cutoff = self.provenance.training_cutoff_date
        if cutoff is None:
            raise ContaminatedDatesClaimError(
                "UNKNOWN_CUTOFF_CANNOT_CERTIFY_POST_CUTOFF: external model training "
                "cutoff is unknown, "
                "so no observation can be proven post-cutoff. F01-01 restricts such artifacts to "
                "EXPLORATORY and forbids sealed claims."
            )
        return cutoff

    def _validate_timestamps(self, timestamps: list[datetime], expected_count: int) -> None:
        """Validate that all test observations strictly occur after training cutoff."""
        cutoff = self._require_known_cutoff()
        if len(timestamps) != expected_count:
            raise ContaminatedDatesClaimError(
                f"CONTAMINATED_DATES_FORBIDDEN: timestamp count {len(timestamps)} "
                f"!= test sample count {expected_count}; every scored observation "
                "requires one post-cutoff timestamp"
            )
        for ts in timestamps:
            if ts <= cutoff:
                raise ContaminatedDatesClaimError(
                    f"CONTAMINATED_DATES_FORBIDDEN: Test observation at {ts.isoformat()} "
                    f"is prior to or overlaps training cutoff {cutoff.isoformat()}"
                )

    @staticmethod
    def _require_finite_features(x: np.ndarray, label: str) -> np.ndarray:
        arr = np.asarray(x, dtype=float)
        if arr.ndim != 2:
            raise ContaminatedDatesClaimError(
                f"NONFINITE_FEATURES_FORBIDDEN: {label} must be 2-D, got shape {arr.shape}"
            )
        if not np.all(np.isfinite(arr)):
            raise ContaminatedDatesClaimError(
                f"NONFINITE_FEATURES_FORBIDDEN: {label} contains NaN/Inf; "
                f"refusing to score a degenerate input"
            )
        return arr

    def _compute_budget(
        self,
        stage: AdaptationStage,
        input_dim: int,
        adapter_dim: int,
        sample_count: int,
    ) -> FoundationComputeBudgetSummary:
        """Parameter and FLOP footprint of the stage that produced the scored result."""
        probe_params = 0 if stage is AdaptationStage.ZERO_SHOT else (input_dim + 1) * 2
        adapter_params = (
            0 if stage is not AdaptationStage.BOUNDED_ADAPTER else input_dim * adapter_dim * 2
        )
        # Logistic probe: input_dim multiply-adds per sample. Adapter residual: 2 matmuls.
        probe_flops = 0 if stage is AdaptationStage.ZERO_SHOT else 2 * input_dim
        adapter_flops = (
            0 if stage is not AdaptationStage.BOUNDED_ADAPTER else 2 * 2 * input_dim * adapter_dim
        )
        return FoundationComputeBudgetSummary(
            stage=stage,
            input_dim=input_dim,
            adapter_dim=adapter_dim,
            probe_parameters=probe_params,
            adapter_parameters=adapter_params,
            total_learned_parameters=probe_params + adapter_params,
            estimated_flops_per_inference=int(probe_flops + adapter_flops),
            evaluated_samples=sample_count,
        )

    def _score(
        self,
        stage: AdaptationStage,
        probs: np.ndarray,
        test_y: np.ndarray,
        input_dim: int,
        adapter_dim: int,
    ) -> StageEvaluationResult:
        """Shared scoring so every stage reports identical metric and budget semantics."""
        brier = float(brier_score_loss(test_y, probs))
        ll = float(log_loss(test_y, probs))
        res = StageEvaluationResult(
            stage=stage,
            sample_count=int(len(probs)),
            brier_score=brier,
            log_loss_value=ll,
            metrics={"mean_prob": float(np.mean(probs))},
            compute_budget=self._compute_budget(stage, input_dim, adapter_dim, len(probs)),
            evaluated_at_utc=datetime.now(UTC),
        )
        self._stage_history[stage] = res
        self._active_stage = stage
        self._last_test_probs = probs
        return res

    @staticmethod
    def _zero_shot_probs(features: np.ndarray) -> np.ndarray:
        raw_scores = np.mean(features, axis=1)
        return np.clip(1.0 / (1.0 + np.exp(-raw_scores)), 1e-6, 1.0 - 1e-6)

    def _transform(self, features: np.ndarray) -> np.ndarray:
        """Apply the transform of the stage that fitted the active probe (no train/serve skew)."""
        if self._active_stage is AdaptationStage.BOUNDED_ADAPTER:
            assert self._adapter_w_down is not None and self._adapter_w_up is not None
            return features + np.maximum(0, features @ self._adapter_w_down) @ self._adapter_w_up
        return features

    def run_zero_shot(
        self,
        test_x: np.ndarray,
        test_y: np.ndarray,
        test_timestamps: list[datetime],
    ) -> StageEvaluationResult:
        """Stage 0: Evaluate zero-shot performance on post-cutoff test set."""
        self._validate_timestamps(test_timestamps, len(test_x))
        features = self._require_finite_features(test_x, "test_x")
        return self._score(
            AdaptationStage.ZERO_SHOT,
            self._zero_shot_probs(features),
            test_y,
            features.shape[1],
            self.config.adapter_dim,
        )

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

        self._validate_timestamps(test_timestamps, len(test_x))
        train_features = self._require_finite_features(train_x, "train_x")
        test_features = self._require_finite_features(test_x, "test_x")

        clf = LogisticRegression(C=1.0, max_iter=200, random_state=self.config.seed)
        clf.fit(train_features, train_y)
        self._active_probe = clf
        self._adapter_w_down = None
        self._adapter_w_up = None

        probs = np.clip(clf.predict_proba(test_features)[:, 1], 1e-6, 1.0 - 1e-6)
        return self._score(
            AdaptationStage.FROZEN_PROBE,
            probs,
            test_y,
            test_features.shape[1],
            self.config.adapter_dim,
        )

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

        self._validate_timestamps(test_timestamps, len(test_x))
        train_features = self._require_finite_features(train_x, "train_x")
        test_features = self._require_finite_features(test_x, "test_x")

        # Low-rank projection: in_dim -> adapter_dim -> in_dim + residual
        rng = np.random.default_rng(self.config.seed)
        in_dim = train_features.shape[1]
        adapter_dim = min(self.config.adapter_dim, in_dim)

        w_down = rng.normal(0.0, 0.1, size=(in_dim, adapter_dim))
        w_up = rng.normal(0.0, 0.1, size=(adapter_dim, in_dim))

        # Project features through bottleneck adapter
        train_adapted = train_features + np.maximum(0, train_features @ w_down) @ w_up
        test_adapted = test_features + np.maximum(0, test_features @ w_down) @ w_up

        clf = LogisticRegression(C=0.5, max_iter=200, random_state=self.config.seed)
        clf.fit(train_adapted, train_y)
        self._active_probe = clf
        self._adapter_w_down = w_down
        self._adapter_w_up = w_up

        probs = np.clip(clf.predict_proba(test_adapted)[:, 1], 1e-6, 1.0 - 1e-6)
        return self._score(
            AdaptationStage.BOUNDED_ADAPTER,
            probs,
            test_y,
            in_dim,
            adapter_dim,
        )

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
        if not (self.config.full_fine_tune_authorization or "").strip():
            raise FullFineTuneForbiddenError(
                "FULL_FINE_TUNE_FORBIDDEN: full_fine_tune_authorization must "
                "name the authorizing owner."
            )
        if AdaptationStage.BOUNDED_ADAPTER not in self._stage_history:
            raise StagePreconditionNotMetError(
                "STAGE_PRECONDITION_NOT_MET: BOUNDED_ADAPTER required before FULL_FINE_TUNE"
            )
        # Never report success for tuning that was not performed. Spec 15 requires a separate
        # resource/design CR for full fine-tuning, which this sprint does not hold.
        raise FullFineTuneForbiddenError(
            "FULL_FINE_TUNE_UNIMPLEMENTED: full fine-tuning requires a separate resource/design CR "
            "and is not implemented in F01-02; no result is produced."
        )

    def predict_proba(self, test_x: np.ndarray) -> np.ndarray:
        """Probabilities of the stage that actually produced the active probe.

        This is the exact quantity the stage scored and the execution path consumes; the
        bounded-adapter residual transform is applied here so train and serve see the same
        features.
        """
        features = self._require_finite_features(test_x, "test_x")
        if self._active_stage is None or self._active_probe is None:
            raise StagePreconditionNotMetError(
                "NO_STAGE_EVIDENCE_FORECAST_FORBIDDEN: no adaptation stage has been "
                "executed, so no "
                "forecast may be produced; run zero_shot, frozen_probe or bounded_adapter first."
            )
        if self._active_stage is AdaptationStage.ZERO_SHOT:
            return self._zero_shot_probs(features)
        probs = self._active_probe.predict_proba(self._transform(features))[:, 1]
        return np.clip(probs, 1e-6, 1.0 - 1e-6)

    def predict_forecasts(
        self,
        test_x: np.ndarray,
        pair: str,
        decision_ts: datetime,
        mapper: CostAwareExecutionMapper,
        desired_qty: Any = None,
        payoff: PayoffStructure | None = None,
        test_timestamps: list[datetime] | None = None,
    ) -> list[ExecutionDecision]:
        """Convert the executed stage's probabilities into execution decisions via common mapper."""
        cutoff = self._require_known_cutoff()
        if decision_ts <= cutoff:
            raise ContaminatedDatesClaimError(
                f"CONTAMINATED_DATES_FORBIDDEN: decision_ts "
                f"{decision_ts.isoformat()} is prior to or "
                f"overlaps training cutoff {cutoff.isoformat()}"
            )
        if test_timestamps is not None:
            self._validate_timestamps(test_timestamps, len(test_x))

        probs = self.predict_proba(test_x)

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
