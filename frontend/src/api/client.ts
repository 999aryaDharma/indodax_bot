import type {
  ApiEnvelope, ApiError, AuditView, OrdersView, PortfolioView, PositionsView,
  ProductionOverview, ReconciliationView, ReleaseView, ResourceEvidence, RiskView,
} from "./types";

const baseUrl = "/api/v1";

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

const serviceStates = new Set(["HEALTHY", "WARNING", "CRITICAL", "UNKNOWN"]);
const resourceStatuses = new Set(["AVAILABLE", "PARTIAL", "UNAVAILABLE", "UNKNOWN"]);
const envelopeStatuses = new Set(["AVAILABLE", "PARTIAL", "UNAVAILABLE", "EMPTY"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isDecimal(value: unknown): value is string {
  return typeof value === "string" && /^-?\d+(?:\.\d+)?$/.test(value);
}

function isNullableDecimal(value: unknown): value is string | null {
  return value === null || isDecimal(value);
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value));
}

function isEvidence(value: unknown): value is ResourceEvidence {
  return isRecord(value)
    && typeof value.status === "string" && resourceStatuses.has(value.status)
    && nonEmptyString(value.source)
    && isNullableString(value.source_revision)
    && (value.as_of === null || isTimestamp(value.as_of))
    && (value.source_updated_at === null || isTimestamp(value.source_updated_at))
    && ["FRESH", "STALE", "UNKNOWN"].includes(String(value.freshness))
    && isNullableString(value.reason);
}

function isOverview(value: unknown): value is ProductionOverview {
  return isRecord(value)
    && (value.mode === null || typeof value.mode === "string")
    && (value.release_id === null || typeof value.release_id === "string")
    && [value.market_health, value.venue_health].every((state) => typeof state === "string" && serviceStates.has(state))
    && typeof value.reconciliation_status === "string" && resourceStatuses.has(value.reconciliation_status)
    && (value.unknown_orders_count === null || (Number.isSafeInteger(value.unknown_orders_count) && Number(value.unknown_orders_count) >= 0))
    && (value.risk_status === "HALTED" || value.risk_status === "UNKNOWN");
}

function isPortfolio(value: unknown): value is PortfolioView {
  return isRecord(value) && isEvidence(value.evidence)
    && Array.isArray(value.balances) && value.balances.every((balance) => isRecord(balance)
      && nonEmptyString(balance.currency) && isDecimal(balance.available)
      && isDecimal(balance.hold) && isDecimal(balance.total))
    && isNullableDecimal(value.quote_available) && isNullableDecimal(value.quote_hold)
    && isNullableString(value.quote_currency) && isNullableDecimal(value.equity)
    && ["AVAILABLE", "UNAVAILABLE"].includes(String(value.balance_authority));
}

function isPositions(value: unknown): value is PositionsView {
  return isRecord(value) && isEvidence(value.evidence) && Array.isArray(value.data)
    && value.data.every((position) => isRecord(position) && nonEmptyString(position.pair)
      && isDecimal(position.base_qty) && isDecimal(position.cost_basis))
    && ["AVAILABLE", "UNAVAILABLE"].includes(String(value.financial_authority));
}

function isOrders(value: unknown): value is OrdersView {
  return isRecord(value) && isEvidence(value.evidence) && Array.isArray(value.data)
    && value.data.every((order) => isRecord(order) && nonEmptyString(order.internal_order_id)
      && isNullableString(order.venue_order_id) && nonEmptyString(order.pair)
      && nonEmptyString(order.side) && isDecimal(order.desired_qty)
      && isDecimal(order.filled_qty) && nonEmptyString(order.state))
    && (value.total === null || (Number.isSafeInteger(value.total) && Number(value.total) >= 0))
    && (value.offset === undefined || (Number.isSafeInteger(value.offset) && Number(value.offset) >= 0))
    && (value.limit === undefined || (Number.isSafeInteger(value.limit) && Number(value.limit) > 0));
}

function isReconciliation(value: unknown): value is ReconciliationView {
  return isRecord(value) && isEvidence(value.evidence)
    && (typeof value.healthy === "boolean" || value.healthy === null)
    && (value.mismatch_count === null || (Number.isSafeInteger(value.mismatch_count) && Number(value.mismatch_count) >= 0));
}

function isRisk(value: unknown): value is RiskView {
  return isRecord(value) && isEvidence(value.evidence)
    && (value.status === "HALTED" || value.status === "UNKNOWN")
    && (typeof value.kill_switch_active === "boolean" || value.kill_switch_active === null)
    && isNullableDecimal(value.utilization) && isNullableDecimal(value.drawdown);
}

function isRelease(value: unknown): value is ReleaseView {
  return isRecord(value) && isEvidence(value.evidence)
    && ["AVAILABLE", "UNAVAILABLE"].includes(String(value.status))
    && isNullableString(value.release_id)
    && (typeof value.verified === "boolean" || value.verified === null);
}

function isAudit(value: unknown): value is AuditView {
  return isRecord(value) && isEvidence(value.evidence)
    && (value.last_event === null || isRecord(value.last_event));
}

function parseEnvelope<T>(body: unknown, isData: (value: unknown) => value is T): ApiEnvelope<T> {
  if (!isRecord(body) || !isRecord(body.provenance) || !isData(body.data)
    || !nonEmptyString(body.request_id) || !isTimestamp(body.as_of)
    || !nonEmptyString(body.source_revision)
    || typeof body.status !== "string" || !envelopeStatuses.has(body.status)
    || !nonEmptyString(body.provenance.source) || !nonEmptyString(body.provenance.revision)) {
    throw new ControlPlaneError("INVALID_RESPONSE", "Production API returned a malformed read model.", false, null);
  }
  return body as ApiEnvelope<T>;
}

async function getEnvelope<T>(
  path: string,
  isData: (value: unknown) => value is T,
  signal?: AbortSignal,
): Promise<ApiEnvelope<T>> {
  const id = globalThis.crypto?.randomUUID?.() ?? `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      method: "GET", headers: { Accept: "application/json", "X-Request-ID": id },
      credentials: "omit", cache: "no-store", signal,
    });
  } catch {
    throw new ControlPlaneError("API_UNAVAILABLE", "Control-plane API is unreachable.", true, id);
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = isRecord(body)
      ? (isRecord(body.error) ? body.error : isRecord(body.detail) ? body.detail : null) as ApiError | null
      : null;
    throw new ControlPlaneError(
      typeof error?.code === "string" ? error.code : "REQUEST_FAILED",
      typeof error?.message === "string" ? error.message : `Request failed (${response.status}).`,
      typeof error?.retryable === "boolean" ? error.retryable : response.status >= 500,
      id,
    );
  }
  try {
    return parseEnvelope(body, isData);
  } catch (error) {
    if (error instanceof ControlPlaneError) {
      throw new ControlPlaneError(error.code, error.message, error.retryable, id);
    }
    throw new ControlPlaneError("INVALID_RESPONSE", "Production API returned a malformed read model.", false, id);
  }
}

export function overviewDataForDisplay(snapshot: ApiEnvelope<ProductionOverview>): ProductionOverview | undefined {
  return snapshot.status === "AVAILABLE" || snapshot.status === "PARTIAL" ? snapshot.data : undefined;
}

export const getProductionOverview = (signal?: AbortSignal) => getEnvelope("/production/overview", isOverview, signal);
export const getProductionPortfolio = (signal?: AbortSignal) => getEnvelope("/production/portfolio", isPortfolio, signal);
export const getProductionPositions = (signal?: AbortSignal) => getEnvelope("/production/positions", isPositions, signal);
export const getProductionReconciliation = (signal?: AbortSignal) => getEnvelope("/production/reconciliation", isReconciliation, signal);
export const getProductionRisk = (signal?: AbortSignal) => getEnvelope("/production/risk", isRisk, signal);
export const getProductionRelease = (signal?: AbortSignal) => getEnvelope("/production/release", isRelease, signal);
export const getProductionAudit = (signal?: AbortSignal) => getEnvelope("/production/audit", isAudit, signal);
export const getProductionOrdersPage = (offset = 0, limit = 50, signal?: AbortSignal) =>
  getEnvelope(`/production/orders/page?offset=${offset}&limit=${limit}`, isOrders, signal);
