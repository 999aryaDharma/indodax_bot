"""Phase 1 checkpoint guards for source quality and immutable bronze lineage."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO

import pytest

from indodax_lab.cli.build_bars import main as build_bars
from indodax_lab.contracts import CandleRecord, CanonicalPair, QualityStatus
from indodax_lab.data.parquet_store import ParquetStore, WriteStatus
from indodax_lab.data.sentry import validate_snapshot

START = datetime(2024, 1, 1, tzinfo=UTC)


def test_phase1_gate_quarantines_checksum_mismatch_before_silver_eligibility(tmp_path) -> None:
    """A changed bronze byte must make the checkpoint ineligible instead of reusing its ID."""
    written = ParquetStore(tmp_path).write_candles(
        [_candle(), _candle(open_time=START + timedelta(hours=1))]
    )
    assert written.status is WriteStatus.SUCCESS
    assert written.dataset_snapshot_id is not None
    bronze = tmp_path / written.partitions[0].path
    bronze.write_bytes(bronze.read_bytes() + b"phase1-corruption")

    result = validate_snapshot(
        tmp_path,
        written.dataset_snapshot_id,
        expected_start=START,
        expected_end=START + timedelta(hours=2),
        as_of=START + timedelta(hours=2),
    )

    assert result.eligible_for_silver is False
    assert result.partition_state == "QUARANTINED"
    assert [finding.code for finding in result.report.findings] == ["PARTITION_CHECKSUM_MISMATCH"]


def test_phase1_gate_refuses_to_publish_bars_without_an_approved_source_decision(tmp_path) -> None:
    """A syntactically valid snapshot ID cannot substitute for a sentry approval artifact."""
    config = tmp_path / "time.yaml"
    config.write_text(
        "config_id: phase1-gate-v1\nsource_selection: trades\nbase_interval: 1m\n"
        "output_intervals: [1m]\navailability_lag_seconds: 0\nprice_tolerance: '0'\n"
        "volume_tolerance: '0'\nrequire_complete_reconciliation: true\n",
        encoding="utf-8",
    )
    trade = {
        "schema_version": "1.0.0",
        "pair": {"pair": "btc_idr"},
        "venue_symbol": "BTCIDR",
        "event_ts": "2024-01-01T00:00:01Z",
        "ingested_at": "2024-01-01T00:00:01Z",
        "available_at": "2024-01-01T00:00:01Z",
        "price": "100",
        "base_qty": "1",
        "quote_qty": "100",
        "source_event_id": "phase1-gate-trade",
        "source": "indodax_public_stream",
        "aggressor_side": "BUY",
        "quality_status": "PASS",
        "quality_flags": [],
    }
    trades = tmp_path / "trades.json"
    trades.write_text(json.dumps([trade]), encoding="utf-8")

    with pytest.raises(ValueError, match="quality decision"):
        build_bars(
            [
                "--mode", "time", "--config", str(config), "--trades", str(trades),
                "--source-snapshot-id", "sha256:" + "a" * 64,
                "--source-session-id", "phase1-gate",
                "--start", "2024-01-01T00:00:00Z", "--end", "2024-01-01T00:01:00Z",
                "--data-root", str(tmp_path),
            ],
            stdout=StringIO(),
        )

    silver = tmp_path / "silver"
    assert not silver.exists() or not list(silver.rglob("bars.json"))


@pytest.mark.parametrize(
    ("records", "expected_code"),
    [
        (lambda: [_candle()], "INTERVAL_GAP"),
        (
            lambda: [
                _candle(QualityStatus.QUARANTINED),
                _candle(open_time=START + timedelta(hours=1)),
            ],
            "UPSTREAM_QUALITY_QUARANTINED",
        ),
    ],
)
def test_phase1_gate_rejects_gaps_and_upstream_quarantine_before_silver(
    records, expected_code, tmp_path
) -> None:
    """A coverage gap or quarantined upstream row must stop the same silver admission gate."""
    written = ParquetStore(tmp_path).write_candles(records())
    assert written.status is WriteStatus.SUCCESS
    assert written.dataset_snapshot_id is not None

    result = validate_snapshot(
        tmp_path,
        written.dataset_snapshot_id,
        expected_start=START,
        expected_end=START + timedelta(hours=2),
        as_of=START + timedelta(hours=2),
    )

    assert result.eligible_for_silver is False
    assert result.partition_state == "QUARANTINED"
    assert expected_code in [finding.code for finding in result.report.findings]


def _candle(
    status: QualityStatus = QualityStatus.PASS,
    open_time: datetime = START,
) -> CandleRecord:
    return CandleRecord(
        schema_version="1.0.0",
        pair=CanonicalPair(pair="btc_idr"),
        venue_symbol="BTCIDR",
        interval="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        base_volume=Decimal("1"),
        is_closed=True,
        available_at=open_time + timedelta(hours=1),
        source="phase1-fixture",
        ingested_at=open_time + timedelta(hours=1),
        quality_status=status,
        quality_flags=[],
    )
