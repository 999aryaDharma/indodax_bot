export type Provenance = { source: string; revision: string };

export type ApiEnvelope<T> = {
  request_id: string;
  as_of: string;
  source_revision: string;
  status: "AVAILABLE" | "PARTIAL" | "UNAVAILABLE" | "EMPTY";
  data: T;
  provenance: Provenance;
};

export type ApiError = {
  code: string;
  message: string;
  retryable: boolean;
  details?: Record<string, unknown> | null;
};

export type ServiceState = "HEALTHY" | "WARNING" | "CRITICAL" | "UNKNOWN";
export type ResourceStatus = "AVAILABLE" | "PARTIAL" | "UNAVAILABLE" | "UNKNOWN";
export type Freshness = "FRESH" | "STALE" | "UNKNOWN";

export type ResourceEvidence = {
  status: ResourceStatus;
  source: string;
  source_revision: string | null;
  as_of: string | null;
  source_updated_at: string | null;
  freshness: Freshness;
  reason: string | null;
};

export type ProductionOverview = {
  mode: string | null;
  release_id: string | null;
  market_health: ServiceState;
  venue_health: ServiceState;
  reconciliation_status: ResourceStatus;
  unknown_orders_count: number | null;
  risk_status: "HALTED" | "UNKNOWN";
};

export type BalanceView = {
  currency: string;
  available: string;
  hold: string;
  total: string;
};

export type PortfolioView = {
  evidence: ResourceEvidence;
  balances: BalanceView[];
  quote_available: string | null;
  quote_hold: string | null;
  quote_currency: string | null;
  equity: string | null;
  balance_authority: "AVAILABLE" | "UNAVAILABLE";
};

export type PositionView = { pair: string; base_qty: string; cost_basis: string };
export type PositionsView = {
  evidence: ResourceEvidence;
  data: PositionView[];
  financial_authority: "AVAILABLE" | "UNAVAILABLE";
};

export type OrderView = {
  internal_order_id: string;
  venue_order_id: string | null;
  pair: string;
  side: string;
  desired_qty: string;
  filled_qty: string;
  state: string;
};
export type OrdersView = {
  evidence: ResourceEvidence;
  data: OrderView[];
  total: number | null;
  offset?: number;
  limit?: number;
};

export type ReconciliationView = { evidence: ResourceEvidence; healthy: boolean | null; mismatch_count: number | null };
export type RiskView = {
  evidence: ResourceEvidence;
  status: "HALTED" | "UNKNOWN";
  kill_switch_active: boolean | null;
  utilization: string | null;
  drawdown: string | null;
};
export type ReleaseView = {
  evidence: ResourceEvidence;
  status: "AVAILABLE" | "UNAVAILABLE";
  release_id: string | null;
  verified: boolean | null;
};
export type AuditView = { evidence: ResourceEvidence; last_event: Record<string, unknown> | null };
