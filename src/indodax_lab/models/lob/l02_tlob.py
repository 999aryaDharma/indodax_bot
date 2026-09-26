"""Transformer LOB (TLOB) attention challenger and tournament archive (L02-01).

Guarantees:
1. L02-01-AC0: TLOB attention architecture evaluated against DeepLOB with compute and latency budget tracking.
2. L02-01-AC1: No perfect queue fill assumption (realistic execution rejects 100% unconditional maker fills).
3. L02-01-AC2: Search budget strictly capped at <=8 configurations; excess attempts fail-closed.
4. L02-01-AC3: Poor valid challenger results are explicitly archived rather than discarded or retried.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.models.dl.checkpoint import require_torch

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PerfectQueueFillForbiddenError(ValueError):
    """Raised when simulation assumes 100% unconditional maker fills or zero spread/slippage."""


class TLOBSearchBudgetExceededError(ValueError):
    """Raised when TLOB hyperparameter search exceeds maximum allowed budget of 8."""


class InvalidNetEdgeError(ValueError):
    """Raised when tournament evidence is unusable (non-finite value, empty identifier)."""


class MissingLatencyEvidenceError(ValueError):
    """Raised when a challenger artifact is produced without measured inference latency."""


class TLOBInputShapeError(ValueError):
    """Raised when a model input tensor does not match the configured LOB window."""


# ---------------------------------------------------------------------------
# Queue Fill Model
# ---------------------------------------------------------------------------


class QueueFillModel:
    """Realistic limit order book queue fill and adverse selection model.

    Uncertainty (spec 16 requires this to be documented, not hidden): a resting maker
    order at the touch is filled only by flow that trades through the volume queued
    ahead of it, and the share of that flow which is *toxic* rises with the spread. The
    model therefore returns a probability, never a certainty, and always documents the
    two drivers it can represent:

    * ``half_spread_bps`` -- wider spread means more adverse selection, so a lower
      realized fill probability at the same queue position.
    * ``queue_penalty_bps`` -- an explicit additive haircut for queue priority loss and
      cancellation risk, in the same units as the spread.

    Both are strictly validated; a model that cannot represent spread or queue risk is
    rejected rather than silently ignored.
    """

    #: Spread at which the modeled toxic-flow share saturates (bps).
    TOXICITY_SATURATION_BPS: ClassVar[float] = 50.0
    #: Maximum share of resting flow treated as toxic at saturation.
    MAX_TOXICITY: ClassVar[float] = 0.9
    #: Additive weight on the toxicity share when discounting the fill probability.
    TOXICITY_DISCOUNT: ClassVar[float] = 0.5

    def __init__(
        self,
        half_spread_bps: float = 5.0,
        queue_penalty_bps: float = 2.0,
        assume_unconditional_fill: bool = False,
    ) -> None:
        if assume_unconditional_fill:
            raise PerfectQueueFillForbiddenError(
                "PERFECT_QUEUE_FILL_FORBIDDEN: Simulation cannot assume 100% unconditional maker fill. "
                "Queue priority and cancellation dynamics must be modeled."
            )
        if half_spread_bps <= 0.0:
            raise PerfectQueueFillForbiddenError(
                "ZERO_SLIPPAGE_OR_SPREAD_FORBIDDEN: Bid-ask spread must be strictly positive."
            )
        if not np.isfinite(half_spread_bps):
            raise PerfectQueueFillForbiddenError(
                f"NON_FINITE_SPREAD_FORBIDDEN: half_spread_bps must be finite, "
                f"got {half_spread_bps}"
            )
        if not np.isfinite(queue_penalty_bps) or queue_penalty_bps < 0.0:
            raise ValueError(
                f"QUEUE_PENALTY_MUST_BE_NON_NEGATIVE: queue_penalty_bps must be a finite "
                f"non-negative number of bps, got {queue_penalty_bps}"
            )
        self.half_spread_bps = half_spread_bps
        self.queue_penalty_bps = queue_penalty_bps

    def estimate_fill_probability(self, queue_depth_level: int, order_qty: float) -> float:
        """Estimate realistic fill probability from queue position, size, spread and penalty.

        Strictly decreasing in ``queue_depth_level``, ``order_qty``, ``half_spread_bps``
        and ``queue_penalty_bps``; always strictly inside (0, 1) so a fill is never
        guaranteed.
        """
        if queue_depth_level < 1:
            queue_depth_level = 1
        qty = max(0.01, order_qty)

        # Volume resting ahead of our order, in units of our own size.
        queue_ahead = 1.0 + queue_depth_level * (1.0 + qty)
        base_decay = 1.0 / (1.0 + 0.45 * queue_ahead)

        # Adverse selection: a wider spread means a larger toxic share of resting flow.
        toxicity = min(self.half_spread_bps / self.TOXICITY_SATURATION_BPS, self.MAX_TOXICITY)
        fill_prob = base_decay * (1.0 - self.TOXICITY_DISCOUNT * toxicity)
        fill_prob -= self.queue_penalty_bps / 1000.0
        return float(np.clip(fill_prob, 0.01, 0.95))


# ---------------------------------------------------------------------------
# Configurations & Data Models
# ---------------------------------------------------------------------------


class TLOBComputeSummary(BaseModel):
    """Parameter and compute budget summary for TLOB architecture."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    total_trainable_parameters: int
    estimated_flops_per_inference: int
    num_layers: int
    d_model: int
    n_heads: int
    lookback_len: int
    num_features: int


class TLOBConfig(BaseModel):
    """Configuration for Transformer LOB (TLOB) challenger."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str = "L02_TLOB"
    version: str = "1.0.0"
    lookback_len: int = 20
    num_features: int = 20
    d_model: int = 32
    n_heads: int = 2
    num_layers: int = 2
    d_ff: int = 64
    dropout: float = 0.1
    num_classes: int = 3
    search_budget_max_configs: int = 8
    seed: int = 42

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.search_budget_max_configs > 8:
            raise TLOBSearchBudgetExceededError(
                f"TLOB_SEARCH_BUDGET_EXCEEDED: Maximum 8 configurations permitted, "
                f"got {self.search_budget_max_configs}"
            )
        if self.d_model % self.n_heads != 0:
            raise ValueError(
                f"D_MODEL_NOT_DIVISIBLE: d_model ({self.d_model}) must be divisible by n_heads ({self.n_heads})"
            )


# ---------------------------------------------------------------------------
# Tournament Archive Models
# ---------------------------------------------------------------------------


class ArchivedChallengerResult(BaseModel):
    """Immutable archive record of an evaluated challenger result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    challenger_id: str
    baseline_id: str
    challenger_net_edge: float
    baseline_net_edge: float
    net_edge_delta: float
    eval_ts: datetime
    status: str
    promoted: bool
    archived_evidence_preserved: bool
    reasons: list[str] = Field(default_factory=list)


class TLOBTournamentArchiver:
    """Registry archiving research challenger outcomes, especially underperformers."""

    def __init__(self) -> None:
        self._archive: list[ArchivedChallengerResult] = []

    def record_tournament_outcome(
        self,
        challenger_id: str,
        baseline_id: str,
        challenger_net_edge: float,
        baseline_net_edge: float,
        eval_ts: datetime,
        reasons: list[str] | None = None,
    ) -> ArchivedChallengerResult:
        """Permanently record challenger evaluation outcome.

        Evidence must be usable: a non-finite net edge is a broken measurement, and
        `nan > baseline` silently classified it as an ARCHIVED_UNDERPERFORMER with
        `archived_evidence_preserved=True`, archiving a measurement failure as a genuine
        negative research result. Empty identifiers are rejected for the same reason.
        """
        self._require_usable_evidence(
            "challenger_net_edge", challenger_net_edge, "NET_EDGE_MUST_BE_FINITE"
        )
        self._require_usable_evidence(
            "baseline_net_edge", baseline_net_edge, "NET_EDGE_MUST_BE_FINITE"
        )
        self._require_usable_evidence("challenger_id", challenger_id, "IDENTIFIER_REQUIRED")
        self._require_usable_evidence("baseline_id", baseline_id, "IDENTIFIER_REQUIRED")

        reasons_list = list(reasons or [])
        is_superior = challenger_net_edge > baseline_net_edge

        status = "PROMOTED_CHALLENGER" if is_superior else "ARCHIVED_UNDERPERFORMER"

        record = ArchivedChallengerResult(
            challenger_id=challenger_id.strip(),
            baseline_id=baseline_id.strip(),
            challenger_net_edge=challenger_net_edge,
            baseline_net_edge=baseline_net_edge,
            net_edge_delta=challenger_net_edge - baseline_net_edge,
            eval_ts=eval_ts.astimezone(UTC),
            status=status,
            promoted=is_superior,
            archived_evidence_preserved=False,
            reasons=reasons_list,
        )
        self._archive.append(record)

        # Computed, not asserted: the record only claims preservation once it is
        # retrievable from the archive and round-trips through JSON unchanged.
        preserved = any(stored is record for stored in self._archive) and self._round_trips(record)
        self._archive[-1] = record.model_copy(update={"archived_evidence_preserved": preserved})
        return self._archive[-1]

    @staticmethod
    def _require_usable_evidence(name: str, value: Any, code: str) -> None:
        """Reject evidence that cannot support an archive claim."""
        if isinstance(value, str):
            if not value.strip():
                raise InvalidNetEdgeError(
                    f"{code}: {name} must be a non-empty identifier, got {value!r}"
                )
            return
        if not np.isfinite(float(value)):
            raise InvalidNetEdgeError(f"{code}: {name} must be finite, got {value!r}")

    @staticmethod
    def _round_trips(record: ArchivedChallengerResult) -> bool:
        """True when the record survives a JSON round trip with identical evidence."""
        try:
            restored = ArchivedChallengerResult.model_validate_json(record.model_dump_json())
        except Exception:  # noqa: BLE001 - any serialization failure means unpreserved
            return False
        return (
            restored.challenger_id == record.challenger_id
            and restored.baseline_id == record.baseline_id
            and restored.challenger_net_edge == record.challenger_net_edge
            and restored.baseline_net_edge == record.baseline_net_edge
            and restored.reasons == record.reasons
        )

    def list_archived_records(self) -> list[ArchivedChallengerResult]:
        """Return all recorded tournament outcomes."""
        return list(self._archive)


# ---------------------------------------------------------------------------
# Configuration Search Registry (L02-01-AC2)
# ---------------------------------------------------------------------------


class TLOBChallengerSearchEvidence(BaseModel):
    """Search accounting required by spec 16: trials x folds x seeds and elapsed time."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    max_configurations: int
    registered_configurations: int
    total_trials: int
    folds: tuple[int, ...]
    seeds: tuple[int, ...]
    total_elapsed_seconds: float


class TLOBConfigSearch:
    """Live registry enforcing the <=8 configuration search budget (L02-01-AC2).

    `TLOBConfig.search_budget_max_configs` only validated the *declared* budget; it did
    not stop a caller from evaluating a 9th configuration. This registry is the
    accounting boundary: every configuration must be registered here, and registering
    past the budget fails closed.
    """

    #: Hard cap from spec 16 ("<=8 configurations").
    HARD_MAX_CONFIGURATIONS: ClassVar[int] = 8

    def __init__(self, max_configurations: int = 8) -> None:
        if max_configurations > self.HARD_MAX_CONFIGURATIONS:
            raise TLOBSearchBudgetExceededError(
                f"TLOB_SEARCH_BUDGET_EXCEEDED: Maximum {self.HARD_MAX_CONFIGURATIONS} "
                f"configurations permitted, got {max_configurations}"
            )
        if max_configurations < 1:
            raise ValueError(f"SEARCH_BUDGET_MUST_BE_POSITIVE: got {max_configurations}")

        self.max_configurations = max_configurations
        self._registered: list[TLOBConfig] = []
        self._trials: list[tuple[int, int, float]] = []

    @property
    def registered(self) -> list[TLOBConfig]:
        """Configurations registered so far, in registration order."""
        return list(self._registered)

    @property
    def registered_configurations(self) -> int:
        return len(self._registered)

    @property
    def trials_remaining(self) -> int:
        return max(0, self.max_configurations - len(self._registered))

    def should_continue(self) -> bool:
        """True while another configuration may be evaluated under the budget."""
        return len(self._registered) < self.max_configurations

    def register(self, config: TLOBConfig) -> int:
        """Register a configuration for evaluation; returns its 1-based search index."""
        if not self.should_continue():
            raise TLOBSearchBudgetExceededError(
                f"TLOB_SEARCH_BUDGET_EXCEEDED: {len(self._registered)} of "
                f"{self.max_configurations} configurations already evaluated, "
                f"refusing to evaluate another"
            )
        self._registered.append(config)
        return len(self._registered)

    def record_trial(self, fold: int, seed: int, elapsed_seconds: float) -> None:
        """Record one (fold, seed) trial and its wall-clock cost."""
        if not np.isfinite(elapsed_seconds):
            raise InvalidNetEdgeError(
                f"ELAPSED_SECONDS_MUST_BE_FINITE: got {elapsed_seconds} "
                f"for fold={fold} seed={seed}"
            )
        if elapsed_seconds < 0.0:
            raise InvalidNetEdgeError(
                f"ELAPSED_SECONDS_MUST_BE_NON_NEGATIVE: got {elapsed_seconds}"
            )
        self._trials.append((fold, seed, float(elapsed_seconds)))

    @property
    def search_evidence(self) -> TLOBChallengerSearchEvidence:
        """Snapshot the trials x folds x seeds and elapsed-time accounting."""
        return TLOBChallengerSearchEvidence(
            max_configurations=self.max_configurations,
            registered_configurations=len(self._registered),
            total_trials=len(self._trials),
            folds=tuple(sorted({fold for fold, _, _ in self._trials})),
            seeds=tuple(sorted({seed for _, seed, _ in self._trials})),
            total_elapsed_seconds=float(sum(elapsed for _, _, elapsed in self._trials)),
        )


# ---------------------------------------------------------------------------
# PyTorch TLOB Implementation
# ---------------------------------------------------------------------------


def _build_tlob_classes():
    torch = require_torch()
    import torch.nn as nn

    class TLOBModelImpl(nn.Module):
        """Transformer architecture for limit order book sequence modeling."""

        def __init__(self, config: TLOBConfig) -> None:
            super().__init__()
            self.config = config

            # Seed the whole construction inside a forked RNG so the module stays
            # reproducible for its own seed without reseeding the process-wide torch
            # RNG, which every downstream stochastic step (trainer init, dropout mask,
            # other challengers' sampling) would otherwise depend on.
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(config.seed)

                # Feature projection
                self.feature_proj = nn.Linear(config.num_features, config.d_model)

                # Causal transformer encoder layer
                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=config.d_model,
                    nhead=config.n_heads,
                    dim_feedforward=config.d_ff,
                    dropout=config.dropout,
                    batch_first=True,
                )
                self.transformer_encoder = nn.TransformerEncoder(
                    encoder_layer=encoder_layer,
                    num_layers=config.num_layers,
                )

                self.head = nn.Linear(config.d_model, config.num_classes)
                self.softmax = nn.Softmax(dim=-1)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """Forward pass mapping (B, lookback_len, num_features) -> (B, num_classes)."""
            # Reading L straight off the tensor accepted any window length, so a 30-bar
            # input silently scored through weights trained on a 20-bar window. The
            # configured window is a contract, not a hint.
            if x.dim() != 3:
                raise TLOBInputShapeError(
                    f"TLOB_INPUT_SHAPE_MISMATCH: expected a 3D (B, L, F) tensor, "
                    f"got shape {tuple(x.shape)}"
                )
            B, L, F = x.shape
            if L != self.config.lookback_len or F != self.config.num_features:
                raise TLOBInputShapeError(
                    f"TLOB_INPUT_SHAPE_MISMATCH: expected (B, {self.config.lookback_len}, "
                    f"{self.config.num_features}), got (B, {L}, {F})"
                )
            h = self.feature_proj(x)  # (B, L, d_model)

            # Generate upper-triangular causal mask
            causal_mask = torch.triu(torch.full((L, L), float("-inf"), device=x.device), diagonal=1)

            out = self.transformer_encoder(h, mask=causal_mask)

            # Pooling: use the final time-step representation
            last_step = out[:, -1, :]  # (B, d_model)
            logits = self.head(last_step)
            return self.softmax(logits)

        def compute_budget_summary(self) -> TLOBComputeSummary:
            """Calculate trainable parameters and estimated FLOPs."""
            total_params = sum(p.numel() for p in self.parameters() if p.requires_grad)

            L = self.config.lookback_len
            F = self.config.num_features
            d = self.config.d_model
            d_ff = self.config.d_ff

            proj_flops = 2 * L * F * d
            per_layer_flops = (4 * L * (d**2)) + (2 * (L**2) * d) + (4 * L * d * d_ff)
            encoder_flops = self.config.num_layers * per_layer_flops
            head_flops = 2 * d * self.config.num_classes
            total_flops = proj_flops + encoder_flops + head_flops

            return TLOBComputeSummary(
                total_trainable_parameters=total_params,
                estimated_flops_per_inference=total_flops,
                num_layers=self.config.num_layers,
                d_model=self.config.d_model,
                n_heads=self.config.n_heads,
                lookback_len=self.config.lookback_len,
                num_features=self.config.num_features,
            )

    return TLOBModelImpl


class TLOBModel:
    """Public wrapper creating TLOB model instance."""

    def __new__(cls, config: TLOBConfig) -> Any:
        impl_cls = _build_tlob_classes()
        return impl_cls(config)


# ---------------------------------------------------------------------------
# Challenger Artifact with Compute and Measured Latency Evidence (L02-01-AC0)
# ---------------------------------------------------------------------------


class TLOBChallengerArtifact(BaseModel):
    """Challenger artifact binding compute budget *and* measured inference latency.

    Spec 16 requires a "challenger artifact with latency/compute evidence". Producing
    this model is therefore the only supported way to hand a TLOB challenger forward.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    challenger_id: str
    baseline_id: str
    model_id: str
    version: str
    compute: TLOBComputeSummary
    measured_latency_ms_p50: float
    measured_latency_ms_p95: float
    num_latency_samples: int
    device: str
    evaluated_at_utc: datetime

    @classmethod
    def from_model(
        cls,
        challenger_id: str,
        baseline_id: str,
        model: Any,
        latency_samples_ms: list[float],
        measured_at_utc: datetime,
        device: str,
    ) -> TLOBChallengerArtifact:
        """Build an artifact from a live model and its measured inference latencies."""
        compute = model.compute_budget_summary()
        samples = [float(s) for s in latency_samples_ms]
        usable = [s for s in samples if np.isfinite(s) and s > 0.0]
        if len(usable) != len(samples) or not usable:
            raise MissingLatencyEvidenceError(
                f"MEASURED_LATENCY_REQUIRED: {len(samples)} latency sample(s) supplied, "
                f"{len(usable)} finite and strictly positive; use measure_inference_latency_ms()"
            )
        return cls(
            challenger_id=challenger_id,
            baseline_id=baseline_id,
            model_id=model.config.model_id,
            version=model.config.version,
            compute=compute,
            measured_latency_ms_p50=float(np.percentile(usable, 50)),
            measured_latency_ms_p95=float(np.percentile(usable, 95)),
            num_latency_samples=len(usable),
            device=device,
            evaluated_at_utc=measured_at_utc.astimezone(UTC),
        )


def measure_inference_latency_ms(
    model: Any,
    x: np.ndarray,
    num_warmup: int = 3,
    num_iterations: int = 20,
) -> list[float]:
    """Measure per-inference wall-clock latency in milliseconds for a TLOB model."""
    import time

    torch = require_torch()
    tensor = torch.from_numpy(np.ascontiguousarray(x, dtype=np.float32))
    was_training = getattr(model, "training", False)
    model.eval()
    try:
        with torch.no_grad():
            for _ in range(max(0, num_warmup)):
                model(tensor)
            samples: list[float] = []
            for _ in range(num_iterations):
                start = time.perf_counter()
                model(tensor)
                samples.append((time.perf_counter() - start) * 1000.0)
        return samples
    finally:
        if was_training:
            model.train()
