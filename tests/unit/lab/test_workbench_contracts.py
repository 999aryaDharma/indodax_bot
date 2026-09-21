"""Unit tests for Workbench domain manifests and immutable identities (RW0-01).

Guarantees:
1. RW0-01-AC0: Key reordering gives same digest; local-root relocation cannot affect it.
2. RW0-01-AC1: Nested mutation cannot change published manifest.
3. RW0-01-AC2: Changed risk/model/feature/seed changes identity.
4. RW0-01-AC3: Extra fields, naive time, NaN and invalid hash reject.
5. RW0-01-AC4: Terminal experiment configuration cannot be edited.
6. RW0-01-AC5: Runtime plan can be verified before any completed experiment exists.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from indodax_lab.contracts.identity import (
    ArtifactRef,
    canonical_bytes,
    manifest_digest,
)
from indodax_lab.contracts.workbench import (
    AgentManifest,
    CandidateManifest,
    DatasetManifest,
    ExperimentManifest,
    ExperimentStatus,
    MetricValidity,
    MetricValue,
    ModelManifest,
    PipelineEdge,
    PipelineManifest,
    PipelineNode,
    Provenance,
    RuntimePlan,
    ServiceError,
    ServiceResponse,
    StrategyManifest,
    TerminalExperimentLockedError,
    VerifiedRuntimePlan,
    verify_runtime_plan,
)

NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=UTC)
DUMMY_SHA = "a" * 64
DUMMY_SHA_2 = "b" * 64


def make_dummy_artifact_ref(
    kind: str = "dataset",
    id_: str = "ds-btc-1h",
    version: str = "1.0.0",
    sha: str = DUMMY_SHA,
) -> ArtifactRef:
    return ArtifactRef(
        kind=kind,
        id=id_,
        version=version,
        sha256=sha,
        schema_version="v1",
    )


# ---------------------------------------------------------------------------
# Acceptance Tests (AC0 - AC5)
# ---------------------------------------------------------------------------


def test_rw0_01_0():
    """RW0-01-AC0: Key reordering gives same digest; local-root relocation cannot affect it."""
    ref1 = make_dummy_artifact_ref(id_="ds-1", sha=DUMMY_SHA)
    ref2 = make_dummy_artifact_ref(id_="pipe-1", sha=DUMMY_SHA_2)

    plan1 = RuntimePlan(
        plan_id="plan-001",
        version="1.0.0",
        universe=("btc_idr", "eth_idr"),
        timeframe="1h",
        dataset_refs=(ref1,),
        pipeline_ref=ref2,
        feature_schema_hash=DUMMY_SHA,
        ordered_feature_names=("close_std_14", "volume_ma_20"),
        sizing_policy_ref=make_dummy_artifact_ref(kind="policy", id_="sizing-1"),
        exit_policy_ref=make_dummy_artifact_ref(kind="policy", id_="exit-1"),
        risk_policy_ref=make_dummy_artifact_ref(kind="policy", id_="risk-1"),
        cost_policy_ref=make_dummy_artifact_ref(kind="policy", id_="cost-1"),
        execution_policy_ref=make_dummy_artifact_ref(kind="policy", id_="exec-1"),
        git_sha="1234567890abcdef1234567890abcdef12345678",
        environment_digest=DUMMY_SHA,
        seed=42,
    )

    digest1 = manifest_digest(plan1)
    bytes1 = canonical_bytes(plan1)

    # Reordering dictionary keys in canonical JSON serialization produces identical bytes
    parsed = json.loads(bytes1.decode("utf-8"))
    reversed_dict = {k: parsed[k] for k in reversed(list(parsed.keys()))}
    re_encoded = canonical_bytes(reversed_dict)

    assert bytes1 == re_encoded
    assert len(digest1) == 64
    assert digest1.lower() == digest1

    # Absolute filesystem paths are strictly rejected from ArtifactRef / identity
    with pytest.raises(ValidationError, match="PATH_SEPARATOR_FORBIDDEN|ABSOLUTE_PATH_FORBIDDEN"):
        ArtifactRef(
            kind="dataset",
            id="/root/data/my_dataset",
            version="1.0.0",
            sha256=DUMMY_SHA,
        )

    with pytest.raises(ValidationError, match="PATH_SEPARATOR_FORBIDDEN|ABSOLUTE_PATH_FORBIDDEN"):
        ArtifactRef(
            kind="dataset",
            id="C:\\Users\\Data\\my_dataset",
            version="1.0.0",
            sha256=DUMMY_SHA,
        )


def test_rw0_01_1():
    """RW0-01-AC1: Nested mutation cannot change published manifest."""
    ref_ds = make_dummy_artifact_ref(kind="dataset", id_="ds-1")
    ref_pipe = make_dummy_artifact_ref(kind="pipeline", id_="pipe-1")

    universe_tuple = ("btc_idr", "eth_idr")
    plan = RuntimePlan(
        plan_id="plan-001",
        version="1.0.0",
        universe=universe_tuple,
        timeframe="1h",
        dataset_refs=(ref_ds,),
        pipeline_ref=ref_pipe,
        feature_schema_hash=DUMMY_SHA,
        ordered_feature_names=("feat_a", "feat_b"),
        sizing_policy_ref=make_dummy_artifact_ref(kind="policy", id_="sizing-1"),
        exit_policy_ref=make_dummy_artifact_ref(kind="policy", id_="exit-1"),
        risk_policy_ref=make_dummy_artifact_ref(kind="policy", id_="risk-1"),
        cost_policy_ref=make_dummy_artifact_ref(kind="policy", id_="cost-1"),
        execution_policy_ref=make_dummy_artifact_ref(kind="policy", id_="exec-1"),
        git_sha="1234567890abcdef1234567890abcdef12345678",
        environment_digest=DUMMY_SHA,
        seed=42,
    )

    # Top-level mutation is forbidden by frozen model
    with pytest.raises(ValidationError):
        plan.seed = 99  # type: ignore

    # Nested tuple cannot be modified in place
    with pytest.raises(TypeError):
        plan.universe[0] = "sol_idr"  # type: ignore

    # Nested artifact ref is also frozen
    with pytest.raises(ValidationError):
        plan.dataset_refs[0].id = "tampered"  # type: ignore


def test_rw0_01_2():
    """RW0-01-AC2: Changed risk/model/feature/seed changes identity."""
    base_kwargs = dict(
        plan_id="plan-001",
        version="1.0.0",
        universe=("btc_idr",),
        timeframe="1h",
        dataset_refs=(make_dummy_artifact_ref(id_="ds-1"),),
        pipeline_ref=make_dummy_artifact_ref(id_="pipe-1"),
        feature_schema_hash=DUMMY_SHA,
        ordered_feature_names=("feat_a",),
        sizing_policy_ref=make_dummy_artifact_ref(kind="policy", id_="sizing-1"),
        exit_policy_ref=make_dummy_artifact_ref(kind="policy", id_="exit-1"),
        risk_policy_ref=make_dummy_artifact_ref(kind="policy", id_="risk-1", sha=DUMMY_SHA),
        cost_policy_ref=make_dummy_artifact_ref(kind="policy", id_="cost-1"),
        execution_policy_ref=make_dummy_artifact_ref(kind="policy", id_="exec-1"),
        git_sha="1234567890abcdef1234567890abcdef12345678",
        environment_digest=DUMMY_SHA,
        seed=42,
    )

    plan_base = RuntimePlan(**base_kwargs)
    base_digest = manifest_digest(plan_base)

    # 1. Changed seed changes digest
    plan_diff_seed = RuntimePlan(**{**base_kwargs, "seed": 43})
    assert manifest_digest(plan_diff_seed) != base_digest

    # 2. Changed risk policy ref changes digest
    diff_risk_ref = make_dummy_artifact_ref(kind="policy", id_="risk-1", sha=DUMMY_SHA_2)
    plan_diff_risk = RuntimePlan(**{**base_kwargs, "risk_policy_ref": diff_risk_ref})
    assert manifest_digest(plan_diff_risk) != base_digest

    # 3. Changed feature schema hash changes digest
    plan_diff_feat = RuntimePlan(**{**base_kwargs, "feature_schema_hash": DUMMY_SHA_2})
    assert manifest_digest(plan_diff_feat) != base_digest

    # 4. Changed pipeline ref (model/pipeline change) changes digest
    diff_pipe_ref = make_dummy_artifact_ref(id_="pipe-2", sha=DUMMY_SHA_2)
    plan_diff_pipe = RuntimePlan(**{**base_kwargs, "pipeline_ref": diff_pipe_ref})
    assert manifest_digest(plan_diff_pipe) != base_digest


def test_rw0_01_3():
    """RW0-01-AC3: Extra fields, naive time, NaN and invalid hash reject."""
    # 1. Extra fields reject fail-closed
    with pytest.raises(ValidationError, match="extra"):
        ArtifactRef(
            kind="dataset",
            id="ds-1",
            version="1.0",
            sha256=DUMMY_SHA,
            unauthorized_field="malicious",  # type: ignore
        )

    # 2. Naive time rejects
    naive_dt = datetime(2026, 9, 21, 12, 0, 0)  # No tzinfo
    with pytest.raises(ValidationError, match="UTC_TIMEZONE_AWARE_REQUIRED"):
        DatasetManifest(
            dataset_id="ds-001",
            version="1.0.0",
            venue="indodax",
            pair="btc_idr",
            timeframe="1h",
            requested_start=naive_dt,
            requested_end=NOW,
            actual_start=NOW,
            actual_end=NOW,
            bar_count=100,
            source_id="src-1",
            source_version="1.0",
            partition_refs=(),
            quality_report_ref=make_dummy_artifact_ref(kind="report", id_="qr-1"),
            created_at_utc=NOW,
        )

    # 3. NaN rejects
    with pytest.raises(ValidationError, match="NON_FINITE_NUMBER_FORBIDDEN"):
        MetricValue(
            value=float("nan"),
            unit="bps",
            validity=MetricValidity.VALID,
        )

    # 4. Invalid hash rejects (not 64-char lowercase hex)
    with pytest.raises(ValidationError, match="INVALID_SHA256_HEX"):
        ArtifactRef(
            kind="dataset",
            id="ds-1",
            version="1.0",
            sha256="not_a_valid_sha256",
        )

    # Uppercase hex also rejects (must be canonical lowercase)
    with pytest.raises(ValidationError, match="INVALID_SHA256_HEX"):
        ArtifactRef(
            kind="dataset",
            id="ds-1",
            version="1.0",
            sha256=DUMMY_SHA.upper(),
        )


def test_rw0_01_4():
    """RW0-01-AC4: Terminal experiment configuration cannot be edited."""
    exp = ExperimentManifest(
        experiment_id="exp-001",
        version="1.0.0",
        dataset_ref=make_dummy_artifact_ref(id_="ds-1"),
        pipeline_ref=make_dummy_artifact_ref(id_="pipe-1"),
        initial_virtual_cash=Decimal("100000000"),
        currency="IDR",
        cost_policy_ref=make_dummy_artifact_ref(kind="policy", id_="cost-1"),
        risk_policy_ref=make_dummy_artifact_ref(kind="policy", id_="risk-1"),
        execution_policy_ref=make_dummy_artifact_ref(kind="policy", id_="exec-1"),
        git_sha="1234567890abcdef1234567890abcdef12345678",
        environment_digest=DUMMY_SHA,
        seed=42,
        status=ExperimentStatus.COMPLETED,
        created_at_utc=NOW,
    )

    # Direct mutation rejected by frozen model
    with pytest.raises(ValidationError):
        exp.seed = 999  # type: ignore

    # Modifying configuration of terminal experiment raises TerminalExperimentLockedError
    with pytest.raises(TerminalExperimentLockedError, match="TERMINAL_EXPERIMENT_LOCKED"):
        exp.update_status(ExperimentStatus.FAILED)


def test_rw0_01_bootstrap_recovery():
    """RW0-01-AC5: Runtime plan can be verified before any completed experiment exists."""
    plan = RuntimePlan(
        plan_id="plan-bootstrap-01",
        version="1.0.0",
        universe=("btc_idr",),
        timeframe="1h",
        dataset_refs=(make_dummy_artifact_ref(id_="ds-1"),),
        pipeline_ref=make_dummy_artifact_ref(id_="pipe-1"),
        feature_schema_hash=DUMMY_SHA,
        ordered_feature_names=("feat_1", "feat_2"),
        sizing_policy_ref=make_dummy_artifact_ref(kind="policy", id_="sizing-1"),
        exit_policy_ref=make_dummy_artifact_ref(kind="policy", id_="exit-1"),
        risk_policy_ref=make_dummy_artifact_ref(kind="policy", id_="risk-1"),
        cost_policy_ref=make_dummy_artifact_ref(kind="policy", id_="cost-1"),
        execution_policy_ref=make_dummy_artifact_ref(kind="policy", id_="exec-1"),
        git_sha="1234567890abcdef1234567890abcdef12345678",
        environment_digest=DUMMY_SHA,
        seed=42,
    )

    # Verification passes without needing any completed experiment or candidate
    verified = verify_runtime_plan(plan)
    assert isinstance(verified, VerifiedRuntimePlan)
    assert verified.plan == plan
    assert verified.plan_digest == manifest_digest(plan)
    assert verified.verified_at_utc.tzinfo is not None


# ---------------------------------------------------------------------------
# Additional Manifest Contract Tests
# ---------------------------------------------------------------------------


def test_strategy_manifest_contract():
    strat = StrategyManifest(
        strategy_id="strat-001",
        family="trend_following",
        version="1.0.0",
        implementation_artifact_ref=make_dummy_artifact_ref(kind="code", id_="code-strat-1"),
        parameter_schema_hash=DUMMY_SHA,
        parameters={"lookback": 20, "threshold": "0.05"},
        required_feature_schema_hash=DUMMY_SHA,
        timeframe_constraints=("1h", "4h"),
        decision_contract_version="v1",
        exit_contract_version="v1",
    )
    digest = manifest_digest(strat)
    assert len(digest) == 64
    assert strat.to_artifact_ref().id == "strat-001"


def test_model_manifest_contract():
    model = ModelManifest(
        model_id="model-001",
        architecture="xgboost",
        version="1.0.0",
        artifact_refs=(make_dummy_artifact_ref(kind="weights", id_="model-weights"),),
        ordered_feature_schema=("feat_a", "feat_b"),
        preprocessing_ref=make_dummy_artifact_ref(kind="scaler", id_="scaler-1"),
        calibration_ref=None,
        training_evidence_ref=make_dummy_artifact_ref(kind="report", id_="train-rep"),
        validation_evidence_ref=make_dummy_artifact_ref(kind="report", id_="val-rep"),
        test_evidence_ref=make_dummy_artifact_ref(kind="report", id_="test-rep"),
        metrics_ref=make_dummy_artifact_ref(kind="metrics", id_="metrics-1"),
        universe=("btc_idr",),
        runtime_requirements={"python": ">=3.11", "torch": "cpu"},
    )
    assert len(manifest_digest(model)) == 64


def test_pipeline_manifest_contract():
    n1 = PipelineNode(node_id="data_in", kind="dataset_input", output_port="observation")
    n2 = PipelineNode(node_id="strategy", kind="strategy", output_port="intent")
    e1 = PipelineEdge(
        source_node="data_in",
        source_port="observation",
        target_node="strategy",
        target_port="observation",
    )

    pipe = PipelineManifest(
        pipeline_id="pipe-001",
        version="1.0.0",
        nodes=(n1, n2),
        edges=(e1,),
        component_refs=(make_dummy_artifact_ref(id_="strat-1"),),
        dataset_timeframe_constraints={"1h": ("btc_idr",)},
        sizing_policy_ref=make_dummy_artifact_ref(kind="policy", id_="sizing-1"),
        exit_policy_ref=make_dummy_artifact_ref(kind="policy", id_="exit-1"),
        risk_policy_ref=make_dummy_artifact_ref(kind="policy", id_="risk-1"),
        cost_policy_ref=make_dummy_artifact_ref(kind="policy", id_="cost-1"),
        execution_policy_ref=make_dummy_artifact_ref(kind="policy", id_="exec-1"),
    )
    assert len(manifest_digest(pipe)) == 64


def test_candidate_and_agent_manifest_contract():
    cand = CandidateManifest(
        candidate_id="cand-001",
        version="1.0.0",
        runtime_plan_ref=make_dummy_artifact_ref(kind="plan", id_="plan-1"),
        completed_experiment_ref=make_dummy_artifact_ref(kind="experiment", id_="exp-1"),
        pipeline_ref=make_dummy_artifact_ref(kind="pipeline", id_="pipe-1"),
        strategy_hashes=(DUMMY_SHA,),
        model_hashes=(DUMMY_SHA_2,),
        ordered_feature_schema_hash=DUMMY_SHA,
        universe=("btc_idr",),
        timeframe="1h",
        risk_policy_ref=make_dummy_artifact_ref(kind="policy", id_="risk-1"),
        cost_policy_ref=make_dummy_artifact_ref(kind="policy", id_="cost-1"),
        execution_policy_ref=make_dummy_artifact_ref(kind="policy", id_="exec-1"),
        git_sha="1234567890abcdef1234567890abcdef12345678",
        environment_digest=DUMMY_SHA,
        evaluation_evidence_refs=(make_dummy_artifact_ref(kind="evidence", id_="ev-1"),),
    )
    cand_digest = manifest_digest(cand)
    assert len(cand_digest) == 64

    agent = AgentManifest(
        agent_id="agent-001",
        version="1.0.0",
        candidate_ref=make_dummy_artifact_ref(kind="candidate", id_="cand-001", sha=cand_digest),
        cohort_id="cohort-alpha",
        initial_virtual_cash=Decimal("50000000"),
        currency="IDR",
        runtime_policy_refs=(make_dummy_artifact_ref(kind="policy", id_="rt-pol"),),
        namespace_id="agent_ns_001",
        canonical_feed_identity="indodax_live_v1",
    )
    assert len(manifest_digest(agent)) == 64


def test_shared_service_envelopes():
    err = ServiceError(
        code="DATASET_NOT_FOUND",
        message="Dataset ds-missing does not exist in registry",
        subject_refs=(make_dummy_artifact_ref(id_="ds-missing"),),
        retryable=False,
    )
    resp_err = ServiceResponse(
        schema_version="v1",
        request_id="req-123",
        error=err,
    )
    assert resp_err.error is not None
    assert resp_err.data is None

    resp_ok = ServiceResponse(
        schema_version="v1",
        request_id="req-124",
        data={"status": "OK"},
    )
    assert resp_ok.data == {"status": "OK"}
    assert resp_ok.error is None

    prov = Provenance(
        source_sha="1234567890abcdef1234567890abcdef12345678",
        environment_digest=DUMMY_SHA,
        input_refs=(make_dummy_artifact_ref(id_="in-1"),),
        policy_refs=(make_dummy_artifact_ref(kind="policy", id_="pol-1"),),
        runtime_plan_digest=DUMMY_SHA_2,
    )
    assert prov.source_sha.startswith("1234")
