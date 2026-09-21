"""Structured JSON logging with automatic credential redaction."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from indodax_lab.security.redaction import redact_text


class RedactingJsonFormatter(logging.Formatter):
    """Formats LogRecord as a single-line JSON string with credentials redacted."""

    def __init__(self, *args: Any, custom_secrets: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.custom_secrets = custom_secrets or []

    def format(self, record: logging.LogRecord) -> str:
        raw_msg = record.getMessage()
        safe_msg = redact_text(raw_msg, custom_secrets=self.custom_secrets)

        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": safe_msg,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            log_data["exception"] = redact_text(exc_text, custom_secrets=self.custom_secrets)

        return json.dumps(log_data)
