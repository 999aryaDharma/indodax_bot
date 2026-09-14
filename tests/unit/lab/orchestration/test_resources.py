"""Unit tests for JOB-02 Resource-aware idle admission.

Acceptance Criteria:
- JOB-02-AC0 (test_job_02_valid_contract): Pekerjaan berat hanya masuk saat profil host, daya, RAM, idle dan thermal memenuhi policy.
- JOB-02-AC1 (test_job_02_contract_1): Sensor UNKNOWN tidak dianggap aman.
- JOB-02-AC2 (test_job_02_contract_2): AC terputus memicu checkpoint pause.
- JOB-02-AC3 (test_job_02_contract_3): ASUS profile tidak mengimpor atau menjalankan training.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import pytest

from indodax_lab.orchestration.jobs import (
    JobDefinition,
    JobRecord,
    JobStatus,
)
from indodax_lab.orchestration.queue import SqliteJobQueue
from indodax_lab.orchestration.resources import (
    AdmissionDecision,
    AdmissionPolicy,
    AsusProfileTrainingProhibitedError,
    HostProfile,
    ResourceClass,
    StaticResourceProbe,
    SystemResourceReading,
    evaluate_admission,
    guard_asus_training_import,
)
from indodax_lab.orchestration.worker import (
    ExecutionResult,
    ResearchWorker,
    WorkerConfig,
)


def _build_test_job(
    job_id: str = "job_heavy_01",
    job_type: str = "train_model",
    resource_class: ResourceClass = ResourceClass.HIGH,
) -> JobDefinition:
    return JobDefinition(
        job_id=job_id,
        job_type=job_type,
        recipe_hash="recipe_abc123",
        input_ids=["dataset_v1"],
        cadence_window="daily_2025_06_01",
        parameters={"resource_class": resource_class.value, "epochs": 5},
        max_attempts=3,
        lease_duration_seconds=60,
        created_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
    )


def test_job_02_valid_contract() -> None:
    """JOB-02-AC0: Pekerjaan berat hanya masuk saat profil host, daya, RAM, idle dan thermal memenuhi policy."""
    job = _build_test_job("job_heavy_ok", resource_class=ResourceClass.HIGH)

    # Compliant Lenovo host reading
    reading = SystemResourceReading(
        ac_power_connected=True,
        free_ram_gb=16.0,
        user_idle_seconds=900.0,
        cpu_temp_celsius=52.0,
        cpu_load_pct=15.0,
        gpu_available=True,
    )
    probe = StaticResourceProbe(reading)
    policy = AdmissionPolicy()

    decision = evaluate_admission(
        job=job,
        reading=probe.read(),
        host_profile=HostProfile.LENOVO,
        policy=policy,
    )

    assert decision.admitted is True
    assert decision.reason is None
    assert decision.resource_class == ResourceClass.HIGH
    assert decision.host_profile == HostProfile.LENOVO


def test_job_02_contract_1() -> None:
    """JOB-02-AC1: Sensor UNKNOWN tidak dianggap aman."""
    job = _build_test_job("job_heavy_probe_unknown", resource_class=ResourceClass.HIGH)
    policy = AdmissionPolicy()

    # 1. Thermal sensor UNKNOWN (None)
    reading_unknown_temp = SystemResourceReading(
        ac_power_connected=True,
        free_ram_gb=16.0,
        user_idle_seconds=900.0,
        cpu_temp_celsius=None,  # UNKNOWN
        cpu_load_pct=10.0,
        gpu_available=True,
    )
    decision = evaluate_admission(
        job=job,
        reading=reading_unknown_temp,
        host_profile=HostProfile.LENOVO,
        policy=policy,
    )
    assert decision.admitted is False
    assert decision.reason == "SENSOR_UNKNOWN:cpu_temp_celsius"

    # 2. AC power sensor UNKNOWN (None)
    reading_unknown_ac = SystemResourceReading(
        ac_power_connected=None,  # UNKNOWN
        free_ram_gb=16.0,
        user_idle_seconds=900.0,
        cpu_temp_celsius=50.0,
        cpu_load_pct=10.0,
        gpu_available=True,
    )
    decision_ac = evaluate_admission(
        job=job,
        reading=reading_unknown_ac,
        host_profile=HostProfile.LENOVO,
        policy=policy,
    )
    assert decision_ac.admitted is False
    assert decision_ac.reason == "SENSOR_UNKNOWN:ac_power_connected"

    # 3. RAM sensor UNKNOWN (None)
    reading_unknown_ram = SystemResourceReading(
        ac_power_connected=True,
        free_ram_gb=None,  # UNKNOWN
        user_idle_seconds=900.0,
        cpu_temp_celsius=50.0,
        cpu_load_pct=10.0,
        gpu_available=True,
    )
    decision_ram = evaluate_admission(
        job=job,
        reading=reading_unknown_ram,
        host_profile=HostProfile.LENOVO,
        policy=policy,
    )
    assert decision_ram.admitted is False
    assert decision_ram.reason == "SENSOR_UNKNOWN:free_ram_gb"

    # 4. Idle sensor UNKNOWN (None)
    reading_unknown_idle = SystemResourceReading(
        ac_power_connected=True,
        free_ram_gb=16.0,
        user_idle_seconds=None,  # UNKNOWN
        cpu_temp_celsius=50.0,
        cpu_load_pct=10.0,
        gpu_available=True,
    )
    decision_idle = evaluate_admission(
        job=job,
        reading=reading_unknown_idle,
        host_profile=HostProfile.LENOVO,
        policy=policy,
    )
    assert decision_idle.admitted is False
    assert decision_idle.reason == "SENSOR_UNKNOWN:user_idle_seconds"


def test_job_02_contract_2(tmp_path: Path) -> None:
    """JOB-02-AC2: AC terputus memicu checkpoint pause."""
    db_path = tmp_path / "queue.db"
    queue = SqliteJobQueue(db_path)
    job_def = _build_test_job("job_train_ac_pause", resource_class=ResourceClass.HIGH)
    queue.submit_job(job_def)

    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # Initial state: AC is connected
    reading = SystemResourceReading(
        ac_power_connected=True,
        free_ram_gb=16.0,
        user_idle_seconds=900.0,
        cpu_temp_celsius=55.0,
        cpu_load_pct=20.0,
        gpu_available=True,
    )
    probe = StaticResourceProbe(reading)

    worker = ResearchWorker(
        config=WorkerConfig(
            worker_id="worker_lenovo_01",
            host_profile=HostProfile.LENOVO,
            checkpoint_dir=checkpoint_dir,
        ),
        queue=queue,
        probe=probe,
    )

    claimed = queue.claim_job("worker_lenovo_01", as_of=datetime(2025, 6, 1, 12, 0, tzinfo=UTC))
    assert claimed is not None

    # Multi-step task tracking completed steps
    executed_steps: list[int] = []

    def mock_step(step_idx: int) -> dict[str, int]:
        executed_steps.append(step_idx)
        # Simulate AC disconnection at step 3
        if step_idx == 2:
            probe.update(ac_power_connected=False)
        return {"current_epoch": step_idx}

    # Execute steps 0 to 4
    result = worker.execute_steps(
        job=claimed,
        total_steps=5,
        step_fn=mock_step,
        start_step=0,
    )

    # AC disconnected at step 2 -> pause execution and save checkpoint
    assert result.status == "PAUSED"
    assert result.reason == "AC_POWER_DISCONNECTED_CHECKPOINT_SAVED"
    assert executed_steps == [0, 1, 2]

    # Verify checkpoint file saved
    checkpoint_file = checkpoint_dir / f"{claimed.job_id}_checkpoint.json"
    assert checkpoint_file.exists()
    checkpoint_data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
    assert checkpoint_data["last_completed_step"] == 2
    assert checkpoint_data["state"] == {"current_epoch": 2}

    # Now AC power is restored!
    probe.update(ac_power_connected=True)

    # Resume from checkpoint
    resumed_result = worker.resume_from_checkpoint(
        job=claimed,
        total_steps=5,
        step_fn=mock_step,
    )

    assert resumed_result.status == "SUCCESS"
    # Steps 3 and 4 ran, step 0, 1, 2 were not re-executed
    assert executed_steps == [0, 1, 2, 3, 4]


def test_job_02_contract_3() -> None:
    """JOB-02-AC3: ASUS profile tidak mengimpor atau menjalankan training."""
    training_job = _build_test_job(
        "job_train_asus",
        job_type="train_model",
        resource_class=ResourceClass.HIGH,
    )

    reading = SystemResourceReading(
        ac_power_connected=True,
        free_ram_gb=16.0,
        user_idle_seconds=1200.0,
        cpu_temp_celsius=40.0,
        cpu_load_pct=5.0,
        gpu_available=False,
    )

    # 1. Admission evaluation strictly rejects training on ASUS profile
    decision = evaluate_admission(
        job=training_job,
        reading=reading,
        host_profile=HostProfile.ASUS,
    )
    assert decision.admitted is False
    assert decision.reason == "ASUS_PROFILE_CANNOT_RUN_TRAINING"

    # 2. Guard against importing training modules on ASUS
    with pytest.raises(AsusProfileTrainingProhibitedError) as exc_info:
        guard_asus_training_import(HostProfile.ASUS)
    assert "ASUS profile cannot import or run training" in str(exc_info.value)

    # Lenovo profile allows training import
    guard_asus_training_import(HostProfile.LENOVO)  # No exception raised


def test_job_02_lenovo_concurrency_limit() -> None:
    """Lenovo profile enforces at most 1 HIGH/GPU or 2 MEDIUM concurrent jobs."""
    policy = AdmissionPolicy()
    reading = SystemResourceReading(
        ac_power_connected=True,
        free_ram_gb=16.0,
        user_idle_seconds=900.0,
        cpu_temp_celsius=50.0,
        cpu_load_pct=10.0,
        gpu_available=True,
    )

    high_job_1 = _build_test_job("job_h1", resource_class=ResourceClass.HIGH)
    high_job_2 = _build_test_job("job_h2", resource_class=ResourceClass.HIGH)

    running_high = JobRecord(
        job_id="job_h1",
        job_type="train_model",
        status=JobStatus.RUNNING,
        owner_id="worker_1",
        generation=1,
        attempts=1,
        max_attempts=3,
        lease_duration_seconds=60,
        created_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
        updated_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
    )

    # If 1 HIGH job is running, second HIGH job is rejected due to concurrency limit
    decision = evaluate_admission(
        job=high_job_2,
        reading=reading,
        host_profile=HostProfile.LENOVO,
        running_jobs=[running_high],
        policy=policy,
    )
    assert decision.admitted is False
    assert decision.reason == "CONCURRENCY_LIMIT_EXCEEDED:max_1_high_or_gpu"
