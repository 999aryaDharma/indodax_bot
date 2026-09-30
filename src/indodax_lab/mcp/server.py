"""Allowlisted read-only QuantOps MCP boundary server (RW7-01).

Plain-Python dispatcher over the read tools in
:mod:`indodax_lab.mcp.read_tools`. Unknown tools (including
``submit_real_order``/``withdraw``/``direct_promote_live``) are rejected;
every response carries ``schema_version``/``request_id`` plus exactly one of
``data``/``error``; each call appends a redacted request/outcome audit
record. No mutations, no credentials, no transport dependency.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from indodax_lab.mcp.read_tools import (
    CODE_DATA_INVALID,
    CODE_NOT_FOUND,
    CODE_SERVICE_UNAVAILABLE,
    CODE_TOOL_ERROR,
    CODE_TOOL_UNKNOWN,
    SCHEMA_VERSION,
    TOOL_ALLOWLIST,
    ReadCapabilities,
    ToolError,
    execute,
)

_MAX_AUDIT_RECORDS = 10000
_REDACT_KEY_HINTS = ("token", "key", "secret", "password", "auth", "credential")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(hint in lowered for hint in _REDACT_KEY_HINTS):
                redacted[str(key)] = "***"
            else:
                redacted[str(key)] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and len(value) > 128:
        return value[:128] + "…"
    return value


class QuantOpsReadServer:
    """Read-only dispatcher; owns no store and performs no writes."""

    def __init__(
        self,
        capabilities: ReadCapabilities | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        audit: list[dict[str, Any]] | None = None,
    ) -> None:
        self.capabilities = capabilities if capabilities is not None else ReadCapabilities()
        self._clock = clock or (lambda: datetime.now(UTC))
        self.audit: list[dict[str, Any]] = audit if audit is not None else []

    def list_tools(self) -> list[str]:
        """Return the explicit tool allowlist."""
        return list(TOOL_ALLOWLIST)

    def call(self, tool: Any, params: Any, request_id: Any) -> dict[str, Any]:
        """Dispatch one tool call and return the response envelope."""
        if isinstance(request_id, str) and request_id.strip():
            rid = request_id
        else:
            rid = "INVALID_REQUEST_ID"
        if len(rid) > 256:
            rid = rid[:256]
        name = tool if isinstance(tool, str) else ""
        if name not in TOOL_ALLOWLIST:
            label = name if isinstance(tool, str) else type(tool).__name__
            self._record_audit(rid, label[:128], params, CODE_TOOL_UNKNOWN)
            error = {
                "code": CODE_TOOL_UNKNOWN,
                "message": f"TOOL_UNKNOWN:{tool}: not an allowlisted read-only tool",
            }
            return {
                "schema_version": SCHEMA_VERSION,
                "request_id": rid,
                "data": None,
                "error": error,
            }
        try:
            data = execute(name, params, self.capabilities)
        except ToolError as exc:
            self._record_audit(rid, name, params, exc.code)
            return {
                "schema_version": SCHEMA_VERSION,
                "request_id": rid,
                "data": None,
                "error": {"code": exc.code, "message": exc.message},
            }
        except Exception as exc:  # fail closed: never a synthetic success
            self._record_audit(rid, name, params, CODE_TOOL_ERROR)
            return {
                "schema_version": SCHEMA_VERSION,
                "request_id": rid,
                "data": None,
                "error": {"code": CODE_TOOL_ERROR, "message": f"TOOL_ERROR:{name}: {exc}"},
            }
        self._record_audit(rid, name, params, "OK")
        return {
            "schema_version": SCHEMA_VERSION,
            "request_id": rid,
            "data": data,
            "error": None,
        }

    def _record_audit(self, request_id: str, tool: str, params: Any, code: str) -> None:
        try:
            at = self._clock()
            stamp = at.isoformat() if isinstance(at, datetime) else str(at)
        except Exception:
            stamp = "CLOCK_UNAVAILABLE"
        try:
            redacted = _redact(params) if isinstance(params, dict) else {"params": "NON_MAPPING"}
        except Exception:
            redacted = {"params": "UNREDACTABLE"}
        self.audit.append(
            {
                "request_id": request_id,
                "tool": tool,
                "params": redacted,
                "outcome": code,
                "at": stamp,
            }
        )
        while len(self.audit) > _MAX_AUDIT_RECORDS:
            del self.audit[0]


__all__ = [
    "CODE_DATA_INVALID",
    "CODE_NOT_FOUND",
    "CODE_SERVICE_UNAVAILABLE",
    "CODE_TOOL_ERROR",
    "CODE_TOOL_UNKNOWN",
    "SCHEMA_VERSION",
    "QuantOpsReadServer",
    "ReadCapabilities",
]
