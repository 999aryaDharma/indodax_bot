import { afterEach, describe, expect, it, vi } from "vitest";
import { ControlPlaneError, getProductionOverview } from "./client";
import type { ApiEnvelope, ProductionOverview } from "./types";

const overview: ProductionOverview = {
  execution_mode: "SHADOW",
  release_id: null,
  market: "HEALTHY",
  venue: "HEALTHY",
  reconciliation: "HEALTHY",
  unknown_orders: 0,
  risk: "HEALTHY",
};

afterEach(() => vi.unstubAllGlobals());

describe("Production overview client", () => {
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
      data: { ...overview, execution_mode: null, release_id: null, market: "UNAVAILABLE", venue: "UNAVAILABLE", reconciliation: "UNAVAILABLE", unknown_orders: null, risk: "UNAVAILABLE" },
      provenance: { source: "production-main", revision: "unavailable" },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(response), { status: 200 })));

    await expect(getProductionOverview()).resolves.toMatchObject({ status: "UNAVAILABLE", data: { unknown_orders: null } });
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
});
