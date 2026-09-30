"""Read-only QuantOps tool implementations (RW7-01).

Allowlisted read-only discovery over existing typed service contracts.
Every tool maps to an existing public service read method; responses carry
``schema_version``/``request_id`` plus exactly one of ``data``/``error``.

Deliberately free of service-implementation imports: services arrive as
duck-typed capabilities, so this boundary can never transitively reach a
live writer, credential store, network client or production database. No
MCP transport package is required; the dispatcher exposes plain Python
callables. A real MCP transport would need a later change request.
"""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from indodax_lab.contracts.identity import ArtifactRef

SCHEMA_VERSION = "rw7-01-v1"

TOOL_ALLOWLIST: tuple[str, ...] = (
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

FORBIDDEN_TOOL_NAMES: tuple[str, ...] = (
    "submit_real_order",
    "withdraw",
    "direct_promote_live",
)

CODE_TOOL_UNKNOWN = "TOOL_UNKNOWN"
CODE_SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
CODE_DATA_INVALID = "DATA_INVALID"
CODE_NOT_FOUND = "NOT_FOUND"
CODE_TOOL_ERROR = "TOOL_ERROR"

_MAX_STRING_LENGTH = 512
_MAX_LIST_ITEMS = 64
_MAX_LIST_RESULTS = 500

_UNSAFE_SUBSTRINGS: tuple[str, ...] = (
    "..",
    "/",
    "\\",
    "\x00",
    "${",
    "{{",
    "--",
    ";",
)
_UNSAFE_WORD_REGEX = re.compile(
    r"(?i)\b(select|drop|insert|delete|update|union|exec|eval|import|pickle"
    r"|script|subprocess|system|popen)\b|\bos\.|\bsys\."
)
_SAFE_KEY_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")
_SHA256_REGEX = re.compile(r"^[a-f0-9]{64}$")


class ToolError(Exception):
    """Typed failure carrying a wire error code (never a synthetic success)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ReadCapabilities:
    """Duck-typed handles to existing public research services.

    Every field is optional; a tool whose service is absent answers
    SERVICE_UNAVAILABLE instead of inventing data. ``source_capabilities``
    accepts any object exposing ``pairs``/``timeframes``/``venue_symbols``
    (e.g. the DATA-07 ``CollectionCapabilities``) without importing it.
    """

    pairs: tuple[str, ...] | None = None
    timeframes: tuple[str, ...] | None = None
    venue_symbols: dict[str, str] | None = None
    dataset_registry: Any = None
    strategy_service: Any = None
    model_registry: Any = None
    pipeline_service: Any = None
    experiment_service: Any = None
    source_capabilities: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        source = self.source_capabilities
        if source is not None:
            if self.pairs is None and hasattr(source, "pairs"):
                self.pairs = tuple(source.pairs)
            if self.timeframes is None and hasattr(source, "timeframes"):
                self.timeframes = tuple(source.timeframes)
            if self.venue_symbols is None and hasattr(source, "venue_symbols"):
                self.venue_symbols = dict(source.venue_symbols)
        self.source_capabilities = None


def _check_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolError(CODE_DATA_INVALID, f"DATA_INVALID:{field_name}: nonempty string required")
    if len(value) > _MAX_STRING_LENGTH:
        raise ToolError(CODE_DATA_INVALID, f"DATA_INVALID:{field_name}: exceeds length limit")
    lowered = value.lower()
    for token in _UNSAFE_SUBSTRINGS:
        if token in value or token in lowered:
            raise ToolError(
                CODE_DATA_INVALID,
                f"DATA_INVALID:{field_name}: executable/path payload rejected by schema",
            )
    if _UNSAFE_WORD_REGEX.search(value):
        raise ToolError(
            CODE_DATA_INVALID,
            f"DATA_INVALID:{field_name}: executable/path payload rejected by schema",
        )
    return value


def _check_id(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ToolError(CODE_DATA_INVALID, f"DATA_INVALID:{field_name}: string required")
    return _check_text(value, field_name)


def _parse_ref(value: Any, field_name: str) -> ArtifactRef:
    if not isinstance(value, dict):
        raise ToolError(CODE_DATA_INVALID, f"DATA_INVALID:{field_name}: mapping required")
    allowed = {"kind", "id", "version", "sha256", "schema_version"}
    unknown = set(value) - allowed
    if unknown:
        raise ToolError(
            CODE_DATA_INVALID, f"DATA_INVALID:{field_name}: unknown fields {sorted(unknown)}"
        )
    for required in ("kind", "id", "version", "sha256"):
        if required not in value:
            raise ToolError(
                CODE_DATA_INVALID,
                f"DATA_INVALID:{field_name}: '{required}' is required; "
                "references are verified before use, never trusted by name",
            )
    cleaned = {key: _check_id(item, f"{field_name}.{key}") for key, item in value.items()}
    try:
        return ArtifactRef.model_validate(cleaned)
    except ValueError as exc:
        raise ToolError(CODE_DATA_INVALID, f"DATA_INVALID:{field_name}: {exc}") from exc


def _parse_iso_datetime(value: Any, field_name: str) -> datetime:
    text = _check_id(value, field_name)
    try:
        parsed = datetime.fromisoformat(text)
    except (ValueError, TypeError) as exc:
        raise ToolError(
            CODE_DATA_INVALID, f"DATA_INVALID:{field_name}: invalid datetime"
        ) from exc
    if parsed.tzinfo is None:
        raise ToolError(
            CODE_DATA_INVALID, f"DATA_INVALID:{field_name}: timezone-aware UTC required"
        )
    return parsed


def _parse_id_list(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ToolError(CODE_DATA_INVALID, f"DATA_INVALID:{field_name}: nonempty list required")
    if len(value) > _MAX_LIST_ITEMS:
        raise ToolError(CODE_DATA_INVALID, f"DATA_INVALID:{field_name}: exceeds item limit")
    return tuple(_check_id(item, f"{field_name}[]") for item in value)


def _validate_params(tool: str, params: Any) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise ToolError(CODE_DATA_INVALID, "DATA_INVALID:params: mapping required")
    for key in params:
        if not isinstance(key, str) or not _SAFE_KEY_REGEX.fullmatch(key):
            raise ToolError(CODE_DATA_INVALID, f"DATA_INVALID:params: illegal key {key!r}")

    def req_str(name: str) -> str:
        if name not in params:
            raise ToolError(CODE_DATA_INVALID, f"DATA_INVALID:{name}: required")
        return _check_id(params[name], name)

    def opt_str(name: str) -> str | None:
        if name not in params or params[name] is None:
            return None
        return _check_id(params[name], name)

    def only(names: set[str]) -> None:
        unknown = set(params) - names
        if unknown:
            raise ToolError(
                CODE_DATA_INVALID, f"DATA_INVALID: unknown params {sorted(unknown)}"
            )

    if tool == "list_pairs":
        only(set())
        return {}
    if tool == "find_dataset":
        only({"venue", "pair", "timeframe", "start", "end"})
        return {
            "venue": req_str("venue"),
            "pair": req_str("pair"),
            "timeframe": req_str("timeframe"),
            "start": _parse_iso_datetime(params.get("start"), "start"),
            "end": _parse_iso_datetime(params.get("end"), "end"),
        }
    if tool == "list_datasets":
        only({"venue", "pair", "timeframe"})
        return {
            "venue": opt_str("venue"),
            "pair": opt_str("pair"),
            "timeframe": opt_str("timeframe"),
        }
    if tool in {"get_dataset", "get_strategy", "get_model", "get_pipeline"}:
        only({"ref"})
        if "ref" not in params:
            raise ToolError(CODE_DATA_INVALID, "DATA_INVALID:ref: required")
        return {"ref": _parse_ref(params["ref"], "ref")}
    if tool in {"list_strategies", "list_models"}:
        only(set())
        return {}
    if tool in {"get_backtest_status", "get_backtest_result"}:
        only({"experiment_id"})
        return {"experiment_id": req_str("experiment_id")}
    if tool == "compare_experiments":
        only({"experiment_ids"})
        if "experiment_ids" not in params:
            raise ToolError(CODE_DATA_INVALID, "DATA_INVALID:experiment_ids: required")
        return {"experiment_ids": _parse_id_list(params["experiment_ids"], "experiment_ids")}
    raise ToolError(CODE_TOOL_UNKNOWN, f"TOOL_UNKNOWN:{tool}: not an allowlisted read-only tool")


def _require(service: Any, name: str, tool: str) -> Any:
    if service is None:
        raise ToolError(
            CODE_SERVICE_UNAVAILABLE,
            f"SERVICE_UNAVAILABLE:{tool}: '{name}' is not wired; no data invented",
        )
    return service


def _ref_dict(ref: ArtifactRef) -> dict[str, Any]:
    return {
        "kind": ref.kind,
        "id": ref.id,
        "version": ref.version,
        "sha256": ref.sha256,
        "schema_version": ref.schema_version,
    }


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ToolError(CODE_TOOL_ERROR, "TOOL_ERROR: non-finite value in service data")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ToolError(CODE_TOOL_ERROR, "TOOL_ERROR: non-finite value in service data")
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ArtifactRef):
        return _ref_dict(value)
    if isinstance(value, BaseModel):
        dumped = value.model_dump(mode="python")
        return {key: _jsonable(item) for key, item in sorted(dumped.items())}
    if isinstance(value, dict):
        ordered = sorted(value.items(), key=lambda kv: str(kv[0]))
        return {str(key): _jsonable(item) for key, item in ordered}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, bytes):
        digest = hashlib.sha256(value).hexdigest()
        return {"bytes_sha256": digest, "byte_length": len(value)}
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return {
            key: _jsonable(item)
            for key, item in sorted(vars(value).items())
            if not key.startswith("_")
        }
    return str(value)


def _catalog_entries(registry: Any) -> list[dict[str, Any]]:
    if hasattr(registry, "all_entries"):
        entries = registry.all_entries()
    elif hasattr(registry, "_catalog") and hasattr(registry._catalog, "all_entries"):
        entries = registry._catalog.all_entries()
    else:
        raise ToolError(
            CODE_SERVICE_UNAVAILABLE,
            "SERVICE_UNAVAILABLE:list_datasets: registry exposes no read listing",
        )
    if not isinstance(entries, list):
        raise ToolError(CODE_TOOL_ERROR, "TOOL_ERROR:list_datasets: unexpected listing shape")
    return copy.deepcopy(entries)


def _model_row(entry: Any) -> dict[str, Any]:
    manifest_ref = getattr(entry, "manifest_ref", None)
    return {
        "model_id": getattr(entry, "model_id", None),
        "version": getattr(entry, "version", None),
        "manifest_ref": _jsonable(manifest_ref) if manifest_ref is not None else None,
        "object_sha256": getattr(entry, "object_sha256", None),
        "registered": bool(getattr(entry, "registered", False)),
        "verified": bool(getattr(entry, "verified", False)),
        "compatible": bool(getattr(entry, "compatible", False)),
        "runtime_eligible": bool(getattr(entry, "runtime_eligible", False)),
        "reason": getattr(entry, "reason", None),
    }


def _run(tool: str, args: dict[str, Any], caps: ReadCapabilities) -> dict[str, Any]:
    if tool == "list_pairs":
        _require(caps.pairs, "pair catalog", tool)
        _require(caps.timeframes, "timeframe catalog", tool)
        return {
            "pairs": sorted(caps.pairs or ()),
            "timeframes": sorted(caps.timeframes or ()),
            "venue_symbols": _jsonable(dict(caps.venue_symbols or {})),
        }
    if tool == "find_dataset":
        registry = _require(caps.dataset_registry, "dataset_registry", tool)
        refs = registry.find(
            args["venue"], args["pair"], args["timeframe"], args["start"], args["end"]
        )
        return {"refs": [_ref_dict(ref) for ref in refs], "count": len(refs)}
    if tool == "list_datasets":
        registry = _require(caps.dataset_registry, "dataset_registry", tool)
        entries = _catalog_entries(registry)

        def _matches(entry: dict[str, Any]) -> bool:
            for key in ("venue", "pair", "timeframe"):
                wanted = args[key]
                if wanted is not None and str(entry.get(key, "")).lower() != wanted.lower():
                    return False
            return True

        kept = [entry for entry in entries if _matches(entry)]
        truncated = len(kept) > _MAX_LIST_RESULTS
        return {
            "entries": _jsonable(kept[:_MAX_LIST_RESULTS]),
            "count": len(kept),
            "truncated": truncated,
        }
    if tool == "get_dataset":
        registry = _require(caps.dataset_registry, "dataset_registry", tool)
        manifest = registry.get(args["ref"])
        return {"manifest": _jsonable(manifest)}
    if tool == "list_strategies":
        service = _require(caps.strategy_service, "strategy_service", tool)
        if hasattr(service, "component_metadata"):
            items = service.component_metadata()
        else:
            items = service.list_strategies()
        return {"strategies": _jsonable(list(items))}
    if tool == "get_strategy":
        service = _require(caps.strategy_service, "strategy_service", tool)
        return {"manifest": _jsonable(service.get(args["ref"]))}
    if tool == "list_models":
        registry = _require(caps.model_registry, "model_registry", tool)
        return {"models": [_model_row(entry) for entry in registry.list_models()]}
    if tool == "get_model":
        registry = _require(caps.model_registry, "model_registry", tool)
        predictor = registry.load_verified(args["ref"])
        return {
            "model_id": predictor.model_id,
            "loader_id": predictor.loader_id,
            "model_ref": _ref_dict(predictor.model_ref),
            "manifest": _jsonable(predictor.manifest),
        }
    if tool == "get_pipeline":
        service = _require(caps.pipeline_service, "pipeline_service", tool)
        store = getattr(service, "store", service)
        return {"manifest": _jsonable(store.get_published(args["ref"]))}
    if tool == "get_backtest_status":
        service = _require(caps.experiment_service, "experiment_service", tool)
        record = service.get(args["experiment_id"])
        return {
            "experiment_id": args["experiment_id"],
            "status": str(getattr(record, "status", "UNKNOWN")),
        }
    if tool == "get_backtest_result":
        service = _require(caps.experiment_service, "experiment_service", tool)
        return {"result": _jsonable(service.result(args["experiment_id"]))}
    if tool == "compare_experiments":
        service = _require(caps.experiment_service, "experiment_service", tool)
        return {"comparison": _jsonable(service.compare(list(args["experiment_ids"])))}
    raise ToolError(CODE_TOOL_UNKNOWN, f"TOOL_UNKNOWN:{tool}: not an allowlisted read-only tool")


def execute(tool: str, params: Any, caps: ReadCapabilities) -> dict[str, Any]:
    """Run one allowlisted read tool; raises ToolError/LookupError/ValueError."""
    args = _validate_params(tool, params)
    try:
        return _run(tool, args, caps)
    except ToolError:
        raise
    except (KeyError, LookupError) as exc:
        raise ToolError(CODE_NOT_FOUND, f"NOT_FOUND:{tool}: {exc}") from exc
    except ValueError as exc:
        raise ToolError(CODE_DATA_INVALID, f"DATA_INVALID:{tool}: {exc}") from exc
