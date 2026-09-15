"""Unit tests for JOB-01 Durable leased jobs and SQLite WAL local queue."""

from datetime import UTC, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import sqlite3
import threading
import pytest

from indodax_lab.orchestration.jobs import (
    JobDefinition,
    JobRecord,
    JobStatus,
    LeaseFencingError,
    PartialArtifactError,
)
from indodax_lab.orchestration.queue import SqliteJobQueue


def _build_test_job(
    job_id: str = "job_001",
    *,
    max_attempts: int = 3,
    lease_duration_seconds: int = 30,
) -> JobDefinition:
    return JobDefinition(
        job_id=job_id,
        job_type="train_model",
        recipe_hash="recipe_hash_123",
        input_ids=["dataset_v1", "features_v1"],
        cadence_window="daily_2025_06_01",
        parameters={"learning_rate": 0.01},
        max_attempts=max_attempts,
        lease_duration_seconds=lease_duration_seconds,
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


def test_expired_running_job_cannot_exceed_attempt_budget(tmp_path: Path) -> None:
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("one-shot", max_attempts=1))
    started = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)

    assert queue.claim_job("first", as_of=started).attempts == 1
    assert queue.claim_job("second", as_of=started + timedelta(seconds=31)) is None
    exhausted = queue.get_job("one-shot")
    assert exhausted.status == JobStatus.FAILED_FINAL
    assert exhausted.attempts == 1


@pytest.mark.parametrize("reset_status", [JobStatus.PENDING, JobStatus.STALE])
def test_attempt_budget_cannot_be_reset_by_state_or_worker_change(
    tmp_path: Path,
    reset_status: JobStatus,
) -> None:
    db_path = tmp_path / "queue.db"
    queue = SqliteJobQueue(db_path)
    queue.submit_job(_build_test_job("reset", max_attempts=1))
    queue.claim_job("first", as_of=datetime(2025, 6, 1, 12, 0, tzinfo=UTC))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, owner_id = NULL WHERE job_id = ?",
            (reset_status.value, "reset"),
        )

    assert queue.claim_job(
        "different-worker",
        as_of=datetime(2025, 6, 1, 12, 1, tzinfo=UTC),
    ) is None
    assert queue.get_job("reset").status == JobStatus.FAILED_FINAL


def test_worker_is_fenced_immediately_at_lease_expiry(tmp_path: Path) -> None:
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("expires", max_attempts=2, lease_duration_seconds=30))
    started = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    claim = queue.claim_job("old", as_of=started)
    expired = started + timedelta(seconds=30)

    with pytest.raises(LeaseFencingError, match="STALE_LEASE_FENCED"):
        queue.heartbeat("expires", "old", claim.generation, as_of=expired)
    with pytest.raises(LeaseFencingError, match="STALE_LEASE_FENCED"):
        queue.complete_job("expires", "old", claim.generation, as_of=expired)

    replacement = queue.claim_job("new", as_of=expired)
    assert replacement is not None
    assert replacement.owner_id == "new"
    assert replacement.generation == claim.generation + 1


def test_concurrent_claims_on_separate_connections_have_one_winner(tmp_path: Path) -> None:
    db_path = tmp_path / "queue.db"
    first = SqliteJobQueue(db_path)
    second = SqliteJobQueue(db_path)
    first.submit_job(_build_test_job("contended"))
    barrier = threading.Barrier(2)
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)

    def claim(queue: SqliteJobQueue, worker: str):
        barrier.wait(timeout=5)
        return queue.claim_job(worker, as_of=as_of)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args: claim(*args), [(first, "a"), (second, "b")]))

    winners = [record for record in results if record is not None]
    assert len(winners) == 1
    assert winners[0].attempts == 1


def test_failed_claim_transaction_rolls_back_attempt_increment(tmp_path: Path) -> None:
    db_path = tmp_path / "queue.db"
    queue = SqliteJobQueue(db_path)
    queue.submit_job(_build_test_job("rollback"))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TRIGGER reject_claim BEFORE UPDATE ON jobs
            WHEN NEW.status = 'RUNNING'
            BEGIN
                SELECT RAISE(ABORT, 'injected claim failure');
            END;
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="injected claim failure"):
        queue.claim_job("worker", as_of=datetime(2025, 6, 1, 12, 0, tzinfo=UTC))

    record = queue.get_job("rollback")
    assert record.status == JobStatus.PENDING
    assert record.attempts == 0


def test_every_queue_connection_enables_foreign_keys(tmp_path: Path) -> None:
    queue = SqliteJobQueue(tmp_path / "queue.db")
    with queue._connect() as conn:
        assert conn.execute("PRAGMA foreign_keys;").fetchone() == (1,)
