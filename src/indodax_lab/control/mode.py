"""Execution mode definitions and autonomous trading constraints (PM-03, FR-23)."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger("mode_store")

_GENESIS_HASH = "0" * 64


class ExecutionMode(StrEnum):
    """Institutional execution operating modes.

    Progression path:
    DISABLED -> RECOVERY -> READ_ONLY -> SHADOW -> MANUAL_APPROVAL -> AUTONOMOUS_LIMITED
    Any mode -> HALTED
    HALTED -> RECOVERY -> READ_ONLY
    """

    DISABLED = "DISABLED"
    RECOVERY = "RECOVERY"
    READ_ONLY = "READ_ONLY"
    SHADOW = "SHADOW"
    MANUAL_APPROVAL = "MANUAL_APPROVAL"
    AUTONOMOUS_LIMITED = "AUTONOMOUS_LIMITED"
    HALTED = "HALTED"

    @property
    def can_read_market(self) -> bool:
        return self not in {ExecutionMode.DISABLED, ExecutionMode.HALTED}

    @property
    def can_reconcile(self) -> bool:
        return self != ExecutionMode.DISABLED

    @property
    def can_write_venue(self) -> bool:
        return self in {ExecutionMode.MANUAL_APPROVAL, ExecutionMode.AUTONOMOUS_LIMITED}

    @property
    def is_shadow(self) -> bool:
        return self == ExecutionMode.SHADOW


ALLOWED_MODE_TRANSITIONS: dict[ExecutionMode, set[ExecutionMode]] = {
    ExecutionMode.DISABLED: {
        ExecutionMode.RECOVERY,
        ExecutionMode.READ_ONLY,
        ExecutionMode.HALTED,
    },
    ExecutionMode.RECOVERY: {
        ExecutionMode.READ_ONLY,
        ExecutionMode.HALTED,
        ExecutionMode.DISABLED,
    },
    ExecutionMode.READ_ONLY: {
        ExecutionMode.SHADOW,
        ExecutionMode.RECOVERY,
        ExecutionMode.HALTED,
        ExecutionMode.DISABLED,
    },
    ExecutionMode.SHADOW: {
        ExecutionMode.MANUAL_APPROVAL,
        ExecutionMode.READ_ONLY,
        ExecutionMode.HALTED,
        ExecutionMode.DISABLED,
    },
    ExecutionMode.MANUAL_APPROVAL: {
        ExecutionMode.AUTONOMOUS_LIMITED,
        ExecutionMode.SHADOW,
        ExecutionMode.READ_ONLY,
        ExecutionMode.HALTED,
        ExecutionMode.DISABLED,
    },
    ExecutionMode.AUTONOMOUS_LIMITED: {
        ExecutionMode.MANUAL_APPROVAL,
        ExecutionMode.SHADOW,
        ExecutionMode.READ_ONLY,
        ExecutionMode.HALTED,
        ExecutionMode.DISABLED,
    },
    ExecutionMode.HALTED: {
        ExecutionMode.RECOVERY,
        ExecutionMode.DISABLED,
    },
}


class InvalidModeTransitionError(ValueError):
    """Raised when an illegal execution mode transition is attempted."""


class CorruptModeJournalError(ValueError):
    """Raised when the mode store journal fails hash chain or integrity checks."""


def validate_mode_transition(from_mode: ExecutionMode, to_mode: ExecutionMode) -> bool:
    """Validate whether an execution mode transition is structurally allowed."""
    if from_mode == to_mode:
        return True
    return to_mode in ALLOWED_MODE_TRANSITIONS.get(from_mode, set())


class DurableModeStore:
    """Thread-safe persistent store for runtime execution mode with chained journal.

    PM-03 Invariants:
    - Every boot/restart initializes effective mode to RECOVERY.
    - Requested mode is stored separately.
    - Persistence failure rolls back in-memory state; writes remain disabled.
    - Tampered or corrupt journal strictly rejects transitions.
    """

    def __init__(
        self,
        path: Path | None = None,
        default_mode: ExecutionMode = ExecutionMode.RECOVERY,
        initial_mode: ExecutionMode | None = None,
        safe_recovery_restart: bool = True,
    ) -> None:
        self.path = Path(path) if path is not None else None
        self._lock = RLock()
        self.safe_recovery_restart = safe_recovery_restart
        self._journal: list[dict[str, Any]] = []
        self._effective_mode = ExecutionMode.RECOVERY
        self._requested_mode = initial_mode or default_mode
        self._mode = self._effective_mode

        if self.path is not None and self.path.exists():
            self._load()
        elif initial_mode is not None:
            self._effective_mode = initial_mode
            self._requested_mode = initial_mode
            self._mode = initial_mode
            self._record_transition_locked(
                from_mode=ExecutionMode.DISABLED,
                to_mode=self._effective_mode,
                operator="system",
                reason="INITIAL_BOOT",
                ts=datetime.now(UTC),
            )
            self._save()

    @staticmethod
    def _compute_entry_hash(
        prev_hash: str,
        from_mode: str,
        to_mode: str,
        operator: str,
        reason: str,
        timestamp_utc: str,
    ) -> str:
        payload = f"{prev_hash}|{from_mode}|{to_mode}|{operator}|{reason}|{timestamp_utc}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _record_transition_locked(
        self,
        from_mode: ExecutionMode,
        to_mode: ExecutionMode,
        operator: str,
        reason: str,
        ts: datetime,
    ) -> None:
        prev_hash = self._journal[-1]["entry_hash"] if self._journal else _GENESIS_HASH
        ts_utc = ts.astimezone(UTC).isoformat()
        entry_hash = self._compute_entry_hash(
            prev_hash=prev_hash,
            from_mode=from_mode.value,
            to_mode=to_mode.value,
            operator=operator,
            reason=reason,
            timestamp_utc=ts_utc,
        )
        self._journal.append(
            {
                "sequence": len(self._journal) + 1,
                "from_mode": from_mode.value,
                "to_mode": to_mode.value,
                "operator": operator,
                "reason": reason,
                "timestamp_utc": ts_utc,
                "prev_hash": prev_hash,
                "entry_hash": entry_hash,
            }
        )

    def _save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        payload = {
            "effective_mode": self._effective_mode.value,
            "requested_mode": self._requested_mode.value,
            "mode": self._effective_mode.value,
            "updated_at": datetime.now(UTC).isoformat(),
            "journal": self._journal,
        }
        try:
            temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temp_path.replace(self.path)
        except Exception as exc:
            raise RuntimeError(f"MODE_PERSISTENCE_FAILED: {exc}") from exc

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        text = self.path.read_text(encoding="utf-8").strip()
        if not text:
            return
        data = json.loads(text)
        self._journal = list(data.get("journal", []))

        raw_requested = data.get("requested_mode") or data.get("mode") or "DISABLED"
        try:
            self._requested_mode = ExecutionMode(raw_requested)
        except Exception:
            self._requested_mode = ExecutionMode.DISABLED

        # Invariant (PM-03-AC0): All persisted modes restart into RECOVERY
        self._effective_mode = ExecutionMode.RECOVERY
        self._mode = ExecutionMode.RECOVERY

        # Check journal integrity upon load
        if not self.verify_journal_integrity():
            self._journal_corrupt = True
            return

        if self._requested_mode != ExecutionMode.RECOVERY:
            self._record_transition_locked(
                from_mode=self._requested_mode,
                to_mode=ExecutionMode.RECOVERY,
                operator="system",
                reason="BOOT_RESTART_RECOVERY_ENFORCED",
                ts=datetime.now(UTC),
            )
            self._save()

    def get_mode(self) -> ExecutionMode:
        with self._lock:
            return self._effective_mode

    def get_effective_mode(self) -> ExecutionMode:
        with self._lock:
            return self._effective_mode

    def get_requested_mode(self) -> ExecutionMode:
        with self._lock:
            return self._requested_mode

    def get_journal(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(self._journal)

    def verify_journal_integrity(self) -> bool:
        with self._lock:
            if getattr(self, "_journal_corrupt", False):
                return False
            expected_prev = _GENESIS_HASH
            for entry in self._journal:
                if entry.get("prev_hash") != expected_prev:
                    return False
                calc_hash = self._compute_entry_hash(
                    prev_hash=entry["prev_hash"],
                    from_mode=entry["from_mode"],
                    to_mode=entry["to_mode"],
                    operator=entry["operator"],
                    reason=entry["reason"],
                    timestamp_utc=entry["timestamp_utc"],
                )
                if calc_hash != entry.get("entry_hash"):
                    return False
                expected_prev = entry["entry_hash"]
            return True

    def transition_to(
        self,
        new_mode: ExecutionMode,
        reason: str = "",
        operator: str = "system",
        at: datetime | None = None,
    ) -> ExecutionMode:
        with self._lock:
            if getattr(self, "_journal_corrupt", False) or not self.verify_journal_integrity():
                raise CorruptModeJournalError("CORRUPT_MODE_JOURNAL")

            if not validate_mode_transition(self._effective_mode, new_mode):
                raise InvalidModeTransitionError(
                    f"ILLEGAL_MODE_TRANSITION:{self._effective_mode.value}->{new_mode.value}"
                )
            now_utc = at or datetime.now(UTC)

            # Store prior state for transactional rollback if persistence fails (PM-03-AC2)
            prior_effective = self._effective_mode
            prior_requested = self._requested_mode
            prior_journal_len = len(self._journal)

            self._record_transition_locked(
                from_mode=self._effective_mode,
                to_mode=new_mode,
                operator=operator,
                reason=reason,
                ts=now_utc,
            )
            self._effective_mode = new_mode
            self._requested_mode = new_mode
            self._mode = new_mode

            try:
                self._save()
            except Exception as exc:
                # Roll back in-memory mutation so writes remain disabled
                self._effective_mode = prior_effective
                self._requested_mode = prior_requested
                self._mode = prior_effective
                del self._journal[prior_journal_len:]
                if not isinstance(exc, RuntimeError) or "MODE_PERSISTENCE_FAILED" not in str(exc):
                    raise RuntimeError(f"MODE_PERSISTENCE_FAILED: {exc}") from exc
                raise

            return self._effective_mode


class AutonomousLimits(BaseModel):
    """Hard capital, risk, and asset boundaries for AUTONOMOUS_LIMITED mode."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_single_order_notional: Decimal = Field(default=Decimal("500000"))  # 500,000 IDR
    max_daily_loss_notional: Decimal = Field(default=Decimal("1000000"))  # 1,000,000 IDR
    allowed_pairs: tuple[str, ...] = Field(default=("btc_idr",))

    @field_validator("max_single_order_notional", "max_daily_loss_notional", mode="before")
    @classmethod
    def parse_positive_decimal(cls, value: Any) -> Decimal:
        dec = Decimal(str(value))
        if not dec.is_finite() or dec <= 0:
            raise ValueError("POSITIVE_DECIMAL_REQUIRED")
        return dec

    @field_validator("allowed_pairs", mode="after")
    @classmethod
    def normalize_pairs(cls, pairs: tuple[str, ...]) -> tuple[str, ...]:
        if not pairs:
            raise ValueError("ALLOWED_PAIRS_REQUIRED")
        return tuple(p.strip().lower() for p in pairs)


@dataclass(frozen=True)
class RecoveryReport:
    """Normative recovery report contract for PM-03."""

    namespace: str
    effective_mode: str
    requested_mode: str
    reloaded_revision: int
    feed_cursor: str | None
    journal_integrity_ok: bool
    halt_reasons: list[str]
    effective_state: str
    permitted_next_actions: list[str]
    status: str


class RecoveryService:
    """Institutional recovery coordinator verifying boot state across stores."""

    def __init__(
        self,
        mode_store: DurableModeStore,
        risk_engine: Any | None = None,
        state_store: Any | None = None,
    ) -> None:
        self.mode_store = mode_store
        self.risk_engine = risk_engine
        self.state_store = state_store

    def restore(self, namespace: str = "prod_paper") -> RecoveryReport:
        effective_mode = self.mode_store.get_effective_mode()
        requested_mode = self.mode_store.get_requested_mode()

        halt_reasons: list[str] = []

        # 1. Verify mode journal integrity
        journal_ok = self.mode_store.verify_journal_integrity()
        if not journal_ok:
            halt_reasons.append("CORRUPT_MODE_JOURNAL")

        # 2. Verify risk engine integrity
        if self.risk_engine is not None:
            if getattr(self.risk_engine, "is_kill_switch_active", False):
                halt_reasons.append("KILL_SWITCH_ACTIVE")
            if hasattr(self.risk_engine, "verify_risk_state_integrity"):
                if not self.risk_engine.verify_risk_state_integrity():
                    halt_reasons.append("CORRUPT_OR_MISSING_RISK_STATE")

        # 3. Verify execution state store
        reloaded_revision = 0
        feed_cursor = None
        if self.state_store is not None:
            try:
                snapshot = self.state_store.restore()
                reloaded_revision = snapshot.revision
                feed_cursor = snapshot.feed_cursor
                if snapshot.halted:
                    halt_reasons.append("EXECUTION_STATE_HALTED")
            except Exception as exc:
                halt_reasons.append(f"EXECUTION_STATE_RESTORE_FAILED:{exc}")

        effective_state = "HALTED" if halt_reasons else effective_mode.value
        permitted_actions = (
            ["AUDIT", "INSPECT_JOURNAL", "RECOVER"]
            if halt_reasons
            else ["AUDIT", "RECONCILE", "TRANSITION_TO_READ_ONLY"]
        )

        return RecoveryReport(
            namespace=namespace,
            effective_mode=effective_mode.value,
            requested_mode=requested_mode.value,
            reloaded_revision=reloaded_revision,
            feed_cursor=feed_cursor,
            journal_integrity_ok=journal_ok,
            halt_reasons=halt_reasons,
            effective_state=effective_state,
            permitted_next_actions=permitted_actions,
            status="RECOVERED" if not halt_reasons else "HALTED",
        )
