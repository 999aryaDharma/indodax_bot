export type Provenance = { source: string; revision: string };

export type ApiEnvelope<T> = {
  request_id: string;
  as_of: string;
  source_revision: string;
  status: "AVAILABLE" | "PARTIAL" | "UNAVAILABLE" | string;
  data: T;
  provenance: Provenance;
};

export type ApiError = {
  code: string;
  message: string;
  retryable: boolean;
  details?: Record<string, unknown> | null;
};

export type ServiceState = "HEALTHY" | "WARNING" | "CRITICAL" | "UNKNOWN" | "UNAVAILABLE";

export type ProductionOverview = {
  execution_mode: string | null;
  release_id: string | null;
  market: ServiceState;
  venue: ServiceState;
  reconciliation: ServiceState;
  unknown_orders: number | null;
  risk: ServiceState;
};
