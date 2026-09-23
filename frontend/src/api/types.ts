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

export type ProductionOverview = {
  mode: string | null;
  release_id: string | null;
  market_health: ServiceState;
  venue_health: ServiceState;
  reconciliation_status: ResourceStatus;
  unknown_orders_count: number | null;
  risk_status: "HALTED" | "UNKNOWN";
};
