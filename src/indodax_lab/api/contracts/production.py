"""Immutable Production read models; unavailable authority stays explicit."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.api.contracts.common import Provenance

ResourceStatus = Literal["AVAILABLE", "PARTIAL", "UNAVAILABLE", "UNKNOWN"]
Freshness = Literal["FRESH", "STALE", "UNKNOWN"]


class ReadModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ResourceEvidence(ReadModel):
    status: ResourceStatus
    source: str
    source_revision: str | None = None
    as_of: datetime | None = None
    source_updated_at: datetime | None = None
    freshness: Freshness = "UNKNOWN"
    reason: str | None = None


class ProductionModeView(ReadModel):
    evidence: ResourceEvidence
    effective_mode: str | None = None
    requested_mode: str | None = None


class PositionView(ReadModel):
    pair: str
    base_qty: Decimal
    cost_basis: Decimal


class BalanceView(ReadModel):
    currency: str
    available: Decimal = Field(ge=0, allow_inf_nan=False)
    hold: Decimal = Field(ge=0, allow_inf_nan=False)
    total: Decimal = Field(ge=0, allow_inf_nan=False)


class PositionsView(ReadModel):
    evidence: ResourceEvidence
    data: tuple[PositionView, ...] = ()
    financial_authority: Literal["AVAILABLE", "UNAVAILABLE"] = "UNAVAILABLE"


class PortfolioView(ReadModel):
    evidence: ResourceEvidence
    balances: tuple[BalanceView, ...] = ()
    quote_available: Decimal | None = None
    quote_hold: Decimal | None = None
    quote_currency: str | None = None
    equity: Decimal | None = None
    balance_authority: Literal["AVAILABLE", "UNAVAILABLE"] = "UNAVAILABLE"


class OrderView(ReadModel):
    internal_order_id: str
    venue_order_id: str | None = None
    pair: str
    side: str
    desired_qty: Decimal
    filled_qty: Decimal
    state: str


class OrdersView(ReadModel):
    evidence: ResourceEvidence
    data: tuple[OrderView, ...] = ()
    total: int | None = None


class FillsView(ReadModel):
    evidence: ResourceEvidence
    data: tuple[dict[str, object], ...] = ()


class ReconciliationView(ReadModel):
    evidence: ResourceEvidence
    healthy: bool | None = None
    mismatch_count: int | None = None


class RiskView(ReadModel):
    evidence: ResourceEvidence
    status: Literal["HALTED", "UNKNOWN"] = "UNKNOWN"
    kill_switch_active: bool | None = None
    utilization: Decimal | None = None
    drawdown: Decimal | None = None


class ReleaseView(ReadModel):
    evidence: ResourceEvidence
    status: Literal["AVAILABLE", "UNAVAILABLE"] = "UNAVAILABLE"
    release_id: str | None = None
    verified: bool | None = None


class AuditView(ReadModel):
    evidence: ResourceEvidence
    last_event: dict[str, object] | None = None


class ProductionOverview(ReadModel):
    mode: str | None = None
    venue_health: Literal["HEALTHY", "WARNING", "CRITICAL", "UNKNOWN"] = "UNKNOWN"
    market_health: Literal["HEALTHY", "WARNING", "CRITICAL", "UNKNOWN"] = "UNKNOWN"
    reconciliation_status: ResourceStatus = "UNAVAILABLE"
    unknown_orders_count: int | None = None
    risk_status: Literal["HALTED", "UNKNOWN"] = "UNKNOWN"
    release_id: str | None = None
    last_audit_event: dict[str, object] | None = None


class ProductionReadSnapshot(ReadModel):
    request_id: str
    as_of: datetime
    source_revision: str
    provenance: Provenance
    status: Literal["PARTIAL", "UNAVAILABLE"]
    overview: ProductionOverview
    mode: ProductionModeView
    portfolio: PortfolioView
    positions: PositionsView
    orders: OrdersView
    fills: FillsView
    reconciliation: ReconciliationView
    risk: RiskView
    release: ReleaseView
    audit: AuditView


__all__ = [
    "AuditView",
    "FillsView",
    "OrderView",
    "OrdersView",
    "PortfolioView",
    "PositionView",
    "PositionsView",
    "ProductionModeView",
    "ProductionOverview",
    "ProductionReadSnapshot",
    "ReconciliationView",
    "ReleaseView",
    "ResourceEvidence",
    "RiskView",
]
