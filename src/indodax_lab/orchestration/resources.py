"""Resource probes, host profiles, and idle admission guards (JOB-02).

Contract:
Injected resource probes + LOW/MEDIUM/HIGH/GPU profile -> admit/defer with reasons.
Sensor UNKNOWN tidak dianggap aman.
ASUS profile tidak mengimpor atau menjalankan training.
Stale/unknown required sensors under the capacity guard reject admission and
optional Research load sheds before Production deadlines (JOB-02-AC4).
Capacity guards resolve configured paths to mounts and account for shared
physical disk contention (JOB-02-AC5).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
import math
from pathlib import Path
from typing import Any, Protocol, Sequence
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from indodax_lab.orchestration.jobs import JobDefinition, JobRecord
from indodax_lab.operations.recovery import MountCapacityInfo, resolve_path_mount


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class HostProfile(StrEnum):
    """Physical or logical host profiles for research lab nodes."""

    ASUS = "ASUS"
    LENOVO = "LENOVO"

    @classmethod
    def parse(cls, value: str | HostProfile) -> HostProfile:
        if isinstance(value, cls):
            return value
        v = value.strip().upper()
        if v in ("ASUS", "COLLECTOR_LIGHT", "PAPER_LIGHT"):
            return cls.ASUS
        if v in ("LENOVO", "RESEARCH_CPU", "RESEARCH_GPU", "RESEARCH_HEAVY"):
            return cls.LENOVO
        raise ValueError(f"UNKNOWN_HOST_PROFILE:{value}")


class ResourceClass(StrEnum):
    """Execution weight class for research jobs."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    GPU = "GPU"


class AsusProfileTrainingProhibitedError(RuntimeError):
    """Raised when an attempt is made to import or run training on ASUS profile."""


class SystemResourceReading(BaseModel):
    """Snapshot of hardware metrics and sensor telemetry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ac_power_connected: bool | None = None
    free_ram_gb: float | None = None
    user_idle_seconds: float | None = None
    cpu_temp_celsius: float | None = None
    cpu_load_pct: float | None = None
    gpu_available: bool | None = None
    gpu_temp_celsius: float | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("timestamp", mode="after")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "timestamp")

    @model_validator(mode="after")
    def validate_sensor_values(self) -> "SystemResourceReading":
        for name in (
            "free_ram_gb",
            "user_idle_seconds",
            "cpu_temp_celsius",
            "cpu_load_pct",
            "gpu_temp_celsius",
        ):
            value = getattr(self, name)
            if value is not None and not math.isfinite(value):
                raise ValueError(f"RESOURCE_SENSOR_NON_FINITE:{name}")
        if self.free_ram_gb is not None and self.free_ram_gb < 0:
            raise ValueError("RESOURCE_SENSOR_OUT_OF_RANGE:free_ram_gb")
        if self.user_idle_seconds is not None and self.user_idle_seconds < 0:
            raise ValueError("RESOURCE_SENSOR_OUT_OF_RANGE:user_idle_seconds")
        if self.cpu_load_pct is not None and not 0 <= self.cpu_load_pct <= 100:
            raise ValueError("RESOURCE_SENSOR_OUT_OF_RANGE:cpu_load_pct")
        return self


class ResourceProbe(Protocol):
    """Protocol for reading system hardware metrics."""

    def read(self) -> SystemResourceReading:
        ...


class StaticResourceProbe:
    """Injectable probe for testing deterministic hardware state."""

    def __init__(self, reading: SystemResourceReading) -> None:
        self._reading = reading

    def read(self) -> SystemResourceReading:
        return self._reading

    def update(self, **kwargs: Any) -> None:
        current_data = self._reading.model_dump()
        current_data.update(kwargs)
        if "timestamp" not in kwargs:
            current_data["timestamp"] = datetime.now(UTC)
        self._reading = SystemResourceReading(**current_data)


class ResourceThresholds(BaseModel):
    """Admission limits for a specific resource class."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_free_ram_gb: float = 0.5
    min_idle_seconds: float = 0.0
    max_thermal_celsius: float | None = 80.0
    require_ac_power: bool = True
    require_gpu: bool = False
    max_cpu_load_pct: float = 85.0


class AdmissionPolicy(BaseModel):
    """Configurable admission thresholds per resource class."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    low: ResourceThresholds = Field(
        default_factory=lambda: ResourceThresholds(
            min_free_ram_gb=0.5,
            min_idle_seconds=0.0,
            max_thermal_celsius=85.0,
            require_ac_power=False,
            require_gpu=False,
        )
    )
    medium: ResourceThresholds = Field(
        default_factory=lambda: ResourceThresholds(
            min_free_ram_gb=2.0,
            min_idle_seconds=0.0,
            max_thermal_celsius=80.0,
            require_ac_power=True,
            require_gpu=False,
        )
    )
    high: ResourceThresholds = Field(
        default_factory=lambda: ResourceThresholds(
            min_free_ram_gb=4.0,
            min_idle_seconds=600.0,
            max_thermal_celsius=75.0,
            require_ac_power=True,
            require_gpu=False,
        )
    )
    gpu: ResourceThresholds = Field(
        default_factory=lambda: ResourceThresholds(
            min_free_ram_gb=4.0,
            min_idle_seconds=600.0,
            max_thermal_celsius=75.0,
            require_ac_power=True,
            require_gpu=True,
        )
    )

    def get_thresholds(self, resource_class: ResourceClass) -> ResourceThresholds:
        if resource_class == ResourceClass.LOW:
            return self.low
        if resource_class == ResourceClass.MEDIUM:
            return self.medium
        if resource_class == ResourceClass.HIGH:
            return self.high
        if resource_class == ResourceClass.GPU:
            return self.gpu
        raise ValueError(f"UNKNOWN_RESOURCE_CLASS:{resource_class}")


class CapacityGuardPolicy(BaseModel):
    """Owner-approved capacity limits for guarded admission (JOB-02-AC4/AC5).

    Every required limit remains unset until supported by measured host
    evidence. When capacity guarding is requested, an unset required value
    fails closed, a stale required sensor rejects admission, optional
    Research load sheds before Production deadlines, and each configured
    storage path must resolve to its actual mount and device; unknown
    mappings and unmet shared-disk reserve block admission. Test fixtures
    supply their own numbers; none of these values are production defaults.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_sensor_age_seconds: float | None = None
    production_deadline_headroom_seconds: float | None = None
    disk_reserve_bytes: int | None = None
    configured_storage_paths: tuple[str, ...] = ()


class AdmissionDecision(BaseModel):
    """Structured result of evaluating resource-aware job admission."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    admitted: bool
    reason: str | None = None
    resource_class: ResourceClass
    host_profile: HostProfile
    reading: SystemResourceReading
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("evaluated_at", mode="after")
    @classmethod
    def validate_evaluated_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "evaluated_at")


def resolve_resource_class(job: JobDefinition | JobRecord | ResourceClass | str) -> ResourceClass:
    """Determine the resource class for a given job or parameter."""
    if isinstance(job, ResourceClass):
        return job
    if isinstance(job, str):
        return ResourceClass(job.upper())

    # Check job parameters
    params: dict[str, Any] = {}
    if isinstance(job, JobDefinition):
        params = job.parameters
    elif isinstance(job, JobRecord):
        # The record carries the parameters the job was submitted with, so a
        # persisted job keeps its declared class instead of being re-guessed.
        params = job.parameters

    rc_val = params.get("resource_class")
    if rc_val is not None:
        return ResourceClass(str(rc_val).upper())

    # Infer from job_type
    job_type = job.job_type.lower()
    if "gpu" in job_type or "neural" in job_type or "deep_learning" in job_type:
        return ResourceClass.GPU
    if "train" in job_type or "tune" in job_type or "sweep" in job_type:
        return ResourceClass.HIGH
    if "backtest" in job_type or "feature" in job_type or "evaluate" in job_type:
        return ResourceClass.MEDIUM
    return ResourceClass.LOW


def is_training_job(job: JobDefinition | JobRecord | ResourceClass | str) -> bool:
    """Check if the job represents model training or heavy search."""
    if isinstance(job, ResourceClass):
        return job in (ResourceClass.HIGH, ResourceClass.GPU)
    if isinstance(job, str):
        j_str = job.lower()
        return "train" in j_str or "tune" in j_str or "sweep" in j_str or "gpu" in j_str

    if job.job_type.lower().startswith("train") or "train" in job.job_type.lower():
        return True

    rc = resolve_resource_class(job)
    return rc in (ResourceClass.HIGH, ResourceClass.GPU)


def guard_asus_training_import(host_profile: HostProfile | str) -> None:
    """Enforce that ASUS profile strictly cannot import or execute training modules."""
    profile = HostProfile.parse(host_profile) if isinstance(host_profile, str) else host_profile
    if profile == HostProfile.ASUS:
        raise AsusProfileTrainingProhibitedError("ASUS profile cannot import or run training")


def evaluate_admission(
    job: JobDefinition | JobRecord | ResourceClass | str,
    reading: SystemResourceReading,
    host_profile: HostProfile | str,
    running_jobs: Sequence[JobRecord] | None = None,
    policy: AdmissionPolicy | None = None,
    capacity: CapacityGuardPolicy | None = None,
    production_deadline: datetime | None = None,
    optional_research: bool = False,
) -> AdmissionDecision:
    """Evaluate whether a job can be admitted on the current host.

    Invariants:
    1. ASUS profile never runs training jobs.
    2. Concurrency limit on Lenovo: at most 1 HIGH/GPU or 2 MEDIUM.
    3. Sensor UNKNOWN is not safe (fails closed).
    4. Hardware thresholds (RAM, idle, thermal, AC power, GPU) must be satisfied.
    5. When capacity guarding is requested (JOB-02-AC4/AC5), unset required
       limits fail closed, stale sensors reject admission, optional Research
       load sheds before Production deadlines, configured paths must resolve
       to measured mounts, and shared physical disk reserve is enforced.
    """
    profile = HostProfile.parse(host_profile) if isinstance(host_profile, str) else host_profile
    active_policy = policy or AdmissionPolicy()
    resource_class = resolve_resource_class(job)
    now = datetime.now(UTC)

    # 1. ASUS Training Prohibition (JOB-02-AC3)
    if profile == HostProfile.ASUS and is_training_job(job):
        return AdmissionDecision(
            admitted=False,
            reason="ASUS_PROFILE_CANNOT_RUN_TRAINING",
            resource_class=resource_class,
            host_profile=profile,
            reading=reading,
            evaluated_at=now,
        )

    # 2. Host Concurrency Limits
    if profile == HostProfile.LENOVO and running_jobs:
        running_classes = [resolve_resource_class(rj) for rj in running_jobs]
        if resource_class in (ResourceClass.HIGH, ResourceClass.GPU):
            if any(rc in (ResourceClass.HIGH, ResourceClass.GPU) for rc in running_classes):
                return AdmissionDecision(
                    admitted=False,
                    reason="CONCURRENCY_LIMIT_EXCEEDED:max_1_high_or_gpu",
                    resource_class=resource_class,
                    host_profile=profile,
                    reading=reading,
                    evaluated_at=now,
                )
        elif resource_class == ResourceClass.MEDIUM:
            medium_count = sum(1 for rc in running_classes if rc == ResourceClass.MEDIUM)
            if medium_count >= 2:
                return AdmissionDecision(
                    admitted=False,
                    reason="CONCURRENCY_LIMIT_EXCEEDED:max_2_medium",
                    resource_class=resource_class,
                    host_profile=profile,
                    reading=reading,
                    evaluated_at=now,
                )

    thresholds = active_policy.get_thresholds(resource_class)

    # 3. Sensor UNKNOWN is not safe (JOB-02-AC1)
    if thresholds.require_ac_power and reading.ac_power_connected is None:
        return AdmissionDecision(
            admitted=False,
            reason="SENSOR_UNKNOWN:ac_power_connected",
            resource_class=resource_class,
            host_profile=profile,
            reading=reading,
            evaluated_at=now,
        )

    if thresholds.min_free_ram_gb > 0 and reading.free_ram_gb is None:
        return AdmissionDecision(
            admitted=False,
            reason="SENSOR_UNKNOWN:free_ram_gb",
            resource_class=resource_class,
            host_profile=profile,
            reading=reading,
            evaluated_at=now,
        )

    if thresholds.min_idle_seconds > 0 and reading.user_idle_seconds is None:
        return AdmissionDecision(
            admitted=False,
            reason="SENSOR_UNKNOWN:user_idle_seconds",
            resource_class=resource_class,
            host_profile=profile,
            reading=reading,
            evaluated_at=now,
        )

    if thresholds.max_thermal_celsius is not None and reading.cpu_temp_celsius is None:
        return AdmissionDecision(
            admitted=False,
            reason="SENSOR_UNKNOWN:cpu_temp_celsius",
            resource_class=resource_class,
            host_profile=profile,
            reading=reading,
            evaluated_at=now,
        )

    if thresholds.require_gpu and reading.gpu_available is None:
        return AdmissionDecision(
            admitted=False,
            reason="SENSOR_UNKNOWN:gpu_available",
            resource_class=resource_class,
            host_profile=profile,
            reading=reading,
            evaluated_at=now,
        )

    # 4. Check policy thresholds
    if thresholds.require_ac_power and not reading.ac_power_connected:
        return AdmissionDecision(
            admitted=False,
            reason="AC_POWER_DISCONNECTED",
            resource_class=resource_class,
            host_profile=profile,
            reading=reading,
            evaluated_at=now,
        )

    if reading.free_ram_gb is not None and reading.free_ram_gb < thresholds.min_free_ram_gb:
        return AdmissionDecision(
            admitted=False,
            reason=f"INSUFFICIENT_RAM:{reading.free_ram_gb}GB < {thresholds.min_free_ram_gb}GB",
            resource_class=resource_class,
            host_profile=profile,
            reading=reading,
            evaluated_at=now,
        )

    if reading.user_idle_seconds is not None and reading.user_idle_seconds < thresholds.min_idle_seconds:
        return AdmissionDecision(
            admitted=False,
            reason=f"HOST_NOT_IDLE:{reading.user_idle_seconds}s < {thresholds.min_idle_seconds}s",
            resource_class=resource_class,
            host_profile=profile,
            reading=reading,
            evaluated_at=now,
        )

    if (
        thresholds.max_thermal_celsius is not None
        and reading.cpu_temp_celsius is not None
        and reading.cpu_temp_celsius > thresholds.max_thermal_celsius
    ):
        return AdmissionDecision(
            admitted=False,
            reason=f"THERMAL_EXCEEDED:{reading.cpu_temp_celsius}C > {thresholds.max_thermal_celsius}C",
            resource_class=resource_class,
            host_profile=profile,
            reading=reading,
            evaluated_at=now,
        )

    if thresholds.require_gpu and not reading.gpu_available:
        return AdmissionDecision(
            admitted=False,
            reason="GPU_UNAVAILABLE",
            resource_class=resource_class,
            host_profile=profile,
            reading=reading,
            evaluated_at=now,
        )

    if reading.cpu_load_pct is not None and reading.cpu_load_pct > thresholds.max_cpu_load_pct:
        return AdmissionDecision(
            admitted=False,
            reason=f"CPU_LOAD_EXCEEDED:{reading.cpu_load_pct}% > {thresholds.max_cpu_load_pct}%",
            resource_class=resource_class,
            host_profile=profile,
            reading=reading,
            evaluated_at=now,
        )

    # 5. Owner-approved capacity guard (JOB-02-AC4/AC5): fail closed while
    #    required limits or path mappings lack measured host evidence.
    if capacity is not None:
        if production_deadline is not None:
            _ensure_utc(production_deadline, "production_deadline")

        max_sensor_age = capacity.max_sensor_age_seconds
        deadline_headroom = capacity.production_deadline_headroom_seconds
        disk_reserve = capacity.disk_reserve_bytes
        for limit_name, limit_value in (
            ("max_sensor_age_seconds", max_sensor_age),
            ("production_deadline_headroom_seconds", deadline_headroom),
            ("disk_reserve_bytes", disk_reserve),
        ):
            if limit_value is None:
                return AdmissionDecision(
                    admitted=False,
                    reason=f"CAPACITY_LIMIT_UNSET:{limit_name}",
                    resource_class=resource_class,
                    host_profile=profile,
                    reading=reading,
                    evaluated_at=now,
                )

        # Stale required sensor rejects admission (AC4).
        sensor_age_seconds = (now - reading.timestamp).total_seconds()
        if sensor_age_seconds > max_sensor_age:
            return AdmissionDecision(
                admitted=False,
                reason=(
                    f"SENSOR_STALE:reading.timestamp:{sensor_age_seconds:.0f}s"
                    f" > {max_sensor_age:.0f}s"
                ),
                resource_class=resource_class,
                host_profile=profile,
                reading=reading,
                evaluated_at=now,
            )

        # Optional Research load sheds before Production deadlines (AC4).
        if optional_research:
            if production_deadline is None:
                return AdmissionDecision(
                    admitted=False,
                    reason="PRODUCTION_DEADLINE_UNKNOWN:optional_research_shed",
                    resource_class=resource_class,
                    host_profile=profile,
                    reading=reading,
                    evaluated_at=now,
                )
            deadline_remaining_seconds = (production_deadline - now).total_seconds()
            if deadline_remaining_seconds <= deadline_headroom:
                return AdmissionDecision(
                    admitted=False,
                    reason=(
                        f"RESEARCH_SHED_PRE_DEADLINE:{deadline_remaining_seconds:.0f}s"
                        f" <= {deadline_headroom:.0f}s"
                    ),
                    resource_class=resource_class,
                    host_profile=profile,
                    reading=reading,
                    evaluated_at=now,
                )

        # Each configured path resolves to its actual mount and device (AC5);
        # an unknown mapping blocks admission.
        resolved_paths: list[tuple[str, MountCapacityInfo]] = []
        for raw_path in capacity.configured_storage_paths:
            try:
                resolved_paths.append((raw_path, resolve_path_mount(Path(raw_path))))
            except OSError as exc:
                return AdmissionDecision(
                    admitted=False,
                    reason=f"PATH_MOUNT_UNRESOLVED:{raw_path}:{exc}",
                    resource_class=resource_class,
                    host_profile=profile,
                    reading=reading,
                    evaluated_at=now,
                )

        # Paths sharing one physical device multiply the reserve demand, so
        # shared physical disk contention is accounted for (AC5).
        paths_by_device: dict[str, list[tuple[str, MountCapacityInfo]]] = {}
        for raw_path, mount_info in resolved_paths:
            paths_by_device.setdefault(mount_info.device, []).append((raw_path, mount_info))
        for device, device_paths in paths_by_device.items():
            required_free_bytes = disk_reserve * len(device_paths)
            free_bytes = device_paths[0][1].free_bytes
            if free_bytes < required_free_bytes:
                shared_paths = ",".join(raw_path for raw_path, _ in device_paths)
                return AdmissionDecision(
                    admitted=False,
                    reason=(
                        f"DISK_RESERVE_EXCEEDED:{device}:{free_bytes}B"
                        f"<{required_free_bytes}B(reserve {disk_reserve}B"
                        f" x {len(device_paths)} paths: {shared_paths})"
                    ),
                    resource_class=resource_class,
                    host_profile=profile,
                    reading=reading,
                    evaluated_at=now,
                )

    return AdmissionDecision(
        admitted=True,
        reason=None,
        resource_class=resource_class,
        host_profile=profile,
        reading=reading,
        evaluated_at=now,
    )
