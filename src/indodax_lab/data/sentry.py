"""Snapshot-level quality gate that never changes bronze or raw evidence."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .checksums import sha256_bytes, sha256_file
from .manifest import (
    ImmutableContentConflictError,
    canonical_json_bytes,
    content_id_path_component,
    read_manifest,
    snapshot_manifest_path,
)
from .publication import (
    IndeterminatePublicationError,
    ensure_directory_tree,
    fsync_directory,
    publish_immutable_bytes,
)
from .quality import (
    POLICY_VERSION,
    QUALITY_REPORT_SCHEMA_VERSION,
    InvalidValidationWindowError,
    QualityReport,
    failure_report,
    validate_candles,
)


class _StrictFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    severity: Literal["WARN", "FAIL"]
    pair: str = Field(min_length=1)
    start_ts: datetime
    end_ts: datetime
    row_count: int = Field(ge=0)
    details: dict[str, str]


class _Coverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start_ts: datetime | None
    end_ts: datetime | None


class _GapRange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start_ts: datetime
    end_ts: datetime


class _StrictQualityReport(BaseModel):
    """Exact persisted candle sentry schema; legacy partial records fail closed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    quality_schema_version: str
    policy_version: str
    expected_start: datetime | None
    expected_end: datetime | None
    interval: str | None
    as_of: datetime | None
    max_final_bar_age_microseconds: int | None = Field(default=None, ge=0)
    expected_rows: int = Field(ge=0)
    actual_rows: int = Field(ge=0)
    gap_ranges: list[_GapRange]
    duplicate_count: int = Field(ge=0)
    invariant_counts: dict[str, int]
    min_ts: datetime | None
    max_ts: datetime | None
    coverage: _Coverage
    source_checksums: list[str]
    status: Literal["PASS", "WARN", "FAIL"]
    silver_eligible: bool
    findings: list[_StrictFinding]

    def approved_status(self, *, allow_warn: bool) -> bool:
        if (
            self.quality_schema_version != QUALITY_REPORT_SCHEMA_VERSION
            or self.policy_version != POLICY_VERSION
            or self.silver_eligible != (self.status == "PASS")
        ):
            return False
        derived = "FAIL" if any(row.severity == "FAIL" for row in self.findings) else (
            "WARN" if self.findings else "PASS"
        )
        if self.status != derived or any(value < 0 for value in self.invariant_counts.values()):
            return False
        if self.min_ts != self.coverage.start_ts:
            return False
        if self.max_ts is None:
            if self.coverage.end_ts is not None:
                return False
        elif self.coverage.end_ts is None or self.coverage.end_ts < self.max_ts:
            return False
        return self.status == "PASS" or (allow_warn and self.status == "WARN")


@dataclass(frozen=True)
class SnapshotValidationResult:
    """A fail-closed decision plus an immutable quality evidence record."""

    report: QualityReport
    partition_state: Literal["APPROVED", "QUARANTINED"]
    eligible_for_silver: bool
    quarantine_record: Path | None


class SnapshotPathUnresolvableError(RuntimeError):
    """A snapshot or decision path cannot be resolved safely below its data root."""


@dataclass(frozen=True)
class ApprovedSnapshotDecision:
    """A durable sentry decision whose source bytes still match the named snapshot."""

    snapshot_id: str
    record_path: Path
    record_sha256: str
    status: Literal["PASS", "WARN"]
    source_checksums: tuple[str, ...]


def validate_snapshot(
    data_root: Path,
    snapshot_id: str,
    *,
    expected_start: datetime,
    expected_end: datetime,
    as_of: datetime,
    approve_warnings: bool = False,
    max_final_bar_age: timedelta | None = None,
) -> SnapshotValidationResult:
    """Validate a published snapshot and write a separate immutable gate decision."""
    validate_snapshot_id(snapshot_id)
    try:
        root = Path(data_root).resolve()
    except (OSError, RuntimeError):
        return _unrecorded_failure("SNAPSHOT_PATH_UNRESOLVABLE")
    checksums: list[str] = []
    try:
        manifest_path = snapshot_manifest_path(root, snapshot_id)
        if _contained_path(root, str(manifest_path.relative_to(root))) is None:
            return _finalize(root, snapshot_id, failure_report("SNAPSHOT_INVALID"))
        if manifest_path is None:
            return _finalize(root, snapshot_id, failure_report("SNAPSHOT_INVALID"))
        manifest = read_manifest(manifest_path)
        if manifest.get("dataset_snapshot_id") != snapshot_id:
            return _finalize(root, snapshot_id, failure_report("SNAPSHOT_INVALID"))
        partitions = manifest.get("partitions")
        if not isinstance(partitions, list):
            return _finalize(root, snapshot_id, failure_report("SNAPSHOT_INVALID"))
    except SnapshotPathUnresolvableError:
        return _unrecorded_failure("SNAPSHOT_PATH_UNRESOLVABLE")
    except (OSError, UnicodeDecodeError, ValueError, TypeError):
        return _finalize(root, snapshot_id, failure_report("SNAPSHOT_INVALID"))

    rows: list[dict[str, object]] = []
    findings: list[QualityReport] = []
    for partition in sorted(
        partitions,
        key=lambda item: str(item.get("path", "")) if isinstance(item, dict) else "",
    ):
        if not isinstance(partition, dict):
            findings.append(failure_report("SNAPSHOT_INVALID", source_checksums=checksums))
            continue
        expected_checksum = partition.get("sha256")
        relative_path = partition.get("path")
        if not isinstance(expected_checksum, str) or not isinstance(relative_path, str):
            findings.append(failure_report("SNAPSHOT_INVALID", source_checksums=checksums))
            continue
        checksums.append(expected_checksum)
        try:
            path = _safe_partition_path(root, relative_path)
            missing = path is None or not path.is_file()
        except (OSError, SnapshotPathUnresolvableError):
            findings.append(
                failure_report("SNAPSHOT_PATH_UNRESOLVABLE", source_checksums=checksums)
            )
            continue
        if missing:
            findings.append(failure_report("PARTITION_MISSING", source_checksums=checksums))
            continue
        try:
            checksum_matches = sha256_file(path) == expected_checksum
        except OSError:
            findings.append(
                failure_report("SNAPSHOT_PATH_UNRESOLVABLE", source_checksums=checksums)
            )
            continue
        if not checksum_matches:
            findings.append(
                failure_report("PARTITION_CHECKSUM_MISMATCH", source_checksums=checksums)
            )
            continue
        try:
            rows.extend(pq.ParquetFile(path).read().to_pylist())
        except (OSError, pa.ArrowException, ValueError):
            findings.append(failure_report("PARTITION_UNREADABLE", source_checksums=checksums))

    if findings:
        report = _combine_failures(findings, checksums)
    else:
        intervals = {str(row.get("interval", "")) for row in rows}
        if len(intervals) != 1:
            report = failure_report("SNAPSHOT_INVALID", source_checksums=checksums)
        else:
            try:
                report = validate_candles(
                    rows,
                    expected_start=expected_start,
                    expected_end=expected_end,
                    interval=intervals.pop(),
                    as_of=as_of,
                    source_checksums=checksums,
                    max_final_bar_age=max_final_bar_age,
                )
            except InvalidValidationWindowError:
                raise
            except ValueError:
                report = failure_report(
                    "SNAPSHOT_CONTENT_INVALID",
                    details={"reason": "VALIDATION_VALUE_ERROR"},
                    source_checksums=checksums,
                )
    return _finalize(root, snapshot_id, report, approve_warnings=approve_warnings)


def require_approved_snapshot_decision(
    data_root: Path,
    snapshot_id: str,
    *,
    approve_warnings: bool = False,
) -> ApprovedSnapshotDecision:
    """Load the immutable sentry approval required before a silver publication.

    This intentionally rechecks the bronze manifest and every partition checksum:
    an old PASS record is not approval for bytes that later changed on disk.
    """
    validate_snapshot_id(snapshot_id)
    root = Path(data_root).resolve()
    manifest_path = snapshot_manifest_path(root, snapshot_id)
    if _contained_path(root, str(manifest_path.relative_to(root))) is None:
        raise ValueError("source snapshot quality decision is unavailable")
    try:
        manifest = read_manifest(manifest_path)
        partitions = manifest["partitions"]
        if manifest.get("dataset_snapshot_id") != snapshot_id or not isinstance(partitions, list):
            raise ValueError
        checksums: list[str] = []
        rows: list[dict[str, object]] = []
        for partition in partitions:
            if not isinstance(partition, dict):
                raise ValueError
            checksum, relative = partition.get("sha256"), partition.get("path")
            if not isinstance(checksum, str) or not isinstance(relative, str):
                raise ValueError
            path = _safe_partition_path(root, relative)
            if path is None or sha256_file(path) != checksum:
                raise ValueError
            checksums.append(checksum)
            rows.extend(pq.ParquetFile(path).read().to_pylist())
    except (OSError, ValueError, TypeError, SnapshotPathUnresolvableError) as error:
        raise ValueError("source snapshot quality decision checksum mismatch") from error

    directory = _contained_path(root, "quality", "snapshots", content_id_path_component(snapshot_id))
    if directory is None or not directory.is_dir():
        raise ValueError("source snapshot quality decision is missing")
    records = sorted(directory.glob("*.json"))
    if len(records) != 1:
        raise ValueError("source snapshot quality decision is missing or ambiguous")
    record = records[0]
    try:
        payload = record.read_bytes()
        if record.stem != sha256_bytes(payload):
            raise ValueError
        report = _StrictQualityReport.model_validate_json(payload)
        if tuple(sorted(report.source_checksums)) != tuple(
            sorted(checksums)
        ):
            raise ValueError
    except (OSError, UnicodeDecodeError, ValueError, TypeError, ValidationError) as error:
        raise ValueError("source snapshot quality decision is not a canonical report") from error
    if (
        report.expected_start is None
        or report.expected_end is None
        or report.interval is None
        or report.as_of is None
    ):
        raise ValueError("source snapshot quality decision is not a canonical report")
    try:
        regenerated = validate_candles(
            rows,
            expected_start=report.expected_start,
            expected_end=report.expected_end,
            interval=report.interval,
            as_of=report.as_of,
            source_checksums=checksums,
            max_final_bar_age=(
                timedelta(microseconds=report.max_final_bar_age_microseconds)
                if report.max_final_bar_age_microseconds is not None
                else None
            ),
            policy_version=report.policy_version,
        )
    except (InvalidValidationWindowError, ValueError, TypeError) as error:
        raise ValueError("source snapshot quality decision is not a canonical report") from error
    if payload != canonical_json_bytes(regenerated.to_dict()):
        raise ValueError("source snapshot quality decision is not a canonical report")
    if report.approved_status(allow_warn=approve_warnings):
        return ApprovedSnapshotDecision(
            snapshot_id=snapshot_id,
            record_path=record,
            record_sha256=sha256_bytes(payload),
            status=report.status,
            source_checksums=tuple(sorted(checksums)),
        )
    raise ValueError("source snapshot quality decision is not approved")


def _safe_partition_path(root: Path, relative_path: str) -> Path | None:
    return _contained_path(root, relative_path)


def validate_snapshot_id(snapshot_id: str) -> None:
    """Reject IDs that cannot safely occupy exactly one path segment."""
    if (
        not isinstance(snapshot_id, str)
        or not snapshot_id
        or snapshot_id in {".", ".."}
        or Path(snapshot_id).is_absolute()
        or "/" in snapshot_id
        or "\\" in snapshot_id
        or any(ord(character) < 32 or ord(character) == 127 for character in snapshot_id)
    ):
        raise ValueError("INVALID_SNAPSHOT_ID")


def _contained_path(root: Path, *segments: str) -> Path | None:
    try:
        candidate = root.joinpath(*segments).resolve()
    except (OSError, RuntimeError) as error:
        raise SnapshotPathUnresolvableError from error
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _combine_failures(reports: Iterable[QualityReport], checksums: Iterable[str]) -> QualityReport:
    reports = tuple(reports)
    first = reports[0]
    findings = tuple(finding for report in reports for finding in report.findings)
    counts: dict[str, int] = {}
    for report in reports:
        for code, count in report.invariant_counts.items():
            counts[code] = counts.get(code, 0) + count
    return QualityReport(
        quality_schema_version=first.quality_schema_version,
        policy_version=first.policy_version,
        expected_start=None,
        expected_end=None,
        interval=None,
        as_of=None,
        max_final_bar_age_microseconds=None,
        expected_rows=0,
        actual_rows=0,
        gap_ranges=(),
        duplicate_count=0,
        invariant_counts=dict(sorted(counts.items())),
        min_ts=None,
        max_ts=None,
        coverage=(None, None),
        source_checksums=tuple(sorted(set(checksums))),
        status="FAIL",
        silver_eligible=False,
        findings=tuple(sorted(findings, key=lambda finding: (finding.code, finding.pair))),
    )


def _finalize(
    root: Path,
    snapshot_id: str,
    report: QualityReport,
    *,
    approve_warnings: bool = False,
) -> SnapshotValidationResult:
    payload = canonical_json_bytes(report.to_dict())
    record_kind = "quarantine" if report.status == "FAIL" else "quality"
    try:
        snapshot_component = content_id_path_component(snapshot_id)
    except ValueError:
        return SnapshotValidationResult(
            report=report,
            partition_state="QUARANTINED",
            eligible_for_silver=False,
            quarantine_record=None,
        )
    try:
        record = _contained_path(
            root,
            record_kind,
            "snapshots",
            snapshot_component,
            f"{sha256_bytes(payload)}.json",
        )
    except SnapshotPathUnresolvableError:
        return _unrecorded_failure("SNAPSHOT_PATH_UNRESOLVABLE")
    if record is None:
        return _unpublished_result(report, "QUALITY_RECORD_UNAVAILABLE", approve_warnings)
    try:
        ensure_directory_tree(record.parent, fsync_directory_fn=fsync_directory)
        publish_immutable_bytes(record, payload, fsync_directory_fn=fsync_directory)
        record_path: Path | None = record
    except ImmutableContentConflictError:
        return _unpublished_result(report, "QUALITY_RECORD_CONFLICT", approve_warnings)
    except IndeterminatePublicationError:
        return _unpublished_result(report, "QUALITY_RECORD_INDETERMINATE", approve_warnings)
    except OSError:
        return _unpublished_result(report, "QUALITY_RECORD_UNAVAILABLE", approve_warnings)
    quarantined = report.status == "FAIL"
    return SnapshotValidationResult(
        report=report,
        partition_state="QUARANTINED" if quarantined else "APPROVED",
        eligible_for_silver=(
            report.status == "PASS" or (report.status == "WARN" and approve_warnings)
        ),
        quarantine_record=record_path if quarantined else None,
    )


def _unpublished_result(
    original_report: QualityReport, code: str, approve_warnings: bool
) -> SnapshotValidationResult:
    """Fail closed without claiming a durable decision record after publication failed."""
    report = failure_report(code, source_checksums=original_report.source_checksums)
    return SnapshotValidationResult(
        report=report,
        partition_state="QUARANTINED",
        eligible_for_silver=False,
        quarantine_record=None,
    )


def _unrecorded_failure(code: str) -> SnapshotValidationResult:
    """Return a structured failure when no decision path can be safely used."""
    return SnapshotValidationResult(
        report=failure_report(code),
        partition_state="QUARANTINED",
        eligible_for_silver=False,
        quarantine_record=None,
    )
