"""Integration and contract tests for read-only Telegram research status (REPORT-02).

Guarantees:
1. REPORT-02-AC0: Telegram displays queue, champion, and health read-only under chat authorization (test_report_02_valid_contract).
2. REPORT-02-AC1: Unauthorized chats are rejected without revealing holdings (test_report_02_contract_1).
3. REPORT-02-AC2: Special markdown characters are escaped and bot tokens/secrets are redacted (test_report_02_contract_2).
4. REPORT-02-AC3: Rate-limit retry does not send duplicate notifications (test_report_02_contract_3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
import pytest

from indodax_lab.paper.portfolio import PaperPosition
from indodax_lab.reporting.telegram import (
    ChampionStatus,
    ReadOnlyTelegramReporter,
    ResearchHoldingsStatus,
    ResearchQueueStatus,
    SystemHealthStatus,
    UnauthorizedChatError,
    escape_telegram_markdown,
    format_research_status,
    redact_secrets,
)


def test_report_02_valid_contract() -> None:
    """AC0: Telegram menampilkan queue, champion dan health secara read-only dengan otorisasi chat."""
    allowed_chat_id = "12345678"
    reporter = ReadOnlyTelegramReporter(
        bot_token="test_token_123456",
        allowed_chat_ids=[allowed_chat_id],
    )

    queue = ResearchQueueStatus(
        pending_tasks=2,
        running_tasks=1,
        completed_tasks=10,
        failed_tasks=0,
        active_task_ids=["task_rf_regime_eval"],
    )
    champion = ChampionStatus(
        champion_id="m01_momentum_v1",
        champion_version="1.0.0",
        forward_days=95,
        closed_trades=120,
        promoted_at=datetime(2026, 9, 1, 0, 0, 0, tzinfo=UTC),
    )
    health = SystemHealthStatus(
        status="HEALTHY",
        single_writer_locked=True,
        active_writer="lab_node_1",
        uptime_seconds=3600.0,
    )
    holdings = ResearchHoldingsStatus(
        available_cash=Decimal("400000.00"),
        open_positions=[
            PaperPosition(
                position_id="pos_evt_001",
                candidate_id="m01_momentum_v1",
                pair="btc_idr",
                cost_basis=Decimal("100000.00"),
                entry_price=Decimal("950000000.00"),
                quantity=Decimal("0.00010526"),
                opened_at=datetime.now(UTC),
            )
        ],
        total_cost_basis=Decimal("100000.00"),
    )

    # Valid authorized query returns formatted read-only status
    report_text = reporter.get_status_report(
        chat_id=allowed_chat_id,
        queue=queue,
        champion=champion,
        health=health,
        holdings=holdings,
    )

    assert "Indodax Research Lab Status" in report_text
    assert "m01_momentum_v1" in report_text
    assert "95" in report_text
    assert "HEALTHY" in report_text
    assert "task_rf_regime_eval" in report_text
    assert "400,000.00" in report_text


def test_report_02_contract_1() -> None:
    """AC1: Unauthorized chat tidak mendapat holdings."""
    allowed_chat_id = "12345678"
    unauthorized_chat_id = "99999999"

    reporter = ReadOnlyTelegramReporter(
        bot_token="test_token_123456",
        allowed_chat_ids=[allowed_chat_id],
    )

    holdings = ResearchHoldingsStatus(
        available_cash=Decimal("500000.00"),
        open_positions=[],
        total_cost_basis=Decimal("0.00"),
    )

    # Request from unauthorized chat MUST raise UnauthorizedChatError
    with pytest.raises(UnauthorizedChatError) as exc_info:
        reporter.get_status_report(
            chat_id=unauthorized_chat_id,
            queue=ResearchQueueStatus(),
            champion=ChampionStatus(champion_id="c1", champion_version="1.0.0"),
            health=SystemHealthStatus(),
            holdings=holdings,
        )

    err_msg = str(exc_info.value)
    # Holdings, balance, or sensitive state must never appear in the unauthorized error or output
    assert "500000" not in err_msg
    assert "holdings" not in err_msg.lower() or "denied" in err_msg.lower()


def test_report_02_contract_2() -> None:
    """AC2: Markdown escaped dan token redacted."""
    # 1. Escaping special markdown characters
    raw_text = "Status: OK! [v1.0.0] (score=0.85) - {test_tag} & price > 100 + 5 = 105 | host.local"
    escaped = escape_telegram_markdown(raw_text)

    for ch in ["!", "[", "]", "(", ")", "-", "{", "}", ">", "+", "=", "|", "."]:
        assert f"\\{ch}" in escaped, f"Character '{ch}' was not escaped in markdown"

    # 2. Token and secret redaction
    sample_bot_token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789"
    sample_secret_key = "sk_live_secretkey999888777"
    raw_log = f"Failed to connect to Telegram with bot token {sample_bot_token} and key {sample_secret_key}"

    redacted = redact_secrets(raw_log, extra_secrets=[sample_secret_key])
    assert sample_bot_token not in redacted
    assert sample_secret_key not in redacted
    assert "[REDACTED_BOT_TOKEN]" in redacted
    assert "[REDACTED_SECRET]" in redacted


def test_report_02_contract_3() -> None:
    """AC3: Rate-limit retry tidak menggandakan notifikasi."""
    allowed_chat_id = "12345678"
    mock_transport = MagicMock()

    # Simulate rate-limit error on 1st call, then success on 2nd call
    call_count = 0

    def fake_send(chat_id: str, text: str, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionResetError("429 Too Many Requests: retry after 1 second")
        return {"ok": True, "message_id": 999}

    mock_transport.send_message.side_effect = fake_send

    reporter = ReadOnlyTelegramReporter(
        bot_token="test_token_123456",
        allowed_chat_ids=[allowed_chat_id],
        transport=mock_transport,
        max_retries=2,
    )

    idempotency_key = "report_20260915_status_001"
    report_text = "Status: Healthy"

    # 1. Initial send with retry
    result1 = reporter.send_report(
        chat_id=allowed_chat_id,
        text=report_text,
        idempotency_key=idempotency_key,
    )
    assert result1.success is True
    assert result1.retries_attempted == 1
    assert call_count == 2

    # 2. Re-send with the EXACT same idempotency key (e.g. duplicate retry from scheduler)
    result2 = reporter.send_report(
        chat_id=allowed_chat_id,
        text=report_text,
        idempotency_key=idempotency_key,
    )
    # Deduplication must suppress second send, call_count remains 2
    assert result2.success is True
    assert call_count == 2  # No duplicate message sent!
