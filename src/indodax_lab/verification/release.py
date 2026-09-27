"""Paper research release candidate packaging, rollback, and qualification gates (REL-01).

Guarantees:
1. REL-01-AC0: Paper research release packaged with lock, runbook, and verified rollback plan.
2. REL-01-AC1: Restoration of previous compatible artifact is verified and deterministic.
3. REL-01-AC2: Experimental/extension work cannot be promoted without explicit owner authorization.
4. REL-01-AC3: Unmet forward duration or trades clearly displayed as pending champion status.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Closed allowlist of candidate tiers. Anything outside this set is refused
#: rather than silently promoted into release runtime (REL-01-AC2).
KNOWN_CANDIDATE_TIERS: tuple[str, ...] = ("CORE", "EXPERIMENTAL", "EXTENSION")

#: Status a sprint must hold in ``sprint-manifest.json`` to count as verified.
_VERIFIED_SPRINT_STATUS = "DONE"

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ExperimentalPromotionForbiddenError(ValueError):
    """Raised when an experimental or extension candidate is promoted to core without approval."""


class RollbackIntegrityError(RuntimeError):
    """Raised when a rollback artifact is missing or fails checksum integrity check."""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ReleaseCandidatePackage(BaseModel):
    """Immutable release candidate package specification."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    release_tag: str
    git_sha: str
    core_sprints_verified: list[str]
    active_champion_id: str
    software_rc_status: str = "NOT_READY"
    champion_status: str = "PENDING_FORWARD_EVALUATION"
    artifacts_manifest: dict[str, str] = Field(default_factory=dict)
    rollback_target_tag: str | None = None
    readiness_reasons: list[str] = Field(default_factory=list)
    packaged_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class ReleaseCandidateManager:
    """Manages paper research release candidate assembly, qualification, and rollback."""

    def package_release(
        self,
        tag: str,
        git_sha: str,
        core_sprints: list[str],
        champion_id: str,
        forward_days: int,
        forward_trades: int,
        artifacts_manifest: dict[str, str],
        rollback_target_tag: str | None = None,
        manifest_path: Path | str | None = None,
    ) -> ReleaseCandidatePackage:
        """Package release candidate, isolating software status from forward longevity.

        Software readiness is *derived* from ``sprint-manifest.json`` (the single
        status authority). It is never assumed: with no manifest evidence, a
        malformed manifest, or any core sprint that is absent or not ``DONE``,
        the package fails closed to ``software_rc_status="NOT_READY"`` and records
        the reason in ``readiness_reasons`` (REL-01-AC0).
        """
        software_ready, readiness_reasons = self._derive_software_readiness(
            core_sprints=core_sprints,
            manifest_path=manifest_path,
        )
        status_info = self.evaluate_release_status(
            software_ready=software_ready,
            forward_days=forward_days,
            forward_trades=forward_trades,
        )

        return ReleaseCandidatePackage(
            release_tag=tag,
            git_sha=git_sha,
            core_sprints_verified=core_sprints,
            active_champion_id=champion_id,
            software_rc_status=status_info["software_rc_status"],
            champion_status=status_info["champion_status"],
            artifacts_manifest=artifacts_manifest,
            rollback_target_tag=rollback_target_tag,
            readiness_reasons=readiness_reasons,
        )

    def _derive_software_readiness(
        self,
        core_sprints: list[str],
        manifest_path: Path | str | None,
    ) -> tuple[bool, list[str]]:
        """Derive software readiness from the sprint manifest, failing closed (REL-01-AC0).

        Returns ``(ready, reasons)``. ``ready`` is ``True`` only when every core
        sprint is present in the manifest with status ``DONE``. Any other outcome
        returns ``False`` together with a human-readable reason per defect.
        """
        sprint_ids = [str(s).strip() for s in core_sprints if str(s).strip()]
        if not sprint_ids:
            return False, ["NO_CORE_SPRINTS: package_release received an empty core sprint list."]

        if manifest_path is None:
            return False, [
                "NO_MANIFEST_EVIDENCE: no sprint manifest supplied, so no core sprint "
                "can be proven verified (REL-01-AC0)."
            ]

        manifest_file = Path(manifest_path)
        if not manifest_file.is_file():
            return False, [
                f"MANIFEST_UNREADABLE: sprint manifest '{manifest_file}' does not exist; "
                "software readiness cannot be derived (REL-01-AC0)."
            ]

        try:
            payload = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return False, [
                f"MANIFEST_MALFORMED: sprint manifest '{manifest_file}' could not be parsed "
                f"({exc}); software readiness cannot be derived (REL-01-AC0)."
            ]

        raw_sprints = payload.get("sprints") if isinstance(payload, dict) else None
        if not isinstance(raw_sprints, list):
            return False, [
                f"MANIFEST_MALFORMED: sprint manifest '{manifest_file}' has no 'sprints' list; "
                "software readiness cannot be derived (REL-01-AC0)."
            ]

        statuses: dict[str, str] = {}
        for entry in raw_sprints:
            if isinstance(entry, dict) and entry.get("id") is not None:
                statuses[str(entry["id"]).strip()] = str(entry.get("status", "")).strip().upper()

        reasons: list[str] = []
        for sprint_id in sprint_ids:
            if sprint_id not in statuses:
                reasons.append(
                    f"{sprint_id}: MISSING_FROM_MANIFEST — cannot be assumed verified (REL-01-AC0)."
                )
            elif statuses[sprint_id] != _VERIFIED_SPRINT_STATUS:
                reasons.append(
                    f"{sprint_id}: STATUS_{statuses[sprint_id] or 'UNKNOWN'} — expected "
                    f"{_VERIFIED_SPRINT_STATUS} (REL-01-AC0)."
                )

        if reasons:
            return False, reasons
        return True, []

    def promote_candidate(
        self,
        candidate_id: str,
        tier: str,
        is_owner_approved: bool = False,
    ) -> str:
        """Promote a candidate into release runtime, rejecting unauthorized models (REL-01-AC2).

        The tier is matched against a closed allowlist. An unrecognized, empty, or
        malformed tier is refused outright — it is never treated as core.
        """
        clean_tier = (tier or "").strip().upper()
        if clean_tier not in KNOWN_CANDIDATE_TIERS:
            raise ExperimentalPromotionForbiddenError(
                f"UNKNOWN_CANDIDATE_TIER: Candidate '{candidate_id}' declares tier "
                f"'{tier!r}' which is not in the known set "
                f"{KNOWN_CANDIDATE_TIERS}. Refused instead of promoted (REL-01-AC2)."
            )
        if clean_tier in ("EXPERIMENTAL", "EXTENSION") and not is_owner_approved:
            raise ExperimentalPromotionForbiddenError(
                f"EXPERIMENTAL_PROMOTION_FORBIDDEN: Candidate '{candidate_id}' belongs to "
                f"{clean_tier} tier and cannot be silently promoted into core release runtime "
                "without explicit owner approval (REL-01-AC2)."
            )
        return "PROMOTED"

    def verify_and_execute_rollback(
        self,
        current_version: str,
        target_version: str,
        target_manifest: dict[str, str],
        artifacts_dir: Path,
        active_dir: Path | None = None,
    ) -> bool:
        """Verify checksum integrity of target version artifacts and execute rollback (REL-01-AC1).

        Verification is performed first and fail-closed. Only once every target
        artifact checks out are the bytes actually written into ``active_dir``.
        If any restore step fails, already-restored files are rolled back to their
        pre-restore content and the error is raised.

        Raises:
            RollbackIntegrityError: If the manifest is empty, declares an unsafe
                key (absolute path or ``..`` traversal), no restore destination was
                supplied, a target artifact is missing or fails its checksum, the restore
                fails, or the post-restore verification does not match.
        """
        if not target_manifest:
            raise RollbackIntegrityError(
                f"ROLLBACK_MANIFEST_EMPTY: Rollback target '{target_version}' declares no "
                "artifacts, so no previous state could be restored. Refused instead of "
                "reporting success (REL-01-AC1)."
            )

        for manifest_key in target_manifest:
            self._reject_unsafe_manifest_key(manifest_key, target_version)

        if active_dir is None:
            raise RollbackIntegrityError(
                f"RESTORATION_NOT_PERFORMED: No active artifact directory was supplied, so "
                f"rollback from '{current_version}' to '{target_version}' cannot write the "
                "verified artifacts anywhere. Refused instead of reporting success (REL-01-AC1)."
            )

        verified: dict[str, bytes] = {}
        for filename, expected_checksum in target_manifest.items():
            artifact_file = artifacts_dir / filename
            if not artifact_file.exists():
                raise RollbackIntegrityError(
                    f"ROLLBACK_ARTIFACT_MISSING: Artifact '{filename}' required for rollback to "
                    f"'{target_version}' was not found in '{artifacts_dir}' (REL-01-AC1)."
                )

            data = artifact_file.read_bytes()
            computed_checksum = hashlib.sha256(data).hexdigest()
            if computed_checksum != expected_checksum:
                raise RollbackIntegrityError(
                    f"ROLLBACK_CHECKSUM_MISMATCH: Artifact '{filename}' has invalid checksum "
                    f"'{computed_checksum}' (expected '{expected_checksum}'). "
                    "Rollback aborted fail-closed before any restore (REL-01-AC1)."
                )
            verified[filename] = data

        active_path = Path(active_dir)
        # Snapshot current active bytes so a partial restore can be undone. An
        # active file that does not exist yet is snapshotted as None so the undo
        # can remove it again.
        previous: dict[str, bytes | None] = {
            filename: (active_path / filename).read_bytes()
            if (active_path / filename).is_file()
            else None
            for filename in verified
        }

        try:
            active_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RollbackIntegrityError(
                f"ROLLBACK_RESTORE_FAILED: Could not create active directory '{active_path}' "
                f"({exc}); active state left untouched (REL-01-AC1)."
            ) from exc

        replaced: list[str] = []
        try:
            for filename, data in verified.items():
                destination = active_path / filename
                temp_file = active_path / f".rollback-{filename}.tmp"
                temp_file.write_bytes(data)
                os.replace(temp_file, destination)
                replaced.append(filename)
        except OSError as exc:
            for temp_name in (f".rollback-{name}.tmp" for name in verified):
                try:
                    (active_path / temp_name).unlink(missing_ok=True)
                except OSError:
                    pass
            self._undo_partial_restore(active_path, replaced, previous)
            raise RollbackIntegrityError(
                f"ROLLBACK_RESTORE_FAILED: Restoring '{target_version}' into '{active_path}' "
                f"failed ({exc}). {len(replaced)} restored file(s) were returned to their "
                "pre-rollback content (REL-01-AC1)."
            ) from exc

        for filename, expected_checksum in target_manifest.items():
            active_file = active_path / filename
            if not active_file.is_file():
                self._undo_partial_restore(active_path, list(verified), previous)
                raise RollbackIntegrityError(
                    f"ROLLBACK_RESTORE_FAILED: Artifact '{filename}' is absent from the active "
                    f"directory after restore; rollback to '{target_version}' was undone (REL-01-AC1)."
                )
            actual = hashlib.sha256(active_file.read_bytes()).hexdigest()
            if actual != expected_checksum:
                self._undo_partial_restore(active_path, list(verified), previous)
                raise RollbackIntegrityError(
                    f"ROLLBACK_RESTORE_FAILED: Post-restore checksum for '{filename}' is "
                    f"'{actual}' (expected '{expected_checksum}'); rollback to '{target_version}' "
                    "was undone (REL-01-AC1)."
                )

        return True

    @staticmethod
    def _reject_unsafe_manifest_key(filename: str, target_version: str) -> None:
        """Refuse a manifest key that could escape the artifacts/active dirs (REL-01-AC1).

        Keys are joined onto both directories for reading and restoring, so an
        absolute key or any ``..`` segment would read/write outside them. Such
        keys are refused fail-closed before any disk access. Both POSIX and
        Windows flavors are inspected so ``..\\evil`` cannot slip through on
        either platform.
        """
        candidates = (
            Path(filename).parts,
            PurePosixPath(filename).parts,
            PureWindowsPath(filename).parts,
        )
        if (
            not filename
            or not str(filename).strip()
            or Path(filename).is_absolute()
            or PurePosixPath(filename).is_absolute()
            or PureWindowsPath(filename).is_absolute()
            or any(part == ".." for parts in candidates for part in parts)
        ):
            raise RollbackIntegrityError(
                f"ROLLBACK_PATH_ESCAPE: Rollback target '{target_version}' declares "
                f"unsafe artifact key {filename!r}; keys must be relative names "
                "without '..' segments so restore stays inside the artifacts and "
                "active directories (REL-01-AC1)."
            )

    @staticmethod
    def _undo_partial_restore(
        active_path: Path,
        filenames: list[str],
        previous: dict[str, bytes | None],
    ) -> None:
        """Best-effort restore of pre-rollback bytes for ``filenames``.

        Uses plain writes and unlinks rather than ``os.replace`` so that recovery
        still works when the underlying replace primitive is the thing that failed.
        """
        for filename in filenames:
            destination = active_path / filename
            original = previous.get(filename)
            try:
                if original is None:
                    if destination.exists():
                        destination.unlink()
                else:
                    destination.write_bytes(original)
            except OSError:
                # Recovery is best-effort; the original failure is what gets reported.
                continue

    def evaluate_release_status(
        self,
        software_ready: bool,
        forward_days: int,
        forward_trades: int,
        min_forward_days: int = 90,
        min_forward_trades: int = 100,
    ) -> dict[str, str]:
        """Decouple software readiness from forward evaluation gates (REL-01-AC3)."""
        sw_status = "READY" if software_ready else "NOT_READY"

        if forward_days < min_forward_days or forward_trades < min_forward_trades:
            reason = (
                f"Pending forward qualification ({forward_days}/{min_forward_days} days, "
                f"{forward_trades}/{min_forward_trades} trades)"
            )
            return {
                "software_rc_status": sw_status,
                "champion_status": "PENDING_FORWARD_EVALUATION",
                "reason": reason,
            }

        return {
            "software_rc_status": sw_status,
            "champion_status": "QUALIFIED",
            "reason": "All release and champion forward gates satisfied",
        }
