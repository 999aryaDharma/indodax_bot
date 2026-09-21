"""Deterministic, fail-closed time-bar construction from public trades."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO

import pytest

from indodax_lab.cli.build_bars import main as build_bars_main
from indodax_lab.contracts import (
    AggressorSide,
    CandleRecord,
    CanonicalPair,
    QualityStatus,
    TradeEvent,
)
from indodax_lab.data.bars import (
    BarType,
    ReconciliationPolicy,
    SourceSelection,
    TimeBarConfig,
    aggregate_time_bars,
    compare_time_bar_sources,
    load_time_bar_config,
    resample_time_bars,
)
from indodax_lab.data.indodax_stream import AppendOnlyStreamWriter
from indodax_lab.data.manifest import canonical_json_bytes, snapshot_manifest_path
from indodax_lab.data.parquet_store import ParquetStore, WriteStatus
from indodax_lab.data.sentry import validate_snapshot
from indodax_lab.data.stream_protocol import parse_public_message
from indodax_lab.data.trade_sentry import validate_trade_batches
from indodax_lab.data.trade_wire import persist_trade_wire_artifact

SNAPSHOT = "sha256:" + "a" * 64
BASE = datetime(2024, 1, 1, tzinfo=UTC)


def _approved_source(root) -> str:
    candle = CandleRecord(
        schema_version="1.0.0",
        pair=CanonicalPair(pair="btc_idr"),
        venue_symbol="BTCIDR",
        interval="1h",
        open_time=BASE, close_time=BASE + timedelta(hours=1), open=Decimal("100"),
        high=Decimal("100"), low=Decimal("100"), close=Decimal("100"),
        base_volume=Decimal("1"), is_closed=True, available_at=BASE + timedelta(hours=1),
        source="fixture", ingested_at=BASE + timedelta(hours=1), quality_status=QualityStatus.PASS,
        quality_flags=[],
    )
    written = ParquetStore(root).write_candles([candle])
    assert written.status is WriteStatus.SUCCESS and written.dataset_snapshot_id is not None
    approved = validate_snapshot(
        root, written.dataset_snapshot_id, expected_start=BASE,
        expected_end=BASE + timedelta(hours=1), as_of=BASE + timedelta(hours=1),
    )
    assert approved.eligible_for_silver
    return written.dataset_snapshot_id


def _batch_args(root, trades: list[TradeEvent]) -> list[str]:
    writer = AppendOnlyStreamWriter(root, max_batch_size=max(1, len(trades)))
    batch = None
    for offset, trade in enumerate(trades):
        parsed, wire = _wire_trade(trade, offset)
        link = persist_trade_wire_artifact(
            root,
            body=canonical_json_bytes(wire),
            received_at=parsed.trades[0].ingested_at,
            expected_pair=trade.pair.pair,
            channel=parsed.channel or "",
            offset=parsed.offset if parsed.offset is not None else -1,
        )
        batch = writer.append(
            {
                "kind": "TRADE",
                "offset": offset,
                "events": [event.model_dump(mode="json") for event in parsed.trades],
                "trade_wire": link.to_record(root),
            },
            acknowledged_offset=offset,
        )
    batch = batch or writer.flush()
    assert batch is not None
    decision = validate_trade_batches(root, (batch,))
    return ["--trade-batch", str(batch), "--trade-quality-decision", str(decision.record_path)]


def _wire_trade(trade: TradeEvent, offset: int):
    sequence = 1_000_000 + offset
    wire = {
        "result": {
            "channel": f"market:trade-activity-{trade.pair.pair.replace('_', '')}",
            "data": {
                "data": [[
                    trade.pair.pair.replace("_", ""),
                    int(trade.event_ts.timestamp()),
                    sequence,
                    (trade.aggressor_side or AggressorSide.UNKNOWN).value.lower(),
                    str(trade.price),
                    str(trade.quote_qty),
                    str(trade.base_qty),
                ]],
                "offset": offset,
            },
        }
    }
    parsed = parse_public_message(
        wire, ingested_at=trade.available_at, expected_pair=trade.pair.pair
    )
    return parsed, wire


def _trade(
    event_id: str,
    seconds: int,
    price: str,
    qty: str,
    *,
    side: AggressorSide | None = AggressorSide.BUY,
    available_delay: int = 1,
    status: QualityStatus = QualityStatus.PASS,
) -> TradeEvent:
    event_ts = BASE + timedelta(seconds=seconds)
    ingested_at = event_ts + timedelta(milliseconds=100)
    return TradeEvent(
        schema_version="1.0.0",
        pair=CanonicalPair(pair="btc_idr"),
        venue_symbol="BTCIDR",
        event_ts=event_ts,
        ingested_at=ingested_at,
        available_at=event_ts + timedelta(seconds=available_delay),
        price=Decimal(price),
        base_qty=Decimal(qty),
        quote_qty=Decimal(price) * Decimal(qty),
        source_event_id=event_id,
        source="indodax_public_stream",
        aggressor_side=side,
        quality_status=status,
        quality_flags=[],
    )


def test_one_minute_bar_is_exact_end_exclusive_and_availability_safe():
    """Changing Decimal math, boundary ownership, or availability max must fail this test."""
    trades = [
        _trade("t3", 59, "101", "2", side=AggressorSide.SELL, available_delay=3),
        _trade("t1", 0, "100.10", "1.5", available_delay=1),
        _trade("t2", 30, "99.90", "0.5", side=AggressorSide.UNKNOWN, available_delay=1),
        _trade("t4", 60, "200", "1", available_delay=1),
    ]

    result = aggregate_time_bars(
        trades,
        interval="1m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=2),
        availability_lag=timedelta(seconds=5),
        source_snapshot_id=SNAPSHOT,
    )

    first, second = result.bars
    assert (first.open, first.high, first.low, first.close) == (
        Decimal("100.10"),
        Decimal("101"),
        Decimal("99.90"),
        Decimal("101"),
    )
    assert first.base_volume == Decimal("4.0")
    assert first.quote_volume == Decimal("402.10")
    assert first.trade_count == 3
    assert first.buy_base_volume == Decimal("1.5")
    assert first.sell_base_volume == Decimal("2")
    assert first.open_time == BASE
    assert first.close_time == BASE + timedelta(minutes=1)
    assert first.first_event_ts == BASE
    assert first.last_event_ts == BASE + timedelta(seconds=59)
    assert first.available_at == BASE + timedelta(seconds=65)
    assert first.source_event_ids == ("t1", "t2", "t3")
    assert second.open_time == BASE + timedelta(minutes=1)
    assert second.open == Decimal("200")
    assert result.gaps == ()


def test_ids_and_values_ignore_input_order_and_ingestion_order():
    """Using input position in bar lineage would make an offline replay non-deterministic."""
    trades = [_trade("b", 10, "101", "2"), _trade("a", 10, "100", "1")]

    first = aggregate_time_bars(
        trades,
        interval="1m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=1),
        availability_lag=timedelta(0),
        source_snapshot_id=SNAPSHOT,
    )
    replay = aggregate_time_bars(
        list(reversed(trades)),
        interval="1m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=1),
        availability_lag=timedelta(0),
        source_snapshot_id=SNAPSHOT,
    )

    assert first == replay
    assert first.bars[0].open == Decimal("100")
    assert first.bars[0].close == Decimal("101")
    assert first.bars[0].bar_id.startswith("sha256:")


def test_bar_preserves_one_trade_source_and_rejects_cross_provider_mixing():
    """A generic or mixed source label would make provider lineage unauditable."""
    trade = _trade("a", 1, "100", "1")
    result = aggregate_time_bars(
        [trade],
        interval="1m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=1),
        availability_lag=timedelta(0),
        source_snapshot_id=SNAPSHOT,
    )
    assert result.bars[0].source == "indodax_public_stream"

    other = _trade("b", 2, "101", "1").model_copy(update={"source": "other_provider"})
    with pytest.raises(ValueError, match="source"):
        aggregate_time_bars(
            [trade, other],
            interval="1m",
            window_start=BASE,
            window_end=BASE + timedelta(minutes=1),
            availability_lag=timedelta(0),
            source_snapshot_id=SNAPSHOT,
        )


def test_empty_bucket_is_an_explicit_gap_not_a_fabricated_candle():
    """Forward-filling an empty minute would create market prices that never traded."""
    result = aggregate_time_bars(
        [_trade("first", 1, "100", "1"), _trade("last", 121, "102", "1")],
        interval="1m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=3),
        availability_lag=timedelta(0),
        source_snapshot_id=SNAPSHOT,
    )

    assert [bar.open_time for bar in result.bars] == [BASE, BASE + timedelta(minutes=2)]
    assert [(gap.start, gap.end, gap.reason) for gap in result.gaps] == [
        (BASE + timedelta(minutes=1), BASE + timedelta(minutes=2), "EMPTY_BUCKET")
    ]


@pytest.mark.parametrize(
    "status", [QualityStatus.WARN, QualityStatus.FAIL, QualityStatus.QUARANTINED]
)
def test_non_pass_trade_fails_the_whole_requested_window(status):
    """Filtering an unreliable event would silently make an incomplete candle appear reliable."""
    with pytest.raises(ValueError, match="reliable PASS trades"):
        aggregate_time_bars(
            [_trade("bad", 1, "100", "1", status=status)],
            interval="1m",
            window_start=BASE,
            window_end=BASE + timedelta(minutes=1),
            availability_lag=timedelta(0),
            source_snapshot_id=SNAPSHOT,
        )


def test_conflicting_duplicate_trade_identity_fails_closed():
    """Choosing one duplicate ID with different economic values would depend on input order."""
    with pytest.raises(ValueError, match="duplicate source_event_id"):
        aggregate_time_bars(
            [_trade("same", 1, "100", "1"), _trade("same", 2, "101", "1")],
            interval="1m",
            window_start=BASE,
            window_end=BASE + timedelta(minutes=1),
            availability_lag=timedelta(0),
            source_snapshot_id=SNAPSHOT,
        )


def test_resampling_requires_every_contiguous_smaller_bar():
    """Crossing an empty minute would hide a source gap inside a valid-looking 5m bar."""
    minute_result = aggregate_time_bars(
        [_trade(str(i), i * 60 + 1, str(100 + i), "1") for i in (0, 1, 3, 4)],
        interval="1m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=5),
        availability_lag=timedelta(0),
        source_snapshot_id=SNAPSHOT,
    )

    resampled = resample_time_bars(
        minute_result.bars,
        target_interval="5m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=5),
        availability_lag=timedelta(seconds=5),
    )

    assert resampled.bars == ()
    assert [(gap.start, gap.end, gap.reason) for gap in resampled.gaps] == [
        (BASE, BASE + timedelta(minutes=5), "INCOMPLETE_SOURCE_BUCKET")
    ]


def test_resampling_uses_smallest_reliable_source_and_exact_ohlcv():
    """Dropping a source minute or changing Decimal aggregation must alter this result."""
    minute_result = aggregate_time_bars(
        [_trade(str(i), i * 60 + 1, str(100 + i), "1") for i in range(5)],
        interval="1m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=5),
        availability_lag=timedelta(0),
        source_snapshot_id=SNAPSHOT,
    )

    result = resample_time_bars(
        minute_result.bars,
        target_interval="5m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=5),
        availability_lag=timedelta(seconds=5),
    )

    assert len(result.bars) == 1
    bar = result.bars[0]
    assert (bar.open, bar.high, bar.low, bar.close) == tuple(
        Decimal(value) for value in ("100", "104", "100", "104")
    )
    assert bar.base_volume == Decimal("5")
    assert bar.quote_volume == Decimal("510")
    assert bar.trade_count == 5
    assert bar.available_at == BASE + timedelta(minutes=5, seconds=5)
    assert bar.source == "indodax_public_stream"


def test_official_mismatch_is_reported_and_source_is_selected_without_merging():
    """Averaging official and derived values would erase provenance and deterministic deltas."""
    derived = aggregate_time_bars(
        [_trade("a", 1, "100", "1")],
        interval="1m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=1),
        availability_lag=timedelta(0),
        source_snapshot_id=SNAPSHOT,
    ).bars
    official = derived[0].model_copy(
        update={"high": Decimal("101"), "close": Decimal("101"), "source": "official"}
    )
    policy = ReconciliationPolicy(
        pair="btc_idr",
        derived_source="indodax_public_stream",
        derived_snapshot_id=SNAPSHOT,
        official_source="official",
        official_snapshot_id=SNAPSHOT,
        price_tolerance=Decimal("0"),
        volume_tolerance=Decimal("0"),
        require_complete=True,
    )

    report = compare_time_bar_sources(
        derived=derived,
        official=[official],
        selection=SourceSelection.OFFICIAL,
        policy=policy,
    )

    assert report.selected == (official,)
    assert report.mismatches[0].deltas == {
        "high": Decimal("1"),
        "close": Decimal("1"),
    }
    assert report.mismatches[0].derived_bar_id == derived[0].bar_id


def test_time_config_loader_rejects_unknown_fields_and_has_content_identity(tmp_path):
    """Ignoring config typos would silently change source and availability policy."""
    good = tmp_path / "time.yaml"
    good.write_text(
        "config_id: time-bars-v1\n"
        "source_selection: trades\n"
        "base_interval: 1m\n"
        "output_intervals: [1m, 5m]\n"
        "availability_lag_seconds: 5\n"
        "price_tolerance: '0'\n"
        "volume_tolerance: '0'\n"
        "require_complete_reconciliation: true\n",
        encoding="utf-8",
    )
    loaded = load_time_bar_config(good)
    assert loaded.config == TimeBarConfig(
        config_id="time-bars-v1",
        source_selection=SourceSelection.TRADES,
        base_interval="1m",
        output_intervals=("1m", "5m"),
        availability_lag_seconds=5,
        price_tolerance=Decimal("0"),
        volume_tolerance=Decimal("0"),
        require_complete_reconciliation=True,
    )
    assert loaded.source_id.startswith("sha256:")

    good.write_text(good.read_text(encoding="utf-8") + "typo: true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="typo"):
        load_time_bar_config(good)


def test_cli_dry_run_is_offline_non_writing_and_identity_is_replay_stable(tmp_path):
    """A dry-run write or order-dependent output ID would make safe replay impossible."""
    config = tmp_path / "time.yaml"
    config.write_text(
        "config_id: time-bars-v1\n"
        "source_selection: trades\n"
        "base_interval: 1m\n"
        "output_intervals: [1m]\n"
        "availability_lag_seconds: 5\n"
        "price_tolerance: '0'\n"
        "volume_tolerance: '0'\n"
        "require_complete_reconciliation: true\n",
        encoding="utf-8",
    )
    trades_path = tmp_path / "trades.json"
    rows = [
        _trade("b", 2, "101", "1").model_dump(mode="json"),
        _trade("a", 1, "100", "1").model_dump(mode="json"),
    ]
    trades_path.write_text(json.dumps(rows), encoding="utf-8")
    output_root = tmp_path / "never-created"
    argv = [
        "--mode",
        "time",
        "--config",
        str(config),
        "--trades",
        str(trades_path),
        "--source-snapshot-id",
        SNAPSHOT,
        "--source-session-id",
        "trade-session-1",
        "--start",
        BASE.isoformat(),
        "--end",
        (BASE + timedelta(minutes=1)).isoformat(),
        "--data-root",
        str(output_root),
        "--dry-run",
    ]

    first = StringIO()
    replay = StringIO()
    assert build_bars_main(argv, stdout=first) == 0
    trades_path.write_text(json.dumps(list(reversed(rows))), encoding="utf-8")
    assert build_bars_main(argv, stdout=replay) == 0

    assert first.getvalue() == replay.getvalue()
    assert "output_id=sha256:" in first.getvalue()
    assert not list((output_root / "silver" / "dataset=bars").rglob("bars.json"))


def test_cli_publishes_content_addressed_time_bars_without_network(tmp_path):
    """Publishing under a mutable latest path would permit silent output replacement."""
    config = tmp_path / "time.yaml"
    config.write_text(
        "config_id: time-bars-v1\n"
        "source_selection: trades\n"
        "base_interval: 1m\n"
        "output_intervals: [1m]\n"
        "availability_lag_seconds: 0\n"
        "price_tolerance: '0'\n"
        "volume_tolerance: '0'\n"
        "require_complete_reconciliation: true\n",
        encoding="utf-8",
    )
    trades_path = tmp_path / "trades.json"
    trades_path.write_text(
        json.dumps([_trade("a", 1, "100", "1").model_dump(mode="json")]),
        encoding="utf-8",
    )
    output_root = tmp_path / "lab-data"
    source_snapshot = _approved_source(output_root)
    batch_args = _batch_args(output_root, [_trade("a", 1, "100", "1")])
    stdout = StringIO()

    assert (
        build_bars_main(
            [
                "--mode",
                "time",
                "--config",
                str(config),
                *batch_args,
                "--source-snapshot-id",
                source_snapshot,
                "--source-session-id",
                "trade-session-1",
                "--start",
                BASE.isoformat(),
                "--end",
                (BASE + timedelta(minutes=1)).isoformat(),
                "--data-root",
                str(output_root),
            ],
            stdout=stdout,
        )
        == 0
    )

    output_id = stdout.getvalue().split("output_id=")[1].split()[0]
    manifest = snapshot_manifest_path(output_root, output_id)
    assert manifest.exists()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["bars_output_id"] == output_id
    assert payload["source_snapshot_id"] == source_snapshot
    assert payload["row_count"] == 1


def test_time_bar_identity_changes_with_lag_provider_session_and_policy():
    """Material construction changes must never reuse a published bar identity."""
    trade = _trade("a", 1, "100", "1")

    def bar_id(**overrides):
        row = overrides.pop("trade", trade)
        return (
            aggregate_time_bars(
                [row],
                interval="1m",
                window_start=BASE,
                window_end=BASE + timedelta(minutes=1),
                availability_lag=overrides.pop("availability_lag", timedelta(0)),
                source_snapshot_id=overrides.pop("source_snapshot_id", SNAPSHOT),
                source_session_id=overrides.pop("source_session_id", "trade-session-1"),
                policy_id=overrides.pop("policy_id", "time-bars-v2"),
                **overrides,
            )
            .bars[0]
            .bar_id
        )

    baseline = bar_id()
    ids = {
        bar_id(availability_lag=timedelta(seconds=1)),
        bar_id(trade=trade.model_copy(update={"source": "other_provider"})),
        bar_id(source_snapshot_id="sha256:" + "f" * 64),
        bar_id(source_session_id="trade-session-2"),
        bar_id(policy_id="time-bars-v3"),
    }
    assert baseline not in ids
    assert len(ids) == 5


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pair", "eth_idr"),
        ("source", "other_provider"),
        ("source_snapshot_id", "sha256:" + "f" * 64),
        ("source_session_id", "trade-session-2"),
    ],
)
def test_resample_rejects_mixed_pair_provider_snapshot_or_session(field, value):
    """A resampled bar must have one complete lower-bar lineage domain."""
    minute_result = aggregate_time_bars(
        [_trade(str(i), i * 60 + 1, str(100 + i), "1") for i in range(5)],
        interval="1m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=5),
        availability_lag=timedelta(0),
        source_snapshot_id=SNAPSHOT,
        source_session_id="trade-session-1",
        policy_id="time-bars-v2",
    )
    mixed = list(minute_result.bars)
    mixed[-1] = mixed[-1].model_copy(update={field: value})

    with pytest.raises(ValueError, match="pair|provider|source|snapshot|session"):
        resample_time_bars(
            mixed,
            target_interval="5m",
            window_start=BASE,
            window_end=BASE + timedelta(minutes=5),
            availability_lag=timedelta(0),
            policy_id="time-bars-v2",
        )


def test_reconciliation_reports_union_missing_keys_and_blocks_incomplete_official_selection():
    """Intersect-only comparison would hide absent official or derived bars."""
    derived = aggregate_time_bars(
        [_trade("a", 1, "100", "1"), _trade("b", 61, "101", "1")],
        interval="1m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=2),
        availability_lag=timedelta(0),
        source_snapshot_id=SNAPSHOT,
        source_session_id="trade-session-1",
        policy_id="time-bars-v2",
    ).bars
    official = derived[0].model_copy(
        update={
            "source": "official_history",
            "source_snapshot_id": "sha256:" + "f" * 64,
            "source_session_id": "official-session-1",
        }
    )
    policy = ReconciliationPolicy(
        pair="btc_idr",
        derived_source="indodax_public_stream",
        derived_snapshot_id=SNAPSHOT,
        official_source="official_history",
        official_snapshot_id="sha256:" + "f" * 64,
        price_tolerance=Decimal("0"),
        volume_tolerance=Decimal("0"),
        require_complete=True,
    )

    report = compare_time_bar_sources(
        derived=derived,
        official=[official],
        selection=SourceSelection.TRADES,
        policy=policy,
    )
    assert report.mismatches[0].kind == "MISSING_OFFICIAL"
    assert report.mismatches[0].derived_bar_id == derived[1].bar_id
    assert report.mismatches[0].official_bar_id is None

    with pytest.raises(ValueError, match="complete|missing"):
        compare_time_bar_sources(
            derived=derived,
            official=[official],
            selection=SourceSelection.OFFICIAL,
            policy=policy,
        )


def test_reconciliation_applies_explicit_tolerance_and_validates_full_lineage():
    """Implicit tolerance or unchecked provider lineage could select unrelated official rows."""
    derived = aggregate_time_bars(
        [_trade("a", 1, "100", "1")],
        interval="1m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=1),
        availability_lag=timedelta(0),
        source_snapshot_id=SNAPSHOT,
        source_session_id="trade-session-1",
        policy_id="time-bars-v2",
    ).bars
    official = derived[0].model_copy(
        update={
            "high": Decimal("100.01"),
            "close": Decimal("100.01"),
            "source": "official_history",
            "source_snapshot_id": "sha256:" + "f" * 64,
            "source_session_id": "official-session-1",
        }
    )
    policy = ReconciliationPolicy(
        pair="btc_idr",
        derived_source="indodax_public_stream",
        derived_snapshot_id=SNAPSHOT,
        official_source="official_history",
        official_snapshot_id="sha256:" + "f" * 64,
        price_tolerance=Decimal("0.01"),
        volume_tolerance=Decimal("0"),
        require_complete=True,
    )
    report = compare_time_bar_sources(
        derived=derived,
        official=[official],
        selection=SourceSelection.OFFICIAL,
        policy=policy,
    )
    assert report.mismatches == ()
    assert report.pair == "btc_idr"
    assert report.derived_source == "indodax_public_stream"
    assert report.derived_snapshot_id == SNAPSHOT
    assert report.official_source == "official_history"
    assert report.official_snapshot_id == "sha256:" + "f" * 64
    assert report.price_tolerance == Decimal("0.01")
    assert report.require_complete is True
    assert report.selected[0].source == "official_history"
    assert report.selected[0].source_snapshot_id == "sha256:" + "f" * 64

    wrong = official.model_copy(update={"source": "unregistered_official"})
    with pytest.raises(ValueError, match="source"):
        compare_time_bar_sources(
            derived=derived,
            official=[wrong],
            selection=SourceSelection.OFFICIAL,
            policy=policy,
        )


def test_reconciliation_compares_availability_interval_and_bar_type():
    """Official rows with different closure semantics must be reported before selection."""
    derived = aggregate_time_bars(
        [_trade("a", 1, "100", "1")],
        interval="1m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=1),
        availability_lag=timedelta(0),
        source_snapshot_id=SNAPSHOT,
        source_session_id="trade-session-1",
        policy_id="time-bars-v2",
    ).bars
    official = derived[0].model_copy(
        update={
            "available_at": derived[0].available_at + timedelta(seconds=1),
            "interval": "5m",
            "bar_type": BarType.CUSUM,
            "source": "official_history",
            "source_snapshot_id": "sha256:" + "f" * 64,
            "source_session_id": "official-session-1",
        }
    )
    policy = ReconciliationPolicy(
        pair="btc_idr",
        derived_source="indodax_public_stream",
        derived_snapshot_id=SNAPSHOT,
        official_source="official_history",
        official_snapshot_id="sha256:" + "f" * 64,
        price_tolerance=Decimal("0"),
        volume_tolerance=Decimal("0"),
        require_complete=True,
    )
    report = compare_time_bar_sources(
        derived=derived,
        official=[official],
        selection=SourceSelection.TRADES,
        policy=policy,
    )
    assert report.mismatches[0].differing_fields == (
        "available_at",
        "interval",
        "bar_type",
    )


def test_cli_requires_independent_official_provider_and_snapshot_anchors(tmp_path):
    """Inferring anchors from the first official row makes lineage validation circular."""
    config = tmp_path / "time.yaml"
    config.write_text(
        "config_id: time-bars-v2\n"
        "source_selection: official\n"
        "base_interval: 1m\n"
        "output_intervals: [1m]\n"
        "availability_lag_seconds: 0\n"
        "price_tolerance: '0'\n"
        "volume_tolerance: '0'\n"
        "require_complete_reconciliation: true\n",
        encoding="utf-8",
    )
    trade = _trade("a", 1, "100", "1")
    trades_path = tmp_path / "trades.json"
    trades_path.write_text(json.dumps([trade.model_dump(mode="json")]), encoding="utf-8")
    derived = aggregate_time_bars(
        [trade],
        interval="1m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=1),
        availability_lag=timedelta(0),
        source_snapshot_id=SNAPSHOT,
        source_session_id="trade-session-1",
        policy_id="time-bars-v2",
    ).bars[0]
    official = derived.model_copy(
        update={
            "source": "official_history",
            "source_snapshot_id": "sha256:" + "f" * 64,
            "source_session_id": "official-session-1",
        }
    )
    official_path = tmp_path / "official.json"
    official_path.write_text(json.dumps([official.model_dump(mode="json")]), encoding="utf-8")
    argv = [
        "--mode",
        "time",
        "--config",
        str(config),
        "--trades",
        str(trades_path),
        "--official-bars",
        str(official_path),
        "--source-snapshot-id",
        SNAPSHOT,
        "--source-session-id",
        "trade-session-1",
        "--start",
        BASE.isoformat(),
        "--end",
        (BASE + timedelta(minutes=1)).isoformat(),
        "--data-root",
        str(tmp_path / "output"),
        "--dry-run",
    ]

    with pytest.raises(ValueError, match="official-provider|official-snapshot"):
        build_bars_main(argv, stdout=StringIO())

    source_snapshot = _approved_source(tmp_path / "output")
    argv[argv.index(SNAPSHOT)] = source_snapshot
    anchored = argv + [
        "--official-provider",
        "official_history",
        "--official-snapshot-id",
        "sha256:" + "f" * 64,
    ]
    assert build_bars_main(anchored, stdout=StringIO()) == 0

    wrong_anchor = list(anchored)
    wrong_anchor[wrong_anchor.index("official_history")] = "wrong_provider"
    with pytest.raises(ValueError, match="official source"):
        build_bars_main(wrong_anchor, stdout=StringIO())


@pytest.mark.parametrize(
    ("rogue_update", "message"),
    [
        ({"interval": "5m", "source": "wrong_provider"}, "source|provider"),
        ({"interval": "5m"}, "interval|configured"),
    ],
)
def test_cli_validates_every_official_row_before_interval_grouping(
    tmp_path, rogue_update, message
):
    """An off-config row must not evade anchor validation by being filtered before comparison."""
    config = tmp_path / "time.yaml"
    config.write_text(
        "config_id: time-bars-v2\n"
        "source_selection: trades\n"
        "base_interval: 1m\n"
        "output_intervals: [1m]\n"
        "availability_lag_seconds: 0\n"
        "price_tolerance: '0'\n"
        "volume_tolerance: '0'\n"
        "require_complete_reconciliation: true\n",
        encoding="utf-8",
    )
    trade = _trade("a", 1, "100", "1")
    trades_path = tmp_path / "trades.json"
    trades_path.write_text(json.dumps([trade.model_dump(mode="json")]), encoding="utf-8")
    derived = aggregate_time_bars(
        [trade],
        interval="1m",
        window_start=BASE,
        window_end=BASE + timedelta(minutes=1),
        availability_lag=timedelta(0),
        source_snapshot_id=SNAPSHOT,
        source_session_id="trade-session-1",
        policy_id="time-bars-v2",
    ).bars[0]
    valid = derived.model_copy(
        update={
            "source": "official_history",
            "source_snapshot_id": "sha256:" + "f" * 64,
            "source_session_id": "official-session-1",
        }
    )
    rogue = valid.model_copy(update=rogue_update)
    official_path = tmp_path / "official.json"
    official_path.write_text(
        json.dumps([valid.model_dump(mode="json"), rogue.model_dump(mode="json")]),
        encoding="utf-8",
    )
    output_root = tmp_path / "must-not-publish"

    with pytest.raises(ValueError, match=message):
        build_bars_main(
            [
                "--mode",
                "time",
                "--config",
                str(config),
                "--trades",
                str(trades_path),
                "--official-bars",
                str(official_path),
                "--official-provider",
                "official_history",
                "--official-snapshot-id",
                "sha256:" + "f" * 64,
                "--source-snapshot-id",
                _approved_source(output_root),
                "--source-session-id",
                "trade-session-1",
                "--start",
                BASE.isoformat(),
                "--end",
                (BASE + timedelta(minutes=1)).isoformat(),
                "--data-root",
                str(output_root),
                "--dry-run",
            ],
        stdout=StringIO(),
    )
    assert not list((output_root / "silver" / "dataset=bars").rglob("bars.json"))


def test_duplicate_policy_is_not_accepted_by_strict_bar_configs(tmp_path):
    """Dedupe belongs upstream; exposing it in bar policy hides duplicate defects."""
    time_path = tmp_path / "time.yaml"
    time_path.write_text(
        "config_id: time-bars-v2\n"
        "source_selection: trades\n"
        "base_interval: 1m\n"
        "output_intervals: [1m]\n"
        "availability_lag_seconds: 0\n"
        "price_tolerance: '0'\n"
        "volume_tolerance: '0'\n"
        "require_complete_reconciliation: true\n"
        "duplicate_policy: dedupe\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate_policy"):
        load_time_bar_config(time_path)
