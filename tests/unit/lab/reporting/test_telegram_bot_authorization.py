"""Authorization regression tests for the shared Telegram command surface (REPORT-02).

Findings fixed (sprint review, batch jobs-reports):
- CRITICAL: five command handlers (``/start``, ``/status``, ``/history``, ``/raport``,
  ``/gate``) had no chat authorization at all, so any Telegram user able to reach the
  bot could read portfolio / status / report data.
- CRITICAL: ``_is_chat_authorized`` returned ``True`` when no allowlist was configured
  (fail-open). Unconfigured authorization must mean DENY.
- CRITICAL: ``ReadOnlyTelegramReporter`` keyed idempotency/dedup state globally, so one
  chat's delivery suppressed or collided with another chat's.

All Telegram interaction here is faked: the ``telegram`` and ``pandas_ta_classic``
modules are stubbed and no network call, real bot token or real Telegram message is used.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import types
from typing import Any

import pytest

_STUBBED_MODULE_NAMES = (
    "telegram",
    "telegram.constants",
    "telegram.error",
    "telegram.ext",
    "pandas_ta_classic",
    "telegram_bot",
)


def _install_telegram_stubs() -> types.ModuleType:
    """Install minimal fake Telegram/TA modules so the shared bot module imports."""
    telegram_stub = types.ModuleType("telegram")
    telegram_stub.Bot = type("Bot", (), {"__init__": lambda self, *a, **k: None})
    telegram_stub.InlineKeyboardButton = type("InlineKeyboardButton", (), {})
    telegram_stub.InlineKeyboardMarkup = type("InlineKeyboardMarkup", (), {})
    telegram_stub.Update = type("Update", (), {})
    sys.modules["telegram"] = telegram_stub

    constants_stub = types.ModuleType("telegram.constants")
    constants_stub.ParseMode = types.SimpleNamespace(MARKDOWN_V2="MarkdownV2", HTML="HTML")
    sys.modules["telegram.constants"] = constants_stub

    error_stub = types.ModuleType("telegram.error")
    error_stub.TelegramError = type("TelegramError", (Exception,), {})
    sys.modules["telegram.error"] = error_stub

    ext_stub = types.ModuleType("telegram.ext")
    ext_stub.Application = type("Application", (), {})
    ext_stub.CallbackQueryHandler = type("CallbackQueryHandler", (), {})
    ext_stub.CommandHandler = type("CommandHandler", (), {})
    ext_stub.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object)
    sys.modules["telegram.ext"] = ext_stub

    sys.modules["pandas_ta_classic"] = types.ModuleType("pandas_ta_classic")
    return telegram_stub


@pytest.fixture
def telegram_bot_module():
    """Import the shared Telegram bot module against fake dependencies, then clean up."""
    for name in _STUBBED_MODULE_NAMES:
        sys.modules.pop(name, None)
    _install_telegram_stubs()
    try:
        module = importlib.import_module("telegram_bot")
        yield module
    finally:
        for name in _STUBBED_MODULE_NAMES:
            sys.modules.pop(name, None)


class _FakeMessage:
    """Records reply_text calls; exposes the text of the last reply."""

    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str, *args: Any, **kwargs: Any) -> "_FakeMessage":
        self.replies.append(text)
        return self

    @property
    def last_reply(self) -> str:
        return self.replies[-1]


def _make_update(chat_id: Any) -> Any:
    message = _FakeMessage()
    update = types.SimpleNamespace(
        message=message,
        effective_chat=types.SimpleNamespace(id=chat_id),
        effective_user=types.SimpleNamespace(id=chat_id),
    )
    return update, message


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _set_allowlist(
    telegram_bot_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    chat_id: Any,
) -> None:
    """Swap the module-level CREDENTIALS binding (the real one is a frozen dataclass)."""
    fake = types.SimpleNamespace(telegram_chat_id=chat_id, telegram_bot_token="test-token")
    monkeypatch.setattr(telegram_bot_module, "CREDENTIALS", fake)


@pytest.fixture
def outbound_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Neutralise every outbound data path so no test can reach Indodax or a real report."""
    calls: list[str] = []

    def _record(name: str, *args: Any, **kwargs: Any) -> Any:
        calls.append(name)
        return None

    import indodax_api

    for name in (
        "fetch_ohlcv",
        "fetch_ticker",
        "fetch_wallet_balance",
        "fetch_recent_trades",
        "is_pair_already_held",
        "fetch_market_context",
        "_fetch_fear_greed",
    ):
        if hasattr(indodax_api, name):
            monkeypatch.setattr(indodax_api, name, lambda *a, _n=name, **k: _record(_n))

    paper_module = types.ModuleType("paper_trader")
    paper_module.paper_trader = types.SimpleNamespace(  # type: ignore[attr-defined]
        format_weekly_report=lambda: _record("paper_trader.format_weekly_report")
        or "REPORT-PAYLOAD",
        open_trade=lambda *a, **k: _record("paper_trader.open_trade"),
        get_all_open=lambda: [],
    )
    monkeypatch.setitem(sys.modules, "paper_trader", paper_module)

    tracker_module = types.ModuleType("position_tracker")
    tracker_module.tracker = types.SimpleNamespace(  # type: ignore[attr-defined]
        get_all_open=lambda: [],
    )
    monkeypatch.setitem(sys.modules, "position_tracker", tracker_module)

    return calls


# ---------------------------------------------------------------------------
# Finding 1 (Critical): every command handler must enforce chat authorization.
# ---------------------------------------------------------------------------


UNPROTECTED_HANDLERS = (
    "cmd_start",
    "cmd_status",
    "cmd_history",
    "cmd_raport",
    "cmd_gate",
)


@pytest.mark.parametrize("handler_name", UNPROTECTED_HANDLERS)
def test_every_command_handler_denies_unauthorized_chat(
    telegram_bot_module, monkeypatch: pytest.MonkeyPatch, outbound_calls: list[str],
    handler_name: str,
) -> None:
    """An unauthorized chat must be refused by every command handler (REPORT-02-AC1)."""
    _set_allowlist(telegram_bot_module, monkeypatch, "111")
    update, message = _make_update("999")

    _run(getattr(telegram_bot_module, handler_name)(update, None))

    assert len(message.replies) == 1, f"{handler_name} replied {len(message.replies)} times"
    assert "Akses ditolak" in message.last_reply, (
        f"{handler_name} answered an unauthorized chat with a payload instead of a denial: "
        f"{message.last_reply!r}"
    )
    assert outbound_calls == [], (
        f"{handler_name} performed work for an unauthorized chat: {outbound_calls}"
    )


def test_unauthorized_raport_does_not_compute_report(
    telegram_bot_module, monkeypatch: pytest.MonkeyPatch, outbound_calls: list[str]
) -> None:
    """`/raport` must refuse before doing any report work (no computation for a stranger)."""
    _set_allowlist(telegram_bot_module, monkeypatch, "111")

    update, message = _make_update("999")
    _run(telegram_bot_module.cmd_raport(update, None))

    assert "REPORT-PAYLOAD" not in message.last_reply
    assert "paper_trader.format_weekly_report" not in outbound_calls, (
        "unauthorized /raport must not compute or emit the weekly report"
    )


def test_unauthorized_gate_does_not_fetch_market_data(
    telegram_bot_module, monkeypatch: pytest.MonkeyPatch, outbound_calls: list[str]
) -> None:
    """`/gate` must refuse before fetching any pair data."""
    _set_allowlist(telegram_bot_module, monkeypatch, "111")

    update, message = _make_update("999")
    _run(telegram_bot_module.cmd_gate(update, None))

    assert "Akses ditolak" in message.last_reply
    assert "fetch_ohlcv" not in outbound_calls, (
        "unauthorized /gate must not fetch any market data"
    )


def test_unauthorized_history_does_not_leak_signal_records(
    telegram_bot_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`/history` must refuse and never echo recorded signal entries."""
    _set_allowlist(telegram_bot_module, monkeypatch, "111")
    telegram_bot_module._signal_history.append(
        {
            "pair": "btc_idr",
            "score_pct": 91,
            "strategy": "SNIPER",
            "market_mode": "BULL_TREND",
            "entry": 900_000_000,
            "sl": 880_000_000,
            "tp": 950_000_000,
            "position_idr": 10_000_000,
            "sent_at": 1_700_000_000.0,
        }
    )
    try:
        update, message = _make_update("999")
        _run(telegram_bot_module.cmd_history(update, None))

        assert "Akses ditolak" in message.last_reply
        assert "900,000,000" not in message.last_reply
    finally:
        telegram_bot_module._signal_history.clear()


def test_authorized_chat_still_receives_payload(
    telegram_bot_module, monkeypatch: pytest.MonkeyPatch, outbound_calls: list[str]
) -> None:
    """Gating must not break the owner: the allowlisted chat still gets its answer."""
    _set_allowlist(telegram_bot_module, monkeypatch, "111")

    update, message = _make_update("111")
    _run(telegram_bot_module.cmd_start(update, None))

    assert "IndoBot Signal" in message.last_reply
    assert outbound_calls == []


# ---------------------------------------------------------------------------
# Finding 2 (Critical): unconfigured allowlist must fail closed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("unconfigured", [None, "", "   "])
def test_unconfigured_allowlist_fails_closed(
    telegram_bot_module, monkeypatch: pytest.MonkeyPatch, unconfigured: Any
) -> None:
    """No configured allowlist must mean DENY, never ALLOW (REPORT-02-AC1)."""
    _set_allowlist(telegram_bot_module, monkeypatch, unconfigured)

    for chat_id in ("111", 111, "-1001234567890", None, "anything"):
        assert telegram_bot_module._is_chat_authorized(chat_id) is False, (
            f"unconfigured allowlist must deny chat {chat_id!r}"        )


def test_unconfigured_allowlist_denies_every_handler(
    telegram_bot_module, monkeypatch: pytest.MonkeyPatch, outbound_calls: list[str]
) -> None:
    """With no allowlist configured, every handler refuses every chat."""
    _set_allowlist(telegram_bot_module, monkeypatch, None)

    for handler_name in (
        "cmd_start",
        "cmd_status",
        "cmd_history",
        "cmd_saldo",
        "cmd_posisi",
        "cmd_raport",
        "cmd_gate",
    ):
        update, message = _make_update("111")
        _run(getattr(telegram_bot_module, handler_name)(update, None))
        assert "Akses ditolak" in message.last_reply, f"{handler_name} did not fail closed"

    assert outbound_calls == [], (
        f"handlers did work with no allowlist configured: {outbound_calls}"
    )


# ---------------------------------------------------------------------------
# Finding 3 (Critical): idempotency state must be scoped per chat.
# ---------------------------------------------------------------------------


def test_idempotency_key_is_scoped_per_chat() -> None:
    """One chat's delivered key must not suppress another allowlisted chat (REPORT-02-AC3)."""
    from indodax_lab.reporting.telegram import ReadOnlyTelegramReporter

    sent: list[dict[str, Any]] = []

    class _Transport:
        def send_message(self, chat_id: str, text: str, **kwargs: Any) -> dict[str, Any]:
            sent.append({"chat_id": chat_id, "text": text})
            return {"message_id": len(sent)}

    reporter = ReadOnlyTelegramReporter(
        bot_token="test_token_123456",
        allowed_chat_ids=["111", "222"],
        transport=_Transport(),
    )

    first = reporter.send_report(chat_id="111", text="status A", idempotency_key="k1")
    second = reporter.send_report(chat_id="222", text="status B", idempotency_key="k1")

    assert len(sent) == 2, "same key for a different chat must not be deduplicated away"
    assert [entry["chat_id"] for entry in sent] == ["111", "222"]
    assert first.chat_id == "111"
    assert second.chat_id == "222"
    assert second.message_id != first.message_id


def test_same_key_same_chat_is_still_deduplicated() -> None:
    """Per-chat scoping must preserve dedup within a single chat."""
    from indodax_lab.reporting.telegram import ReadOnlyTelegramReporter

    sent: list[dict[str, Any]] = []

    class _Transport:
        def send_message(self, chat_id: str, text: str, **kwargs: Any) -> dict[str, Any]:
            sent.append({"chat_id": chat_id, "text": text})
            return {"message_id": len(sent)}

    reporter = ReadOnlyTelegramReporter(
        bot_token="test_token_123456",
        allowed_chat_ids=["111", "222"],
        transport=_Transport(),
    )

    reporter.send_report(chat_id="111", text="status", idempotency_key="dup")
    again = reporter.send_report(chat_id="111", text="status", idempotency_key="dup")

    assert len(sent) == 1
    assert again.chat_id == "111"
