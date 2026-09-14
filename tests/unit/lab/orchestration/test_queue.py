"""Unit tests for JOB-01 Durable leased jobs and SQLite WAL local queue."""

from datetime import UTC, datetime, timedelta
import hashlib
from pathlib import Path
import pytest

from indodax_lab.orchestration.jobs import (
    JobDefinition,
    JobRecord,
    JobStatus,
    LeaseFencingError,
    PartialArtifactError,
)
from indodax_lab.orchestration.queue import SqliteJobQueue


def _build_test_job(job_id: str = "job_001") -> JobDefinition:
    return JobDefinition(
        job_id=job_id,
        job_type="train_model",
        recipe_hash="recipe_hash_123",
        input_ids=["dataset_v1", "features_v1"],
        cadence_window="daily_2025_06_01",
        parameters={"learning_rate": 0.01},
        max_attempts=3,
        lease_duration_seconds=30,
        created_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
    )


def test_job_01_valid_contract(tmp_path: Path) -> None:
    """JOB-01-AC0: Submit, claim, heartbeat, and complete job with verified artifact."""
    db_path = tmp_path / "queue.db"
    queue = SqliteJobQueue(db_path)

    job_def = _build_test_job("job_normal")
    queue.submit_job(job_def)

    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    claimed = queue.claim_job("worker_a", as_of=now)
    assert claimed is not None
    assert claimed.status == JobStatus.RUNNING
    assert claimed.owner_id == "worker_a"
    assert claimed.generation == 1

    # Heartbeat extends lease
    later = now + timedelta(seconds=10)
    queue.heartbeat("job_normal", "worker_a", generation=1, as_of=later)

    # Valid artifact
    artifact_file = tmp_path / "model.bin"
    artifact_content = b"complete_model_artifact_content"
    artifact_file.write_bytes(artifact_content)
    expected_hash = hashlib.sha256(artifact_content).hexdigest()

    completed = queue.complete_job(
        "job_normal",
        "worker_a",
        generation=1,
        artifact_path=artifact_file,
        expected_hash=expected_hash,
        as_of=later,
    )
    assert completed.status == JobStatus.SUCCESS
    assert completed.result_artifact_hash == expected_hash


def test_job_01_contract_1(tmp_path: Path) -> None:
    """JOB-01-AC1: Atomic claim with two connections: only one wins."""
    db_path = tmp_path / "queue.db"
    queue1 = SqliteJobQueue(db_path)
    queue2 = SqliteJobQueue(db_path)

    queue1.submit_job(_build_test_job("job_atomic"))

    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    claim1 = queue1.claim_job("worker_1", as_of=now)
    claim2 = queue2.claim_job("worker_2", as_of=now)

    # Exactly one worker wins the atomic claim
    assert (claim1 is not None and claim2 is None) or (claim1 is None and claim2 is not None)
    winner = claim1 or claim2
    assert winner.generation == 1
    assert winner.status == JobStatus.RUNNING


def test_job_01_contract_2(tmp_path: Path) -> None:
    """JOB-01-AC2: Stale lease fencing rejects publish from lagged worker."""
    db_path = tmp_path / "queue.db"
    queue = SqliteJobQueue(db_path)

    queue.submit_job(_build_test_job("job_fenced"))

    t0 = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    worker1_claim = queue.claim_job("worker_1", as_of=t0)
    assert worker1_claim is not None
    assert worker1_claim.generation == 1

    # Lease expires after 30s
    t_stale = t0 + timedelta(seconds=35)
    worker2_claim = queue.claim_job("worker_2", as_of=t_stale)
    assert worker2_claim is not None
    assert worker2_claim.owner_id == "worker_2"
    assert worker2_claim.generation == 2

    # Worker 1 attempts to publish result with obsolete generation 1
    artifact_file = tmp_path / "model1.bin"
    artifact_file.write_bytes(b"worker_1_late_result")

    with pytest.raises(LeaseFencingError, match="STALE_LEASE_FENCED"):
        queue.complete_job(
            "job_fenced",
            "worker_1",
            generation=1,
            artifact_path=artifact_file,
            as_of=t_stale,
        )

    # Worker 2 successfully completes with generation 2
    artifact_file2 = tmp_path / "model2.bin"
    artifact_file2.write_bytes(b"worker_2_valid_result")
    completed = queue.complete_job(
        "job_fenced",
        "worker_2",
        generation=2,
        artifact_path=artifact_file2,
        as_of=t_stale + timedelta(seconds=5),
    )
    assert completed.status == JobStatus.SUCCESS


def test_job_01_contract_3(tmp_path: Path) -> None:
    """JOB-01-AC3: Partial or corrupted artifact does not mark SUCCESS."""
    db_path = tmp_path / "queue.db"
    queue = SqliteJobQueue(db_path)

    queue.submit_job(_build_test_job("job_partial"))

    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    claimed = queue.claim_job("worker_1", as_of=now)
    assert claimed is not None

    # Case A: File does not exist
    missing_file = tmp_path / "non_existent.bin"
    with pytest.raises(PartialArtifactError, match="ARTIFACT_FILE_NOT_FOUND"):
        queue.complete_job(
            "job_partial",
            "worker_1",
            generation=1,
            artifact_path=missing_file,
            as_of=now,
        )

    # Status must still be RUNNING, never SUCCESS
    rec = queue.get_job("job_partial")
    assert rec.status == JobStatus.RUNNING

    # Case B: File is empty (0 bytes)
    empty_file = tmp_path / "empty.bin"
    empty_file.write_bytes(b"")
    with pytest.raises(PartialArtifactError, match="ARTIFACT_FILE_EMPTY"):
        queue.complete_job(
            "job_partial",
            "worker_1",
            generation=1,
            artifact_path=empty_file,
            as_of=now,
        )
    rec = queue.get_job("job_partial")
    assert rec.status == JobStatus.RUNNING

    # Case C: Checksum mismatch (corrupted / truncated)
    corrupt_file = tmp_path / "corrupt.bin"
    corrupt_file.write_bytes(b"partial_payload")
    with pytest.raises(PartialArtifactError, match="ARTIFACT_CHECKSUM_MISMATCH"):
        queue.complete_job(
            "job_partial",
            "worker_1",
            generation=1,
            artifact_path=corrupt_file,
            expected_hash="expected_hash_that_does_not_match",
            as_of=now,
        )
    rec = queue.get_job("job_partial")
    assert rec.status == JobStatus.RUNNING
