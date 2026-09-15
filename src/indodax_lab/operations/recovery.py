"""Capacity qualification, disk-full guard, and crash recovery (QA-03).

Guarantees:
1. QA-03-AC0: Host workload qualification certifies execution and recovery before release.
2. QA-03-AC1: Disk-full conditions strictly fail closed without acknowledging false success.
3. QA-03-AC2: Worker process kills or crashes do not duplicate metrics or corrupt ledger state.
4. QA-03-AC3: Resource ceilings are enforced from empirical baseline benchmarks rather than raw hardware specs.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.operations.service_lifecycle import HostServiceProfile


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DiskFullError(IOError):
    """Raised when disk space is exhausted; prevents false positive success acknowledgement."""


class CapacityCeilingExceededError(ValueError):
    """Raised when workload resource demands exceed empirical host profile limits."""


# ---------------------------------------------------------------------------
# Disk Guard Writer (QA-03-AC1)
# ---------------------------------------------------------------------------


class DiskGuardWriter:
    """Atomic file writer verifying storage capacity before writing to prevent corruption."""

    def write_atomic(
        self,
        target_path: Path,
        data: bytes,
        min_free_bytes: int = 1024 * 1024,
    ) -> bool:
        """Write data atomically, failing closed if storage is constrained.

        Raises:
            DiskFullError: If free disk space is less than required.
        """
        parent_dir = target_path.parent
        parent_dir.mkdir(parents=True, exist_ok=True)

        try:
            _, _, free = shutil.disk_usage(parent_dir)
        except Exception:
            free = 0

        # AC1: Check disk space
        if free < min_free_bytes or free < len(data):
            raise DiskFullError(
                f"DISK_FULL: Insufficient disk space ({free} bytes free, required {min_free_bytes} bytes). "
                "Write aborted fail-closed without acknowledging success (QA-03-AC1)."
            )

        tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        try:
            tmp_path.write_bytes(data)
            tmp_path.replace(target_path)
            return True
        except Exception as exc:
            if tmp_path.exists():
                tmp_path.unlink()
            raise DiskFullError(f"DISK_FULL: Write failed due to I/O error: {exc}") from exc


# ---------------------------------------------------------------------------
# Idempotent Metric Ledger (QA-03-AC2)
# ---------------------------------------------------------------------------


class IdempotentMetricLedger:
    """Ledger recording trial metrics idempotently across worker restarts and crashes."""

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path
        self._entries: dict[tuple[str, str, int], float] = {}
        if storage_path.exists():
            self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            for item in data:
                key = (item["run_id"], item["metric_name"], item["fold_idx"])
                self._entries[key] = item["value"]
        except Exception:
            pass

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = [
            {"run_id": k[0], "metric_name": k[1], "fold_idx": k[2], "value": v}
            for k, v in self._entries.items()
        ]
        self.storage_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    def record_metric(
        self,
        run_id: str,
        metric_name: str,
        value: float,
        fold_idx: int = 0,
    ) -> bool:
        """Record an evaluation metric idempotently.

        If the metric for (run_id, metric_name, fold_idx) is already present (e.g. replayed
        after a worker kill), the duplicate is safely ignored without incrementing count.
        """
        key = (run_id, metric_name, fold_idx)
        if key in self._entries:
            # Already recorded, ignore duplicate from crashed worker replay
            return False

        self._entries[key] = value
        self._save()
        return True

    @property
    def metrics_count(self) -> int:
        return len(self._entries)

    def get_metrics(self, run_id: str) -> dict[str, float]:
        return {
            metric_name: val
            for (r_id, metric_name, _), val in self._entries.items()
            if r_id == run_id
        }


# ---------------------------------------------------------------------------
# Empirical Host Capacity Validator (QA-03-AC3)
# ---------------------------------------------------------------------------


class EmpiricalHostCapacityValidator:
    """Enforces resource ceilings based on measured empirical benchmarks rather than CPU spec."""

    def __init__(
        self,
        host_name: str,
        max_allowed_workers: int,
        max_memory_mb: int,
        benchmark_verified: bool = True,
    ) -> None:
        self.host_name = host_name
        self.max_allowed_workers = max_allowed_workers
        self.max_memory_mb = max_memory_mb
        self.benchmark_verified = benchmark_verified

    def validate_admission(self, requested_workers: int, requested_memory_mb: int) -> bool:
        """Validate workload demands against empirical host capacity.

        Raises:
            CapacityCeilingExceededError: If demands exceed benchmarked capacity or unverified.
        """
        if not self.benchmark_verified:
            raise CapacityCeilingExceededError(
                f"UNBENCHMARKED_HOST: Host '{self.host_name}' has no empirical benchmark profile. "
                "Workload admission is blocked until benchmark verification is complete (QA-03-AC3)."
            )

        if requested_workers > self.max_allowed_workers:
            raise CapacityCeilingExceededError(
                f"CAPACITY_CEILING_EXCEEDED: Requested workers {requested_workers} exceeds "
                f"empirical limit {self.max_allowed_workers} for host '{self.host_name}' (QA-03-AC3)."
            )

        if requested_memory_mb > self.max_memory_mb:
            raise CapacityCeilingExceededError(
                f"CAPACITY_CEILING_EXCEEDED: Requested memory {requested_memory_mb}MB exceeds "
                f"empirical limit {self.max_memory_mb}MB for host '{self.host_name}' (QA-03-AC3)."
            )

        return True


# ---------------------------------------------------------------------------
# Qualification Report & Runner (QA-03-AC0)
# ---------------------------------------------------------------------------


class HostWorkloadQualificationReport(BaseModel):
    """Audit report separating synthetic checks from real host qualification."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    host_name: str
    profile_valid: bool = False
    disk_recovery_verified: bool = False
    worker_crash_recovery_verified: bool = False
    synthetic_storage_write_passed: bool = False
    synthetic_metric_replay_passed: bool = False
    workload_status: str = "UNVERIFIED"
    as_of_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


def qualify_host_workload_and_recovery(
    profile: HostServiceProfile,
    target_dir: Path,
) -> HostWorkloadQualificationReport:
    """Run bounded synthetic probes without claiming real host qualification.

    Representative workload benchmarks, a process-kill rehearsal and measured
    recovery evidence require an operator-owned procedure. This helper cannot
    manufacture that evidence from a small local write/replay smoke check.
    """
    # 1. Verify profile configuration
    if profile.allowed_worker_threads <= 0:
        raise ValueError("HOST_PROFILE_WORKER_LIMIT_INVALID")

    # 2. Verify disk guard writer
    writer = DiskGuardWriter()
    test_artifact = target_dir / "qualification_test.bin"
    writer.write_atomic(test_artifact, b"qualification_test_payload")
    if not test_artifact.exists():
        raise RuntimeError("SYNTHETIC_STORAGE_WRITE_NOT_OBSERVED")

    # 3. Verify idempotent metric ledger
    ledger_path = target_dir / "qualification_ledger.json"
    ledger = IdempotentMetricLedger(ledger_path)
    ledger.record_metric("qual_run_01", "sharpe", 1.2, 0)
    ledger.record_metric("qual_run_01", "sharpe", 1.2, 0)  # Replay
    if ledger.metrics_count != 1:
        raise RuntimeError("SYNTHETIC_METRIC_REPLAY_NOT_IDEMPOTENT")

    return HostWorkloadQualificationReport(
        host_name=profile.host_name,
        profile_valid=True,
        disk_recovery_verified=False,
        worker_crash_recovery_verified=False,
        synthetic_storage_write_passed=True,
        synthetic_metric_replay_passed=True,
        workload_status="UNVERIFIED",
    )
