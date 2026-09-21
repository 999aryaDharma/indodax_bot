"""Tests for structured logging, credential redaction, and metrics collector."""

from __future__ import annotations

import json
import logging

from indodax_lab.observability.logging import RedactingJsonFormatter
from indodax_lab.observability.metrics import MetricsCollector


def test_redacting_json_formatter_formats_and_redacts() -> None:
    formatter = RedactingJsonFormatter(custom_secrets=["super_secret_key_123"])
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Connecting with api_key='my_key_99998888' and secret=super_secret_key_123",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert "my_key_99998888" not in parsed["message"]
    assert "super_secret_key_123" not in parsed["message"]
    assert "[REDACTED]" in parsed["message"]


def test_metrics_collector_counters_and_gauges() -> None:
    collector = MetricsCollector()

    # Counter
    c1 = collector.increment("orders_submitted", 1.0, labels={"pair": "btc_idr", "side": "buy"})
    assert c1 == 1.0
    c2 = collector.increment("orders_submitted", 2.0, labels={"pair": "btc_idr", "side": "buy"})
    assert c2 == 3.0

    # Gauge
    collector.set_gauge("portfolio_cash_idr", 50000000.0)

    # Timing
    collector.record_timing("order_submit_latency_ms", 120.0)
    collector.record_timing("order_submit_latency_ms", 180.0)

    exported = collector.export()
    assert exported["counters"]["orders_submitted{pair=btc_idr,side=buy}"] == 3.0
    assert exported["gauges"]["portfolio_cash_idr"] == 50000000.0
    timing_data = exported["timings"]["order_submit_latency_ms"]
    assert timing_data["count"] == 2
    assert timing_data["avg_ms"] == 150.0
    assert timing_data["max_ms"] == 180.0
