"""Offline-only CLI for content-addressed time and event-bar builds."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TextIO

from indodax_lab.contracts import TradeEvent
from indodax_lab.data.bars import (
    BarType,
    ReconciliationPolicy,
    SilverBar,
    SourceSelection,
    aggregate_time_bars,
    compare_time_bar_sources,
    load_time_bar_config,
    resample_time_bars,
)
from indodax_lab.data.checksums import sha256_bytes
from indodax_lab.data.event_bars import TradeContinuity, build_event_bars, load_event_bar_config
from indodax_lab.data.manifest import canonical_json_bytes, snapshot_manifest_path
from indodax_lab.data.publication import publish_immutable_bytes, rollback_or_raise_indeterminate
from indodax_lab.data.sentry import require_approved_snapshot_decision
from indodax_lab.data.trade_sentry import require_existing_approved_trade_decision


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _arguments() -> argparse.ArgumentParser:
    parser = _Parser(description="Build immutable bars from explicit offline trade JSON")
    parser.add_argument("--mode", choices=("time", "event"), required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--trades", type=Path)
    parser.add_argument("--trade-batch", type=Path, action="append")
    parser.add_argument("--trade-quality-decision", type=Path)
    parser.add_argument("--official-bars", type=Path)
    parser.add_argument("--official-provider")
    parser.add_argument("--official-snapshot-id")
    parser.add_argument("--source-snapshot-id", required=True)
    parser.add_argument("--source-session-id")
    parser.add_argument("--continuity", type=Path)
    parser.add_argument("--start", type=_utc_datetime)
    parser.add_argument("--end", type=_utc_datetime)
    parser.add_argument("--build-as-of", type=_utc_datetime)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--approve-source-warnings", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None, *, stdout: TextIO = sys.stdout) -> int:
    """Build from local inputs only; dry-run computes identity without filesystem output."""
    arguments = _arguments().parse_args(argv)
    if not arguments.dry_run:
        quality = require_approved_snapshot_decision(
            arguments.data_root,
            arguments.source_snapshot_id,
            approve_warnings=arguments.approve_source_warnings,
        )
    else:
        quality = None
    if (arguments.trades is None) == (arguments.trade_batch is None):
        raise ValueError("provide exactly one of --trades or --trade-batch")
    if arguments.trades is not None:
        if not arguments.dry_run:
            raise ValueError("normal bar publication requires durable --trade-batch inputs")
        trades = _read_trades(arguments.trades)
        trade_input = {"kind": "json", "path": arguments.trades.name}
    else:
        assert arguments.trade_batch is not None
        if not arguments.dry_run and arguments.trade_quality_decision is None:
            raise ValueError("normal bar publication requires --trade-quality-decision")
        decision = (
            require_existing_approved_trade_decision(
                arguments.data_root,
                tuple(arguments.trade_batch),
                arguments.trade_quality_decision,
            )
            if not arguments.dry_run
            else None
        )
        trades = tuple(event for path in arguments.trade_batch for event in _read_trade_batch(path))
        trade_input = {
            "kind": "public-market-stream-batches",
            "batches": [
                {
                    "path": path.relative_to(arguments.data_root).as_posix(),
                    "sha256": sha256_bytes(path.read_bytes()),
                }
                for path in (() if decision is None else decision.batch_paths)
            ],
            "quality_record": (
                decision.record_path.relative_to(arguments.data_root).as_posix()
                if decision is not None else None
            ),
            "quality_sha256": decision.record_sha256 if decision is not None else None,
        }
    if arguments.mode == "time":
        if arguments.start is None or arguments.end is None:
            raise ValueError("time mode requires --start and --end")
        if not arguments.source_session_id:
            raise ValueError("time mode requires --source-session-id")
        if arguments.official_bars is not None and (
            not arguments.official_provider or not arguments.official_snapshot_id
        ):
            raise ValueError(
                "--official-provider and --official-snapshot-id are required with official bars"
            )
        loaded = load_time_bar_config(arguments.config)
        payload = _build_time_payload(
            trades=trades,
            config=loaded.config,
            config_source_id=loaded.source_id,
            source_snapshot_id=arguments.source_snapshot_id,
            source_session_id=arguments.source_session_id,
            start=arguments.start,
            end=arguments.end,
            official_path=arguments.official_bars,
            official_provider=arguments.official_provider,
            official_snapshot_id=arguments.official_snapshot_id,
            source_quality=_source_quality_row(quality, arguments.data_root),
            trade_input=trade_input,
        )
    else:
        if arguments.build_as_of is None:
            raise ValueError("event mode requires --build-as-of")
        if arguments.continuity is None:
            raise ValueError("event mode requires explicit --continuity")
        loaded_event = load_event_bar_config(arguments.config)
        payload = _build_event_payload(
            trades=trades,
            config=loaded_event.config,
            config_source_id=loaded_event.source_id,
            source_snapshot_id=arguments.source_snapshot_id,
            build_as_of=arguments.build_as_of,
            continuity=_read_continuity(arguments.continuity),
            source_quality=_source_quality_row(quality, arguments.data_root),
            trade_input=trade_input,
        )

    output_id = f"sha256:{sha256_bytes(canonical_json_bytes(payload))}"
    rows = payload["bars"]
    assert isinstance(rows, list)
    stdout.write(f"bars={len(rows)} output_id={output_id}")
    if arguments.dry_run:
        stdout.write(" dry_run=true\n")
        return 0

    artifact_path, manifest_path = _publish(
        data_root=arguments.data_root,
        output_id=output_id,
        source_snapshot_id=arguments.source_snapshot_id,
        payload=payload,
    )
    stdout.write(f" artifact={artifact_path} manifest={manifest_path}\n")
    return 0


def _build_time_payload(
    *,
    trades: tuple[TradeEvent, ...],
    config,
    config_source_id: str,
    source_snapshot_id: str,
    source_session_id: str,
    start: datetime,
    end: datetime,
    official_path: Path | None,
    official_provider: str | None,
    official_snapshot_id: str | None,
    source_quality,
    trade_input: dict[str, object],
) -> dict[str, object]:
    lag = timedelta(seconds=config.availability_lag_seconds)
    baseline = aggregate_time_bars(
        trades,
        interval=config.base_interval,
        window_start=start,
        window_end=end,
        availability_lag=lag,
        source_snapshot_id=source_snapshot_id,
        source_session_id=source_session_id,
        policy_id=f"{config.config_id}@{config_source_id}",
    )
    by_interval = {config.base_interval: baseline}
    for interval in config.output_intervals[1:]:
        by_interval[interval] = resample_time_bars(
            baseline.bars,
            target_interval=interval,
            window_start=start,
            window_end=end,
            availability_lag=lag,
            policy_id=f"{config.config_id}@{config_source_id}",
        )
    derived = tuple(
        bar for interval in config.output_intervals for bar in by_interval[interval].bars
    )
    mismatch_rows: list[dict[str, object]] = []
    comparison_policy = None
    official: tuple[SilverBar, ...] = ()
    if official_path is not None:
        assert official_provider is not None and official_snapshot_id is not None
        official = _read_bars(official_path)
        if not trades or not official:
            raise ValueError("official reconciliation requires non-empty trade and official rows")
        _validate_official_sequence(
            official,
            pair=trades[0].pair.pair,
            provider=official_provider,
            snapshot_id=official_snapshot_id,
            allowed_intervals=config.output_intervals,
        )
        comparison_policy = ReconciliationPolicy(
            pair=trades[0].pair.pair,
            derived_source=trades[0].source,
            derived_snapshot_id=source_snapshot_id,
            official_source=official_provider,
            official_snapshot_id=official_snapshot_id,
            price_tolerance=config.price_tolerance,
            volume_tolerance=config.volume_tolerance,
            require_complete=config.require_complete_reconciliation,
        )
    if config.source_selection is SourceSelection.OFFICIAL:
        if official_path is None:
            raise ValueError(
                "official source_selection requires explicit --official-bars offline input"
            )
        assert comparison_policy is not None
        selected: list[SilverBar] = []
        for interval in config.output_intervals:
            comparison = compare_time_bar_sources(
                derived=[bar for bar in derived if bar.interval == interval],
                official=[bar for bar in official if bar.interval == interval],
                selection=config.source_selection,
                policy=comparison_policy,
            )
            selected.extend(comparison.selected)
            mismatch_rows.extend(row.model_dump(mode="json") for row in comparison.mismatches)
        bars = tuple(selected)
    else:
        bars = derived
        if comparison_policy is not None:
            for interval in config.output_intervals:
                comparison = compare_time_bar_sources(
                    derived=[bar for bar in derived if bar.interval == interval],
                    official=[bar for bar in official if bar.interval == interval],
                    selection=config.source_selection,
                    policy=comparison_policy,
                )
                mismatch_rows.extend(row.model_dump(mode="json") for row in comparison.mismatches)
    gap_rows = [
        {"interval": interval, **gap.model_dump(mode="json")}
        for interval in config.output_intervals
        for gap in by_interval[interval].gaps
    ]
    return {
        "dataset": "silver_bars_v1",
        "mode": "time",
        "config_id": config.config_id,
        "config_source_id": config_source_id,
        "source_snapshot_id": source_snapshot_id,
        "source_quality": source_quality,
        "trade_input": trade_input,
        "source_selection": config.source_selection.value,
        "official_anchor": (
            {
                "provider": official_provider,
                "snapshot_id": official_snapshot_id,
            }
            if official_path is not None
            else None
        ),
        "bars": [bar.model_dump(mode="json") for bar in sorted(bars, key=_bar_key)],
        "gaps": gap_rows,
        "mismatches": mismatch_rows,
    }


def _build_event_payload(
    *,
    trades: tuple[TradeEvent, ...],
    config,
    config_source_id: str,
    source_snapshot_id: str,
    build_as_of: datetime,
    continuity: tuple[TradeContinuity, ...],
    source_quality,
    trade_input: dict[str, object],
) -> dict[str, object]:
    bars: list[SilverBar] = []
    remainders: list[dict[str, object]] = []
    quarantined_remainders: list[dict[str, object]] = []
    threshold_lineage: list[dict[str, object]] = []
    lag = timedelta(seconds=config.availability_lag_seconds)
    for registered in config.thresholds:
        threshold = (
            registered.fixed_threshold
            if registered.fixed_threshold is not None
            else registered.fit_artifact
        )
        if threshold is None:
            raise ValueError("registered event threshold has no source")
        result = build_event_bars(
            trades,
            bar_type=registered.bar_type,
            threshold=threshold,
            threshold_config_id=registered.config_id,
            source_snapshot_id=source_snapshot_id,
            build_as_of=build_as_of,
            availability_lag=lag,
            continuity=continuity,
            policy_id=f"{config.config_id}@{config_source_id}",
        )
        bars.extend(result.bars)
        if result.remainder is not None:
            remainders.append(result.remainder.model_dump(mode="json"))
        quarantined_remainders.extend(
            remainder.model_dump(mode="json") for remainder in result.quarantined_remainders
        )
        threshold_lineage.append(
            {
                "threshold_config_id": registered.config_id,
                "bar_type": registered.bar_type.value,
                "threshold_value": str(
                    registered.fixed_threshold
                    if registered.fixed_threshold is not None
                    else registered.fit_artifact.threshold
                ),
                "threshold_provenance": result.threshold_provenance,
                "threshold_artifact_id": result.threshold_artifact_id,
                "threshold_artifact_version": result.threshold_artifact_version,
                "threshold_train_end": _optional_utc_iso(result.threshold_train_end),
                "threshold_available_at": _optional_utc_iso(result.threshold_available_at),
                "policy_id": f"{config.config_id}@{config_source_id}",
            }
        )
    return {
        "dataset": "silver_bars_v1",
        "mode": "event",
        "config_id": config.config_id,
        "config_source_id": config_source_id,
        "source_snapshot_id": source_snapshot_id,
        "source_quality": source_quality,
        "trade_input": trade_input,
        "build_as_of": build_as_of.isoformat(),
        "bars": [bar.model_dump(mode="json") for bar in sorted(bars, key=_bar_key)],
        "remainders": remainders,
        "quarantined_remainders": quarantined_remainders,
        "threshold_lineage": threshold_lineage,
    }


def _publish(
    *, data_root: Path, output_id: str, source_snapshot_id: str, payload: dict[str, object]
) -> tuple[Path, Path]:
    digest = output_id.removeprefix("sha256:")
    artifact_path = (
        Path(data_root) / "silver" / "dataset=bars" / "schema=v1" / f"output={digest}" / "bars.json"
    )
    artifact_bytes = canonical_json_bytes(payload)
    manifest_path = snapshot_manifest_path(Path(data_root), output_id)
    manifest = {
        "dataset": "silver_bars_v1",
        "manifest_version": "1.0.0",
        "schema_version": "1.0.0",
        "bars_output_id": output_id,
        "source_snapshot_id": source_snapshot_id,
        "source_quality": payload.get("source_quality"),
        "trade_input": payload.get("trade_input"),
        "row_count": len(payload["bars"]),
        "threshold_lineage": payload.get("threshold_lineage", []),
        "partition": {
            "path": artifact_path.relative_to(data_root).as_posix(),
            "sha256": sha256_bytes(artifact_bytes),
            "size_bytes": len(artifact_bytes),
            "row_count": len(payload["bars"]),
        },
    }
    published = publish_immutable_bytes(artifact_path, artifact_bytes)
    try:
        publish_immutable_bytes(manifest_path, canonical_json_bytes(manifest))
    except Exception:
        if published:
            rollback_or_raise_indeterminate(artifact_path, "bars manifest publication")
        raise
    return artifact_path, manifest_path


def _source_quality_row(decision, data_root: Path) -> dict[str, object] | None:
    if decision is None:
        return None
    return {
        "record_path": decision.record_path.relative_to(data_root).as_posix(),
        "record_sha256": decision.record_sha256,
        "status": decision.status,
        "source_checksums": list(decision.source_checksums),
    }


def _read_trades(path: Path) -> tuple[TradeEvent, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal)
    if not isinstance(raw, list):
        raise ValueError("trades JSON must contain one array")
    rows = []
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError("each trade JSON row must be an object")
        converted = dict(row)
        for field in ("price", "base_qty", "quote_qty"):
            converted[field] = _json_decimal(converted.get(field), field)
        rows.append(TradeEvent.model_validate(converted))
    return tuple(rows)


def _read_trade_batch(path: Path) -> tuple[TradeEvent, ...]:
    """Load one immutable public-stream batch and preserve only public TRADE events."""
    raw = Path(path).read_bytes()
    digest = sha256_bytes(raw)
    if Path(path).name != f"batch={digest}.jsonl":
        raise ValueError("trade batch filename checksum does not match its bytes")
    rows: list[TradeEvent] = []
    for line in raw.splitlines():
        record = json.loads(line)
        if not isinstance(record, dict) or record.get("kind") != "TRADE":
            continue
        events = record.get("events")
        if not isinstance(events, list):
            raise ValueError("trade batch TRADE record has invalid events")
        for event in events:
            if not isinstance(event, dict):
                raise ValueError("trade batch event is invalid")
            converted = dict(event)
            for field in ("price", "base_qty", "quote_qty"):
                converted[field] = _json_decimal(converted.get(field), field)
            rows.append(TradeEvent.model_validate(converted))
    if not rows:
        raise ValueError("trade batch contains no public trades")
    return tuple(rows)


def _read_bars(path: Path) -> tuple[SilverBar, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal)
    if not isinstance(raw, list):
        raise ValueError("official bars JSON must contain one array")
    rows = []
    decimal_fields = (
        "open",
        "high",
        "low",
        "close",
        "base_volume",
        "quote_volume",
        "buy_base_volume",
        "sell_base_volume",
    )
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError("each official bar JSON row must be an object")
        converted = dict(row)
        for field in decimal_fields:
            if converted.get(field) is not None:
                converted[field] = _json_decimal(converted[field], field)
        rows.append(SilverBar.model_validate(converted))
    return tuple(rows)


def _read_continuity(path: Path) -> tuple[TradeContinuity, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("continuity JSON must contain one array")
    return tuple(TradeContinuity.model_validate(row) for row in raw)


def _validate_official_sequence(
    bars: tuple[SilverBar, ...],
    *,
    pair: str,
    provider: str,
    snapshot_id: str,
    allowed_intervals: tuple[str, ...],
) -> None:
    """Reject any official row outside the independently declared whole-file contract."""
    for bar in bars:
        if bar.pair != pair:
            raise ValueError("official pair does not match requested trade pair")
        if bar.source != provider:
            raise ValueError("official source does not match --official-provider")
        if bar.source_snapshot_id != snapshot_id:
            raise ValueError("official snapshot does not match --official-snapshot-id")
        if bar.bar_type is not BarType.TIME:
            raise ValueError("official bars must all use TIME bar_type")
        if bar.interval not in allowed_intervals:
            raise ValueError("official interval is outside configured output intervals")
        if bar.available_at < bar.close_time:
            raise ValueError("official final bar must be available no earlier than close_time")


def _json_decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{field} must not use binary float")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (str, int)):
        return Decimal(str(value))
    raise ValueError(f"{field} must be an exact decimal string or integer")


def _utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamps must use timezone-aware UTC ISO-8601")
    return parsed


def _optional_utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _bar_key(bar: SilverBar) -> tuple[str, str, datetime, str]:
    return (bar.bar_type.value, bar.interval or "", bar.open_time, bar.bar_id)


if __name__ == "__main__":
    raise SystemExit(main())
