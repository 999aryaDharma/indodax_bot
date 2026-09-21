"""Tests for secret redaction and credential masking."""

from __future__ import annotations

from indodax_lab.security.redaction import redact_text


def test_redact_api_key_and_secret() -> None:
    raw = "Request with api_key='abcdef1234567890' and secret_key='secret_key_9876543210'"
    clean = redact_text(raw)
    assert "abcdef1234567890" not in clean
    assert "secret_key_9876543210" not in clean
    assert "[REDACTED]" in clean


def test_redact_custom_secret() -> None:
    active_token = "my_custom_super_secret_token_12345"
    raw = f"Connecting to exchange using token={active_token}"
    clean = redact_text(raw, custom_secrets=[active_token])
    assert active_token not in clean
    assert "[REDACTED]" in clean


def test_redact_empty_or_clean_text() -> None:
    assert redact_text("") == ""
    clean = "Normal trading message with order_id=ord_123 qty=0.5"
    assert redact_text(clean) == clean
