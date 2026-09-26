"""Unit tests for JOB-01 Durable leased jobs and SQLite WAL local queue."""

import hashlib
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from indodax_lab.orchestration.jobs import (
    JobDefinition,
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
        expected_hash=hashlib.sha256(b"worker_2_valid_result").hexdigest(),
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
            expected_hash=hashlib.sha256(b"different expected complete result").hexdigest(),
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


# ---------------------------------------------------------------------------
# Sprint-review fix cycle. Actor for every line below:
# opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
# ---------------------------------------------------------------------------


def test_complete_job_cannot_publish_success_without_a_result_artifact(tmp_path: Path) -> None:
    """JOB-01-AC3: a job with no artifact at all is a partial result, never SUCCESS.

    ``artifact_path=None`` previously flowed straight through to
    ``status=SUCCESS`` with a null result path and hash, so a worker that
    produced nothing - or died before writing - published a successful job.
    """
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("no_artifact"))
    started = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    claimed = queue.claim_job("worker_1", as_of=started)
    assert claimed is not None

    with pytest.raises(PartialArtifactError) as exc_info:
        queue.complete_job("no_artifact", "worker_1", generation=claimed.generation, as_of=started)

    assert "ARTIFACT_PATH_REQUIRED" in str(exc_info.value)

    record = queue.get_job("no_artifact")
    assert record.status == JobStatus.RUNNING
    assert record.result_artifact_path is None
    assert record.result_artifact_hash is None


def test_complete_job_requires_expected_digest_for_complete_artifact(tmp_path: Path) -> None:
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("missing_digest"))
    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    claimed = queue.claim_job("worker_1", as_of=now)
    assert claimed is not None
    artifact = tmp_path / "partial.bin"
    artifact.write_bytes(b"prefix of an interrupted output")

    with pytest.raises(PartialArtifactError, match="ARTIFACT_EXPECTED_HASH_REQUIRED"):
        queue.complete_job(
            "missing_digest", "worker_1", claimed.generation,
            artifact_path=artifact, as_of=now,
        )

    assert queue.get_job("missing_digest").status == JobStatus.RUNNING


def test_completion_publishes_content_addressed_copy_not_worker_path(tmp_path: Path) -> None:
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("immutable_output"))
    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    claimed = queue.claim_job("worker_1", as_of=now)
    assert claimed is not None
    source = tmp_path / "worker-output.bin"
    content = b"complete immutable artifact"
    source.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()

    completed = queue.complete_job(
        "immutable_output", "worker_1", claimed.generation,
        artifact_path=source, expected_hash=digest, as_of=now,
    )

    assert completed.result_artifact_path != str(source)
    assert Path(completed.result_artifact_path).read_bytes() == content
    source.write_bytes(b"stale worker changed its local output")
    assert Path(completed.result_artifact_path).read_bytes() == content
    assert queue.read_result_artifact("immutable_output") == content


def test_commit_crash_recovers_staged_artifact_without_recomputation(
    tmp_path: Path, monkeypatch
) -> None:
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("recover_artifact", lease_duration_seconds=10))
    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    first = queue.claim_job("worker_1", as_of=now)
    assert first is not None
    source = tmp_path / "output.bin"
    content = b"completed output survives db commit crash"
    source.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    connect = queue._connect
    commit_state = {"count": 0}

    class FailSecondCommit:
        def __init__(self, connection):
            self.connection = connection
            self.commits = 0

        @property
        def in_transaction(self):
            return self.connection.in_transaction

        def execute(self, sql, *args):
            if sql == "COMMIT;":
                commit_state["count"] += 1
            if sql == "COMMIT;" and commit_state["count"] == 2:
                raise sqlite3.OperationalError("injected commit crash")
            return self.connection.execute(sql, *args)

        def close(self):
            self.connection.close()

    monkeypatch.setattr(queue, "_connect", lambda: FailSecondCommit(connect()))
    with pytest.raises(sqlite3.OperationalError, match="injected commit crash"):
        queue.complete_job(
            "recover_artifact", "worker_1", first.generation,
            artifact_path=source, expected_hash=digest, as_of=now,
        )
    monkeypatch.setattr(queue, "_connect", connect)
    assert queue.get_job("recover_artifact").status == JobStatus.RUNNING

    retry_time = now + timedelta(seconds=11)
    second = queue.claim_job("worker_2", as_of=retry_time)
    assert second is not None and second.generation == first.generation + 1
    completed = queue.recover_completed_artifact(
        "recover_artifact", "worker_2", second.generation, as_of=retry_time,
    )

    stored = Path(completed.result_artifact_path)
    assert completed.status == JobStatus.SUCCESS
    assert stored.read_bytes() == content
    assert len(list((tmp_path / "queue.db.artifacts").rglob(digest))) == 1


def test_read_result_artifact_rejects_tampering(tmp_path: Path) -> None:
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("tampered_output"))
    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    claimed = queue.claim_job("worker_1", as_of=now)
    assert claimed is not None
    source = tmp_path / "output.bin"
    content = b"verified output"
    source.write_bytes(content)
    completed = queue.complete_job(
        "tampered_output", "worker_1", claimed.generation,
        artifact_path=source, expected_hash=hashlib.sha256(content).hexdigest(), as_of=now,
    )
    published = Path(completed.result_artifact_path)
    published.write_bytes(b"tampered")

    with pytest.raises(PartialArtifactError, match="ARTIFACT_PUBLISHED_CHECKSUM_MISMATCH"):
        queue.read_result_artifact("tampered_output")


def test_fenced_worker_is_fenced_before_artifact_inspection(tmp_path: Path) -> None:
    """JOB-01-AC2: lease fencing is authoritative and is checked before the artifact.

    A superseded worker must be refused as stale regardless of what it passes
    as ``artifact_path``. Previously a fenced worker got
    ``ARTIFACT_FILE_NOT_FOUND`` for a bad path, which both leaked artifact
    filesystem details to a fenced caller and reported the wrong reason.
    """
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("fenced_first", lease_duration_seconds=30))
    started = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    first = queue.claim_job("worker_1", as_of=started)
    assert first is not None

    expired = started + timedelta(seconds=35)
    second = queue.claim_job("worker_2", as_of=expired)
    assert second is not None and second.generation == first.generation + 1

    with pytest.raises(LeaseFencingError, match="STALE_LEASE_FENCED"):
        queue.complete_job(
            "fenced_first",
            "worker_1",
            generation=first.generation,
            artifact_path=tmp_path / "definitely_absent.bin",
            as_of=expired,
        )


def test_expired_lease_takeover_is_recorded_for_audit(tmp_path: Path) -> None:
    """A crashed attempt must leave a durable trail when its lease is taken over.

    ``JobStatus.STALE`` is part of the declared JOB-01 lifecycle but nothing in
    the queue ever produced it, so a worker that died mid-flight was silently
    re-claimed with no observable evidence. The takeover must be recorded.
    """
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("crashed", lease_duration_seconds=30, max_attempts=3))
    started = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    first = queue.claim_job("dead_worker", as_of=started)
    assert first is not None

    expired = started + timedelta(seconds=35)
    replacement = queue.claim_job("live_worker", as_of=expired)
    assert replacement is not None
    assert replacement.owner_id == "live_worker"

    marker = replacement.error_message
    assert marker is not None, "expired-lease takeover left no audit marker"
    assert "STALE_LEASE_TAKEOVER" in marker
    assert "dead_worker" in marker
    assert str(first.generation) in marker


def test_successful_completion_clears_the_takeover_marker(tmp_path: Path) -> None:
    """Regression guard: a clean SUCCESS must not inherit a stale-takeover marker."""
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("recovered", lease_duration_seconds=30, max_attempts=3))
    started = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    queue.claim_job("dead_worker", as_of=started)

    expired = started + timedelta(seconds=35)
    replacement = queue.claim_job("live_worker", as_of=expired)
    assert replacement is not None

    artifact = tmp_path / "recovered.bin"
    artifact.write_bytes(b"recovered_result_payload")
    completed = queue.complete_job(
        "recovered",
        "live_worker",
        generation=replacement.generation,
        artifact_path=artifact,
        expected_hash=hashlib.sha256(b"recovered_result_payload").hexdigest(),
        as_of=expired + timedelta(seconds=5),
    )
    assert completed.status == JobStatus.SUCCESS
    assert completed.error_message is None


def test_first_claim_carries_no_takeover_marker(tmp_path: Path) -> None:
    """Regression guard: a first-time PENDING claim is not a stale takeover."""
    queue = SqliteJobQueue(tmp_path / "queue.db")
    queue.submit_job(_build_test_job("fresh"))
    claimed = queue.claim_job("worker_1", as_of=datetime(2025, 6, 1, 12, 0, tzinfo=UTC))
    assert claimed is not None
    assert claimed.error_message is None
