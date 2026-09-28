"""Graph validation and YAML presentation contract for RW2-03.

Normative sources: ``docs/implementation/CONTRACTS.md`` (typed ports, DAG
rules, abstention) and ``docs/implementation/BOT-TRADE-PROGRAM.md`` (one
PipelineManifest for form/YAML/MCP; YAML rejection rules).
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from collections.abc import Callable
from heapq import heapify, heappop, heappush
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from indodax_lab.contracts.identity import ArtifactRef, canonical_bytes
from indodax_lab.contracts.workbench import PipelineEdge, PipelineManifest, PipelineNode
from indodax_lab.models.registry import ModelRegistry, ModelRegistryError
from indodax_lab.strategies.store import StrategyService

# ---------------------------------------------------------------------------
# Typed port contract: a node's output port is its kind's output type and an
# edge is only legal when the target kind accepts the target port.
# ---------------------------------------------------------------------------

KIND_INPUTS: dict[str, frozenset[str]] = {
    "dataset_input": frozenset(),
    "indicators_features": frozenset({"MarketObservation"}),
    "regime_filter": frozenset({"FeatureFrame"}),
    "ta": frozenset({"MarketObservation", "FeatureFrame"}),
    "ml": frozenset({"FeatureFrame"}),
    "dl": frozenset({"FeatureFrame"}),
    "ensemble": frozenset({"ProbabilityVector"}),
    "gate_veto": frozenset({"DecisionProposal", "ProbabilityVector"}),
    "sizing": frozenset({"SignalIntent"}),
    "exits": frozenset({"SignalIntent"}),
    "execution_policy": frozenset(),
}

KIND_OUTPUTS: dict[str, str] = {
    "dataset_input": "MarketObservation",
    "indicators_features": "FeatureFrame",
    "regime_filter": "FeatureFrame",
    "ta": "DecisionProposal",
    "ml": "ProbabilityVector",
    "dl": "ProbabilityVector",
    "ensemble": "ProbabilityVector",
    "gate_veto": "SignalIntent",
    "sizing": "SignalIntent",
    "exits": "SignalIntent",
    "execution_policy": "ExecutionPolicyRef",
}

MODEL_KINDS = frozenset({"ml", "dl"})
DECISION_REF_KINDS = {"ta": "strategy_manifest", "ml": "model", "dl": "model"}
# ``exits`` ends the signal chain; ``execution_policy`` is a standalone product.
TERMINAL_KINDS = frozenset({"exits", "execution_policy"})
# Roots that need no incoming edge to be part of the runnable graph.
ROOT_KINDS = frozenset({"dataset_input", "execution_policy"})

PORTS = frozenset(KIND_OUTPUTS.values()) | frozenset().union(*KIND_INPUTS.values())
NODE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")

YAML_MAX_BYTES = 65536
YAML_MAX_DEPTH = 32
_YAML_TAG_PREFIXES = ("tag:yaml.org,2002:", "!!")
_YAML_TAGS = frozenset(
    {
        "binary",
        "bool",
        "float",
        "int",
        "list",
        "map",
        "null",
        "seq",
        "set",
        "str",
        "timestamp",
        "value",
        "yaml",
    }
)

AddIssue = Callable[..., None]


class ValidationIssue(BaseModel):
    """One rejection/abstention reason: ``errors(code, node_id, port)``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    node_id: str | None = None
    port: str | None = None
    message: str = ""


class ValidationReport(BaseModel):
    """``(valid, errors(code, node_id, port), resolved_refs)`` plus order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool
    errors: tuple[ValidationIssue, ...] = ()
    resolved_refs: tuple[ArtifactRef, ...] = ()
    evaluation_order: tuple[str, ...] = ()


class PipelineValidationError(ValueError):
    """Raised by create/update/publish when a manifest fails validation."""

    def __init__(self, report: ValidationReport) -> None:
        codes = ",".join(sorted({issue.code for issue in report.errors}))
        super().__init__(f"PIPELINE_MANIFEST_INVALID: {codes}")
        self.report = report


def canonicalize(manifest: PipelineManifest) -> PipelineManifest:
    """Canonical semantic form of a manifest (presentation-order independent).

    Nodes, edges and component references are sorted by identity, and the
    ensemble input list is sorted, so form view, graph view and YAML
    presentations of the same graph share one digest.
    """
    inputs = manifest.ensemble_parameters.get("inputs")
    params = dict(manifest.ensemble_parameters)
    if isinstance(inputs, (list, tuple)) and all(isinstance(item, str) for item in inputs):
        params["inputs"] = sorted(inputs)
    return manifest.model_copy(
        update={
            "nodes": tuple(sorted(manifest.nodes, key=lambda node: node.node_id)),
            "edges": tuple(
                sorted(
                    manifest.edges,
                    key=lambda edge: (
                        edge.source_node,
                        edge.source_port,
                        edge.target_node,
                        edge.target_port,
                    ),
                )
            ),
            "component_refs": tuple(
                sorted(
                    manifest.component_refs,
                    key=lambda ref: (ref.kind, ref.id, ref.version, ref.sha256),
                )
            ),
            "ensemble_parameters": params,
        }
    )


# ---------------------------------------------------------------------------
# YAML presentation: size/depth/tag/duplicate-key rejection happens before any
# object is constructed, so a crafted document never reaches the constructor.
# ---------------------------------------------------------------------------


def import_yaml(text: str) -> PipelineManifest:
    """Parse a YAML presentation into a PipelineManifest, fail-closed."""
    if len(text.encode("utf-8", "replace")) > YAML_MAX_BYTES:
        raise ValueError(
            f"PIPELINE_YAML_TOO_LARGE: document exceeds {YAML_MAX_BYTES} bytes"
        )
    try:
        root = yaml.compose(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"PIPELINE_YAML_INVALID: {exc}") from exc
    except RecursionError as exc:
        raise ValueError(
            f"PIPELINE_YAML_TOO_DEEP: document nests deeper than {YAML_MAX_DEPTH} levels"
        ) from exc
    if root is None:
        raise ValueError("PIPELINE_YAML_INVALID: document is empty")
    _inspect_yaml_node(root, 1)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"PIPELINE_YAML_INVALID: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("PIPELINE_YAML_INVALID: root must be a mapping")
    _reject_non_finite(data, "root")
    try:
        return canonicalize(PipelineManifest.model_validate(data))
    except ValidationError as exc:
        raise _manifest_error(exc) from exc


def export_yaml(manifest: PipelineManifest) -> str:
    """Serialize a PipelineManifest as its canonical YAML presentation."""
    return yaml.safe_dump(
        json.loads(canonical_bytes(canonicalize(manifest))), sort_keys=True, allow_unicode=True
    )


def _yaml_tag_allowed(tag: str) -> bool:
    for prefix in _YAML_TAG_PREFIXES:
        if tag.startswith(prefix):
            return tag[len(prefix) :] in _YAML_TAGS
    return False


def _inspect_yaml_node(node: Node, depth: int) -> None:
    if depth > YAML_MAX_DEPTH:
        raise ValueError(
            f"PIPELINE_YAML_TOO_DEEP: document nests deeper than {YAML_MAX_DEPTH} levels"
        )
    if not _yaml_tag_allowed(node.tag):
        raise ValueError(f"PIPELINE_YAML_FORBIDDEN_TAG: tag {node.tag!r} is not allowed")
    if isinstance(node, MappingNode):
        seen: set[str] = set()
        for key, value in node.value:
            if isinstance(key, ScalarNode):
                if key.value in seen:
                    raise ValueError(f"PIPELINE_YAML_DUPLICATE_KEY: duplicate key {key.value!r}")
                seen.add(key.value)
            _inspect_yaml_node(key, depth + 1)
            _inspect_yaml_node(value, depth + 1)
    elif isinstance(node, SequenceNode):
        for child in node.value:
            _inspect_yaml_node(child, depth + 1)


def _reject_non_finite(value: Any, path: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"PIPELINE_YAML_NON_FINITE: non-finite number at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_non_finite(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_non_finite(item, f"{path}[{index}]")


def _manifest_error(exc: ValidationError) -> ValueError:
    for error in exc.errors():
        if error.get("type") == "extra_forbidden":
            field = ".".join(str(part) for part in error.get("loc", ()))
            return ValueError(f"PIPELINE_MANIFEST_UNKNOWN_FIELD: {field}: {error.get('msg', '')}")
    return ValueError(f"PIPELINE_MANIFEST_INVALID: {exc}")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_manifest(
    manifest: PipelineManifest,
    *,
    strategies: StrategyService,
    models: ModelRegistry,
) -> ValidationReport:
    """Validate a pipeline manifest against the RW2-03 contract."""
    manifest = canonicalize(manifest)
    issues: list[ValidationIssue] = []

    def add(
        code: str, message: str, node_id: str | None = None, port: str | None = None
    ) -> None:
        issues.append(ValidationIssue(code=code, node_id=node_id, port=port, message=message))

    node_by_id = _index_nodes(manifest, add)
    adjacency, in_edges, out_edges = _index_edges(manifest, node_by_id, add)
    evaluation_order = _evaluation_order(node_by_id, adjacency, add)
    _check_graph_rules(manifest, node_by_id, adjacency, in_edges, out_edges, add)
    _check_ensemble(manifest, node_by_id, in_edges, add)
    resolved = _resolve_components(manifest, node_by_id, strategies, models, add)

    ordered = sorted(
        issues,
        key=lambda issue: (issue.code, issue.node_id or "", issue.port or "", issue.message),
    )
    return ValidationReport(
        valid=not ordered,
        errors=tuple(ordered),
        resolved_refs=resolved,
        evaluation_order=evaluation_order,
    )


def _index_nodes(manifest: PipelineManifest, add: AddIssue) -> dict[str, PipelineNode]:
    node_by_id: dict[str, PipelineNode] = {}
    for node in manifest.nodes:
        if not NODE_ID.fullmatch(node.node_id):
            add("PIPELINE_NODE_ID_INVALID", f"node id {node.node_id!r} is not a valid identifier")
        if node.node_id in node_by_id:
            add(
                "PIPELINE_NODE_DUPLICATE_ID",
                f"node id {node.node_id!r} is declared more than once",
                node.node_id,
            )
            continue
        node_by_id[node.node_id] = node
        if node.kind not in KIND_OUTPUTS:
            add(
                "PIPELINE_KIND_UNKNOWN",
                f"node {node.node_id!r} declares unknown kind {node.kind!r}",
                node.node_id,
            )
            continue
        if node.output_port not in PORTS:
            add(
                "PIPELINE_PORT_TYPE_INVALID",
                f"node {node.node_id!r} declares unknown output port {node.output_port!r}",
                node.node_id,
                node.output_port,
            )
        elif node.output_port != KIND_OUTPUTS[node.kind]:
            add(
                "PIPELINE_PORT_TYPE_MISMATCH",
                f"node {node.node_id!r} of kind {node.kind!r} outputs "
                f"{KIND_OUTPUTS[node.kind]}, not {node.output_port}",
                node.node_id,
                node.output_port,
            )
    return node_by_id


def _index_edges(
    manifest: PipelineManifest, node_by_id: dict[str, PipelineNode], add: AddIssue
) -> tuple[dict[str, set[str]], dict[str, list[PipelineEdge]], dict[str, list[PipelineEdge]]]:
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_by_id}
    in_edges: dict[str, list[PipelineEdge]] = defaultdict(list)
    out_edges: dict[str, list[PipelineEdge]] = defaultdict(list)
    for edge in manifest.edges:
        source = node_by_id.get(edge.source_node)
        target = node_by_id.get(edge.target_node)
        if source is None:
            add(
                "PIPELINE_EDGE_UNKNOWN_NODE",
                f"edge source {edge.source_node!r} is not a declared node",
                edge.source_node,
                edge.source_port,
            )
            continue
        if target is None:
            add(
                "PIPELINE_EDGE_UNKNOWN_NODE",
                f"edge target {edge.target_node!r} is not a declared node",
                edge.target_node,
                edge.target_port,
            )
            continue
        invalid = False
        if edge.source_port not in PORTS:
            add(
                "PIPELINE_PORT_UNKNOWN",
                f"edge source port {edge.source_port!r} does not exist",
                source.node_id,
                edge.source_port,
            )
            invalid = True
        if edge.target_port not in PORTS:
            add(
                "PIPELINE_PORT_UNKNOWN",
                f"edge target port {edge.target_port!r} does not exist",
                target.node_id,
                edge.target_port,
            )
            invalid = True
        if not invalid:
            if edge.source_port != source.output_port:
                add(
                    "PIPELINE_PORT_TYPE_MISMATCH",
                    f"node {source.node_id!r} does not output {edge.source_port}",
                    source.node_id,
                    edge.source_port,
                )
                invalid = True
            elif target.kind not in KIND_INPUTS:
                invalid = True
            elif edge.target_port not in KIND_INPUTS[target.kind]:
                add(
                    "PIPELINE_PORT_TYPE_MISMATCH",
                    f"node {target.node_id!r} of kind {target.kind!r} does not accept "
                    f"{edge.target_port}",
                    target.node_id,
                    edge.target_port,
                )
                invalid = True
        if "execution_policy" in (source.kind, target.kind):
            policy_node = source if source.kind == "execution_policy" else target
            add(
                "PIPELINE_EXECUTION_POLICY_EDGE",
                f"execution policy node {policy_node.node_id!r} must not be wired into the graph",
                policy_node.node_id,
                policy_node.output_port,
            )
            invalid = True
        if invalid:
            continue
        adjacency[source.node_id].add(target.node_id)
        in_edges[target.node_id].append(edge)
        out_edges[source.node_id].append(edge)
    return adjacency, in_edges, out_edges


def _evaluation_order(
    node_by_id: dict[str, PipelineNode], adjacency: dict[str, set[str]], add: AddIssue
) -> tuple[str, ...]:
    indegree = {node_id: 0 for node_id in node_by_id}
    for targets in adjacency.values():
        for target in targets:
            indegree[target] += 1
    ready = [node_id for node_id, degree in indegree.items() if degree == 0]
    heapify(ready)
    order: list[str] = []
    while ready:
        node_id = heappop(ready)
        order.append(node_id)
        for target in sorted(adjacency[node_id]):
            indegree[target] -= 1
            if indegree[target] == 0:
                heappush(ready, target)
    if len(order) == len(node_by_id):
        return tuple(order)
    stuck = sorted(set(node_by_id) - set(order))
    add(
        "PIPELINE_CYCLE_DETECTED",
        "pipeline graph is not acyclic; nodes involved: " + ", ".join(stuck),
    )
    return ()


def _check_graph_rules(
    manifest: PipelineManifest,
    node_by_id: dict[str, PipelineNode],
    adjacency: dict[str, set[str]],
    in_edges: dict[str, list[PipelineEdge]],
    out_edges: dict[str, list[PipelineEdge]],
    add: AddIssue,
) -> None:
    by_kind: dict[str, list[PipelineNode]] = defaultdict(list)
    for node in node_by_id.values():
        by_kind[node.kind].append(node)

    datasets = by_kind["dataset_input"]
    if not datasets:
        add("PIPELINE_DATASET_INPUT_REQUIRED", "at least one dataset_input node is required")
    elif not _has_timeframe(manifest):
        add(
            "PIPELINE_DATASET_TIMEFRAME_REQUIRED",
            "no dataset timeframe constraint is declared",
            datasets[0].node_id,
        )

    for kind, required, unique in (
        ("sizing", "PIPELINE_SIZING_REQUIRED", "PIPELINE_SIZING_NOT_UNIQUE"),
        ("exits", "PIPELINE_EXIT_REQUIRED", "PIPELINE_EXIT_NOT_UNIQUE"),
    ):
        nodes = by_kind[kind]
        if not nodes:
            add(required, f"exactly one {kind} node is required")
        elif len(nodes) > 1:
            add(unique, f"{len(nodes)} {kind} nodes declared; exactly one is allowed")

    for target_id, edges in in_edges.items():
        if node_by_id[target_id].kind == "ensemble":
            continue
        per_port: dict[str, int] = defaultdict(int)
        for edge in edges:
            per_port[edge.target_port] += 1
        for port, count in sorted(per_port.items()):
            if count > 1:
                add(
                    "PIPELINE_AMBIGUOUS_FAN_IN",
                    f"node {target_id!r} receives {count} writers on port {port}",
                    target_id,
                    port,
                )

    for node in node_by_id.values():
        if node.kind in TERMINAL_KINDS:
            continue
        if not out_edges.get(node.node_id):
            add(
                "PIPELINE_UNCONSUMED_OUTPUT",
                f"node {node.node_id!r} outputs {node.output_port} into nothing",
                node.node_id,
                node.output_port,
            )

    reachable: set[str] = set()
    stack = [node_id for node_id, node in node_by_id.items() if node.kind in ROOT_KINDS]
    while stack:
        node_id = stack.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        stack.extend(adjacency[node_id])
    for node_id in sorted(set(node_by_id) - reachable):
        add("PIPELINE_UNREACHABLE_NODE", f"node {node_id!r} is not reachable from a root", node_id)


def _has_timeframe(manifest: PipelineManifest) -> bool:
    return any(
        key
        and timeframes
        and all(isinstance(timeframe, str) and timeframe.strip() for timeframe in timeframes)
        for key, timeframes in manifest.dataset_timeframe_constraints.items()
    )


def _check_ensemble(
    manifest: PipelineManifest,
    node_by_id: dict[str, PipelineNode],
    in_edges: dict[str, list[PipelineEdge]],
    add: AddIssue,
) -> None:
    ensemble_nodes = [node for node in node_by_id.values() if node.kind == "ensemble"]
    params = manifest.ensemble_parameters
    if len(ensemble_nodes) > 1:
        add(
            "PIPELINE_ENSEMBLE_NOT_UNIQUE",
            f"{len(ensemble_nodes)} ensemble nodes declared; exactly one is allowed",
        )
    if params and not ensemble_nodes:
        add(
            "PIPELINE_ENSEMBLE_PARAMS_ORPHANED",
            "ensemble parameters are declared without an ensemble node",
        )
        return
    if not ensemble_nodes:
        return
    ensemble = ensemble_nodes[0]
    if not isinstance(params, dict) or not params:
        add(
            "PIPELINE_ENSEMBLE_PARAMS_INVALID",
            f"ensemble node {ensemble.node_id!r} declares no combination parameters",
            ensemble.node_id,
            ensemble.output_port,
        )
        return
    _check_soft_vote(ensemble, node_by_id, in_edges, params, add)


def _check_soft_vote(
    ensemble: PipelineNode,
    node_by_id: dict[str, PipelineNode],
    in_edges: dict[str, list[PipelineEdge]],
    params: dict[str, Any],
    add: AddIssue,
) -> None:
    node_id = ensemble.node_id
    port = ensemble.output_port
    if params.get("mode") != "soft_vote":
        add(
            "PIPELINE_ENSEMBLE_MODE_UNSUPPORTED",
            f"ensemble {node_id!r} declares mode {params.get('mode')!r}; "
            "only 'soft_vote' is supported",
            node_id,
            port,
        )

    inputs = params.get("inputs")
    declared: list[str] | None = None
    if isinstance(inputs, (list, tuple)) and all(
        isinstance(item, str) and item for item in inputs
    ):
        declared = list(inputs)
        if len(declared) < 2:
            add(
                "PIPELINE_ENSEMBLE_INPUT_REQUIRED",
                f"ensemble {node_id!r} requires at least two inputs",
                node_id,
                port,
            )
        elif len(set(declared)) != len(declared):
            add(
                "PIPELINE_ENSEMBLE_INPUT_REQUIRED",
                f"ensemble {node_id!r} inputs must be distinct node ids",
                node_id,
                port,
            )
    else:
        add(
            "PIPELINE_ENSEMBLE_INPUT_REQUIRED",
            f"ensemble {node_id!r} inputs must be a list of ML/DL node ids",
            node_id,
            port,
        )

    if declared is not None:
        _check_weights(declared, params, add, node_id, port)
        threshold = params.get("threshold")
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not math.isfinite(threshold)
            or not 0 < threshold < 1
        ):
            add(
                "PIPELINE_ENSEMBLE_THRESHOLD_INVALID",
                f"ensemble {node_id!r} threshold must be a finite number in (0, 1)",
                node_id,
                port,
            )

    sources = {edge.source_node for edge in in_edges.get(node_id, ())}
    undelivered = sorted(sources - set(declared or ()))
    if undelivered:
        add(
            "PIPELINE_ENSEMBLE_INPUT_REQUIRED",
            f"ensemble {node_id!r} receives inputs that its parameters do not declare: "
            + ", ".join(undelivered),
            node_id,
            port,
        )

    for name in declared or ():
        node = node_by_id.get(name)
        if node is None:
            detail = "is not present in the graph"
        elif node.kind not in MODEL_KINDS:
            detail = f"is a {node.kind!r} node, not an ML/DL node"
        elif name not in sources:
            detail = "is not connected to the ensemble node"
        else:
            continue
        add(
            "PIPELINE_ABSTAIN_MISSING_MODEL_OUTPUT",
            f"ensemble {node_id!r} abstains: declared input {name!r} {detail}",
            node_id,
            port,
        )


def _check_weights(
    declared: list[str],
    params: dict[str, Any],
    add: AddIssue,
    node_id: str,
    port: str,
) -> None:
    weights = params.get("weights")
    reason: str | None
    if not isinstance(weights, dict):
        reason = "weights must map each declared input to a weight"
    elif set(weights) != set(declared):
        reason = "weights must cover exactly the declared inputs"
    else:
        total = 0.0
        reason = None
        for name in declared:
            value = weights[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                reason = f"weight for {name!r} must be a number"
                break
            if not math.isfinite(value) or value < 0:
                reason = f"weight for {name!r} must be a finite non-negative number"
                break
            total += float(value)
        else:
            if total <= 0:
                reason = "weights must sum to a positive value"
    if reason is not None:
        add(
            "PIPELINE_ENSEMBLE_WEIGHT_INVALID",
            f"ensemble {node_id!r} {reason}",
            node_id,
            port,
        )


def _resolve_components(
    manifest: PipelineManifest,
    node_by_id: dict[str, PipelineNode],
    strategies: StrategyService,
    models: ModelRegistry,
    add: AddIssue,
) -> tuple[ArtifactRef, ...]:
    refs = list(manifest.component_refs)
    consumed = [False] * len(refs)
    resolved: list[ArtifactRef] = []
    for node in node_by_id.values():
        expected_kind = DECISION_REF_KINDS.get(node.kind)
        if expected_kind is None:
            continue
        is_model = node.kind in MODEL_KINDS
        port = node.output_port if is_model else None
        same_id = [index for index, ref in enumerate(refs) if ref.id == node.node_id]
        candidates = [index for index in same_id if refs[index].kind == expected_kind]
        if not same_id:
            _report_binding(
                add,
                is_model,
                "PIPELINE_COMPONENT_REF_MISSING",
                f"no {expected_kind} component reference declares id {node.node_id!r}",
                node.node_id,
                port,
            )
            continue
        if not candidates:
            declared_kinds = ", ".join(sorted({refs[index].kind for index in same_id}))
            _report_binding(
                add,
                is_model,
                "PIPELINE_COMPONENT_REF_KIND_MISMATCH",
                f"node {node.node_id!r} needs a {expected_kind} reference but only "
                f"{declared_kinds} is declared",
                node.node_id,
                port,
            )
            continue
        if len(candidates) > 1:
            _report_binding(
                add,
                is_model,
                "PIPELINE_COMPONENT_REF_DUPLICATE",
                f"node {node.node_id!r} matches {len(candidates)} {expected_kind} references",
                node.node_id,
                port,
            )
            continue
        index = candidates[0]
        ref = refs[index]
        consumed[index] = True
        failure = _resolve_ref(node, ref, strategies, models)
        if failure is not None:
            _report_binding(
                add,
                is_model,
                "PIPELINE_COMPONENT_REF_UNRESOLVED",
                failure,
                node.node_id,
                port,
            )
            continue
        resolved.append(ref)

    for index, ref in enumerate(refs):
        if not consumed[index]:
            add(
                "PIPELINE_COMPONENT_REF_ORPHANED",
                f"component reference {ref.kind}:{ref.id}:{ref.version} is used by no node",
            )
    return tuple(sorted(resolved, key=lambda ref: (ref.kind, ref.id, ref.version, ref.sha256)))


def _report_binding(
    add: AddIssue, is_model: bool, code: str, detail: str, node_id: str, port: str | None
) -> None:
    """A broken model binding abstains; a broken strategy binding rejects."""
    if is_model:
        add(
            "PIPELINE_ABSTAIN_MISSING_MODEL_OUTPUT",
            f"node {node_id!r} abstains: {detail}",
            node_id,
            port,
        )
    else:
        add(code, detail, node_id, None)


def _resolve_ref(
    node: PipelineNode,
    ref: ArtifactRef,
    strategies: StrategyService,
    models: ModelRegistry,
) -> str | None:
    """Return a failure reason, or ``None`` once the component resolves."""
    if node.kind == "ta":
        try:
            strategies.get(ref)
        except (KeyError, ValueError) as exc:
            return f"strategy component {ref.id}:{ref.version} does not resolve ({exc})"
        return None
    try:
        models.load_verified(ref)
    except (ModelRegistryError, KeyError, ValueError) as exc:
        return f"model component {ref.id}:{ref.version} is unavailable ({exc})"
    return None
