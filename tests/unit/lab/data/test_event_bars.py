"""Information-driven bars remain deterministic challengers with no future fitting."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO

import pytest
from pydantic import ValidationError

from indodax_lab.cli.build_bars import main as build_bars_main
from indodax_lab.contracts import AggressorSide, CanonicalPair, QualityStatus, TradeEvent
from indodax_lab.data.bars import BarType
from indodax_lab.data.event_bars import (
    EventBarConfig,
    ThresholdArtifact,
    TradeContinuity,
    build_event_bars,
    load_event_bar_config,
)
from indodax_lab.data.indodax_stream import AppendOnlyStreamWriter
from indodax_lab.data.manifest import canonical_json_bytes, snapshot_manifest_path
from indodax_lab.data.parquet_store import ParquetStore, WriteStatus
from indodax_lab.data.sentry import validate_snapshot
from indodax_lab.data.stream_protocol import parse_public_message
from indodax_lab.data.trade_sentry import validate_trade_batches
from indodax_lab.data.trade_wire import persist_trade_wire_artifact

BASE = datetime(2024, 1, 1, tzinfo=UTC)
AS_OF = BASE + timedelta(hours=1)
SNAPSHOT = "sha256:" + "b" * 64


def _approved_source(root) -> str:
    from indodax_lab.contracts import CandleRecord

    candle = CandleRecord(
        schema_version="1.0.0", pair=CanonicalPair(pair="btc_idr"), venue_symbol="BTCIDR",
        interval="1h", open_time=BASE, close_time=AS_OF, open=Decimal("100"),
        high=Decimal("100"), low=Decimal("100"), close=Decimal("100"), base_volume=Decimal("1"),
        is_closed=True, available_at=AS_OF, source="fixture", ingested_at=AS_OF,
        quality_status=QualityStatus.PASS, quality_flags=[],
    )
    written = ParquetStore(root).write_candles([candle])
    assert written.status is WriteStatus.SUCCESS and written.dataset_snapshot_id is not None
    assert validate_snapshot(
        root, written.dataset_snapshot_id, expected_start=BASE, expected_end=AS_OF, as_of=AS_OF
    ).eligible_for_silver
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
    qty: str = "1",
    *,
    pair: str = "btc_idr",
    status: QualityStatus = QualityStatus.PASS,
) -> TradeEvent:
    event_ts = BASE + timedelta(seconds=seconds)
    return TradeEvent(
        schema_version="1.0.0",
        pair=CanonicalPair(pair=pair),
        venue_symbol=pair.replace("_", "").upper(),
        event_ts=event_ts,
        ingested_at=event_ts + timedelta(milliseconds=100),
        available_at=event_ts + timedelta(seconds=1),
        price=Decimal(price),
        base_qty=Decimal(qty),
        quote_qty=Decimal(price) * Decimal(qty),
        source_event_id=event_id,
        source="indodax_public_stream",
        aggressor_side=AggressorSide.BUY,
        quality_status=status,
        quality_flags=[],
    )


def _build(trades, bar_type: BarType, threshold: str):
    continuity = tuple(
        TradeContinuity(
            source_event_id=trade.source_event_id,
            stream_session_id="trade-session-1",
            continuous_from_previous=index > 0,
        )
        for index, trade in enumerate(
            sorted(trades, key=lambda row: (row.event_ts, row.source_event_id))
        )
    )
    return build_event_bars(
        trades,
        bar_type=bar_type,
        threshold=Decimal(threshold),
        threshold_config_id=f"{bar_type.value.lower()}-fixed-v1",
        source_snapshot_id=SNAPSHOT,
        build_as_of=AS_OF,
        availability_lag=timedelta(seconds=2),
        continuity=continuity,
        policy_id="event-bars-v2",
    )


def test_cusum_closes_on_positive_and_negative_boundaries_then_resets():
    """Sharing an accumulator across a trigger would change the second bar's boundary."""
    result = _build(
        [
            _trade("a", 1, "100"),
            _trade("b", 2, "101"),
            _trade("c", 3, "102"),
            _trade("d", 4, "101"),
            _trade("e", 5, "100"),
            _trade("f", 6, "100.5"),
        ],
        BarType.CUSUM,
        "2",
    )

    assert [bar.last_event_ts for bar in result.bars] == [
        BASE + timedelta(seconds=3),
        BASE + timedelta(seconds=5),
    ]
    assert [bar.boundary_direction for bar in result.bars] == ["POSITIVE", "NEGATIVE"]
    assert [bar.source_event_ids for bar in result.bars] == [("a", "b", "c"), ("d", "e")]
    assert all(bar.bar_type is BarType.CUSUM and bar.interval is None for bar in result.bars)
    assert result.remainder is not None
    assert result.remainder.source_event_ids == ("f",)


def test_range_boundary_includes_crossing_trade_and_resets_range():
    """Closing before the threshold-crossing trade would produce wrong OHLC and lineage."""
    result = _build(
        [
            _trade("a", 1, "100"),
            _trade("b", 2, "102"),
            _trade("c", 3, "103"),
            _trade("d", 4, "101"),
            _trade("e", 5, "98"),
        ],
        BarType.RANGE,
        "3",
    )

    assert [(bar.open, bar.high, bar.low, bar.close) for bar in result.bars] == [
        (Decimal("100"), Decimal("103"), Decimal("100"), Decimal("103")),
        (Decimal("101"), Decimal("101"), Decimal("98"), Decimal("98")),
    ]
    assert result.remainder is None


@pytest.mark.parametrize(
    ("bar_type", "threshold", "expected_ids"),
    [
        (BarType.VOLUME, "3", ("a", "b")),
        (BarType.DOLLAR, "350", ("a", "b")),
    ],
)
def test_cumulative_volume_and_dollar_boundaries_are_exact(bar_type, threshold, expected_ids):
    """Binary float accumulation or checking before inclusion would move this boundary."""
    result = _build(
        [_trade("a", 1, "100", "1"), _trade("b", 2, "125", "2"), _trade("c", 3, "90", "1")],
        bar_type,
        threshold,
    )

    assert result.bars[0].source_event_ids == expected_ids
    assert result.bars[0].base_volume == Decimal("3")
    assert result.bars[0].quote_volume == Decimal("350")
    assert result.remainder is not None
    assert result.remainder.source_event_ids == ("c",)


def test_partial_final_bar_is_excluded_with_auditable_remainder():
    """Emitting the final incomplete bucket would leak a bar that had not closed."""
    result = _build([_trade("a", 1, "100"), _trade("b", 2, "100.5")], BarType.RANGE, "5")

    assert result.bars == ()
    assert result.remainder is not None
    assert result.remainder.closed is False
    assert result.remainder.source_event_ids == ("a", "b")
    assert result.remainder.base_volume == Decimal("2")


def test_input_order_does_not_change_event_boundaries_or_ids():
    """Consuming arrival order instead of event timestamp and ID would break replay identity."""
    trades = [_trade("b", 1, "101"), _trade("a", 1, "100"), _trade("c", 2, "102")]

    first = _build(trades, BarType.RANGE, "2")
    replay = _build(list(reversed(trades)), BarType.RANGE, "2")

    assert first == replay
    assert first.bars[0].source_event_ids == ("a", "b", "c")
    assert first.bars[0].bar_id.startswith("sha256:")


def test_fit_threshold_must_exist_by_as_of_and_end_before_as_of():
    """A full-sample or future-published threshold would encode future volatility."""
    future_train = ThresholdArtifact(
        artifact_id="sha256:" + "c" * 64,
        threshold=Decimal("2"),
        train_end=AS_OF + timedelta(seconds=1),
        available_at=BASE,
    )
    future_publish = future_train.model_copy(
        update={"train_end": BASE, "available_at": AS_OF + timedelta(seconds=1)}
    )

    for artifact in (future_train, future_publish):
        with pytest.raises(ValueError, match="future|as-of|train_end|available_at"):
            build_event_bars(
                (trades := [_trade("a", 1, "100")]),
                bar_type=BarType.CUSUM,
                threshold=artifact,
                threshold_config_id="cusum-fit-v1",
                source_snapshot_id=SNAPSHOT,
                build_as_of=AS_OF,
                availability_lag=timedelta(0),
                continuity=_continuity(trades),
                policy_id="event-bars-v2",
            )


def test_valid_fit_artifact_is_lineage_and_never_refit_from_events():
    """Re-estimating from input events would change a registered train-only threshold."""
    artifact = ThresholdArtifact(
        artifact_id="sha256:" + "c" * 64,
        threshold=Decimal("2"),
        train_end=BASE - timedelta(days=1),
        available_at=BASE - timedelta(hours=1),
    )

    trades = [_trade("a", 1, "100"), _trade("b", 2, "102")]
    result = build_event_bars(
        trades,
        bar_type=BarType.CUSUM,
        threshold=artifact,
        threshold_config_id="cusum-fit-v1",
        source_snapshot_id=SNAPSHOT,
        build_as_of=AS_OF,
        availability_lag=timedelta(0),
        continuity=_continuity(trades),
        policy_id="event-bars-v2",
    )

    assert result.threshold_artifact_id == artifact.artifact_id
    assert result.bars[0].threshold_config_id == "cusum-fit-v1"


@pytest.mark.parametrize(
    "threshold",
    [Decimal("0"), Decimal("-1"), 1.0],
)
def test_threshold_must_be_positive_exact_decimal(threshold):
    """Zero, negative, or float thresholds make boundaries unsafe or non-exact."""
    with pytest.raises(
        (TypeError, ValueError, ValidationError), match="threshold|Decimal|positive"
    ):
        trades = [_trade("a", 1, "100")]
        build_event_bars(
            trades,
            bar_type=BarType.RANGE,
            threshold=threshold,
            threshold_config_id="range-fixed-v1",
            source_snapshot_id=SNAPSHOT,
            build_as_of=AS_OF,
            availability_lag=timedelta(0),
            continuity=_continuity(trades),
            policy_id="event-bars-v2",
        )


def test_wrong_pair_unreliable_or_future_trade_fails_closed():
    """Filtering invalid events would make the retained session look complete and reliable."""
    cases = [
        [_trade("a", 1, "100"), _trade("b", 2, "101", pair="eth_idr")],
        [_trade("a", 1, "100", status=QualityStatus.FAIL)],
        [_trade("a", 3601, "100")],
    ]
    for trades in cases:
        with pytest.raises(ValueError):
            _build(trades, BarType.RANGE, "1")


def test_event_config_loader_is_strict_and_content_addressed(tmp_path):
    """Accepting an unknown config key would hide a misspelled threshold policy."""
    path = tmp_path / "event.yaml"
    path.write_text(
        "config_id: event-bars-v1\n"
        "availability_lag_seconds: 2\n"
        "thresholds:\n"
        "  - config_id: cusum-fixed-v1\n"
        "    bar_type: CUSUM\n"
        "    fixed_threshold: '2'\n"
        "  - config_id: volume-fixed-v1\n"
        "    bar_type: VOLUME\n"
        "    fixed_threshold: '100'\n",
        encoding="utf-8",
    )

    loaded = load_event_bar_config(path)
    assert loaded.config.config_id == "event-bars-v1"
    assert loaded.config.thresholds[0].fixed_threshold == Decimal("2")
    assert loaded.source_id.startswith("sha256:")

    path.write_text(path.read_text(encoding="utf-8") + "unknown: true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown"):
        load_event_bar_config(path)


def test_event_threshold_config_rejects_cusum_time_bar_and_duplicate_ids():
    """A TIME threshold or duplicate config ID would make challenger selection ambiguous."""
    with pytest.raises(ValidationError):
        EventBarConfig.model_validate(
            {
                "config_id": "event-bars-v1",
                "availability_lag_seconds": 0,
                "thresholds": [{"config_id": "bad", "bar_type": "TIME", "fixed_threshold": "1"}],
            }
        )


def _continuity(trades, *, session_id="trade-session-1", gap_before=()):
    ordered = sorted(trades, key=lambda trade: (trade.event_ts, trade.source_event_id))
    return tuple(
        TradeContinuity(
            source_event_id=trade.source_event_id,
            stream_session_id=session_id,
            continuous_from_previous=index > 0 and trade.source_event_id not in gap_before,
        )
        for index, trade in enumerate(ordered)
    )


def test_fitted_threshold_must_predate_first_event_and_be_available_by_first_input():
    """A threshold learned or published after historical input would leak future information."""
    trades = [_trade("a", 10, "100"), _trade("b", 11, "102")]
    after_event = ThresholdArtifact(
        artifact_id="sha256:" + "d" * 64,
        threshold=Decimal("2"),
        train_end=trades[0].event_ts,
        available_at=BASE,
    )
    after_input_availability = after_event.model_copy(
        update={
            "train_end": BASE - timedelta(seconds=1),
            "available_at": trades[0].available_at + timedelta(microseconds=1),
        }
    )

    for artifact in (after_event, after_input_availability):
        with pytest.raises(ValueError, match="first|train_end|available"):
            build_event_bars(
                trades,
                bar_type=BarType.CUSUM,
                threshold=artifact,
                threshold_config_id="cusum-fit-v2",
                source_snapshot_id=SNAPSHOT,
                build_as_of=AS_OF,
                availability_lag=timedelta(0),
                continuity=_continuity(trades),
                policy_id="event-bars-v2",
            )


def test_fitted_threshold_lineage_and_availability_reach_result_bar_and_cli_payload():
    """Discarding artifact lineage would make a fitted historical bar unauditable."""
    trades = [_trade("a", 10, "100"), _trade("b", 11, "102")]
    artifact = ThresholdArtifact(
        artifact_id="sha256:" + "d" * 64,
        threshold=Decimal("2"),
        train_end=BASE - timedelta(seconds=2),
        available_at=BASE + timedelta(milliseconds=500),
        artifact_version="threshold-v2",
    )

    result = build_event_bars(
        trades,
        bar_type=BarType.CUSUM,
        threshold=artifact,
        threshold_config_id="cusum-fit-v2",
        source_snapshot_id=SNAPSHOT,
        build_as_of=AS_OF,
        availability_lag=timedelta(0),
        continuity=_continuity(trades),
        policy_id="event-bars-v2",
    )

    assert result.threshold_artifact_id == artifact.artifact_id
    assert result.threshold_artifact_version == "threshold-v2"
    assert result.threshold_train_end == artifact.train_end
    assert result.threshold_available_at == artifact.available_at
    assert result.threshold_provenance == "FITTED"
    assert result.bars[0].threshold_artifact_id == artifact.artifact_id
    assert result.bars[0].threshold_artifact_version == "threshold-v2"
    assert result.bars[0].threshold_train_end == artifact.train_end
    assert result.bars[0].threshold_available_at == artifact.available_at
    assert result.bars[0].threshold_provenance == "FITTED"
    assert result.bars[0].available_at >= artifact.available_at


def test_event_bar_identity_changes_for_every_material_construction_input():
    """Reusing an ID after a material policy mutation would violate immutable lineage."""
    trades = [_trade("a", 1, "100"), _trade("b", 2, "101"), _trade("c", 3, "102")]

    def bar_id(**overrides):
        rows = overrides.pop("trades", trades)
        result = build_event_bars(
            rows,
            bar_type=BarType.CUSUM,
            threshold=overrides.pop("threshold", Decimal("2")),
            threshold_config_id="cusum-fixed-v2",
            source_snapshot_id=overrides.pop("source_snapshot_id", SNAPSHOT),
            build_as_of=AS_OF,
            availability_lag=overrides.pop("availability_lag", timedelta(0)),
            continuity=overrides.pop("continuity", _continuity(rows)),
            policy_id=overrides.pop("policy_id", "event-bars-v2"),
            **overrides,
        )
        return result.bars[0].bar_id

    baseline = bar_id()
    alternative_provider = [
        trade.model_copy(update={"source": "other_provider"}) for trade in trades
    ]
    negative = [
        _trade("a", 1, "102"),
        _trade("b", 2, "101"),
        _trade("c", 3, "100"),
    ]
    ids = {
        bar_id(threshold=Decimal("1.5")),
        bar_id(availability_lag=timedelta(seconds=1)),
        bar_id(trades=alternative_provider),
        bar_id(source_snapshot_id="sha256:" + "e" * 64),
        bar_id(continuity=_continuity(trades, session_id="trade-session-2")),
        bar_id(policy_id="event-bars-v3"),
        bar_id(trades=negative),
    }
    assert baseline not in ids
    assert len(ids) == 7

    def fitted_id(artifact_id):
        artifact = ThresholdArtifact(
            artifact_id=artifact_id,
            artifact_version="threshold-v2",
            threshold=Decimal("2"),
            train_end=BASE - timedelta(seconds=2),
            available_at=BASE - timedelta(seconds=1),
        )
        return (
            build_event_bars(
                trades,
                bar_type=BarType.CUSUM,
                threshold=artifact,
                threshold_config_id="cusum-fit-v2",
                source_snapshot_id=SNAPSHOT,
                build_as_of=AS_OF,
                availability_lag=timedelta(0),
                continuity=_continuity(trades),
                policy_id="event-bars-v2",
            )
            .bars[0]
            .bar_id
        )

    assert fitted_id("sha256:" + "d" * 64) != fitted_id("sha256:" + "e" * 64)

    def temporal_id(*, train_end, available_at):
        artifact = ThresholdArtifact(
            artifact_id="sha256:" + "d" * 64,
            artifact_version="threshold-v2",
            threshold=Decimal("2"),
            train_end=train_end,
            available_at=available_at,
        )
        return (
            build_event_bars(
                trades,
                bar_type=BarType.CUSUM,
                threshold=artifact,
                threshold_config_id="cusum-fit-v2",
                source_snapshot_id=SNAPSHOT,
                build_as_of=AS_OF,
                availability_lag=timedelta(0),
                continuity=_continuity(trades),
                policy_id="event-bars-v2",
            )
            .bars[0]
            .bar_id
        )

    assert temporal_id(
        train_end=BASE - timedelta(seconds=2),
        available_at=BASE - timedelta(seconds=1),
    ) != temporal_id(
        train_end=BASE - timedelta(seconds=3),
        available_at=BASE - timedelta(milliseconds=500),
    )


def test_stream_event_bars_require_continuity_and_never_bridge_gap_or_session():
    """A gap jump must not contribute to CUSUM or merge an unfinished prior session."""
    trades = [
        _trade("a", 1, "100"),
        _trade("b", 2, "101"),
        _trade("c", 3, "103"),
        _trade("d", 4, "104"),
    ]
    with pytest.raises(ValueError, match="continuity|session"):
        build_event_bars(
            trades,
            bar_type=BarType.CUSUM,
            threshold=Decimal("2"),
            threshold_config_id="cusum-fixed-v2",
            source_snapshot_id=SNAPSHOT,
            build_as_of=AS_OF,
            availability_lag=timedelta(0),
            policy_id="event-bars-v2",
        )

    result = build_event_bars(
        trades,
        bar_type=BarType.CUSUM,
        threshold=Decimal("2"),
        threshold_config_id="cusum-fixed-v2",
        source_snapshot_id=SNAPSHOT,
        build_as_of=AS_OF,
        availability_lag=timedelta(0),
        continuity=_continuity(trades, gap_before=("c",)),
        policy_id="event-bars-v2",
    )
    assert result.bars == ()
    assert result.remainder is not None
    assert result.remainder.source_event_ids == ("c", "d")
    assert result.quarantined_remainders[0].source_event_ids == ("a", "b")
    assert result.quarantined_remainders[0].reason == "CONTINUITY_GAP"


def test_bar_builders_always_reject_even_identical_duplicate_event_ids():
    """Bar-layer dedupe would hide upstream canonicalization defects."""
    trade = _trade("duplicate", 1, "100")
    with pytest.raises(ValueError, match="duplicate source_event_id"):
        build_event_bars(
            [trade, trade],
            bar_type=BarType.VOLUME,
            threshold=Decimal("1"),
            threshold_config_id="volume-fixed-v2",
            source_snapshot_id=SNAPSHOT,
            build_as_of=AS_OF,
            availability_lag=timedelta(0),
            continuity=(
                TradeContinuity(
                    source_event_id="duplicate",
                    stream_session_id="trade-session-1",
                    continuous_from_previous=False,
                ),
            ),
            policy_id="event-bars-v2",
        )


@pytest.mark.parametrize("yaml_threshold", ["'2.5'", "2"])
def test_fitted_artifact_yaml_accepts_exact_string_or_integer(yaml_threshold, tmp_path):
    """Normal YAML numeric representations must load without binary float conversion."""
    path = tmp_path / "event-fit.yaml"
    path.write_text(
        "config_id: event-bars-v2\n"
        "availability_lag_seconds: 0\n"
        "thresholds:\n"
        "  - config_id: cusum-fit-v2\n"
        "    bar_type: CUSUM\n"
        "    fit_artifact:\n"
        f"      artifact_id: sha256:{'d' * 64}\n"
        "      artifact_version: threshold-v2\n"
        f"      threshold: {yaml_threshold}\n"
        "      train_end: 2023-12-31T00:00:00Z\n"
        "      available_at: 2023-12-31T00:00:01Z\n",
        encoding="utf-8",
    )
    loaded = load_event_bar_config(path)
    assert loaded.config.thresholds[0].fit_artifact.threshold == Decimal(
        "2.5" if "2.5" in yaml_threshold else "2"
    )


@pytest.mark.parametrize("bad", [True, 2.5])
def test_fitted_artifact_rejects_bool_and_float_thresholds(bad):
    with pytest.raises(ValidationError, match="threshold"):
        ThresholdArtifact(
            artifact_id="sha256:" + "d" * 64,
            artifact_version="threshold-v2",
            threshold=bad,
            train_end=BASE - timedelta(days=1),
            available_at=BASE - timedelta(hours=1),
        )


def test_event_cli_publishes_fitted_threshold_id_version_and_policy_lineage(tmp_path):
    """A published artifact must retain the exact fit threshold and policy identities."""
    config = tmp_path / "event.yaml"
    config.write_text(
        "config_id: event-bars-v2\n"
        "availability_lag_seconds: 0\n"
        "thresholds:\n"
        "  - config_id: cusum-fit-v2\n"
        "    bar_type: CUSUM\n"
        "    fit_artifact:\n"
        f"      artifact_id: sha256:{'d' * 64}\n"
        "      artifact_version: threshold-v2\n"
        "      threshold: '2'\n"
        "      train_end: 2023-12-31T23:59:58Z\n"
        "      available_at: 2023-12-31T23:59:59Z\n",
        encoding="utf-8",
    )
    trades = [
        _wire_trade(trade, index)[0].trades[0]
        for index, trade in enumerate(
            (_trade("a", 1, "100"), _trade("b", 2, "102"))
        )
    ]
    trades_path = tmp_path / "trades.json"
    trades_path.write_text(
        json.dumps([trade.model_dump(mode="json") for trade in trades]), encoding="utf-8"
    )
    continuity_path = tmp_path / "continuity.json"
    continuity_path.write_text(
        json.dumps([row.model_dump(mode="json") for row in _continuity(trades)]),
        encoding="utf-8",
    )
    data_root = tmp_path / "lab-data"
    source_snapshot = _approved_source(data_root)
    batch_args = _batch_args(data_root, trades)
    stdout = StringIO()

    assert (
        build_bars_main(
            [
                "--mode",
                "event",
                "--config",
                str(config),
                    *batch_args,
                "--continuity",
                str(continuity_path),
                "--source-snapshot-id",
                source_snapshot,
                "--build-as-of",
                AS_OF.isoformat(),
                "--data-root",
                str(data_root),
            ],
            stdout=stdout,
        )
        == 0
    )
    payload = json.loads(next(data_root.rglob("bars.json")).read_text(encoding="utf-8"))
    lineage = payload["threshold_lineage"][0]
    assert lineage["threshold_artifact_id"] == "sha256:" + "d" * 64
    assert lineage["threshold_artifact_version"] == "threshold-v2"
    assert lineage["threshold_provenance"] == "FITTED"
    assert lineage["threshold_train_end"] == "2023-12-31T23:59:58Z"
    assert lineage["threshold_available_at"] == "2023-12-31T23:59:59Z"
    assert lineage["policy_id"].startswith("event-bars-v2@sha256:")
    assert payload["bars"][0]["threshold_artifact_id"] == "sha256:" + "d" * 64
    assert payload["bars"][0]["threshold_train_end"] == "2023-12-31T23:59:58Z"
    assert payload["bars"][0]["threshold_available_at"] == "2023-12-31T23:59:59Z"
    match = __import__("re").search(r"output_id=(sha256:[0-9a-f]{64})", stdout.getvalue())
    assert match is not None
    manifest = json.loads(
        snapshot_manifest_path(data_root, match.group(1)).read_text(encoding="utf-8")
    )
    assert manifest["threshold_lineage"] == payload["threshold_lineage"]


def test_fixed_threshold_has_explicit_null_artifact_provenance():
    trades = [_trade("a", 1, "100")]
    result = build_event_bars(
        trades,
        bar_type=BarType.VOLUME,
        threshold=Decimal("1"),
        threshold_config_id="volume-fixed-v2",
        source_snapshot_id=SNAPSHOT,
        build_as_of=AS_OF,
        availability_lag=timedelta(0),
        continuity=_continuity(trades),
        policy_id="event-bars-v2",
    )
    assert result.threshold_provenance == "FIXED"
    assert result.threshold_artifact_id is None
    assert result.threshold_artifact_version is None
    assert result.threshold_train_end is None
    assert result.threshold_available_at is None
    assert result.bars[0].threshold_provenance == "FIXED"


def test_event_config_rejects_removed_duplicate_policy(tmp_path):
    path = tmp_path / "event.yaml"
    path.write_text(
        "config_id: event-bars-v2\n"
        "availability_lag_seconds: 0\n"
        "duplicate_policy: dedupe\n"
        "thresholds:\n"
        "  - config_id: volume-fixed-v2\n"
        "    bar_type: VOLUME\n"
        "    fixed_threshold: '1'\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate_policy"):
        load_event_bar_config(path)
