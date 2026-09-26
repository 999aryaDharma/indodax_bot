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

from indodax_lab.orchestration.jobs import JobRecord, JobStatus, LeaseFencingError
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
        as_of: datetime | None = None,
    ) -> ExecutionResult:
        """Execute a staged sequence of steps, checking for AC disconnect at each boundary.

        Lease coordination: the worker verifies it still holds the active queue
        lease (owner/generation/status/expiry) at every step boundary and extends
        it via heartbeat after each completed step. A stolen or expired lease
        raises LeaseFencingError fail-closed instead of executing blindly.

        If AC power is disconnected or UNKNOWN:
        - Saves current progress into a checkpoint JSON file.
        - Immediately pauses execution with status PAUSED and reason AC_POWER_DISCONNECTED_CHECKPOINT_SAVED.
        """
        # Guard: ASUS profile strictly cannot import or execute training (JOB-02-AC3)
        if self.config.host_profile == HostProfile.ASUS and is_training_job(job):
            guard_asus_training_import(self.config.host_profile)

        now = as_of or datetime.now(UTC)
        self._verify_lease(job, now)

        last_completed_step = start_step - 1
        last_state: dict[str, Any] | None = None

        for step_idx in range(start_step, total_steps):
            self._verify_lease(job, now)
            # Check resource probe before executing step (UNKNOWN AC is not safe)
            reading = self.probe.read()
            if reading.ac_power_connected is not True:
                return self._trigger_checkpoint_pause(job.job_id, last_completed_step, last_state)

            # Execute step
            last_state = step_fn(step_idx)
            last_completed_step = step_idx
            self.queue.heartbeat(job.job_id, self.config.worker_id, job.generation, as_of=now)

            # Check resource probe immediately after completing step
            post_reading = self.probe.read()
            if post_reading.ac_power_connected is not True:
                return self._trigger_checkpoint_pause(job.job_id, last_completed_step, last_state)

        return ExecutionResult(
            status="SUCCESS",
            reason=None,
            last_completed_step=last_completed_step,
            checkpoint_path=None,
            metrics={"total_completed_steps": total_steps},
        )

    def _verify_lease(self, job: JobRecord, as_of: datetime) -> None:
        """Fail closed unless this worker holds the active queue lease."""
        try:
            current = self.queue.get_job(job.job_id)
        except KeyError:
            raise LeaseFencingError(
                f"STALE_LEASE_FENCED: job {job.job_id} is not tracked by the queue"
            ) from None
        if (
            current.status != JobStatus.RUNNING
            or current.owner_id != self.config.worker_id
            or current.generation != job.generation
            or current.lease_expires_at is None
            or current.lease_expires_at <= as_of
        ):
            raise LeaseFencingError(
                f"STALE_LEASE_FENCED: worker {self.config.worker_id} generation "
                f"{job.generation} does not hold the active lease for job {job.job_id}"
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
        as_of: datetime | None = None,
    ) -> ExecutionResult:
        """Resume execution from the last persisted checkpoint."""
        checkpoint_path = self.get_checkpoint_path(job.job_id)
        if not checkpoint_path.exists():
            return self.execute_steps(job, total_steps, step_fn, start_step=0, as_of=as_of)

        data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        next_step = data["last_completed_step"] + 1

        if next_step >= total_steps:
            return ExecutionResult(
                status="SUCCESS",
                reason="ALREADY_COMPLETED",
                last_completed_step=data["last_completed_step"],
                checkpoint_path=checkpoint_path,
            )

        return self.execute_steps(job, total_steps, step_fn, start_step=next_step, as_of=as_of)
