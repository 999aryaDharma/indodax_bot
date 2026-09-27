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
import time
import pytest
from pydantic import ValidationError

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
    is_training_job,
    resolve_resource_class,
)
from indodax_lab.orchestration.worker import (
    CheckpointIntegrityError,
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

    claimed = queue.claim_job("worker_lenovo_01", as_of=datetime.now(UTC))
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


# ---------------------------------------------------------------------------
# Sprint-review fix cycle. Actor for every line below:
# opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
# ---------------------------------------------------------------------------


def test_declared_resource_class_survives_the_queue_round_trip(tmp_path: Path) -> None:
    """JOB-02-AC3: a declared GPU/HIGH class must not decay to LOW once persisted.

    ``JobRecord`` carried no ``parameters``, so ``resolve_resource_class`` fell
    back to substring-guessing the ``job_type`` for every queued job. A job
    submitted as ``resource_class=GPU`` with a job_type that contains none of
    the training keywords came back out of the queue as LOW, which also
    disabled the ASUS training prohibition and every HIGH/GPU threshold.
    """
    queue = SqliteJobQueue(tmp_path / "queue.db")
    definition = JobDefinition(
        job_id="gpu_fit",
        job_type="model_fit",  # no 'train'/'gpu'/'neural'/'tune'/'sweep' substring
        recipe_hash="recipe_abc",
        input_ids=["dataset_v1"],
        parameters={"resource_class": "GPU", "epochs": 5},
        created_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
    )
    assert resolve_resource_class(definition) == ResourceClass.GPU

    queue.submit_job(definition)
    record = queue.get_job("gpu_fit")

    # Behavioral core: the declared class must survive persistence.
    assert resolve_resource_class(record) == ResourceClass.GPU
    assert is_training_job(record) is True
    assert record.parameters["resource_class"] == "GPU"


def test_queued_gpu_job_cannot_run_on_the_asus_profile(tmp_path: Path) -> None:
    """JOB-02-AC3: the ASUS training prohibition must survive persistence.

    Before the fix, a persisted GPU job whose job_type contained no training
    keyword was classified LOW, so ``is_training_job`` returned False, the ASUS
    guard never fired, and the job executed on the ASUS host.
    """
    queue = SqliteJobQueue(tmp_path / "queue.db")
    definition = JobDefinition(
        job_id="gpu_fit_asus",
        job_type="model_fit",
        recipe_hash="recipe_abc",
        input_ids=["dataset_v1"],
        parameters={"resource_class": "GPU"},
        created_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
    )
    queue.submit_job(definition)
    record = queue.get_job("gpu_fit_asus")

    reading = SystemResourceReading(
        ac_power_connected=True,
        free_ram_gb=16.0,
        user_idle_seconds=1200.0,
        cpu_temp_celsius=40.0,
        cpu_load_pct=5.0,
        gpu_available=False,
    )
    decision = evaluate_admission(
        job=record,
        reading=reading,
        host_profile=HostProfile.ASUS,
    )
    assert decision.admitted is False
    assert decision.reason == "ASUS_PROFILE_CANNOT_RUN_TRAINING"

    worker = ResearchWorker(
        config=WorkerConfig(
            worker_id="w1",
            host_profile=HostProfile.ASUS,
            checkpoint_dir=tmp_path / "ckpt",
        ),
        queue=queue,
        probe=StaticResourceProbe(reading),
    )
    executed: list[int] = []
    with pytest.raises(AsusProfileTrainingProhibitedError):
        worker.execute_steps(record, total_steps=3, step_fn=lambda i: executed.append(i))


def test_resume_refuses_a_checkpoint_claiming_more_steps_than_exist(tmp_path: Path) -> None:
    """JOB-02-AC2: a corrupt checkpoint must not become a fake SUCCESS.

    ``resume_from_checkpoint`` trusted ``last_completed_step`` without validating
    it against ``total_steps``, so a checkpoint claiming more progress than the
    workload contains returned ``status="SUCCESS"`` with
    ``reason="ALREADY_COMPLETED"`` while executing no steps at all.
    """
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("resume_fake"))
    record = queue.get_job("resume_fake")

    worker = ResearchWorker(
        config=WorkerConfig(
            worker_id="w1",
            host_profile=HostProfile.LENOVO,
            checkpoint_dir=tmp_path / "ckpt",
        ),
        queue=queue,
        probe=StaticResourceProbe(
            SystemResourceReading(ac_power_connected=True, free_ram_gb=16.0)
        ),
    )
    checkpoint = worker.get_checkpoint_path("resume_fake")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text(
        json.dumps(
            {
                "job_id": "resume_fake",
                "last_completed_step": 999,  # total_steps is only 3
                "state": None,
                "saved_at": "2025-06-01T12:00:00+00:00",
                "reason": "AC_POWER_DISCONNECTED",
            }
        ),
        encoding="utf-8",
    )

    executed: list[int] = []
    with pytest.raises(CheckpointIntegrityError, match="CHECKPOINT_STEP_OUT_OF_RANGE"):
        worker.resume_from_checkpoint(
            record, total_steps=3, step_fn=lambda i: executed.append(i)
        )
    assert executed == []


def test_resume_refuses_a_checkpoint_for_a_different_job(tmp_path: Path) -> None:
    """JOB-02-AC2: a checkpoint's recorded job identity must be verified."""
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("owner_job"))
    record = queue.get_job("owner_job")

    worker = ResearchWorker(
        config=WorkerConfig(
            worker_id="w1",
            host_profile=HostProfile.LENOVO,
            checkpoint_dir=tmp_path / "ckpt",
        ),
        queue=queue,
        probe=StaticResourceProbe(
            SystemResourceReading(ac_power_connected=True, free_ram_gb=16.0)
        ),
    )
    checkpoint = worker.get_checkpoint_path("owner_job")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text(
        json.dumps(
            {
                "job_id": "some_other_job",  # identity mismatch
                "last_completed_step": 1,
                "state": None,
                "saved_at": "2025-06-01T12:00:00+00:00",
                "reason": "AC_POWER_DISCONNECTED",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CheckpointIntegrityError, match="CHECKPOINT_JOB_ID_MISMATCH"):
        worker.resume_from_checkpoint(record, total_steps=5, step_fn=lambda i: None)


def test_resume_refuses_a_negative_step_index(tmp_path: Path) -> None:
    """JOB-02-AC2: a negative step index must not execute phantom steps."""
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("negative_step"))
    record = queue.get_job("negative_step")

    worker = ResearchWorker(
        config=WorkerConfig(
            worker_id="w1",
            host_profile=HostProfile.LENOVO,
            checkpoint_dir=tmp_path / "ckpt",
        ),
        queue=queue,
        probe=StaticResourceProbe(
            SystemResourceReading(ac_power_connected=True, free_ram_gb=16.0)
        ),
    )
    checkpoint = worker.get_checkpoint_path("negative_step")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text(
        json.dumps(
            {
                "job_id": "negative_step",
                "last_completed_step": -5,
                "state": None,
                "saved_at": "2025-06-01T12:00:00+00:00",
                "reason": "AC_POWER_DISCONNECTED",
            }
        ),
        encoding="utf-8",
    )

    executed: list[int] = []
    with pytest.raises(CheckpointIntegrityError, match="CHECKPOINT_STEP_OUT_OF_RANGE"):
        worker.resume_from_checkpoint(
            record, total_steps=3, step_fn=lambda i: executed.append(i)
        )
    assert executed == []


def test_resume_refuses_a_corrupt_checkpoint_file(tmp_path: Path) -> None:
    """JOB-02-AC2: an unparseable checkpoint must be refused, not crash or restart."""
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("corrupt_ckpt"))
    record = queue.get_job("corrupt_ckpt")

    worker = ResearchWorker(
        config=WorkerConfig(
            worker_id="w1",
            host_profile=HostProfile.LENOVO,
            checkpoint_dir=tmp_path / "ckpt",
        ),
        queue=queue,
        probe=StaticResourceProbe(
            SystemResourceReading(ac_power_connected=True, free_ram_gb=16.0)
        ),
    )
    checkpoint = worker.get_checkpoint_path("corrupt_ckpt")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text("{not json", encoding="utf-8")

    executed: list[int] = []
    with pytest.raises(CheckpointIntegrityError, match="CHECKPOINT_UNREADABLE"):
        worker.resume_from_checkpoint(
            record, total_steps=3, step_fn=lambda i: executed.append(i)
        )
    assert executed == [], "a corrupt checkpoint must not silently restart the workload"


def test_valid_checkpoint_still_resumes_from_the_next_step(tmp_path: Path) -> None:
    """Regression guard: the integrity guards must not break legitimate resume."""
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("good_resume"))
    record = queue.claim_job("w1")
    assert record is not None

    worker = ResearchWorker(
        config=WorkerConfig(
            worker_id="w1",
            host_profile=HostProfile.LENOVO,
            checkpoint_dir=tmp_path / "ckpt",
        ),
        queue=queue,
        probe=StaticResourceProbe(
            SystemResourceReading(ac_power_connected=True, free_ram_gb=16.0)
        ),
    )
    checkpoint = worker.get_checkpoint_path("good_resume")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text(
        json.dumps(
            {
                "job_id": "good_resume",
                "last_completed_step": 1,  # steps 0 and 1 already done
                "state": None,
                "saved_at": "2025-06-01T12:00:00+00:00",
                "reason": "AC_POWER_DISCONNECTED",
            }
        ),
        encoding="utf-8",
    )

    executed: list[int] = []
    result = worker.resume_from_checkpoint(
        record, total_steps=4, step_fn=lambda i: executed.append(i)
    )
    assert executed == [2, 3]
    assert result.status == "SUCCESS"
    assert result.last_completed_step == 3


def test_completed_workload_still_reports_already_completed(tmp_path: Path) -> None:
    """Regression guard: a fully completed checkpoint must not be treated as corrupt."""
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("all_done"))
    record = queue.claim_job("w1")
    assert record is not None

    worker = ResearchWorker(
        config=WorkerConfig(
            worker_id="w1",
            host_profile=HostProfile.LENOVO,
            checkpoint_dir=tmp_path / "ckpt",
        ),
        queue=queue,
        probe=StaticResourceProbe(
            SystemResourceReading(ac_power_connected=True, free_ram_gb=16.0)
        ),
    )
    checkpoint = worker.get_checkpoint_path("all_done")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text(
        json.dumps(
            {
                "job_id": "all_done",
                "last_completed_step": 2,  # == total_steps - 1
                "state": None,
                "saved_at": "2025-06-01T12:00:00+00:00",
                "reason": "AC_POWER_DISCONNECTED",
            }
        ),
        encoding="utf-8",
    )

    executed: list[int] = []
    result = worker.resume_from_checkpoint(
        record, total_steps=3, step_fn=lambda i: executed.append(i)
    )
    assert executed == []
    assert result.status == "SUCCESS"
    assert result.reason == "ALREADY_COMPLETED"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("free_ram_gb", float("nan")),
        ("user_idle_seconds", float("inf")),
        ("cpu_temp_celsius", float("nan")),
        ("cpu_load_pct", float("inf")),
    ],
)
def test_non_finite_sensor_readings_are_rejected(field: str, value: float) -> None:
    values = {
        "ac_power_connected": True,
        "free_ram_gb": 8.0,
        "user_idle_seconds": 900.0,
        "cpu_temp_celsius": 50.0,
        "cpu_load_pct": 10.0,
        "gpu_available": True,
    }
    values[field] = value

    with pytest.raises(ValidationError):
        SystemResourceReading(**values)


def test_worker_renews_short_lease_during_long_step(tmp_path: Path) -> None:
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(
        _build_test_job(
            "long_step",
            resource_class=ResourceClass.HIGH,
        ).model_copy(update={"lease_duration_seconds": 1})
    )
    claimed_at = datetime.now(UTC)
    job = queue.claim_job("worker-1", as_of=claimed_at)
    assert job is not None
    worker = ResearchWorker(
        config=WorkerConfig(
            worker_id="worker-1",
            host_profile=HostProfile.LENOVO,
            checkpoint_dir=tmp_path / "checkpoints",
            poll_interval_seconds=0.1,
        ),
        queue=queue,
        probe=StaticResourceProbe(SystemResourceReading(ac_power_connected=True)),
    )

    result = worker.execute_steps(
        job,
        total_steps=1,
        step_fn=lambda _: (time.sleep(1.2) or {"finished": True}),
    )

    assert result.status == "SUCCESS"
    assert queue.claim_job("worker-2", as_of=datetime.now(UTC)) is None
