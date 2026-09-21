"""Offline Phase 1 golden replay through the public data-pipeline boundaries."""

from __future__ import annotations

import io
import json
import os
import platform
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.cli.backfill_candles import run_backfill
from indodax_lab.cli.build_bars import main as build_bars
from indodax_lab.contracts import QualityStatus
from indodax_lab.data.checksums import sha256_file
from indodax_lab.data.indodax_candles import HttpResponse
from indodax_lab.data.indodax_stream import AppendOnlyStreamWriter
from indodax_lab.data.manifest import canonical_json_bytes, snapshot_manifest_path
from indodax_lab.data.sentry import validate_snapshot
from indodax_lab.data.stream_protocol import parse_public_message
from indodax_lab.data.trade_sentry import validate_trade_batches
from indodax_lab.data.trade_wire import persist_trade_wire_artifact
from indodax_lab.universe import (
    PipelineLineageInputs,
    load_bar_artifact,
    load_book_artifact,
    load_bronze_snapshot_artifact,
    load_candle_quality_artifact,
    load_candle_wire_artifact,
    load_cap_provider_artifact,
    load_listing_artifact,
    load_materialization_profile,
    load_trade_artifacts,
    load_universe_policy_artifact,
    materialize_universe_metrics,
)
from indodax_lab.universe.coingecko_adapter import CoinGeckoAdapter
from indodax_lab.universe.snapshot import build_daily_snapshot

START = datetime(2024, 1, 1, tzinfo=UTC)
END = START + timedelta(hours=2)
RECEIVED_AT = END
CONFIG_ROOT = Path(__file__).parents[3] / "configs"
STREAM_FIXTURES = Path(__file__).parents[2] / "fixtures" / "indodax" / "stream"
PHASE1_FIXTURES = Path(__file__).parents[2] / "fixtures" / "indodax" / "phase1"


class FixtureTransport:
    """Transport double exposing fixed public wire bytes and no network surface."""

    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls = 0

    def get(self, _url, *, params, timeout):
        del params, timeout
        self.calls += 1
        return HttpResponse(
            200, {"Content-Type": "application/json", "ETag": '"phase1"'}, self.body
        )


def test_golden_raw_to_silver_replay_is_immutable_and_content_addressed(tmp_path: Path) -> None:
    """A changed raw, bronze, quality, bar, or universe link must stop the Phase 1 checkpoint."""
    first = _run_golden_pipeline(tmp_path / "first")
    replay = _run_golden_pipeline(tmp_path / "replay")
    changed_wire = _run_golden_pipeline(tmp_path / "changed-wire", mutate_candle_wire=True)
    changed_trade_wire = _run_golden_pipeline(
        tmp_path / "changed-trade-wire", mutate_trade_wire=True
    )

    assert first["bronze_rows"] == replay["bronze_rows"] == 2
    assert first["quality"] == replay["quality"] == "PASS"
    assert first["bars"] == replay["bars"] == {
        "rows": 6,
        "five_minute_ohlc": (Decimal("100"), Decimal("104"), Decimal("100"), Decimal("104")),
        "five_minute_volume": Decimal("15"),
        "gaps": [],
    }
    assert first["universe"] == replay["universe"] == {
        "btc_idr": (True, "BIG_CAP", []),
    }
    assert first["global_trade_decision_id"] == replay["global_trade_decision_id"] == (
        "sha256:5b422231814c7ac899768ee2ba7a803e335826f4954d266bb3b56d054f33b712"
    )
    assert first["snapshot_id"] == replay["snapshot_id"]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", str(first["snapshot_id"]))
    assert changed_wire["snapshot_id"] != first["snapshot_id"]
    assert changed_trade_wire["snapshot_id"] != first["snapshot_id"]
    assert first["lineage"] == replay["lineage"] == {
        "source_input_ids": (
            "sha256:09ceeeb94fa4b9db523a7a1ab8acd63cba17b8dbfe3130bc4711aaafb5c54fe8",
            "sha256:10398558fa6d4de0deb3b883f2b906bac8bc747d74e9220bead4d10c1b7b6bf9",
            "sha256:1058592f689e4652639c8cb8bff6279dfaa7b360a368ef5dd68120afb1b10855",
            "sha256:12801df3ea295ea3ed8320b9681ef82977ecd9d93cf2c346ed4c44dfee9fdf3b",
            "sha256:14fe1b4bdde66a8b51e324515cf890c8508e3a67f2b7088ec608ae24dc781cfc",
            "sha256:17b90102acf879c1825834c3be487fc2963d6db1ad10241b8fe1e65bc1bd9f56",
            "sha256:191bf5d7817d60d97947f158e135a45884c77f2dbb5c58478762a15e1c4daf7e",
            "sha256:2fcb17fba99de2dc02584f55ff05ea2f428af4e90d513e39fde42adec303b152",
            "sha256:31175f66a11dbde1c5c51e3754f2c0ea9e481d74eeee2a6d59e31de3f8f66795",
            "sha256:32b67da0f84a8902a15a3fd4d70ee31330d55164dbb740efab5aa96765985517",
            "sha256:34b156ec921962df1c2622016ee8e94c241bb9cc48da276512558dde9960dd17",
            "sha256:39f5297f6a8a4c2afb74c07eacb12a4d257c9695438517122646229a63c33af6",
            "sha256:3dd0e57e6841b4b0f54824b4ced75dcf5563f0be7c1882cc0c3a77302eac18c7",
            "sha256:3f1d19308186caf0b180fc1781c2174431b6616ab97bd6a30bf68e0debb50461",
            "sha256:3f222114a2e7d84262f81ddb01ecb67d31c2058d9d10d7a58ed431c372cc7bd5",
            "sha256:4a950368d36538ba22a3311f0e5a8832e642d97356e7e9e3c8c5ac89d51bd20b",
            "sha256:4bd37093b60f5becd88fc5b8d82fd134ca2fe301e0c8106f760671c7c75ce6db",
            "sha256:5b422231814c7ac899768ee2ba7a803e335826f4954d266bb3b56d054f33b712",
            "sha256:6841c305b663349300c2f55e804c84abc5483ffb46c42b7d0bec6c8ff5b66d9b",
            "sha256:6b74738134d0a092713215c4e9371bde5d9ab3b2d9cf4351af5cd4e36553b9b6",
            "sha256:73dbeab9fddc5feac45d6d7ae7f418c8c701ff2d3b3d61caa80081cbc94d63fd",
            "sha256:7713afb0d4c8de658513b7cc38aac6471c506e1e81c495f07d1b4172c3ab5d47",
            "sha256:7add1099b503f5a7974fcfe98ab0c8066d0c901a458d48f03a60a5424de76866",
            "sha256:80949b9d7a694abef6fe8fe0dbc836be4706855bc14e8f604e362ddcea095990",
            "sha256:876daeb2b3a202be9a881f8f192eae4a72db73991d71c1e06b03e22e7345b1d1",
            "sha256:8bb2745f86811e59ad5741e4627878492138c464155afac748466711bd6b5e1b",
            "sha256:92a3055aa7a7d9ff473afbc8983f400e1da9a33df29c14d7e1f2b1f034d3bf15",
            "sha256:95893ea7315b6550a0d14af2f89950adb980c909f139665b4918a7e98054748a",
            "sha256:97b97afbab3b61ab625b600872c3ba761b95ed95fb8221c1d3ebb622d615c430",
            "sha256:9db44ea164ed370feb18125b35aa84a0dc7888d9a3b10933b8a07b509573529e",
            "sha256:9e8bcbed9e7bbd120bfa4bc93b634e0784c00f671b31a103161ed5cc2f8a2c0d",
            "sha256:9f70e18453bbfc9038d58267d8c1f85dda383c6ba80e91ff0a6920d69b289bfb",
            "sha256:a865e14801a8fb152009f6f75de8e68865254589e3890ce10713056a4c74fee2",
            "sha256:ac72cc5d779fde2f4cf5183232da2241538fa81acd09a6067013d7d9fafa3f53",
            "sha256:b22e2eb5e77f61258ee0d30c84cd44b06af6fa9ea1fa2360df64df0ff821e689",
            "sha256:bfcbaef63f43fd82ba6bc841467980aa78805be745ddbd572cb76f95b00689ae",
            "sha256:bfe4388b2ec29b9270675a0e42633172e7d058ceb38e8b4e2d745f81ff012059",
            "sha256:cb50c8d35cdcb1e93f48fb22db90f82c00b780e4101e98b5ee4069f5c854bcfe",
            "sha256:dd2b90489b6de24c637452a70a867d520146eb3413f35a4073d042bcb9e19446",
            "sha256:dd905e56161dae110ce29d7e10b90c59f7f718d04587e3b547e15e2ef07f75f2",
            "sha256:de0a200b74f2ae22cf69e76d1f2a8f591ee201ab46839ffc6d3abf4f0675b562",
            "sha256:e3322b147458bdcb66630f4e7c06aaf294a3132b2baeabc75a674ab9221c399b",
            "sha256:ea5bdfd41220409f417dd11135fb5d6cf1c6888e74a08c28d76a384cd1291194",
            "sha256:f284a94a45794b0ee845dce46e0b63dde9d818b2ab930f02442e4c7cc7524c11",
            "sha256:f99182814560ed6688ba33e1a8f4cbba22731142d558da50d8bc942d964fcbd1",
        ),
    }


def test_24_hour_trade_batch_resource_smoke_records_child_vm_hwm_without_hardware_gate() -> None:
    """Linux-only child measurement isolates bounded 24-hour production-shaped bar batching."""
    if platform.system() != "Linux":
        pytest.skip("VmHWM resource smoke needs Linux /proc; use platform profiler elsewhere")
    code = """
import runpy, tempfile, time
from pathlib import Path
ns = runpy.run_path('tests/integration/lab/test_raw_to_silver_pipeline.py')
started = time.perf_counter()
result = ns['_run_golden_pipeline'](
    Path(tempfile.mkdtemp(prefix='phase1-resource-')),
    trade_count=1440,
    trade_batch_size=128,
    build_cutoff=ns['START'] + ns['timedelta'](days=1, seconds=5),
)
hwm = next(line.split()[1] for line in open('/proc/self/status') if line.startswith('VmHWM:'))
elapsed = time.perf_counter() - started
print(f"rows={result['bars']['rows']} elapsed_seconds={elapsed:.6f} vm_hwm_kib={hwm}")
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        cwd=Path(__file__).parents[3],
        env=environment,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    match = re.fullmatch(
        r"rows=1728 elapsed_seconds=([0-9.]+) vm_hwm_kib=(\d+)\n", completed.stdout
    )
    assert match is not None
    assert float(match.group(1)) >= 0
    assert int(match.group(2)) > 0
    print(f"phase1_resource_smoke child_{completed.stdout.strip()}")


def test_quarantined_trade_batch_cannot_publish_bars(tmp_path: Path) -> None:
    """The trade-data gate refuses a quarantined writer batch before publication."""
    with pytest.raises(ValueError, match="non-PASS events"):
        _run_golden_pipeline(tmp_path, quarantine_trade_wire=True)
    assert not list((tmp_path / "silver" / "dataset=bars").glob("**/bars.json"))


def _run_golden_pipeline(
    root: Path,
    *,
    mutate_candle_wire: bool = False,
    mutate_trade_wire: bool = False,
    quarantine_trade_wire: bool = False,
    trade_count: int = 5,
    trade_batch_size: int = 100,
    build_cutoff: datetime = END,
) -> dict[str, object]:
    body = json.dumps(
        [
            {
                "Time": 1704067200,
                "Open": "100",
                "High": "103",
                "Low": "99",
                "Close": "102",
                "Volume": "2",
            },
            {
                "Time": 1704070800,
                "Open": "102",
                "High": "104",
                "Low": "101",
                "Close": "103",
                "Volume": "3",
            },
        ],
        separators=(",", ":"),
    ).encode()
    if mutate_candle_wire:
        body = body.replace(b'"Close":"103"', b'"Close":"103.5"')
    transport = FixtureTransport(body)
    bronze = run_backfill(
        data_root=root,
        pair="btc_idr",
        interval="1h",
        start=START,
        end=END,
        transport=transport,
        clock=lambda: RECEIVED_AT,
        sleeper=lambda _seconds: None,
        rate_limit_seconds=0,
    )
    assert transport.calls == 1
    assert bronze.dataset_snapshot_ids
    bronze_snapshot_id = bronze.dataset_snapshot_ids[0]
    checkpoint_path = next(root.glob("ops/backfills/candles/window=*/completed.json"))
    candle_wire = load_candle_wire_artifact(root, checkpoint_path)
    bronze_artifact = load_bronze_snapshot_artifact(root, bronze_snapshot_id)

    quality = validate_snapshot(
        root,
        bronze_snapshot_id,
        expected_start=START,
        expected_end=END,
        as_of=END,
    )
    if quality.report.status != "PASS" or not quality.eligible_for_silver:
        raise AssertionError(f"bronze sentry did not approve snapshot: {quality.report.to_dict()}")

    candle_quality = load_candle_quality_artifact(root, bronze_artifact)
    bars = _build_bars(
        root,
        bronze_snapshot_id,
        trade_count=trade_count,
        trade_batch_size=trade_batch_size,
        mutate_trade_wire=mutate_trade_wire,
        quarantine_trade_wire=quarantine_trade_wire,
    )
    policy = load_universe_policy_artifact(CONFIG_ROOT / "universe" / "default_v1.yaml")
    metrics = _materialize_metrics(
        root,
        bars,
        candle_wire=candle_wire,
        bronze_artifact=bronze_artifact,
        candle_quality=candle_quality,
        policy=policy,
        build_cutoff=build_cutoff,
    )
    artifact = build_daily_snapshot(
        data_root=root,
        metrics=[metrics],
        policy=policy.loaded.policy,
        policy_source_id=policy.loaded.source_id,
    )
    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
    if manifest["universe_snapshot_id"] != artifact.universe_snapshot_id:
        raise AssertionError("universe manifest identity does not match its published snapshot")
    if manifest["partition"]["sha256"] != sha256_file(artifact.data_path):
        raise AssertionError("universe manifest checksum does not match final snapshot bytes")
    expected_ids = tuple(sorted({*metrics.additional_source_input_ids, metrics.cap_input_id}))
    if tuple(artifact.decisions[0].source_input_ids) != expected_ids:
        raise AssertionError("universe decisions lost their time-bar lineage")

    return {
        "bronze_rows": bronze.accepted_rows,
        "quality": quality.report.status,
        "bars": {
            "rows": bars["rows"],
            "five_minute_ohlc": bars["five_minute_ohlc"],
            "five_minute_volume": bars["five_minute_volume"],
            "gaps": bars["gaps"],
        },
        "universe": {
            decision.pair: (
                decision.eligible,
                decision.tier,
                [reason.value for reason in decision.reason_codes],
            )
            for decision in artifact.decisions
        },
        "snapshot_id": artifact.universe_snapshot_id,
        "global_trade_decision_id": bars["global_trade_decision_id"],
        "lineage": {
            "source_input_ids": tuple(artifact.decisions[0].source_input_ids),
        },
    }


def _build_bars(
    root: Path,
    bronze_snapshot_id: str,
    *,
    trade_count: int = 5,
    trade_batch_size: int = 100,
    mutate_trade_wire: bool = False,
    quarantine_trade_wire: bool = False,
) -> dict[str, object]:
    config = root / "phase1-time-bars.yaml"
    config.write_text(
        "config_id: phase1-time-bars-v1\nsource_selection: trades\nbase_interval: 1m\n"
        "output_intervals: [1m, 5m]\navailability_lag_seconds: 5\nprice_tolerance: '0'\n"
        "volume_tolerance: '0'\nrequire_complete_reconciliation: true\n",
        encoding="utf-8",
    )
    trade_batches = _write_public_trade_batch(
        root,
        trade_count=trade_count,
        max_batch_size=trade_batch_size,
        mutate_trade_wire=mutate_trade_wire,
        quarantine_trade_wire=quarantine_trade_wire,
    )
    output = io.StringIO()
    trade_decision = validate_trade_batches(root, trade_batches)
    exit_code = build_bars(
        [
            "--mode", "time", "--config", str(config),
            *sum((["--trade-batch", str(batch)] for batch in trade_batches), []),
            "--trade-quality-decision", str(trade_decision.record_path),
            "--source-snapshot-id", bronze_snapshot_id, "--source-session-id", "phase1-trades-1",
            "--start", START.isoformat(),
            "--end", (START + timedelta(minutes=trade_count)).isoformat(),
            "--data-root", str(root),
        ],
        stdout=output,
    )
    assert exit_code == 0
    match = re.search(r"output_id=(sha256:[0-9a-f]{64})", output.getvalue())
    assert match is not None
    output_id = match.group(1)
    manifest = json.loads(snapshot_manifest_path(root, output_id).read_text())
    if manifest["source_snapshot_id"] != bronze_snapshot_id:
        raise AssertionError("bar manifest source snapshot lineage changed")
    bars_path = root / manifest["partition"]["path"]
    if manifest["partition"]["sha256"] != sha256_file(bars_path):
        raise AssertionError("bar manifest checksum changed")
    payload = json.loads(bars_path.read_text())
    five_minute = next(row for row in payload["bars"] if row["interval"] == "5m")
    trade_artifacts = load_trade_artifacts(root, trade_batches, trade_decision.record_path)
    bar_artifact = load_bar_artifact(root, output_id, config)
    return {
        "rows": len(payload["bars"]),
        "gaps": payload["gaps"],
        "five_minute_ohlc": tuple(
            Decimal(five_minute[field]) for field in ("open", "high", "low", "close")
        ),
        "five_minute_volume": Decimal(five_minute["base_volume"]),
        "trade_artifacts": trade_artifacts,
        "bar_artifact": bar_artifact,
        "global_trade_decision_id": trade_artifacts.quality.decision_id,
    }


def _write_public_trade_batch(
    root: Path,
    *,
    trade_count: int = 5,
    max_batch_size: int = 100,
    mutate_trade_wire: bool = False,
    quarantine_trade_wire: bool = False,
) -> tuple[Path, ...]:
    """Replay official public-trade wire rows through the durable bounded batch interface."""
    writer = AppendOnlyStreamWriter(root, max_batch_size=max_batch_size)
    batches: list[Path] = []
    for index in range(trade_count):
        wire = json.loads((STREAM_FIXTURES / "public_trade.json").read_text())
        row = wire["result"]["data"]["data"][0]
        row[1] = int((START + timedelta(minutes=index, seconds=1)).timestamp())
        row[2] = 21_999_427 + index
        wire["result"]["data"]["offset"] = 243_556 + index
        price = Decimal(100 + index)
        if mutate_trade_wire and index == 3:
            price += Decimal("0.5")
        row[4] = str(price)
        row[5] = str(price * Decimal(index + 1))
        row[6] = str(index + 1)
        parsed = parse_public_message(
            wire,
            ingested_at=START + timedelta(minutes=index, seconds=2),
            expected_pair="btc_idr",
        )
        event_rows = [event.model_dump(mode="json") for event in parsed.trades]
        if quarantine_trade_wire and index == 0:
            event_rows[0]["quality_status"] = QualityStatus.QUARANTINED.value
        received_at = START + timedelta(minutes=index, seconds=2)
        trade_wire = persist_trade_wire_artifact(
            root,
            body=canonical_json_bytes(wire),
            received_at=received_at,
            expected_pair="btc_idr",
            channel=parsed.channel or "",
            offset=parsed.offset if parsed.offset is not None else -1,
        )
        batch = writer.append(
            {
                "kind": parsed.kind,
                "offset": parsed.offset,
                "events": event_rows,
                "trade_wire": trade_wire.to_record(root),
            },
            acknowledged_offset=parsed.offset or 0,
            checkpoint_key=parsed.channel or "trade",
        )
        if batch is not None:
            batches.append(batch)
    batch = writer.flush()
    if batch is not None:
        batches.append(batch)
    assert batches
    return tuple(batches)


def _materialize_metrics(
    root: Path,
    bars: dict[str, object],
    *,
    candle_wire,
    bronze_artifact,
    candle_quality,
    policy,
    build_cutoff: datetime,
):
    """Use raw listing/cap/book fixtures and parsed trade/bar artifacts as the only inputs."""
    listing = load_listing_artifact(PHASE1_FIXTURES / "listing.json")
    cap_raw = json.loads((PHASE1_FIXTURES / "cap.json").read_bytes())
    book_wire = json.loads((STREAM_FIXTURES / "book_snapshot.json").read_text())
    parsed_book = parse_public_message(
        book_wire,
        ingested_at=START + timedelta(seconds=3),
        book_session_id="phase1-book-session",
        book_event_type="SNAPSHOT",
        expected_pair="btc_idr",
    )
    book_writer = AppendOnlyStreamWriter(root, max_batch_size=1)
    book_batch = book_writer.append(
        {
            "kind": parsed_book.kind,
            "offset": parsed_book.offset,
            "payload": book_wire,
            "events": [event.model_dump(mode="json") for event in parsed_book.books],
        },
        acknowledged_offset=parsed_book.offset or 0,
        checkpoint_key=parsed_book.channel or "book",
    )
    assert book_batch is not None
    book = load_book_artifact(root, book_batch)
    cap_body = json.dumps(
        [
            {
                "id": listing.evidence.provider_asset_id,
                "market_cap": int(cap_raw["market_cap_usd"]),
                "market_cap_rank": cap_raw["market_cap_rank"],
                "last_updated": cap_raw["source_ts"],
            }
        ],
        separators=(",", ":"),
    ).encode()
    cap_batch = CoinGeckoAdapter(
        transport=FixtureTransport(cap_body),
        data_root=root,
        ttl_seconds=172800,
    ).fetch_market_caps(
        asset_ids=(listing.evidence.provider_asset_id,),
        as_of_date=START.date(),
        received_at=datetime.fromisoformat(cap_raw["available_at"].replace("Z", "+00:00")),
    )
    cap = load_cap_provider_artifact(cap_batch, listing)
    profile = load_materialization_profile(
        CONFIG_ROOT / "universe" / "phase1_materialization_v1.yaml"
    )
    trade_artifacts = bars["trade_artifacts"]
    bar_artifact = bars["bar_artifact"]
    lineage = PipelineLineageInputs(
        candle_wires=(candle_wire,),
        bronze_snapshot=bronze_artifact,
        candle_quality=candle_quality,
        trade_wires=trade_artifacts.wires,
        trade_batches=trade_artifacts.batches,
        global_trade_quality=trade_artifacts.quality,
        bars=bar_artifact.reference,
        book=book.reference,
        listing=listing.reference,
        cap=cap.reference,
        profile=profile.reference,
        universe_policy=policy.reference,
    )
    return materialize_universe_metrics(
        as_of_date=START.date(),
        build_cutoff=build_cutoff,
        listing=listing.evidence,
        cap=cap.evidence,
        trades=trade_artifacts.trades,
        bars=bar_artifact.bars,
        books=book.books,
        lineage=lineage,
    )
