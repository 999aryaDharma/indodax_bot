"""DATA-07 acceptance: selectable public collection and coverage workflow.

Fake transport + temporary state only. No network, no credentials, no live DB.
"""
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from indodax_lab.contracts.common import CanonicalPair
from indodax_lab.data.dataset_registry import DatasetCoverageError, DatasetRequest
from indodax_lab.data.indodax_candles import HttpResponse
from indodax_lab.data.selectable_collection import (
    CollectionCapabilities,
    SelectableCollector,
)

START = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
END = datetime(2026, 1, 1, 4, 0, tzinfo=UTC)
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
EPOCHS = [int((START + timedelta(hours=h)).timestamp()) for h in range(4)]


def _payload(epochs):
    n = len(epochs)
    return {
        "t": epochs,
        "o": [100.0 + i for i in range(n)],
        "h": [101.0 + i for i in range(n)],
        "l": [99.0 + i for i in range(n)],
        "c": [100.5 + i for i in range(n)],
        "v": [10.0 + i for i in range(n)],
    }


class FakeTransport:
    """Public history_v2 stand-in; records every call, knows no credentials."""

    def __init__(self, mode="full"):
        self.mode = mode
        self.calls = []

    def get(self, url, *, params, timeout):
        params = dict(params)
        epochs = list(EPOCHS)
        if self.mode == "gap":
            epochs = [e for e in epochs if e != EPOCHS[1]]
        body = json.dumps(_payload(epochs)).encode()
        self.calls.append({"url": url, "params": params, "body": body})
        return HttpResponse(status_code=200, headers={}, body=body)


def _service(tmp_path: Path, mode="full", capabilities=None, admission=None):

    data_root = tmp_path / "data"
    data_root.mkdir(exist_ok=True)
    fake = FakeTransport(mode)
    wires: list = []
    service = SelectableCollector(
        data_root=data_root,
        registry_root=data_root / "registry",
        queue_path=data_root / "jobs.sqlite",
        transport=fake,
        clock=lambda: NOW,
        capabilities=capabilities or CollectionCapabilities.defaults(),
        admission=admission,
        wire_sink=wires.append,
    )
    return service, fake, wires


def _request(pair="btc_idr", timeframe="1h", end=END):
    return DatasetRequest(
        venue="indodax",
        pair=pair,
        timeframe=timeframe,
        start=START,
        end=end,
        source_id="indodax-history-v2",
        source_version="v1",
    )


def _job_count(data_root: Path) -> int:
    conn = sqlite3.connect(str(data_root / "jobs.sqlite"))
    try:
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    finally:
        conn.close()


def test_data_07_0(tmp_path):
    """DATA-07-AC0: unsupported pair/timeframe rejects before any fetch."""
    service, fake, _ = _service(tmp_path)
    bad_pair = service.collect(_request(pair="doge_idr"), "req-0a")
    assert bad_pair.status == "REJECTED"
    assert bad_pair.reason.startswith("UNSUPPORTED_PAIR:")
    assert bad_pair.dataset_ref is None
    bad_tf = service.collect(_request(timeframe="2h"), "req-0b")
    assert bad_tf.status == "REJECTED"
    assert bad_tf.reason.startswith("UNSUPPORTED_TIMEFRAME:")
    assert fake.calls == []
    assert _job_count(tmp_path / "data") == 0
    with pytest.raises(DatasetCoverageError):
        service.registry.find("indodax", "doge_idr", "1h", START, END)


def test_data_07_1(tmp_path):
    """DATA-07-AC1: range gaps stay explicit and never read as complete."""
    service, _, _ = _service(tmp_path, mode="gap")
    result = service.collect(_request(), "req-1")
    assert result.status == "COLLECTED"
    assert result.complete_coverage is False
    assert result.dataset_ref is not None
    assert result.quality is not None
    assert result.quality.status == "WARN"
    assert result.quality.silver_eligible is False
    assert list(result.quality.gap_ranges) == [
        (
            datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
        )
    ]
    manifest = service.registry.get(result.dataset_ref)
    assert len(manifest.missing_intervals) == 1


def test_data_07_2(tmp_path):
    """DATA-07-AC2: identical retry resumes durable state, never republishes."""
    service, fake, _ = _service(tmp_path)
    first = service.collect(_request(), "req-2")
    assert first.status == "COLLECTED"
    assert first.resumed is False
    catalog_before = (tmp_path / "data" / "registry" / "dataset_catalog.json").read_bytes()
    second = service.collect(_request(), "req-2")
    assert second.resumed is True
    assert second.dataset_ref == first.dataset_ref
    assert len(fake.calls) == 1
    catalog_after = (tmp_path / "data" / "registry" / "dataset_catalog.json").read_bytes()
    assert catalog_after == catalog_before
    conflict = service.collect(_request(end=END + timedelta(hours=1)), "req-2")
    assert conflict.status == "REJECTED"
    assert conflict.reason.startswith("REQUEST_ID_CONFLICT:")
    assert len(fake.calls) == 1


def test_data_07_3(tmp_path):
    """DATA-07-AC3: public fetch carries no credential and keeps raw bytes."""
    service, fake, wires = _service(tmp_path)
    result = service.collect(_request(), "req-3")
    assert result.status == "COLLECTED"
    assert len(fake.calls) == 1
    params = fake.calls[0]["params"]
    assert set(params) == {"symbol", "tf", "from", "to"}
    assert "key" not in json.dumps(params).lower()
    assert "secret" not in json.dumps(params).lower()
    assert len(wires) == 1
    assert Path(wires[0].body_path).read_bytes() == fake.calls[0]["body"]


def test_data_07_4(tmp_path):
    """DATA-07-AC4: pair extension preserves validation and historical hashes."""
    service, _, _ = _service(tmp_path)
    assert CanonicalPair(pair="btc_idr").pair == "btc_idr"
    with pytest.raises(ValueError):
        CanonicalPair(pair="BTC_IDR")
    first = service.collect(_request(), "req-4a")
    assert first.status == "COLLECTED"
    sha_before = service.registry.get(first.dataset_ref).to_artifact_ref().sha256

    extended = CollectionCapabilities.defaults().extend_pairs({"doge_idr": "DOGEIDR"})
    service2, fake2, _ = _service(tmp_path, capabilities=extended)
    again = service2.collect(_request(), "req-4b")
    assert again.resumed is True
    assert service2.registry.get(again.dataset_ref).to_artifact_ref().sha256 == sha_before
    assert len(fake2.calls) == 0
    doge = service2.collect(_request(pair="doge_idr"), "req-4c")
    assert doge.status == "COLLECTED"
    assert doge.complete_coverage is True
    still_bad = service2.collect(_request(pair="xrp_idr"), "req-4d")
    assert still_bad.status == "REJECTED"


def test_data_07_capacity_5(tmp_path):
    """DATA-07-AC5: stale headroom defers; fresh reading resumes durable job."""
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    from indodax_lab.orchestration.resources import (
        AdmissionPolicy,
        CapacityGuardPolicy,
        HostProfile,
        SystemResourceReading,
    )

    _fresh_ts = _dt.now(_UTC)
    stale = SystemResourceReading(
        ac_power_connected=True,
        free_ram_gb=16.0,
        user_idle_seconds=900.0,
        cpu_temp_celsius=52.0,
        cpu_load_pct=15.0,
        gpu_available=True,
        timestamp=_fresh_ts - timedelta(hours=1),
    )
    readings = {"current": stale}
    service, fake, _ = _service(
        tmp_path,
        admission={
            "host_profile": HostProfile.LENOVO,
            "policy": AdmissionPolicy(),
            "capacity": CapacityGuardPolicy(
                max_sensor_age_seconds=60.0,
                production_deadline_headroom_seconds=300.0,
                disk_reserve_bytes=1,
                configured_storage_paths=(str(tmp_path),),
            ),
            "reading_provider": lambda: readings["current"],
        },
    )
    deferred = service.collect(_request(), "req-5")
    assert deferred.status == "DEFERRED"
    assert deferred.reason.startswith("SENSOR_STALE:")
    assert deferred.dataset_ref is None
    assert fake.calls == []
    assert _job_count(tmp_path / "data") == 1

    readings["current"] = SystemResourceReading(
        ac_power_connected=True,
        free_ram_gb=16.0,
        user_idle_seconds=900.0,
        cpu_temp_celsius=52.0,
        cpu_load_pct=15.0,
        gpu_available=True,
        timestamp=_fresh_ts,
    )
    resumed = service.collect(_request(), "req-5")
    assert resumed.status == "COLLECTED"
    assert resumed.resumed is False
    assert resumed.dataset_ref is not None
    assert len(fake.calls) == 1
    assert _job_count(tmp_path / "data") == 1
