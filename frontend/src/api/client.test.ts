import { afterEach, describe, expect, it, vi } from "vitest";
import { ControlPlaneError, getProductionOverview, overviewDataForDisplay } from "./client";
import type { ApiEnvelope, ProductionOverview } from "./types";

const overview: ProductionOverview = {
  mode: "SHADOW",
  release_id: null,
  market_health: "HEALTHY",
  venue_health: "HEALTHY",
  reconciliation_status: "AVAILABLE",
  unknown_orders_count: 0,
  risk_status: "UNKNOWN",
};

afterEach(() => vi.unstubAllGlobals());

describe("Production overview client", () => {
  it("does not display operational values from EMPTY snapshots", () => {
    const empty: ApiEnvelope<ProductionOverview> = {
      request_id: "request-empty",
      as_of: "2026-09-23T00:00:00Z",
      source_revision: "empty-r1",
      status: "EMPTY",
      data: overview,
      provenance: { source: "production-main", revision: "empty-r1" },
    };
    expect(overviewDataForDisplay(empty)).toBeUndefined();
  });

  it("sends a request ID and preserves backend string values", async () => {
    const data = { ...overview, equity: "102.43000000" };
    const response: ApiEnvelope<typeof data> = {
      request_id: "server-request",
      as_of: "2026-09-23T00:00:00Z",
      source_revision: "ledger-r17",
      status: "AVAILABLE",
      data,
      provenance: { source: "production-main", revision: "r17" },
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(response), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await getProductionOverview();

    expect((result.data as ProductionOverview & { equity: string }).equity).toBe("102.43000000");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/production/overview",
      expect.objectContaining({
        method: "GET",
        credentials: "omit",
        cache: "no-store",
        headers: expect.objectContaining({ "X-Request-ID": expect.any(String) }),
      }),
    );
  });

  it("preserves explicit unavailable snapshots", async () => {
    const response: ApiEnvelope<ProductionOverview> = {
      request_id: "request-2",
      as_of: "2026-09-23T00:00:00Z",
      source_revision: "unavailable",
      status: "UNAVAILABLE",
      data: { ...overview, mode: null, release_id: null, market_health: "UNKNOWN", venue_health: "UNKNOWN", reconciliation_status: "UNAVAILABLE", unknown_orders_count: null, risk_status: "UNKNOWN" },
      provenance: { source: "production-main", revision: "unavailable" },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(response), { status: 200 })));

    await expect(getProductionOverview()).resolves.toMatchObject({ status: "UNAVAILABLE", data: { unknown_orders_count: null } });
  });

  it("rejects malformed successful snapshots and accepts explicit empty state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "READY" }), { status: 200 })));
    await expect(getProductionOverview()).rejects.toMatchObject({ code: "INVALID_RESPONSE", retryable: false });

    const empty: ApiEnvelope<ProductionOverview> = {
      request_id: "request-empty",
      as_of: "2026-09-23T00:00:00Z",
      source_revision: "empty-r1",
      status: "EMPTY",
      data: { ...overview, mode: null, release_id: null, market_health: "UNKNOWN", venue_health: "UNKNOWN", reconciliation_status: "UNAVAILABLE", unknown_orders_count: null, risk_status: "UNKNOWN" },
      provenance: { source: "production-main", revision: "empty-r1" },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...empty, as_of: "2026-09-23T00:00:00" }), { status: 200 })));
    await expect(getProductionOverview()).rejects.toMatchObject({ code: "INVALID_RESPONSE", retryable: false });

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(empty), { status: 200 })));
    await expect(getProductionOverview()).resolves.toMatchObject({ status: "EMPTY" });
  });

  it("keeps API errors stable and marks network failures retryable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: {
      code: "CAPABILITY_REQUIRED", message: "Read capability required", retryable: false,
    } }), { status: 403 })));
    await expect(getProductionOverview()).rejects.toMatchObject({ code: "CAPABILITY_REQUIRED", retryable: false });

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    const request = getProductionOverview();
    await expect(request).rejects.toBeInstanceOf(ControlPlaneError);
    await expect(request).rejects.toMatchObject({ code: "API_UNAVAILABLE", retryable: true });
  });

  it("preserves the FastAPI capability denial detail shape", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: {
      code: "PRODUCTION_READ_FORBIDDEN", request_id: "request-denied",
    } }), { status: 403 })));
    await expect(getProductionOverview()).rejects.toMatchObject({
      code: "PRODUCTION_READ_FORBIDDEN", retryable: false, requestId: expect.any(String),
    });
  });
});
