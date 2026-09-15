"""Backtest replay outcome and canonical hash verification model (SIM-03)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict


class BacktestResult(BaseModel):
    """The canonical deterministic replay outcome for a strategy run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    candidate_id: str = "default_candidate"
    start_time: datetime
    end_time: datetime
    initial_cash: Decimal
    ending_cash: Decimal
    ending_equity: Decimal
    total_net_pnl: Decimal
    total_gross_pnl: Decimal
    total_fees_paid: Decimal
    fill_count: int
    transaction_count: int
    postings_hash: str
    status: str = "SUCCESS"
    execution_version: str = "legacy-unversioned"
    execution_assumptions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "candidate_id": self.candidate_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "initial_cash": str(self.initial_cash),
            "ending_cash": str(self.ending_cash),
            "ending_equity": str(self.ending_equity),
            "total_net_pnl": str(self.total_net_pnl),
            "total_gross_pnl": str(self.total_gross_pnl),
            "total_fees_paid": str(self.total_fees_paid),
            "fill_count": self.fill_count,
            "transaction_count": self.transaction_count,
            "postings_hash": self.postings_hash,
            "status": self.status,
            "execution_version": self.execution_version,
            "execution_assumptions": list(self.execution_assumptions),
        }

    def save_json(self, path: Path) -> None:
        """Atomically persist manifest to path using temp-file rename."""
        target = Path(path)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(target)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BacktestResult:
        return cls(
            run_id=data["run_id"],
            candidate_id=data.get("candidate_id", "default_candidate"),
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            initial_cash=Decimal(data["initial_cash"]),
            ending_cash=Decimal(data["ending_cash"]),
            ending_equity=Decimal(data["ending_equity"]),
            total_net_pnl=Decimal(data["total_net_pnl"]),
            total_gross_pnl=Decimal(data["total_gross_pnl"]),
            total_fees_paid=Decimal(data["total_fees_paid"]),
            fill_count=data["fill_count"],
            transaction_count=data["transaction_count"],
            postings_hash=data["postings_hash"],
            status=data.get("status", "SUCCESS"),
            execution_version=data.get("execution_version", "legacy-unversioned"),
            execution_assumptions=tuple(data.get("execution_assumptions", ())),
        )

    @classmethod
    def load_json(cls, path: Path) -> BacktestResult:
        raw = Path(path).read_text(encoding="utf-8")
        return cls.from_dict(json.loads(raw))
