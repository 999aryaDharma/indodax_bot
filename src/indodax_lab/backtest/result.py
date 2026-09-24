"""Backtest replay outcome and canonical hash verification model (SIM-03)."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

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
    market_input_hash: str | None = None
    cost_schedule_set_id: str | None = None
    cost_schedule_version: str | None = None
    risk_policy_id: str | None = None
    risk_policy_version: str | None = None
    strategy_ids: tuple[str, ...] = ()
    rejections: tuple[tuple[str, str], ...] = ()
    status: Literal["SUCCESS", "COMPLETED_WITH_REJECTIONS"] = "SUCCESS"
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
            "market_input_hash": self.market_input_hash,
            "cost_schedule_set_id": self.cost_schedule_set_id,
            "cost_schedule_version": self.cost_schedule_version,
            "risk_policy_id": self.risk_policy_id,
            "risk_policy_version": self.risk_policy_version,
            "strategy_ids": list(self.strategy_ids),
            "rejections": [list(rejection) for rejection in self.rejections],
            "status": self.status,
            "execution_version": self.execution_version,
            "execution_assumptions": list(self.execution_assumptions),
        }

    def save_json(self, path: Path) -> None:
        """Atomically persist manifest to path using temp-file rename."""
        target = Path(path)
        temp_path: Path | None = None
        try:
            fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
            temp_path = Path(temp_name)
            with os.fdopen(fd, "w", encoding="utf-8") as artifact:
                artifact.write(json.dumps(self.to_dict(), indent=2))
                artifact.flush()
                os.fsync(artifact.fileno())
            os.replace(temp_path, target)
            temp_path = None
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

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
            market_input_hash=data.get("market_input_hash"),
            cost_schedule_set_id=data.get("cost_schedule_set_id"),
            cost_schedule_version=data.get("cost_schedule_version"),
            risk_policy_id=data.get("risk_policy_id"),
            risk_policy_version=data.get("risk_policy_version"),
            strategy_ids=tuple(data.get("strategy_ids", ())),
            rejections=tuple(tuple(item) for item in data.get("rejections", ())),
            status=data.get("status", "SUCCESS"),
            execution_version=data.get("execution_version", "legacy-unversioned"),
            execution_assumptions=tuple(data.get("execution_assumptions", ())),
        )

    @classmethod
    def load_json(cls, path: Path) -> BacktestResult:
        raw = Path(path).read_text(encoding="utf-8")
        return cls.from_dict(json.loads(raw))
