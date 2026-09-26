"""Unit tests for L02-01 TLOB challenger, queue fill model and tournament archive.

Deliberately does not import `indodax_lab.features` (L01-01 extraction path needs
`pyarrow`, which is not installed in this environment) so this file collects and runs
independently of the parquet-backed feature gate. `tests/integration/lab/test_tlob_smoke.py`
covers the tensor-extraction path end to end.

Guarantees:
1. L02-01-AC0: compute *and* measured latency evidence are attached to the challenger artifact.
2. L02-01-AC1: queue fill actually responds to spread/queue penalty and never guarantees a fill.
3. L02-01-AC2: the search budget of <=8 configurations is enforced by a live registry.
4. L02-01-AC3: archive records carry computed (not hardcoded) evidence-preservation state.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from indodax_lab.models.lob.l02_tlob import (
    ArchivedChallengerResult,
    InvalidNetEdgeError,
    MissingLatencyEvidenceError,
    QueueFillModel,
    TLOBChallengerArtifact,
    TLOBConfig,
    TLOBConfigSearch,
    TLOBInputShapeError,
    TLOBModel,
    TLOBSearchBudgetExceededError,
    TLOBTournamentArchiver,
    measure_inference_latency_ms,
)

# ---------------------------------------------------------------------------
# L02-01-AC1 -- queue fill realism
# ---------------------------------------------------------------------------


def test_l02_01_queue_fill_respects_spread_and_queue_penalty() -> None:
    """Critical: half_spread_bps and queue_penalty_bps were accepted and then ignored.

    A 5 bps and a 50 bps spread returned the *identical* 0.625 fill probability, and a
    queue penalty of 2 bps and 80 bps did the same, so the two risk parameters that
    decide whether a maker fill survives costs had no effect on any number produced.
    """
    tight = QueueFillModel(half_spread_bps=5.0, queue_penalty_bps=2.0)
    wide = QueueFillModel(half_spread_bps=50.0, queue_penalty_bps=2.0)
    penalised = QueueFillModel(half_spread_bps=5.0, queue_penalty_bps=80.0)

    p_tight = tight.estimate_fill_probability(queue_depth_level=1, order_qty=1.0)
    p_wide = wide.estimate_fill_probability(queue_depth_level=1, order_qty=1.0)
    p_penalised = penalised.estimate_fill_probability(queue_depth_level=1, order_qty=1.0)

    assert p_wide < p_tight
    assert p_penalised < p_tight
    for p in (p_tight, p_wide, p_penalised):
        assert 0.0 < p < 1.0


def test_l02_01_queue_fill_is_strictly_monotone() -> None:
    """Important: fill probability must keep decreasing in queue depth and order size."""
    model = QueueFillModel(half_spread_bps=5.0, queue_penalty_bps=2.0)
    by_depth = [
        model.estimate_fill_probability(queue_depth_level=d, order_qty=1.0) for d in (1, 2, 5, 10)
    ]
    by_qty = [
        model.estimate_fill_probability(queue_depth_level=1, order_qty=q) for q in (0.1, 1.0, 5.0)
    ]

    assert by_depth == sorted(by_depth, reverse=True)
    assert len(set(by_depth)) == len(by_depth)
    assert by_qty == sorted(by_qty, reverse=True)
    assert len(set(by_qty)) == len(by_qty)


def test_l02_01_queue_penalty_must_be_non_negative() -> None:
    """Important: a negative queue penalty was accepted and would raise fill probability.

    A negative penalty is not more favourable execution, it is a sign error that inflates
    the modeled fill probability above the no-penalty case.
    """
    with pytest.raises(ValueError, match="QUEUE_PENALTY_MUST_BE_NON_NEGATIVE"):
        QueueFillModel(half_spread_bps=5.0, queue_penalty_bps=-5.0)


def test_l02_01_never_returns_a_guaranteed_fill() -> None:
    """L02-01-AC1: no input combination may produce a 1.0 fill probability."""
    for half_spread in (0.1, 1.0, 5.0, 100.0):
        for penalty in (0.0, 5.0, 200.0):
            model = QueueFillModel(half_spread_bps=half_spread, queue_penalty_bps=penalty)
            best = model.estimate_fill_probability(queue_depth_level=1, order_qty=0.01)
            assert best < 1.0


# ---------------------------------------------------------------------------
# L02-01-AC3 -- archive evidence
# ---------------------------------------------------------------------------


def test_l02_01_archive_rejects_non_finite_net_edge() -> None:
    """Critical: a NaN net edge archived as a clean underperformer.

    `nan > baseline` is False, so a NaN was recorded as ARCHIVED_UNDERPERFORMER with
    `archived_evidence_preserved=True`, i.e. a measurement failure was archived as a
    genuine negative research result.
    """
    archiver = TLOBTournamentArchiver()
    with pytest.raises(InvalidNetEdgeError, match="NET_EDGE_MUST_BE_FINITE"):
        archiver.record_tournament_outcome(
            challenger_id="L02_TLOB_ATTN",
            baseline_id="L01_DEEPLOB",
            challenger_net_edge=float("nan"),
            baseline_net_edge=0.001,
            eval_ts=datetime(2025, 3, 1, 12, 0, tzinfo=UTC),
        )
    assert archiver.list_archived_records() == []


def test_l02_01_archive_rejects_empty_identifiers() -> None:
    """Important: an empty challenger/baseline id produced an unusable archive row."""
    archiver = TLOBTournamentArchiver()
    with pytest.raises(InvalidNetEdgeError, match="IDENTIFIER_REQUIRED"):
        archiver.record_tournament_outcome(
            challenger_id="   ",
            baseline_id="L01_DEEPLOB",
            challenger_net_edge=0.002,
            baseline_net_edge=0.001,
            eval_ts=datetime(2025, 3, 1, 12, 0, tzinfo=UTC),
        )
    assert archiver.list_archived_records() == []


def test_l02_01_archive_preservation_flag_is_derived() -> None:
    """Important: archived_evidence_preserved was the literal True.

    It is now derived from the record actually being retrievable from the archive and
    round-tripping through JSON with identical evidence, so a record whose evidence
    cannot be re-read cannot claim preservation.
    """
    archiver = TLOBTournamentArchiver()
    record = archiver.record_tournament_outcome(
        challenger_id="L02_TLOB_ATTN",
        baseline_id="L01_DEEPLOB",
        challenger_net_edge=-0.0015,
        baseline_net_edge=0.001,
        eval_ts=datetime(2025, 3, 1, 12, 0, tzinfo=UTC),
        reasons=["NET_EDGE_BELOW_BASELINE"],
    )
    assert record.status == "ARCHIVED_UNDERPERFORMER"
    assert record.promoted is False
    assert record.net_edge_delta == pytest.approx(-0.0025)
    assert record.archived_evidence_preserved is True

    records = archiver.list_archived_records()
    assert len(records) == 1
    assert records[0] is record
    # The preservation claim is backed by a real round trip, not by a constant.
    restored = ArchivedChallengerResult.model_validate_json(record.model_dump_json())
    assert restored.challenger_id == record.challenger_id
    assert restored.challenger_net_edge == record.challenger_net_edge
    assert restored.reasons == record.reasons
    assert restored.archived_evidence_preserved is True


# ---------------------------------------------------------------------------
# L02-01-AC2 -- search budget registry
# ---------------------------------------------------------------------------


def test_l02_01_search_registry_stops_at_eight_configurations() -> None:
    """L02-01-AC2: nothing stopped a 9th configuration from being evaluated.

    Only `TLOBConfig.search_budget_max_configs > 8` was rejected; a caller that
    registered configurations on the side could evaluate as many as it liked.
    """
    search = TLOBConfigSearch(max_configurations=8)

    for i in range(8):
        assert search.should_continue() is True
        search.register(TLOBConfig(d_model=16 + 4 * i))

    assert search.should_continue() is False
    assert search.registered_configurations == 8
    assert search.trials_remaining == 0

    with pytest.raises(TLOBSearchBudgetExceededError, match="TLOB_SEARCH_BUDGET_EXCEEDED"):
        search.register(TLOBConfig(d_model=64))

    assert search.registered_configurations == 8
    assert len(search.registered) == 8


def test_l02_01_search_records_trials_folds_seeds_and_elapsed_time() -> None:
    """Important: spec 16 requires trials x folds x seeds and elapsed CPU/GPU time."""
    search = TLOBConfigSearch(max_configurations=2)
    search.register(TLOBConfig(d_model=16))
    search.register(TLOBConfig(d_model=32))

    search.record_trial(fold=1, seed=42, elapsed_seconds=1.5)
    search.record_trial(fold=2, seed=42, elapsed_seconds=2.5)
    search.record_trial(fold=1, seed=7, elapsed_seconds=1.0)

    evidence = search.search_evidence
    assert evidence.registered_configurations == 2
    assert evidence.total_trials == 3
    assert evidence.folds == (1, 2)
    assert evidence.seeds == (7, 42)
    assert evidence.total_elapsed_seconds == pytest.approx(5.0)
    assert evidence.max_configurations == 2
    assert TLOBConfigSearch.HARD_MAX_CONFIGURATIONS == 8


def test_l02_01_search_rejects_non_finite_trial_time() -> None:
    """Important: a NaN elapsed time is a broken measurement, not a fast trial."""
    search = TLOBConfigSearch(max_configurations=8)
    with pytest.raises(InvalidNetEdgeError, match="ELAPSED_SECONDS_MUST_BE_FINITE"):
        search.record_trial(fold=1, seed=42, elapsed_seconds=float("inf"))


def test_l02_01_search_budget_config_cannot_exceed_eight() -> None:
    """L02-01-AC2: the registry itself refuses a >8 budget."""
    with pytest.raises(TLOBSearchBudgetExceededError, match="TLOB_SEARCH_BUDGET_EXCEEDED"):
        TLOBConfigSearch(max_configurations=9)


# ---------------------------------------------------------------------------
# L02-01-AC0 -- compute and measured latency evidence
# ---------------------------------------------------------------------------


def test_l02_01_challenger_artifact_requires_measured_latency() -> None:
    """Critical: no latency evidence existed at all (spec 16 AC0).

    "Challenger artifact with latency/compute evidence" -- only a compute summary was
    produced, so latency was never measured, recorded or required.
    """
    config = TLOBConfig(d_model=16, d_ff=32, lookback_len=8, num_features=4)
    model = TLOBModel(config)
    x = np.zeros((1, 8, 4), dtype=np.float32)

    with pytest.raises(MissingLatencyEvidenceError, match="MEASURED_LATENCY_REQUIRED"):
        TLOBChallengerArtifact.from_model(
            challenger_id="L02_TLOB_ATTN",
            baseline_id="L01_DEEPLOB",
            model=model,
            latency_samples_ms=[],
            measured_at_utc=datetime(2025, 3, 1, 12, 0, tzinfo=UTC),
            device="cpu",
        )

    artifact = TLOBChallengerArtifact.from_model(
        challenger_id="L02_TLOB_ATTN",
        baseline_id="L01_DEEPLOB",
        model=model,
        latency_samples_ms=measure_inference_latency_ms(model, x),
        measured_at_utc=datetime(2025, 3, 1, 12, 0, tzinfo=UTC),
        device="cpu",
    )

    assert artifact.challenger_id == "L02_TLOB_ATTN"
    assert artifact.baseline_id == "L01_DEEPLOB"
    assert artifact.compute.total_trainable_parameters > 0
    assert artifact.compute.estimated_flops_per_inference > 0
    assert artifact.measured_latency_ms_p50 > 0.0
    assert artifact.measured_latency_ms_p95 >= artifact.measured_latency_ms_p50
    assert artifact.num_latency_samples >= 5
    assert artifact.evaluated_at_utc.tzinfo is not None
    assert artifact.compute.num_layers == config.num_layers


def test_l02_01_challenger_artifact_rejects_non_positive_latency() -> None:
    """Important: a zero/NaN latency sample is not evidence."""
    config = TLOBConfig(d_model=16, d_ff=32, lookback_len=8, num_features=4)
    model = TLOBModel(config)
    with pytest.raises(MissingLatencyEvidenceError, match="MEASURED_LATENCY_REQUIRED"):
        TLOBChallengerArtifact.from_model(
            challenger_id="L02_TLOB_ATTN",
            baseline_id="L01_DEEPLOB",
            model=model,
            latency_samples_ms=[float("nan"), 1.0],
            measured_at_utc=datetime(2025, 3, 1, 12, 0, tzinfo=UTC),
            device="cpu",
        )


# ---------------------------------------------------------------------------
# Model surface: input shape contract and global RNG hygiene
# ---------------------------------------------------------------------------


def test_l02_01_forward_rejects_wrong_lookback_length() -> None:
    """Critical: `lookback_len=20` accepted a sequence of length 30.

    `B, L, F = x.shape` read whatever length arrived and only used it to build the causal
    mask, so a 30-bar window silently scored with 20-step-trained weights.
    """
    torch = pytest.importorskip("torch")
    config = TLOBConfig(d_model=16, d_ff=32, lookback_len=20, num_features=4)
    model = TLOBModel(config)
    model.eval()

    with pytest.raises(TLOBInputShapeError, match="TLOB_INPUT_SHAPE_MISMATCH"):
        model(torch.zeros((2, 30, 4)))

    with pytest.raises(TLOBInputShapeError, match="TLOB_INPUT_SHAPE_MISMATCH"):
        model(torch.zeros((2, 20, 7)))

    with torch.no_grad():
        probs = model(torch.zeros((2, 20, 4)))
    assert probs.shape == (2, config.num_classes)


def test_l02_01_model_construction_does_not_clobber_global_rng() -> None:
    """Important: `torch.manual_seed` in __init__ reseeded the process-wide RNG.

    Building a TLOB model rewrote the global torch RNG state, so any downstream
    stochastic step (trainer init, dropout mask, other challenger's sampling) became
    dependent on whether a TLOB model happened to be constructed first.
    """
    torch = pytest.importorskip("torch")
    torch.manual_seed(1234)
    before = torch.random.get_rng_state().clone()

    _ = TLOBModel(TLOBConfig(d_model=16, d_ff=32, lookback_len=8, num_features=4))

    after = torch.random.get_rng_state()
    assert torch.equal(before, after), "TLOBModel construction mutated the global torch RNG state"


def test_l02_01_model_is_still_deterministic_for_a_fixed_seed() -> None:
    """Minor guard: fork_rng must not make weights non-reproducible."""
    torch = pytest.importorskip("torch")
    config = TLOBConfig(d_model=16, d_ff=32, lookback_len=8, num_features=4)
    a = TLOBModel(config)
    b = TLOBModel(config)
    x = torch.arange(8 * 4, dtype=torch.float32).reshape(1, 8, 4) / 100.0
    a.eval()
    b.eval()
    with torch.no_grad():
        assert torch.allclose(a(x), b(x))
