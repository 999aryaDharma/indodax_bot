"""Behavioral acceptance tests for RW2-03: typed declarative pipeline composer.

Every test drives the public ``PipelineService`` boundary inside temporary
namespaces: no network, no Telegram, no production database and no real
market data. Component references resolve through the real RW2-01 strategy
store and the real RW2-02 model registry with verified artifact bytes.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from indodax_lab.contracts.identity import ArtifactRef, canonical_bytes, manifest_digest
from indodax_lab.contracts.workbench import (
    ModelManifest,
    PipelineEdge,
    PipelineManifest,
    PipelineNode,
)
from indodax_lab.models.artifacts import PortableBundle
from indodax_lab.models.m01_logistic import M01Config, M01LogisticTrainer
from indodax_lab.models.registry import ModelRegistry
from indodax_lab.pipelines import (
    PipelineService,
    PipelineValidationError,
    canonicalize,
)
from indodax_lab.strategies.base import DraftRef
from indodax_lab.strategies.store import StrategyService, StrategyStore

FEATURE_NAMES = ["feat_a", "feat_b", "feat_c"]
_BUNDLE_CACHE: dict[tuple[str, str, tuple[str, ...]], bytes] = {}


# ---------------------------------------------------------------------------
# Fixtures (synthetic, deterministic, local)
# ---------------------------------------------------------------------------


def _bundle_bytes(model_id: str, version: str, feature_names: list[str], seed: int = 42) -> bytes:
    """Train a small M01 model and serialize it as verified portable-bundle bytes."""
    key = (model_id, version, tuple(feature_names))
    cached = _BUNDLE_CACHE.get(key)
    if cached is not None:
        return cached

    row_count = 300
    rng = np.random.default_rng(seed)
    features = pd.DataFrame(
        rng.standard_normal((row_count, len(feature_names))), columns=feature_names
    )
    labels = pd.Series([index % 2 for index in range(row_count)])
    config = M01Config(model_id=model_id, version=version, max_iter=50, seed=seed)
    trainer = M01LogisticTrainer(config=config)
    fitted = trainer.train_and_calibrate(
        X_train=features.iloc[:240],
        y_train=labels.iloc[:240],
        X_val=features.iloc[240:],
        y_val=labels.iloc[240:],
        feature_names=feature_names,
    )
    payload = PortableBundle.from_m01(bundle=fitted, trainer=trainer).to_bytes()
    _BUNDLE_CACHE[key] = payload
    return payload


def _register_model(
    registry: ModelRegistry,
    model_id: str,
    *,
    runtime_requirements: dict[str, str] | None = None,
) -> ArtifactRef:
    """Publish a verified model identity in the temporary RW2-02 registry."""
    bundle = _bundle_bytes(model_id, "1.0.0", FEATURE_NAMES)
    bundle_ref = registry.put_bytes(
        bundle, kind="model", artifact_id=f"{model_id}_bundle", version="1.0.0"
    )
    manifest = ModelManifest(
        model_id=model_id,
        architecture="m01_logistic",
        version="1.0.0",
        artifact_refs=(bundle_ref,),
        ordered_feature_schema=tuple(FEATURE_NAMES),
        universe=("BTC-IDR",),
        runtime_requirements=dict(runtime_requirements or {}),
    )
    return registry.register(manifest)


def _publish_strategy(strategies: StrategyService, strategy_id: str) -> ArtifactRef:
    """Publish a built-in strategy version in the temporary RW2-01 store."""
    manifest = strategies.builtin_manifest(strategy_id)
    draft = strategies.create_draft(manifest)
    return strategies.publish(draft.id, draft.revision)


def _workspace(tmp_path) -> tuple[PipelineService, StrategyService, ModelRegistry]:
    strategies = StrategyService(StrategyStore(tmp_path / "strategies.sqlite"))
    models = ModelRegistry(tmp_path / "models")
    service = PipelineService(tmp_path / "pipelines.sqlite", strategies, models)
    return service, strategies, models


def _policy_ref(kind: str) -> ArtifactRef:
    return ArtifactRef(kind=kind, id=f"{kind}_v1", version="1.0.0", sha256="0" * 64)


def _build(
    nodes: tuple[PipelineNode, ...],
    edges: tuple[PipelineEdge, ...],
    component_refs: tuple[ArtifactRef, ...],
    *,
    ensemble_parameters: dict | None = None,
    constraints: dict[str, tuple[str, ...]] | None = None,
    pipeline_id: str = "pipe_rw2_03",
    version: str = "1.0.0",
) -> PipelineManifest:
    return PipelineManifest(
        pipeline_id=pipeline_id,
        version=version,
        nodes=tuple(nodes),
        edges=tuple(edges),
        component_refs=tuple(component_refs),
        dataset_timeframe_constraints=dict(constraints or {"btc_idr": ("1h",)}),
        ensemble_parameters=dict(ensemble_parameters or {}),
        sizing_policy_ref=_policy_ref("sizing_policy"),
        exit_policy_ref=_policy_ref("exit_policy"),
        risk_policy_ref=_policy_ref("risk_policy"),
        cost_policy_ref=_policy_ref("cost_policy"),
        execution_policy_ref=_policy_ref("execution_policy"),
    )


def _edge(source: str, source_port: str, target: str, target_port: str) -> PipelineEdge:
    return PipelineEdge(
        source_node=source,
        source_port=source_port,
        target_node=target,
        target_port=target_port,
    )


def _ta_only(strategy_ref: ArtifactRef, *, strategy_id: str = "C07", **kwargs) -> PipelineManifest:
    """TA-only graph: dataset -> strategy -> gate -> sizing -> exits."""
    nodes = (
        PipelineNode(node_id="ds_1", kind="dataset_input", output_port="MarketObservation"),
        PipelineNode(node_id=strategy_id, kind="ta", output_port="DecisionProposal"),
        PipelineNode(node_id="gate", kind="gate_veto", output_port="SignalIntent"),
        PipelineNode(node_id="sizing", kind="sizing", output_port="SignalIntent"),
        PipelineNode(node_id="exits", kind="exits", output_port="SignalIntent"),
    )
    edges = (
        _edge("ds_1", "MarketObservation", strategy_id, "MarketObservation"),
        _edge(strategy_id, "DecisionProposal", "gate", "DecisionProposal"),
        _edge("gate", "SignalIntent", "sizing", "SignalIntent"),
        _edge("sizing", "SignalIntent", "exits", "SignalIntent"),
    )
    return _build(nodes, edges, (strategy_ref,), **kwargs)


def _hybrid(
    strategy_ref: ArtifactRef,
    ml_ref: ArtifactRef,
    dl_ref: ArtifactRef,
    *,
    include_dl: bool = True,
    ensemble_parameters: dict | None = None,
    **kwargs,
) -> PipelineManifest:
    """TA + ML + DL soft-vote graph with an explicit ensemble fan-in."""
    nodes = [
        PipelineNode(node_id="ds_1", kind="dataset_input", output_port="MarketObservation"),
        PipelineNode(node_id="feats", kind="indicators_features", output_port="FeatureFrame"),
        PipelineNode(node_id=strategy_ref.id, kind="ta", output_port="DecisionProposal"),
        PipelineNode(node_id=ml_ref.id, kind="ml", output_port="ProbabilityVector"),
        PipelineNode(node_id="ens", kind="ensemble", output_port="ProbabilityVector"),
        PipelineNode(node_id="gate", kind="gate_veto", output_port="SignalIntent"),
        PipelineNode(node_id="sizing", kind="sizing", output_port="SignalIntent"),
        PipelineNode(node_id="exits", kind="exits", output_port="SignalIntent"),
    ]
    edges = [
        _edge("ds_1", "MarketObservation", "feats", "MarketObservation"),
        _edge("ds_1", "MarketObservation", strategy_ref.id, "MarketObservation"),
        _edge("feats", "FeatureFrame", ml_ref.id, "FeatureFrame"),
        _edge(ml_ref.id, "ProbabilityVector", "ens", "ProbabilityVector"),
        _edge(strategy_ref.id, "DecisionProposal", "gate", "DecisionProposal"),
        _edge("ens", "ProbabilityVector", "gate", "ProbabilityVector"),
        _edge("gate", "SignalIntent", "sizing", "SignalIntent"),
        _edge("sizing", "SignalIntent", "exits", "SignalIntent"),
    ]
    refs = [strategy_ref, ml_ref]
    if include_dl:
        nodes.insert(
            4, PipelineNode(node_id=dl_ref.id, kind="dl", output_port="ProbabilityVector")
        )
        edges.insert(4, _edge("feats", "FeatureFrame", dl_ref.id, "FeatureFrame"))
        edges.insert(5, _edge(dl_ref.id, "ProbabilityVector", "ens", "ProbabilityVector"))
        refs.append(dl_ref)
    params = ensemble_parameters
    if params is None:
        params = {
            "mode": "soft_vote",
            "inputs": [ml_ref.id, dl_ref.id],
            "weights": {ml_ref.id: 0.6, dl_ref.id: 0.4},
            "threshold": 0.55,
        }
    return _build(nodes, edges, tuple(refs), ensemble_parameters=params, **kwargs)


def _codes(report) -> list[str]:
    return [issue.code for issue in report.errors]


# ---------------------------------------------------------------------------
# RW2-03-AC0: TA-only and TA+ML+DL soft-vote graphs validate
# ---------------------------------------------------------------------------


def test_rw2_03_0(tmp_path) -> None:
    service, strategies, models = _workspace(tmp_path)
    strategy_ref = _publish_strategy(strategies, "C07")
    ml_ref = _register_model(models, "rw2_03_ml")
    dl_ref = _register_model(models, "rw2_03_dl")

    # TA-only graph: zero model nodes, published strategy component resolves.
    ta_manifest = _ta_only(strategy_ref)
    ta_report = service.validate(ta_manifest)
    assert ta_report.valid is True
    assert ta_report.errors == ()
    assert ta_report.resolved_refs == (strategy_ref,)
    assert ta_report.evaluation_order == ("ds_1", "C07", "gate", "sizing", "exits")

    draft = service.create(ta_manifest)
    assert draft.revision == 1
    assert draft.digest == manifest_digest(canonicalize(ta_manifest))
    published = service.publish(draft.id, draft.revision)
    assert published.kind == "pipeline_manifest"
    assert published.id == "pipe_rw2_03"
    assert published.sha256 == draft.digest

    # TA+ML+DL soft-vote graph: explicit ensemble fan-in resolves both models.
    hybrid = _hybrid(strategy_ref, ml_ref, dl_ref)
    hybrid_report = service.validate(hybrid)
    assert hybrid_report.valid is True
    assert hybrid_report.errors == ()
    assert set(hybrid_report.resolved_refs) == {strategy_ref, ml_ref, dl_ref}
    assert hybrid_report.evaluation_order == (
        "ds_1",
        "C07",
        "feats",
        "rw2_03_dl",
        "rw2_03_ml",
        "ens",
        "gate",
        "sizing",
        "exits",
    )
    hybrid_draft = service.create(hybrid)
    assert hybrid_draft.digest == manifest_digest(canonicalize(hybrid))


# ---------------------------------------------------------------------------
# RW2-03-AC1: cycles, incompatible ports, dangling refs, ambiguous fan-in reject
# ---------------------------------------------------------------------------


def test_rw2_03_1(tmp_path) -> None:
    service, strategies, models = _workspace(tmp_path)
    strategy_ref = _publish_strategy(strategies, "C07")

    # (a) Cycle: exits feeding back into sizing.
    cyclic = _build(
        _ta_only(strategy_ref).nodes,
        _ta_only(strategy_ref).edges + (_edge("exits", "SignalIntent", "sizing", "SignalIntent"),),
        (strategy_ref,),
    )
    cycle_report = service.validate(cyclic)
    assert cycle_report.valid is False
    assert "PIPELINE_CYCLE_DETECTED" in _codes(cycle_report)
    assert cycle_report.evaluation_order == ()
    with pytest.raises(PipelineValidationError, match="PIPELINE_CYCLE_DETECTED"):
        service.create(cyclic)

    # (b) Incompatible ports: a DecisionProposal output into sizing's SignalIntent port.
    base = _ta_only(strategy_ref)
    port_clash = _build(
        base.nodes,
        base.edges + (_edge("C07", "DecisionProposal", "sizing", "DecisionProposal"),),
        (strategy_ref,),
    )
    port_report = service.validate(port_clash)
    assert port_report.valid is False
    assert "PIPELINE_PORT_TYPE_MISMATCH" in _codes(port_report)

    # (c) Dangling ref: a strategy version that was never published never resolves.
    ghost_ref = ArtifactRef(
        kind="strategy_manifest", id="C07", version="9.9.9", sha256="1" * 64
    )
    ghost_report = service.validate(_ta_only(ghost_ref))
    assert ghost_report.valid is False
    assert "PIPELINE_COMPONENT_REF_UNRESOLVED" in _codes(ghost_report)
    assert ghost_report.resolved_refs == ()

    # (d) Ambiguous fan-in: two strategies writing DecisionProposal into one gate port.
    second_ref = _publish_strategy(strategies, "C02")
    ambiguous = _build(
        base.nodes
        + (PipelineNode(node_id="C02", kind="ta", output_port="DecisionProposal"),),
        (
            _edge("ds_1", "MarketObservation", "C07", "MarketObservation"),
            _edge("ds_1", "MarketObservation", "C02", "MarketObservation"),
            _edge("C07", "DecisionProposal", "gate", "DecisionProposal"),
            _edge("C02", "DecisionProposal", "gate", "DecisionProposal"),
            _edge("gate", "SignalIntent", "sizing", "SignalIntent"),
            _edge("sizing", "SignalIntent", "exits", "SignalIntent"),
        ),
        (strategy_ref, second_ref),
    )
    fan_in_report = service.validate(ambiguous)
    assert fan_in_report.valid is False
    assert "PIPELINE_AMBIGUOUS_FAN_IN" in _codes(fan_in_report)


# ---------------------------------------------------------------------------
# RW2-03-AC2: missing required model output abstains with reason
# ---------------------------------------------------------------------------


def test_rw2_03_2(tmp_path) -> None:
    service, strategies, models = _workspace(tmp_path)
    strategy_ref = _publish_strategy(strategies, "C07")
    ml_ref = _register_model(models, "rw2_03_ml")
    dl_ref = _register_model(models, "rw2_03_dl")

    # Declared ensemble input whose model node is absent from the graph:
    # abstain with a reason instead of silently dropping the vote.
    manifest = _hybrid(strategy_ref, ml_ref, dl_ref, include_dl=False)
    report = service.validate(manifest)
    assert report.valid is False
    abstains = [issue for issue in report.errors if issue.code.startswith("PIPELINE_ABSTAIN")]
    assert len(abstains) == 1
    assert abstains[0].code == "PIPELINE_ABSTAIN_MISSING_MODEL_OUTPUT"
    assert abstains[0].node_id == "ens"
    assert abstains[0].port == "ProbabilityVector"
    assert "rw2_03_dl" in abstains[0].message
    with pytest.raises(PipelineValidationError, match="PIPELINE_ABSTAIN_MISSING_MODEL_OUTPUT"):
        service.create(manifest)

    # Runtime-blocked model (RW2-02 BLOCKED_RESOURCE): its output is missing at
    # runtime, so the ensemble abstains with that reason; never a neutral vote.
    blocked_ref = _register_model(
        models, "rw2_03_blocked", runtime_requirements={"accelerator": "gpu"}
    )
    blocked_report = service.validate(_hybrid(strategy_ref, blocked_ref, dl_ref))
    assert blocked_report.valid is False
    blocked_abstains = [
        issue for issue in blocked_report.errors if issue.code.startswith("PIPELINE_ABSTAIN")
    ]
    assert len(blocked_abstains) == 1
    assert "BLOCKED_RESOURCE" in blocked_abstains[0].message
    assert blocked_ref not in blocked_report.resolved_refs


# ---------------------------------------------------------------------------
# RW2-03-AC3: identical graph yields identical digest regardless of UI mode
# ---------------------------------------------------------------------------


def test_rw2_03_3(tmp_path) -> None:
    service, strategies, _ = _workspace(tmp_path)
    strategy_ref = _publish_strategy(strategies, "C07")

    # Form view: the operator's declaration order.
    form_view = _ta_only(strategy_ref)
    # Graph view: the same semantic graph in a different presentation order
    # (layout order), with reversed nodes, edges and component refs.
    graph_view = _build(
        tuple(reversed(form_view.nodes)),
        tuple(reversed(form_view.edges)),
        tuple(reversed(form_view.component_refs)),
        constraints={"btc_idr": ("1h",)},
        pipeline_id=form_view.pipeline_id,
        version=form_view.version,
    )

    form_draft = service.create(form_view)
    graph_draft = service.create(graph_view)
    assert form_draft.digest == graph_draft.digest
    assert form_draft.digest == manifest_digest(canonicalize(form_view))
    assert form_draft.digest == manifest_digest(canonicalize(graph_view))

    # Publishing either presentation yields the same immutable identity,
    # and repeat publication is idempotent (no clobber, no second effect).
    form_ref = service.publish(form_draft.id, form_draft.revision)
    graph_ref = service.publish(graph_draft.id, graph_draft.revision)
    assert form_ref == graph_ref
    assert service.publish(graph_draft.id, graph_draft.revision) == form_ref


# ---------------------------------------------------------------------------
# RW2-03-AC4: form YAML and MCP round trip to an identical canonical digest
# ---------------------------------------------------------------------------


def test_rw2_03_program_4(tmp_path) -> None:
    service, strategies, models = _workspace(tmp_path)
    strategy_ref = _publish_strategy(strategies, "C07")
    ml_ref = _register_model(models, "rw2_03_ml")
    dl_ref = _register_model(models, "rw2_03_dl")

    form_view = _hybrid(strategy_ref, ml_ref, dl_ref)
    form_draft = service.create(form_view)

    # Form -> YAML -> manifest (YAML is presentation for canonical JSON identity).
    yaml_text = service.export_yaml(form_view)
    imported = service.import_yaml(yaml_text)
    assert service.validate(imported).valid is True
    yaml_draft = service.create(imported)
    assert yaml_draft.digest == form_draft.digest
    assert service.export_yaml(imported) == yaml_text

    # MCP: canonical JSON payload -> manifest, same digest as the other modes.
    payload = json.loads(canonical_bytes(canonicalize(form_view)))
    mcp_manifest = PipelineManifest.model_validate(payload)
    mcp_draft = service.create(mcp_manifest)
    assert mcp_draft.digest == form_draft.digest

    # Form YAML text handed to MCP parses back to the same canonical digest.
    from_yaml_payload = PipelineManifest.model_validate(
        json.loads(canonical_bytes(service.import_yaml(yaml_text)))
    )
    assert service.create(from_yaml_payload).digest == form_draft.digest

    # Presentation order must not change the canonical identity either.
    reordered_yaml = service.export_yaml(
        _build(
            tuple(reversed(form_view.nodes)),
            tuple(reversed(form_view.edges)),
            tuple(reversed(form_view.component_refs)),
            ensemble_parameters=form_view.ensemble_parameters,
            pipeline_id=form_view.pipeline_id,
            version=form_view.version,
        )
    )
    assert service.create(service.import_yaml(reordered_yaml)).digest == form_draft.digest


# ---------------------------------------------------------------------------
# RW2-03-AC5: duplicate keys, custom tags, unknown fields, oversized payloads reject
# ---------------------------------------------------------------------------


def test_rw2_03_program_5(tmp_path) -> None:
    service, strategies, models = _workspace(tmp_path)
    strategy_ref = _publish_strategy(strategies, "C07")
    valid_yaml = service.export_yaml(_ta_only(strategy_ref))

    # Duplicate YAML keys reject instead of silently overwriting.
    duplicate_key = valid_yaml.replace(
        "pipeline_id: pipe_rw2_03",
        "pipeline_id: pipe_rw2_03\npipeline_id: pipe_duplicate",
    )
    assert duplicate_key != valid_yaml
    with pytest.raises(ValueError, match="PIPELINE_YAML_DUPLICATE_KEY"):
        service.import_yaml(duplicate_key)

    # Custom/Python tags never construct objects.
    custom_tag = 'payload: !!python/object/apply:os.system ["echo pwned"]\n'
    with pytest.raises(ValueError, match="PIPELINE_YAML_FORBIDDEN_TAG"):
        service.import_yaml(custom_tag)

    # Executable expressions inside otherwise-valid documents reject too.
    executable = valid_yaml + "extra: !!python/name:os.system\n"
    with pytest.raises(ValueError, match="PIPELINE_YAML_FORBIDDEN_TAG"):
        service.import_yaml(executable)

    # Unknown fields reject before any semantic use.
    unknown_field = valid_yaml + "bogus_field: true\n"
    with pytest.raises(ValueError, match="PIPELINE_MANIFEST_UNKNOWN_FIELD") as excinfo:
        service.import_yaml(unknown_field)
    assert "bogus_field" in str(excinfo.value)

    # Oversized nested payloads reject before semantic use.
    deep_payload = "ensemble_parameters: " + "[" * 40 + "]" * 40 + "\n"
    with pytest.raises(ValueError, match="PIPELINE_YAML_TOO_DEEP"):
        service.import_yaml(deep_payload)

    oversized = "pipeline_id: " + "x" * 70_000 + "\n"
    with pytest.raises(ValueError, match="PIPELINE_YAML_TOO_LARGE"):
        service.import_yaml(oversized)

    # Non-finite values reject (never silently hashed or defaulted).
    non_finite = "ensemble_parameters: {threshold: .nan}\n"
    with pytest.raises(ValueError, match="PIPELINE_YAML_NON_FINITE"):
        service.import_yaml(non_finite)


# ---------------------------------------------------------------------------
# Soft-vote parameter rules (RW2-03 Step 3)
# ---------------------------------------------------------------------------


def test_rw2_03_ensemble_soft_vote_parameter_rules(tmp_path) -> None:
    service, strategies, models = _workspace(tmp_path)
    strategy_ref = _publish_strategy(strategies, "C07")
    ml_ref = _register_model(models, "rw2_03_ml")
    dl_ref = _register_model(models, "rw2_03_dl")

    valid_params = {
        "mode": "soft_vote",
        "inputs": [ml_ref.id, dl_ref.id],
        "weights": {ml_ref.id: 0.6, dl_ref.id: 0.4},
        "threshold": 0.55,
    }

    negative = dict(valid_params, weights={ml_ref.id: -0.6, dl_ref.id: 0.4})
    report = service.validate(_hybrid(strategy_ref, ml_ref, dl_ref, ensemble_parameters=negative))
    assert "PIPELINE_ENSEMBLE_WEIGHT_INVALID" in _codes(report)

    zero_sum = dict(valid_params, weights={ml_ref.id: 0.0, dl_ref.id: 0.0})
    report = service.validate(_hybrid(strategy_ref, ml_ref, dl_ref, ensemble_parameters=zero_sum))
    assert "PIPELINE_ENSEMBLE_WEIGHT_INVALID" in _codes(report)

    missing_threshold = {k: v for k, v in valid_params.items() if k != "threshold"}
    report = service.validate(
        _hybrid(strategy_ref, ml_ref, dl_ref, ensemble_parameters=missing_threshold)
    )
    assert "PIPELINE_ENSEMBLE_THRESHOLD_INVALID" in _codes(report)

    single_input = dict(valid_params, inputs=[ml_ref.id], weights={ml_ref.id: 1.0})
    report = service.validate(
        _hybrid(strategy_ref, ml_ref, dl_ref, ensemble_parameters=single_input)
    )
    assert "PIPELINE_ENSEMBLE_INPUT_REQUIRED" in _codes(report)

    wrong_mode = dict(valid_params, mode="max")
    report = service.validate(_hybrid(strategy_ref, ml_ref, dl_ref, ensemble_parameters=wrong_mode))
    assert "PIPELINE_ENSEMBLE_MODE_UNSUPPORTED" in _codes(report)

    # Soft-vote parameters without an ensemble node never validate silently.
    base = _ta_only(strategy_ref)
    orphaned = _build(
        base.nodes,
        base.edges,
        (strategy_ref,),
        ensemble_parameters=valid_params,
    )
    assert "PIPELINE_ENSEMBLE_PARAMS_ORPHANED" in _codes(service.validate(orphaned))

    # Sizing and exit policies stay explicit and unique.
    no_exit = _build(base.nodes[:4], base.edges[:3], (strategy_ref,))
    assert "PIPELINE_EXIT_REQUIRED" in _codes(service.validate(no_exit))


# ---------------------------------------------------------------------------
# Draft revision fencing and idempotent publication
# ---------------------------------------------------------------------------


def test_rw2_03_draft_revision_fencing_and_idempotent_publication(tmp_path) -> None:
    service, strategies, _ = _workspace(tmp_path)
    strategy_ref = _publish_strategy(strategies, "C07")
    manifest = _ta_only(strategy_ref)
    variant = _ta_only(strategy_ref, constraints={"btc_idr": ("1h", "4h")})

    draft = service.create(manifest)
    assert draft.revision == 1
    updated = service.update(draft.id, 1, variant)
    assert updated.revision == 2
    assert updated.digest == manifest_digest(canonicalize(variant))

    # A stale revision cannot clobber the newer edit.
    with pytest.raises(ValueError, match="STALE_DRAFT_REVISION"):
        service.update(draft.id, 1, _ta_only(strategy_ref, version="9.9.9"))

    # Fencing also holds across a second service connection to the same store.
    second = PipelineService(
        tmp_path / "pipelines.sqlite", strategies, ModelRegistry(tmp_path / "models")
    )
    with pytest.raises(ValueError, match="STALE_DRAFT_REVISION"):
        second.update(draft.id, 1, _ta_only(strategy_ref, version="8.8.8"))

    published = service.publish(draft.id, updated.revision)
    assert published.sha256 == updated.digest

    # Publishing with a stale revision rejects; duplicate publication is idempotent.
    with pytest.raises(ValueError, match="STALE_DRAFT_REVISION"):
        service.publish(draft.id, 1)
    assert service.publish(draft.id, updated.revision) == published

    # Published drafts never mutate again.
    with pytest.raises(ValueError, match="PIPELINE_DRAFT_ALREADY_PUBLISHED"):
        service.update(draft.id, updated.revision, variant)

    # Same identity with different semantics never clobbers the publication.
    conflicting = _ta_only(strategy_ref, version="1.0.0", constraints={"btc_idr": ("4h",)})
    conflicting_draft = service.create(conflicting)
    with pytest.raises(ValueError, match="IMMUTABLE_VERSION_CONFLICT"):
        service.publish(conflicting_draft.id, conflicting_draft.revision)


# ---------------------------------------------------------------------------
# Clone identity fencing and published fork
# ---------------------------------------------------------------------------


def test_rw2_03_clone_identity_fencing_and_published_fork(tmp_path) -> None:
    service, strategies, _ = _workspace(tmp_path)
    strategy_ref = _publish_strategy(strategies, "C07")
    manifest = _ta_only(strategy_ref)
    variant = _ta_only(strategy_ref, constraints={"btc_idr": ("1h", "4h")})

    draft = service.create(manifest)
    current = service.update(draft.id, 1, variant)

    # A stale identity (old digest) cannot authorize a clone.
    stale_ref = DraftRef(id=draft.id, revision=1, digest=manifest_digest(canonicalize(manifest)))
    with pytest.raises(ValueError, match="PIPELINE_DRAFT_REF_MISMATCH"):
        service.clone(stale_ref)

    # Cloning the current draft yields a new draft with identical content.
    clone = service.clone(current)
    assert clone.id != draft.id
    assert clone.revision == 1
    assert clone.digest == current.digest

    # Cloning a published artifact forks a new version without touching the parent.
    published = service.publish(draft.id, current.revision)
    fork = service.clone(published)
    assert fork.digest != published.sha256
    fork_ref = service.publish(fork.id, fork.revision)
    assert fork_ref.id == published.id
    assert fork_ref.version.startswith(f"{published.version}-clone-")
    assert fork_ref.sha256 != published.sha256
