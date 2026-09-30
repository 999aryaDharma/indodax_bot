"""Read-only QuantOps MCP boundary (RW7-01).

Allowlisted read-only discovery over existing typed service contracts.
No mutations, no credentials, no network, no live databases. Fake clocks
and tmp_path only.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_T0 = datetime(2024, 1, 1, tzinfo=UTC)
_T1 = datetime(2024, 1, 10, tzinfo=UTC)

_ALLOWLIST = (
    "list_pairs",
    "find_dataset",
    "list_datasets",
    "get_dataset",
    "list_strategies",
    "get_strategy",
    "list_models",
    "get_model",
    "get_pipeline",
    "get_backtest_status",
    "get_backtest_result",
    "compare_experiments",
)
_FORBIDDEN_TOOLS = ("submit_real_order", "withdraw", "direct_promote_live")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_partition(bar_count: int = 100) -> dict[str, Any]:
    content = f"{bar_count}:{_T0.isoformat()}:{_T1.isoformat()}".encode()
    return {
        "row_count": bar_count,
        "sha256": hashlib.sha256(content).hexdigest(),
        "start_ts": _T0.isoformat(),
        "end_ts": _T1.isoformat(),
        "bytes": content,
    }


def _make_registry(tmp_path: Path, fetch_calls: list | None = None):
    from indodax_lab.data.dataset_registry import DatasetRegistry, DatasetRequest

    def provider(req: DatasetRequest) -> list[dict[str, Any]]:
        if fetch_calls is not None:
            fetch_calls.append(req)
        return [_make_partition()]

    registry = DatasetRegistry(
        root=tmp_path / "store",
        catalog_path=tmp_path / "catalog.json",
        fetch_provider=provider,
    )
    request = DatasetRequest(
        venue="indodax",
        pair="btc_idr",
        timeframe="1h",
        start=_T0,
        end=_T1,
        source_id="indodax_raw",
        source_version="v1",
    )
    manifest = registry.create(request)
    return registry, manifest


def _make_server(
    tmp_path: Path,
    *,
    with_services: bool = True,
    models=None,
    experiments=None,
):
    from indodax_lab.data.selectable_collection import CollectionCapabilities
    from indodax_lab.mcp.server import QuantOpsReadServer, ReadCapabilities
    from indodax_lab.models.registry import ModelRegistry
    from indodax_lab.strategies.store import StrategyService, StrategyStore

    registry, manifest = _make_registry(tmp_path / "data")
    if not with_services:
        return QuantOpsReadServer(ReadCapabilities()), registry, manifest
    store = StrategyStore(tmp_path / "strategies.sqlite")
    strategies = StrategyService(store)
    model_registry = models if models is not None else ModelRegistry(tmp_path / "models")
    caps = ReadCapabilities(
        source_capabilities=CollectionCapabilities.defaults(),
        dataset_registry=registry,
        strategy_service=strategies,
        model_registry=model_registry,
        experiment_service=experiments,
    )
    return QuantOpsReadServer(caps), registry, manifest


def _snapshot(paths: list[Path]) -> dict[str, str]:
    return {str(p): _sha(p) for p in paths if p.exists()}


def _store_files(tmp_path: Path) -> list[Path]:
    return [p for p in tmp_path.rglob("*") if p.is_file()]


def test_rw7_01_0(tmp_path: Path) -> None:
    """RW7-01-AC0: read tools return registry truth without mutation."""
    from indodax_lab.models.registry import ModelRegistry

    server, registry, manifest = _make_server(tmp_path)
    before = _snapshot(_store_files(tmp_path))
    expected_ref = manifest.to_artifact_ref()

    pairs = server.call("list_pairs", {}, "req-0a")
    assert pairs["schema_version"] and pairs["request_id"] == "req-0a"
    assert pairs["error"] is None
    assert "btc_idr" in pairs["data"]["pairs"]
    assert "1h" in pairs["data"]["timeframes"]

    found = server.call(
        "find_dataset",
        {
            "venue": "indodax",
            "pair": "btc_idr",
            "timeframe": "1h",
            "start": _T0.isoformat(),
            "end": _T1.isoformat(),
        },
        "req-0b",
    )
    assert found["error"] is None, found
    assert len(found["data"]["refs"]) == 1
    assert found["data"]["refs"][0]["sha256"] == expected_ref.sha256

    ref = found["data"]["refs"][0]
    got = server.call("get_dataset", {"ref": ref}, "req-0c")
    assert got["error"] is None, got
    assert got["data"]["manifest"]["dataset_id"] == manifest.dataset_id
    assert got["data"]["manifest"]["bar_count"] == 100

    listed = server.call("list_datasets", {"pair": "btc_idr"}, "req-0d")
    assert listed["error"] is None, listed
    assert any(e["dataset_id"] == manifest.dataset_id for e in listed["data"]["entries"])

    strategies = server.call("list_strategies", {}, "req-0e")
    assert strategies["error"] is None, strategies
    ids = {s["component_id"] for s in strategies["data"]["strategies"]}
    assert {"C02", "C07"} <= ids

    models = server.call("list_models", {}, "req-0f")
    assert models["error"] is None, models
    assert models["data"]["models"] == []

    ghost = server.call("get_backtest_status", {"experiment_id": "exp_ghost"}, "req-0g")
    assert ghost["data"] is None
    assert ghost["error"]["code"] == "SERVICE_UNAVAILABLE"

    after = _snapshot(_store_files(tmp_path))
    assert before == after
    assert isinstance(ModelRegistry, type)


def test_rw7_01_1(tmp_path: Path) -> None:
    """RW7-01-AC1: unknown submit_real_order/withdraw/direct_promote_live rejects."""
    server, registry, _ = _make_server(tmp_path)
    before = _snapshot(_store_files(tmp_path))

    for tool in (*_FORBIDDEN_TOOLS, "delete_everything"):
        resp = server.call(tool, {}, f"req-1-{tool}")
        assert resp["data"] is None
        assert resp["error"] is not None
        assert resp["error"]["code"] == "TOOL_UNKNOWN"
        assert resp["request_id"] == f"req-1-{tool}"

    assert set(server.list_tools()) == set(_ALLOWLIST)
    for forbidden in _FORBIDDEN_TOOLS:
        assert forbidden not in server.list_tools()

    after = _snapshot(_store_files(tmp_path))
    assert before == after

    # Transitive import boundary: mcp modules must not reach a live writer.
    repo_root = Path(__file__).resolve().parents[2]
    probe = (
        "import sys, json; "
        "import indodax_lab.mcp.server, indodax_lab.mcp.read_tools; "
        "bad = ['live', 'production', 'execution', 'trading_venue', 'shadow_venue', "
        "'simulator_venue', 'place_order', 'withdraw', 'credential', 'telegram', "
        "'order_manager', 'oms']; "
        "hits = sorted({m for m in sys.modules if any(k in m.lower() for k in bad)}); "
        "print(json.dumps(hits))"
    )
    env = dict(os.environ, PYTHONPATH=str(repo_root / "src"))
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        env=env,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout.strip()) == []

    for name in ("indodax_lab/mcp/server.py", "indodax_lab/mcp/read_tools.py"):
        tree = ast.parse((repo_root / "src" / name).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module)
        assert not any(
            any(k in mod.lower() for k in ("live", "production", "execution", "venue"))
            for mod in imported
        ), imported
        assert not any(
            isinstance(node, ast.Call)
            and getattr(getattr(node, "func", None), "id", "") in {"eval", "exec"}
            for node in ast.walk(tree)
        )


def test_rw7_01_2(tmp_path: Path) -> None:
    """RW7-01-AC2: traversal/SQL/code payloads are data rejected by schema."""
    server, registry, manifest = _make_server(tmp_path)
    before = _snapshot(_store_files(tmp_path))

    evil = [
        "../../etc/passwd",
        "/etc/shadow",
        "C:\\Windows\\win.ini",
        "nested/../../../secret.env",
        "1h; DROP TABLE datasets",
        "SELECT * FROM datasets",
        "__import__('os').system('id')",
        "eval(1+1)",
        "${HOME}",
        "{{7*7}}",
        "pickle.loads",
        "x" * 600,
    ]
    ref = {"kind": "dataset", "id": manifest.dataset_id, "version": "v1", "sha256": "0" * 64}
    for i, payload in enumerate(evil):
        r1 = server.call(
            "find_dataset",
            {
                "venue": "indodax",
                "pair": payload,
                "timeframe": "1h",
                "start": _T0.isoformat(),
                "end": _T1.isoformat(),
            },
            f"req-2a-{i}",
        )
        assert r1["data"] is None and r1["error"]["code"] == "DATA_INVALID", payload
        r2 = server.call("get_dataset", {"ref": {**ref, "id": payload}}, f"req-2b-{i}")
        assert r2["data"] is None and r2["error"]["code"] == "DATA_INVALID", payload

    r3 = server.call("compare_experiments", {"experiment_ids": evil[:3]}, "req-2c")
    assert r3["data"] is None and r3["error"]["code"] == "DATA_INVALID"
    r4 = server.call("find_dataset", ["not", "a", "dict"], "req-2d")  # type: ignore[arg-type]
    assert r4["data"] is None and r4["error"]["code"] == "DATA_INVALID"
    r5 = server.call(
        "get_dataset", {"ref": ref, "extra_param": "nope"}, "req-2e"
    )
    assert r5["data"] is None and r5["error"]["code"] == "DATA_INVALID"

    after = _snapshot(_store_files(tmp_path))
    assert before == after


def test_rw7_01_3(tmp_path: Path) -> None:
    """RW7-01-AC3: missing service gives unavailable error, never synthetic success."""
    server, _, _ = _make_server(tmp_path, with_services=False)
    valid = {
        "list_pairs": {},
        "find_dataset": {
            "venue": "indodax",
            "pair": "btc_idr",
            "timeframe": "1h",
            "start": _T0.isoformat(),
            "end": _T1.isoformat(),
        },
        "list_datasets": {},
        "get_dataset": {
            "ref": {"kind": "dataset", "id": "ds_x", "version": "v1", "sha256": "0" * 64},
        },
        "list_strategies": {},
        "get_strategy": {
            "ref": {
                "kind": "strategy_manifest",
                "id": "C07",
                "version": "1.0.0",
                "sha256": "0" * 64,
            },
        },
        "list_models": {},
        "get_model": {
            "ref": {
                "kind": "model_manifest",
                "id": "M01",
                "version": "1.0.0",
                "sha256": "0" * 64,
            },
        },
        "get_pipeline": {
            "ref": {
                "kind": "pipeline_manifest",
                "id": "P01",
                "version": "1.0.0",
                "sha256": "0" * 64,
            },
        },
        "get_backtest_status": {"experiment_id": "exp_abc"},
        "get_backtest_result": {"experiment_id": "exp_abc"},
        "compare_experiments": {"experiment_ids": ["exp_a", "exp_b"]},
    }
    assert set(valid) == set(_ALLOWLIST)
    for tool, params in valid.items():
        resp = server.call(tool, params, f"req-3-{tool}")
        assert resp["data"] is None, tool
        assert resp["error"] is not None, tool
        assert resp["error"]["code"] == "SERVICE_UNAVAILABLE", tool
        assert resp["error"]["message"], tool


def test_rw7_01_program_4(tmp_path: Path) -> None:
    """RW7-01-AC4: source coverage and model readiness, explicit unavailable reasons."""
    from indodax_lab.data.selectable_collection import CollectionCapabilities

    server, _, _ = _make_server(tmp_path)
    coverage = server.call("list_pairs", {}, "req-4a")
    assert coverage["error"] is None, coverage
    assert set(CollectionCapabilities.defaults().pairs) <= set(coverage["data"]["pairs"])
    assert "1h" in coverage["data"]["timeframes"]

    class _Entry:
        def __init__(self, **kw: Any) -> None:
            self.__dict__.update(kw)

    class _StubModels:
        def list_models(self) -> tuple:
            return (
                _Entry(
                    model_id="M01",
                    version="1.0.0",
                    manifest_ref=None,
                    object_sha256="0" * 64,
                    registered=True,
                    verified=False,
                    compatible=False,
                    runtime_eligible=False,
                    reason="MODEL_NOT_VERIFIED",
                ),
            )

    from indodax_lab.mcp.server import QuantOpsReadServer, ReadCapabilities

    ready_server = QuantOpsReadServer(
        ReadCapabilities(
            source_capabilities=CollectionCapabilities.defaults(),
            model_registry=_StubModels(),
        )
    )
    readiness = ready_server.call("list_models", {}, "req-4b")
    assert readiness["error"] is None, readiness
    rows = readiness["data"]["models"]
    assert len(rows) == 1
    assert rows[0]["runtime_eligible"] is False
    assert rows[0]["reason"] == "MODEL_NOT_VERIFIED"

    bare, _, _ = _make_server(tmp_path / "bare", with_services=False)
    missing_models = bare.call("list_models", {}, "req-4c")
    assert missing_models["data"] is None
    assert missing_models["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert "model" in missing_models["error"]["message"].lower()
    missing_pairs = bare.call("list_pairs", {}, "req-4d")
    assert missing_pairs["data"] is None
    assert missing_pairs["error"]["code"] == "SERVICE_UNAVAILABLE"
