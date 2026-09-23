import type { ApiEnvelope, ApiError, ProductionOverview } from "./types";

const baseUrl = import.meta.env.VITE_CONTROL_PLANE_API_URL ?? "http://127.0.0.1:8000/api/v1";

export class ControlPlaneError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly retryable: boolean,
    readonly requestId: string | null,
  ) {
    super(message);
    this.name = "ControlPlaneError";
  }
}

export function overviewDataForDisplay(
  snapshot: ApiEnvelope<ProductionOverview>,
): ProductionOverview | undefined {
  return snapshot.status === "AVAILABLE" || snapshot.status === "PARTIAL"
    ? snapshot.data
    : undefined;
}

const serviceStates = new Set(["HEALTHY", "WARNING", "CRITICAL", "UNKNOWN", "UNAVAILABLE", "MISMATCH", "STALE"]);
const envelopeStatuses = new Set(["AVAILABLE", "PARTIAL", "UNAVAILABLE", "EMPTY"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function parseOverviewEnvelope(body: unknown): ApiEnvelope<ProductionOverview> {
  if (!isRecord(body) || !isRecord(body.provenance) || !isRecord(body.data)) {
    throw new ControlPlaneError("INVALID_RESPONSE", "Production API returned a malformed snapshot.", false, null);
  }
  const { data } = body;
  const timestampHasZone = typeof body.as_of === "string" && /(?:Z|[+-]\d{2}:\d{2})$/i.test(body.as_of);
  const valid = nonEmptyString(body.request_id)
    && timestampHasZone && Number.isFinite(Date.parse(body.as_of as string))
    && nonEmptyString(body.source_revision)
    && typeof body.status === "string" && envelopeStatuses.has(body.status)
    && nonEmptyString(body.provenance.source) && nonEmptyString(body.provenance.revision)
    && (data.execution_mode === null || typeof data.execution_mode === "string")
    && (data.release_id === null || typeof data.release_id === "string")
    && [data.market, data.venue, data.reconciliation, data.risk].every((value) => typeof value === "string" && serviceStates.has(value))
    && (data.unknown_orders === null || (Number.isSafeInteger(data.unknown_orders) && Number(data.unknown_orders) >= 0));
  if (!valid) {
    throw new ControlPlaneError("INVALID_RESPONSE", "Production API returned a malformed snapshot.", false, null);
  }
  return body as ApiEnvelope<ProductionOverview>;
}

function requestId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function getProductionOverview(signal?: AbortSignal): Promise<ApiEnvelope<ProductionOverview>> {
  const id = requestId();
  let response: Response;
  try {
    response = await fetch(`${baseUrl}/production/overview`, {
      method: "GET",
      headers: { Accept: "application/json", "X-Request-ID": id },
      credentials: "omit",
      cache: "no-store",
      signal,
    });
  } catch {
    throw new ControlPlaneError("API_UNAVAILABLE", "Control-plane API is unreachable.", true, id);
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = isRecord(body) && isRecord(body.error) ? body.error as ApiError : null;
    throw new ControlPlaneError(
      typeof error?.code === "string" ? error.code : "REQUEST_FAILED",
      typeof error?.message === "string" ? error.message : `Request failed (${response.status}).`,
      typeof error?.retryable === "boolean" ? error.retryable : response.status >= 500,
      id,
    );
  }
  try {
    return parseOverviewEnvelope(body);
  } catch (error) {
    if (error instanceof ControlPlaneError) {
      throw new ControlPlaneError(error.code, error.message, error.retryable, id);
    }
    throw new ControlPlaneError("INVALID_RESPONSE", "Production API returned a malformed snapshot.", false, id);
  }
}
