"""Read-only Telegram research status and delivery dispatcher (REPORT-02).

Guarantees:
1. REPORT-02-AC0: Telegram displays research queue, champion, and health status under chat authorization.
2. REPORT-02-AC1: Unauthorized chats are rejected without revealing holdings or internal balances (UnauthorizedChatError).
3. REPORT-02-AC2: Special markdown characters are escaped and secrets/tokens are redacted.
4. REPORT-02-AC3: Rate-limit retry does not send duplicate notifications (idempotent delivery).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import re
from typing import Any, Sequence
from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.paper.portfolio import PaperPosition


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UnauthorizedChatError(PermissionError):
    """Raised when an unauthorized chat ID attempts to request status or holdings."""


# ---------------------------------------------------------------------------
# Sanitization & Escaping Helpers (REPORT-02-AC2)
# ---------------------------------------------------------------------------

_MD2_SPECIAL_CHARS = ["\\", "_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
_BOT_TOKEN_REGEX = re.compile(r"\b\d{8,11}:[A-Za-z0-9_-]{35}\b")
_GENERIC_KEY_REGEX = re.compile(r"\b(?:sk_live_[a-zA-Z0-9]+|indodax_secret_[a-zA-Z0-9]+)\b")


def escape_telegram_markdown(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2 compatibility.

    All special characters are prefixed with a backslash.
    """
    if not text:
        return text
    escaped = text
    # Escape backslash first to prevent double-escaping later additions
    escaped = escaped.replace("\\", "\\\\")
    for char in _MD2_SPECIAL_CHARS[1:]:
        escaped = escaped.replace(char, f"\\{char}")
    return escaped


def redact_secrets(text: str, extra_secrets: Sequence[str] = ()) -> str:
    """Redact Telegram bot tokens, API keys, and custom secret tokens from string."""
    if not text:
        return text

    redacted = _BOT_TOKEN_REGEX.sub("[REDACTED_BOT_TOKEN]", text)
    redacted = _GENERIC_KEY_REGEX.sub("[REDACTED_SECRET]", redacted)

    for secret in extra_secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED_SECRET]")

    return redacted


# ---------------------------------------------------------------------------
# Domain Models (REPORT-02-AC0)
# ---------------------------------------------------------------------------


class ResearchQueueStatus(BaseModel):
    """Queue activity and task progress in the research pipeline."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    pending_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    active_task_ids: list[str] = Field(default_factory=list)


class ChampionStatus(BaseModel):
    """Current active champion strategy state and forward longevity."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    champion_id: str
    champion_version: str
    forward_days: int = 0
    closed_trades: int = 0
    promoted_at: datetime | None = None


class SystemHealthStatus(BaseModel):
    """Operational health, lock leases, and node status."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    status: str = "HEALTHY"
    single_writer_locked: bool = True
    active_writer: str | None = None
    uptime_seconds: float = 0.0
    as_of: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResearchHoldingsStatus(BaseModel):
    """Paper capital allocations and open positions in shared ledger."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    available_cash: Decimal = Decimal("500000.00")
    open_positions: list[PaperPosition] = Field(default_factory=list)
    total_cost_basis: Decimal = Decimal("0.00")


class TelegramDeliveryResult(BaseModel):
    """Audit log of message delivery attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    success: bool
    chat_id: str
    idempotency_key: str
    message_id: str | int | None = None
    retries_attempted: int = 0
    error_message: str | None = None
    delivered_at: datetime | None = None


# ---------------------------------------------------------------------------
# Status Formatter
# ---------------------------------------------------------------------------


def format_research_status(
    queue: ResearchQueueStatus,
    champion: ChampionStatus,
    health: SystemHealthStatus,
    holdings: ResearchHoldingsStatus | None = None,
) -> str:
    """Format a compact, read-only research report for Telegram."""
    as_of_str = health.as_of.strftime("%Y-%m-%d %H:%M:%S UTC")
    active_tasks_str = ", ".join(queue.active_task_ids) if queue.active_task_ids else "None"

    lines = [
        "🔬 *Indodax Research Lab Status*",
        f"📅 `As of: {as_of_str}`",
        "",
        "📊 *Research Queue:*",
        f"• Pending: {queue.pending_tasks} | Running: {queue.running_tasks} | Completed: {queue.completed_tasks} | Failed: {queue.failed_tasks}",
        f"• Active: `{active_tasks_str}`",
        "",
        "🏆 *Champion Strategy:*",
        f"• ID: `{champion.champion_id}` (v{champion.champion_version})",
        f"• Forward: {champion.forward_days} days | Trades: {champion.closed_trades}",
        "",
        "🩺 *System Health:*",
        f"• Status: `{health.status}`",
        f"• Writer Lock: `{'LOCKED' if health.single_writer_locked else 'FREE'}` (writer: `{health.active_writer or 'None'}`)",
    ]

    if holdings is not None:
        lines.extend([
            "",
            "💰 *Paper Capital & Holdings:*",
            f"• Available Cash: `Rp {holdings.available_cash:,.2f}`",
            f"• Open Positions: {len(holdings.open_positions)}",
        ])
        for pos in holdings.open_positions:
            lines.append(f"  - `{pos.pair.upper()}`: `Rp {pos.cost_basis:,.2f}` (candidate: `{pos.candidate_id}`)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ReadOnlyTelegramReporter
# ---------------------------------------------------------------------------


class ReadOnlyTelegramReporter:
    """Read-only Telegram status reporter enforcing chat authorization and idempotency."""

    def __init__(
        self,
        bot_token: str,
        allowed_chat_ids: Sequence[str | int],
        transport: Any = None,
        max_retries: int = 3,
    ) -> None:
        self.bot_token = bot_token
        self.allowed_chat_ids: set[str] = {str(cid) for cid in allowed_chat_ids}
        self.transport = transport
        self.max_retries = max_retries
        self._sent_idempotency_keys: dict[str, TelegramDeliveryResult] = {}
        self._delivery_log: list[TelegramDeliveryResult] = []

    def is_authorized(self, chat_id: str | int) -> bool:
        """Verify whether chat_id is in the authorized allowlist."""
        return str(chat_id) in self.allowed_chat_ids

    def get_status_report(
        self,
        chat_id: str | int,
        queue: ResearchQueueStatus,
        champion: ChampionStatus,
        health: SystemHealthStatus,
        holdings: ResearchHoldingsStatus | None = None,
    ) -> str:
        """Generate formatted research status for an authorized chat.

        Raises:
            UnauthorizedChatError: If chat_id is not authorized (REPORT-02-AC1).
        """
        if not self.is_authorized(chat_id):
            raise UnauthorizedChatError(
                f"UNAUTHORIZED_CHAT: Chat ID '{chat_id}' access denied. Unauthorized chat cannot view research status."
            )

        raw_report = format_research_status(queue, champion, health, holdings)
        redacted = redact_secrets(raw_report, extra_secrets=[self.bot_token])
        return redacted

    def send_report(
        self,
        chat_id: str | int,
        text: str,
        idempotency_key: str,
    ) -> TelegramDeliveryResult:
        """Deliver report text to an authorized chat, with rate-limit retry and deduplication.

        Raises:
            UnauthorizedChatError: If chat_id is not authorized.
        """
        str_chat_id = str(chat_id)
        if not self.is_authorized(str_chat_id):
            raise UnauthorizedChatError(
                f"UNAUTHORIZED_CHAT: Chat ID '{str_chat_id}' access denied. Unauthorized chat cannot receive research reports."
            )

        # REPORT-02-AC3: Deduplication guard
        if idempotency_key in self._sent_idempotency_keys:
            return self._sent_idempotency_keys[idempotency_key]

        sanitized_text = redact_secrets(text, extra_secrets=[self.bot_token])

        # If no transport provided, treat as dry-run / success
        if self.transport is None:
            result = TelegramDeliveryResult(
                success=True,
                chat_id=str_chat_id,
                idempotency_key=idempotency_key,
                message_id="mock_msg_001",
                retries_attempted=0,
                delivered_at=datetime.now(UTC),
            )
            self._sent_idempotency_keys[idempotency_key] = result
            self._delivery_log.append(result)
            return result

        retries = 0
        last_error: Exception | None = None

        while retries <= self.max_retries:
            try:
                resp = self.transport.send_message(
                    chat_id=str_chat_id,
                    text=sanitized_text,
                )
                msg_id = resp.get("message_id") if isinstance(resp, dict) else getattr(resp, "message_id", None)
                result = TelegramDeliveryResult(
                    success=True,
                    chat_id=str_chat_id,
                    idempotency_key=idempotency_key,
                    message_id=msg_id,
                    retries_attempted=retries,
                    delivered_at=datetime.now(UTC),
                )
                self._sent_idempotency_keys[idempotency_key] = result
                self._delivery_log.append(result)
                return result
            except Exception as exc:
                retries += 1
                last_error = exc
                if retries > self.max_retries:
                    break

        # Max retries exceeded
        failed_result = TelegramDeliveryResult(
            success=False,
            chat_id=str_chat_id,
            idempotency_key=idempotency_key,
            retries_attempted=retries - 1,
            error_message=str(last_error),
        )
        self._delivery_log.append(failed_result)
        return failed_result
