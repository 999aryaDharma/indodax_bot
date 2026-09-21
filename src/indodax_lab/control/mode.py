"""Execution mode definitions and autonomous trading constraints."""

from __future__ import annotations

import hashlib
import json
import logging
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


def validate_mode_transition(from_mode: ExecutionMode, to_mode: ExecutionMode) -> bool:
    """Validate whether an execution mode transition is structurally allowed."""
    if from_mode == to_mode:
        return True
    return to_mode in ALLOWED_MODE_TRANSITIONS.get(from_mode, set())


class DurableModeStore:
    """Thread-safe persistent store for runtime execution mode with chained journal."""

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
        self._mode = initial_mode or default_mode
        if self.path is not None and self.path.exists():
            self._load()
        elif initial_mode is not None:
            self._record_transition_locked(
                from_mode=ExecutionMode.DISABLED,
                to_mode=self._mode,
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
            "mode": self._mode.value,
            "updated_at": datetime.now(UTC).isoformat(),
            "journal": self._journal,
        }
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        text = self.path.read_text(encoding="utf-8").strip()
        if not text:
            return
        data = json.loads(text)
        loaded_mode = ExecutionMode(data["mode"])
        self._journal = list(data.get("journal", []))

        # Safe recovery restart: active/write modes on reboot must fall back to RECOVERY
        if self.safe_recovery_restart and loaded_mode in {
            ExecutionMode.AUTONOMOUS_LIMITED,
            ExecutionMode.MANUAL_APPROVAL,
            ExecutionMode.SHADOW,
        }:
            logger.warning(
                "DurableModeStore: Restarted while in active mode %s. Defaulting to RECOVERY.",
                loaded_mode.value,
            )
            self._mode = ExecutionMode.RECOVERY
            self._record_transition_locked(
                from_mode=loaded_mode,
                to_mode=ExecutionMode.RECOVERY,
                operator="system",
                reason="CRASH_RESTART_RECOVERY_FALLBACK",
                ts=datetime.now(UTC),
            )
            self._save()
        else:
            self._mode = loaded_mode

    def get_mode(self) -> ExecutionMode:
        with self._lock:
            return self._mode

    def get_journal(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(self._journal)

    def verify_journal_integrity(self) -> bool:
        with self._lock:
            expected_prev = _GENESIS_HASH
            for entry in self._journal:
                if entry["prev_hash"] != expected_prev:
                    return False
                calc_hash = self._compute_entry_hash(
                    prev_hash=entry["prev_hash"],
                    from_mode=entry["from_mode"],
                    to_mode=entry["to_mode"],
                    operator=entry["operator"],
                    reason=entry["reason"],
                    timestamp_utc=entry["timestamp_utc"],
                )
                if calc_hash != entry["entry_hash"]:
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
            if not validate_mode_transition(self._mode, new_mode):
                raise InvalidModeTransitionError(
                    f"ILLEGAL_MODE_TRANSITION:{self._mode.value}->{new_mode.value}"
                )
            now_utc = at or datetime.now(UTC)
            self._record_transition_locked(
                from_mode=self._mode,
                to_mode=new_mode,
                operator=operator,
                reason=reason,
                ts=now_utc,
            )
            self._mode = new_mode
            self._save()
            return self._mode


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
