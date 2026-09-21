"""Secret redaction and sensitive string sanitization."""

from __future__ import annotations

import re
from collections.abc import Sequence

# Standard sensitive patterns: API keys, Bearer tokens, Signatures, Hashes
_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*['\"]?)([\w\-]{8,})(['\"]?)"),
    re.compile(r"(?i)(secret[_-]?key\s*[:=]\s*['\"]?)([\w\-]{8,})(['\"]?)"),
    re.compile(r"(?i)(sign\s*[:=]\s*['\"]?)([0-9a-fA-F]{32,})(['\"]?)"),
    re.compile(r"(?i)(bearer\s+)([\w\-\.]{16,})"),
    re.compile(r"(?i)(password\s*[:=]\s*['\"]?)([^\s'\"]{4,})(['\"]?)"),
    re.compile(r"(?i)(token\s*[:=]\s*['\"]?)([\w\-]{16,})(['\"]?)"),
)


def redact_text(
    text: str,
    custom_secrets: Sequence[str] | None = None,
    replacement: str = "[REDACTED]",
) -> str:
    """Sanitize sensitive strings, credentials, and API secrets from output text."""
    if not text:
        return text

    redacted = text
    # 1. Custom exact string matches (e.g. active API key or secret in memory)
    if custom_secrets:
        for secret in custom_secrets:
            if secret and len(secret) >= 4:
                redacted = redacted.replace(secret, replacement)

    # 2. Regex patterns
    for pattern in _SECRET_PATTERNS:
        repl = (
            rf"\g<1>{replacement}\g<3>" if r"\g<3>" in pattern.pattern else rf"\g<1>{replacement}"
        )
        redacted = pattern.sub(repl, redacted)

    return redacted
