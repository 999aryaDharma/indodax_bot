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
    const error = (body as { error?: ApiError } | null)?.error;
    throw new ControlPlaneError(
      error?.code ?? "REQUEST_FAILED",
      error?.message ?? `Request failed (${response.status}).`,
      error?.retryable ?? response.status >= 500,
      id,
    );
  }
  return body as ApiEnvelope<ProductionOverview>;
}
