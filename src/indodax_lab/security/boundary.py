"""Security boundary enforcement, path traversal defense, and credential auditing (QA-02).

Guarantees:
1. QA-02-AC0: Security audit proves secret, artifact loader, and destructive paths are closed.
2. QA-02-AC1: Path traversal attacks and malicious/tampered artifacts are rejected fail-closed.
3. QA-02-AC2: Live trade and withdrawal credentials are strictly forbidden.
4. QA-02-AC3: Telegram allowlists are strictly enforced.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PathTraversalError(ValueError):
    """Raised when an artifact path attempts to escape the root directory."""


class SecurityViolationError(RuntimeError):
    """Raised when a security invariant or forbidden credential is detected."""


# ---------------------------------------------------------------------------
# Forbidden Credential Keywords (QA-02-AC2)
# ---------------------------------------------------------------------------

# Trade/withdrawal authority: the research lab must never hold these.
_CREDENTIAL_PATTERNS_TRADE_WITHDRAW = (
    "TRADE_KEY",
    "TRADE_SECRET",
    "TRADE_TOKEN",
    "WITHDRAW_KEY",
    "WITHDRAWAL_KEY",
    "WITHDRAW_SECRET",
    "WITHDRAWAL_SECRET",
    "LIVE_ORDER_SECRET",
    "PRIVATE_EXECUTION_KEY",
)

# Real credential names this project actually uses, plus the generic families an
# API key / API secret can hide behind. QA-02-F1: the previous list only covered
# trade/withdrawal variants, so INDODAX_API_KEY, INDODAX_SECRET_KEY and the generic
# API_KEY / API_SECRET / SECRET_KEY / PRIVATE_KEY forms passed the audit undetected.
_CREDENTIAL_PATTERNS_API = (
    "INDODAX_API_KEY",
    "INDODAX_SECRET_KEY",
    "API_KEY",
    "APIKEY",
    "API_SECRET",
    "APISECRET",
    "SECRET_KEY",
    "SECRETKEY",
    "PRIVATE_KEY",
    "PRIVATEKEY",
    "ACCESS_KEY",
    "ACCESSKEY",
    "SECRET_ACCESS_KEY",
)

# Ordered longest-prefix-first families so a specific name is reported as itself
# rather than as a generic family match.
_FORBIDDEN_CREDENTIAL_PATTERNS: tuple[str, ...] = tuple(
    sorted(
        _CREDENTIAL_PATTERNS_TRADE_WITHDRAW + _CREDENTIAL_PATTERNS_API,
        key=len,
        reverse=True,
    )
)

# ``*_API_KEY`` / ``*_SECRET*`` / ``*_PRIVATE_KEY`` style families, matched on
# underscore/dot/dash separated name components.
_CREDENTIAL_FAMILY_PATTERNS = (
    re.compile(r"(?:^|[_.\-])SECRETS?(?:$|[_.\-])"),
    re.compile(r"(?:^|[_.\-])API_?KEYS?(?:$|[_.\-])"),
    re.compile(r"(?:^|[_.\-])API_?SECRETS?(?:$|[_.\-])"),
    re.compile(r"(?:^|[_.\-])SECRET_?KEYS?(?:$|[_.\-])"),
    re.compile(r"(?:^|[_.\-])PRIVATE_?KEYS?(?:$|[_.\-])"),
    re.compile(r"(?:^|[_.\-])ACCESS_?KEYS?(?:$|[_.\-])"),
)

# Probed by the audit itself to prove the destructive-path boundary is closed.
_DESTRUCTIVE_ESCAPE_PROBE = "../../../etc/passwd"

# Pickle opcodes and protocol headers
_PICKLE_SIGNATURES = (
    b"\x80\x02",
    b"\x80\x03",
    b"\x80\x04",
    b"\x80\x05",
    b"c__builtin__",
    b"cbuiltins",
    b"cposix",
    b"cnt",
    b"cos\nsystem",
)


# ---------------------------------------------------------------------------
# Boundary Functions
# ---------------------------------------------------------------------------


def safe_resolve_artifact_path(base_dir: Path, target_subpath: str | Path) -> Path:
    """Safely resolve an artifact subpath, strictly rejecting traversal attacks (QA-02-AC1).

    Raises:
        PathTraversalError: If the target subpath escapes base_dir.
    """
    base_resolved = base_dir.resolve()
    target_str = str(target_subpath)

    # Reject traversal and foreign-platform absolute paths before host resolution.
    normalized_parts = target_str.replace("\\", "/").split("/")
    windows_path = PureWindowsPath(target_str)
    if windows_path.is_absolute() or windows_path.drive:
        raise PathTraversalError(
            f"PATH_TRAVERSAL_DETECTED: Absolute Windows path is forbidden: '{target_str}'."
        )
    if ".." in normalized_parts:
        raise PathTraversalError(
            f"PATH_TRAVERSAL_DETECTED: Relative path traversal ('..') detected in '{target_str}'."
        )

    # Resolve target
    if os.path.isabs(target_str):
        candidate = Path(target_str).resolve()
    else:
        candidate = (base_resolved / target_subpath).resolve()

    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        msg = (
            f"PATH_TRAVERSAL_DETECTED: Target path '{target_str}' "
            f"resolves outside base root '{base_resolved}'."
        )
        raise PathTraversalError(msg) from exc

    return candidate


def verify_artifact_bytes_safe(data: bytes) -> bool:
    """Verify that artifact bytes do not contain malicious executable payloads (QA-02-AC1).

    Rejects Python pickle bytecode fail-closed. Requires valid JSON or Parquet structure.

    Raises:
        SecurityViolationError: If pickle opcodes or suspicious bytecode are detected.
    """
    # 1. Check pickle signatures
    for sig in _PICKLE_SIGNATURES:
        if sig in data[:64] or (len(sig) > 4 and sig in data):
            msg = (
                "PICKLE_FORBIDDEN: Deserialization of arbitrary Python pickle payloads is "
                "strictly forbidden. All research lab artifacts must be plain JSON or Parquet."
            )
            raise SecurityViolationError(msg)

    # 2. Check JSON validity if text-like
    try:
        json.loads(data.decode("utf-8"))
        return True
    except (UnicodeDecodeError, json.JSONDecodeError):
        # If not JSON, check for Parquet magic header: 'PAR1'
        if data.startswith(b"PAR1") and data.endswith(b"PAR1"):
            return True

    raise SecurityViolationError(
        "UNSUPPORTED_ARTIFACT_FORMAT: Only validated JSON or Parquet artifacts are accepted."
    )


def _forbidden_credential_keys(env_dict: Mapping[str, str]) -> list[str]:
    """Return every environment key that looks like a trade/withdrawal/API credential."""
    offending: list[str] = []
    for env_key in env_dict:
        normalized = str(env_key).upper()
        if any(pattern in normalized for pattern in _FORBIDDEN_CREDENTIAL_PATTERNS) or any(
            family.search(normalized) for family in _CREDENTIAL_FAMILY_PATTERNS
        ):
            offending.append(str(env_key))
    return sorted(offending)


def audit_no_trade_withdraw_keys(env_dict: Mapping[str, str] | None = None) -> list[str]:
    """Verify that no live trading, withdrawal, or API credentials are present (QA-02-AC2).

    Every offending key is reported, not only the first one found: a partial audit that
    stops at the first match hides the remaining credentials.

    Raises:
        SecurityViolationError: If any trade, withdrawal, or API credential key is discovered.
    """
    env_to_check = dict(env_dict) if env_dict is not None else dict(os.environ)

    offending = _forbidden_credential_keys(env_to_check)
    if offending:
        listed = ", ".join(offending)
        msg = (
            f"FORBIDDEN_CREDENTIALS: forbidden credential key(s) discovered in environment: "
            f"{listed}. The research lab operates strictly in paper/shadow mode and must "
            "not hold live trading, withdrawal, or API signing credentials."
        )
        raise SecurityViolationError(msg)

    return []


# ---------------------------------------------------------------------------
# Audit Runner & Models (QA-02-AC0)
# ---------------------------------------------------------------------------


class SecurityAuditReport(BaseModel):
    """Immutable audit report summarizing security boundary compliance."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    status: str
    verified_checks: list[str]
    critical_findings_count: int = 0
    checks_executed: int = 0
    as_of_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SecurityAuditRunner:
    """Coordinates and certifies all security boundary checks for release qualification."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def run_audit(self, env_dict: Mapping[str, str] | None = None) -> SecurityAuditReport:
        """Execute boundary audit and produce verifiable report (QA-02-AC0).

        Every invariant is enforced with an explicit exception. ``assert`` is deliberately
        not used: it is stripped under ``python -O`` / ``PYTHONOPTIMIZE``, which would make
        the security boundary silently disappear in an optimized production run.
        """
        verified: list[str] = []

        # 1. Secret boundary audit (QA-02-AC2)
        audit_no_trade_withdraw_keys(env_dict)
        verified.append("SECRET_BOUNDARY_VERIFIED")

        # 2. Artifact loader & traversal audit (QA-02-AC1)
        test_subpath = "safe_dir/test_model.json"
        resolved = safe_resolve_artifact_path(self.base_dir, test_subpath)
        base_root = self.base_dir.resolve()
        if not resolved.is_relative_to(base_root):
            msg = (
                f"PATH_TRAVERSAL_DETECTED: resolved artifact '{resolved}' escapes base root "
                f"'{base_root}'."
            )
            raise SecurityViolationError(msg)
        verify_artifact_bytes_safe(b'{"status": "ok"}')
        verified.append("ARTIFACT_LOADER_VERIFIED")

        # 3. Destructive-path boundary (QA-02-AC0). The same traversal guard must refuse
        #    an escape target before any destructive operation is applied to it.
        try:
            safe_resolve_artifact_path(self.base_dir, _DESTRUCTIVE_ESCAPE_PROBE)
        except PathTraversalError:
            verified.append("DESTRUCTIVE_PATH_BOUNDARY_VERIFIED")
        else:
            msg = (
                "DESTRUCTIVE_PATH_ESCAPE_NOT_BLOCKED: the traversal guard resolved an "
                f"out-of-root target ('{_DESTRUCTIVE_ESCAPE_PROBE}') instead of rejecting it."
            )
            raise SecurityViolationError(msg)

        # 4. Telegram allowlist audit (QA-02-AC3)
        from indodax_lab.reporting.telegram import ReadOnlyTelegramReporter

        reporter = ReadOnlyTelegramReporter(bot_token="test_token", allowed_chat_ids=["10001"])
        if not reporter.is_authorized("10001"):
            msg = "TELEGRAM_ALLOWLIST_BROKEN: an allowlisted chat was rejected by the reporter."
            raise SecurityViolationError(msg)
        if reporter.is_authorized("99999"):
            msg = "TELEGRAM_ALLOWLIST_BROKEN: a non-allowlisted chat was authorized by the reporter."
            raise SecurityViolationError(msg)
        verified.append("TELEGRAM_ALLOWLIST_VERIFIED")

        return SecurityAuditReport(
            status="PASSED",
            verified_checks=verified,
            critical_findings_count=0,
            checks_executed=len(verified),
        )
