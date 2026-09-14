"""Integration and qualification tests for capacity and crash recovery (QA-03).

Guarantees:
1. QA-03-AC0: Host workload qualification proves execution and recovery before release (test_qa_03_valid_contract).
2. QA-03-AC1: Disk-full condition strictly fails closed and never acknowledges success (test_qa_03_contract_1).
3. QA-03-AC2: Worker termination/kill does not produce duplicate metrics or corrupted state (test_qa_03_contract_2).
4. QA-03-AC3: Resource ceiling is enforced from empirical baseline measurements rather than raw CPU count (test_qa_03_contract_3).
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch
import pytest

from indodax_lab.operations.recovery import (
    CapacityCeilingExceededError,
    DiskFullError,
    DiskGuardWriter,
    EmpiricalHostCapacityValidator,
    HostWorkloadQualificationReport,
    IdempotentMetricLedger,
    qualify_host_workload_and_recovery,
)
from indodax_lab.operations.service_lifecycle import HostServiceProfile


def test_qa_03_valid_contract(tmp_path: Path) -> None:
    """AC0: Host yang dipilih punya bukti workload dan recovery sebelum release."""
    profile = HostServiceProfile(
        host_name="LenovoThinkPad",
        allowed_worker_threads=2,
        data_root=str(tmp_path),
    )

    report: HostWorkloadQualificationReport = qualify_host_workload_and_recovery(
        profile=profile,
        target_dir=tmp_path,
    )

    assert report.workload_status == "QUALIFIED"
    assert report.profile_valid is True
    assert report.disk_recovery_verified is True
    assert report.worker_crash_recovery_verified is True
    assert report.host_name == "LenovoThinkPad"


def test_qa_03_contract_1(tmp_path: Path) -> None:
    """AC1: Disk-full tidak mengakui sukses."""
    writer = DiskGuardWriter()
    target_file = tmp_path / "model_checkpoint.bin"
    payload = b"important_model_checkpoint_data_bytes"

    # Simulate ENOSPC (disk full) during write
    with patch("shutil.disk_usage", return_value=(1000, 1000, 0)):  # 0 bytes free
        with pytest.raises(DiskFullError) as exc_info:
            writer.write_atomic(target_file, payload, min_free_bytes=1024 * 1024)

        assert "DISK_FULL" in str(exc_info.value)
        # Verify file was NOT written as a successful artifact
        assert not target_file.exists()


def test_qa_03_contract_2(tmp_path: Path) -> None:
    """AC2: Worker kill tidak duplicate metrics."""
    ledger = IdempotentMetricLedger(storage_path=tmp_path / "metrics_ledger.json")

    # 1. Worker writes metrics for fold 0 and fold 1
    ledger.record_metric(run_id="run_m01_001", metric_name="val_sharpe", value=1.45, fold_idx=0)
    ledger.record_metric(run_id="run_m01_001", metric_name="val_sharpe", value=1.38, fold_idx=1)
    assert ledger.metrics_count == 2

    # 2. Simulate worker crash/kill mid-execution and restarted replay
    # Worker replays fold 1 and then continues to fold 2
    ledger.record_metric(run_id="run_m01_001", metric_name="val_sharpe", value=1.38, fold_idx=1)
    assert ledger.metrics_count == 2  # Replay MUST NOT duplicate existing fold 1 metric!

    # 3. New fold records normally
    ledger.record_metric(run_id="run_m01_001", metric_name="val_sharpe", value=1.52, fold_idx=2)
    assert ledger.metrics_count == 3


def test_qa_03_contract_3() -> None:
    """AC3: Resource ceiling ditetapkan dari baseline bukan spesifikasi CPU semata."""
    # 1. Host with empirically verified baseline ceiling (e.g. Lenovo: max 2 workers, 4096MB)
    validator = EmpiricalHostCapacityValidator(
        host_name="LenovoThinkPad",
        max_allowed_workers=2,
        max_memory_mb=4096,
        benchmark_verified=True,
    )

    # Valid workload within empirical capacity passes
    assert validator.validate_admission(requested_workers=2, requested_memory_mb=2048) is True

    # Workload exceeding empirical worker limit fails even if hardware has 16 logical CPUs
    with pytest.raises(CapacityCeilingExceededError) as exc_info:
        validator.validate_admission(requested_workers=8, requested_memory_mb=2048)
    assert "CAPACITY_CEILING_EXCEEDED" in str(exc_info.value)

    # Workload exceeding empirical memory limit fails
    with pytest.raises(CapacityCeilingExceededError) as exc_info2:
        validator.validate_admission(requested_workers=2, requested_memory_mb=8192)
    assert "CAPACITY_CEILING_EXCEEDED" in str(exc_info2.value)

    # 2. Host without verified empirical benchmark cannot admit workloads
    unverified_validator = EmpiricalHostCapacityValidator(
        host_name="RawServerWithoutBenchmark",
        max_allowed_workers=32,
        max_memory_mb=65536,
        benchmark_verified=False,
    )
    with pytest.raises(CapacityCeilingExceededError) as exc_info3:
        unverified_validator.validate_admission(requested_workers=1, requested_memory_mb=512)
    assert "UNBENCHMARKED_HOST" in str(exc_info3.value)
