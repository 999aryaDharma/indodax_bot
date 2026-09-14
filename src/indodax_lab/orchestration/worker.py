"""Resource-aware research worker with checkpoint pause and idle guards (JOB-02).

Contract:
- AC terputus memicu checkpoint pause.
- ASUS profile tidak mengimpor atau menjalankan training.
- Checkpoint enables deterministic resume without duplicating prior steps.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Callable
from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.orchestration.jobs import JobRecord
from indodax_lab.orchestration.queue import SqliteJobQueue
from indodax_lab.orchestration.resources import (
    AdmissionPolicy,
    HostProfile,
    ResourceProbe,
    guard_asus_training_import,
    is_training_job,
)


class WorkerConfig(BaseModel):
    """Configuration for an execution worker process."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    worker_id: str
    host_profile: HostProfile
    checkpoint_dir: Path
    poll_interval_seconds: float = 1.0


class ExecutionResult(BaseModel):
    """Execution status and checkpoint information from a worker run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str
    reason: str | None = None
    last_completed_step: int = -1
    checkpoint_path: Path | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class ResearchWorker:
    """Worker engine that executes staged multi-step research workloads."""

    def __init__(
        self,
        config: WorkerConfig,
        queue: SqliteJobQueue,
        probe: ResourceProbe,
        policy: AdmissionPolicy | None = None,
    ) -> None:
        self.config = config
        self.queue = queue
        self.probe = probe
        self.policy = policy or AdmissionPolicy()
        self.checkpoint_dir = Path(config.checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def get_checkpoint_path(self, job_id: str) -> Path:
        """Derive the deterministic checkpoint file path for a job."""
        return self.checkpoint_dir / f"{job_id}_checkpoint.json"

    def execute_steps(
        self,
        job: JobRecord,
        total_steps: int,
        step_fn: Callable[[int], dict[str, Any] | None],
        start_step: int = 0,
    ) -> ExecutionResult:
        """Execute a staged sequence of steps, checking for AC disconnect at each boundary.

        If AC power is disconnected:
        - Saves current progress into a checkpoint JSON file.
        - Immediately pauses execution with status PAUSED and reason AC_POWER_DISCONNECTED_CHECKPOINT_SAVED.
        """
        # Guard: ASUS profile strictly cannot import or execute training (JOB-02-AC3)
        if self.config.host_profile == HostProfile.ASUS and is_training_job(job):
            guard_asus_training_import(self.config.host_profile)

        last_completed_step = start_step - 1
        last_state: dict[str, Any] | None = None

        for step_idx in range(start_step, total_steps):
            # Check resource probe before executing step
            reading = self.probe.read()
            if reading.ac_power_connected is False:
                return self._trigger_checkpoint_pause(job.job_id, last_completed_step, last_state)

            # Execute step
            last_state = step_fn(step_idx)
            last_completed_step = step_idx

            # Check resource probe immediately after completing step
            post_reading = self.probe.read()
            if post_reading.ac_power_connected is False:
                return self._trigger_checkpoint_pause(job.job_id, last_completed_step, last_state)

        return ExecutionResult(
            status="SUCCESS",
            reason=None,
            last_completed_step=last_completed_step,
            checkpoint_path=None,
            metrics={"total_completed_steps": total_steps},
        )

    def _trigger_checkpoint_pause(
        self,
        job_id: str,
        last_completed_step: int,
        last_state: dict[str, Any] | None,
    ) -> ExecutionResult:
        """Save durable checkpoint to disk and emit pause status."""
        checkpoint_path = self.get_checkpoint_path(job_id)
        checkpoint_data = {
            "job_id": job_id,
            "last_completed_step": last_completed_step,
            "state": last_state,
            "saved_at": datetime.now(UTC).isoformat(),
            "reason": "AC_POWER_DISCONNECTED",
        }
        checkpoint_path.write_text(json.dumps(checkpoint_data, indent=2), encoding="utf-8")
        return ExecutionResult(
            status="PAUSED",
            reason="AC_POWER_DISCONNECTED_CHECKPOINT_SAVED",
            last_completed_step=last_completed_step,
            checkpoint_path=checkpoint_path,
        )

    def resume_from_checkpoint(
        self,
        job: JobRecord,
        total_steps: int,
        step_fn: Callable[[int], dict[str, Any] | None],
    ) -> ExecutionResult:
        """Resume execution from the last persisted checkpoint."""
        checkpoint_path = self.get_checkpoint_path(job.job_id)
        if not checkpoint_path.exists():
            return self.execute_steps(job, total_steps, step_fn, start_step=0)

        data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        next_step = data["last_completed_step"] + 1

        if next_step >= total_steps:
            return ExecutionResult(
                status="SUCCESS",
                reason="ALREADY_COMPLETED",
                last_completed_step=data["last_completed_step"],
                checkpoint_path=checkpoint_path,
            )

        return self.execute_steps(job, total_steps, step_fn, start_step=next_step)
