import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ApiEnvelope, OrdersView, ReconciliationView, ResourceEvidence } from "../../api/types";
import { OrdersPage, ReconciliationPage } from "./pages";

const evidence: ResourceEvidence = { status: "AVAILABLE", source: "production-main", source_revision: "r1", as_of: "2026-09-24T12:00:00Z", source_updated_at: "2026-09-24T12:00:00Z", freshness: "FRESH", reason: null };
const envelope = <T,>(data: T): ApiEnvelope<T> => ({ request_id: "req-1", as_of: evidence.as_of!, source_revision: "r1", status: "AVAILABLE", data, provenance: { source: "production-main", revision: "r1" } });

describe("Production read pages", () => {
  it("labels unresolved Orders venue truth and displays source provenance", () => {
    const response = envelope<OrdersView>({ evidence, total: 1, offset: 0, limit: 50, data: [{ internal_order_id: "oms-1", venue_order_id: null, pair: "btc_idr", side: "buy", desired_qty: "0.25", filled_qty: "0", state: "UNKNOWN" }] });
    const html = renderToStaticMarkup(<OrdersPage response={response} state="ready" message={null} now={new Date("2026-09-24T12:00:05Z")} reload={() => undefined} loadMore={() => undefined} loadingMore={false} />);
    expect(html).toContain("UNKNOWN · venue truth unresolved");
    expect(html).toContain("production-main");
    expect(html).toContain("0.25");
  });

  it("makes a mismatch explicit without adding repair controls", () => {
    const response = envelope<ReconciliationView>({ evidence, healthy: false, mismatch_count: 2 });
    const html = renderToStaticMarkup(<ReconciliationPage response={response} state="ready" message={null} now={new Date("2026-09-24T12:00:05Z")} reload={() => undefined} />);
    expect(html).toContain("RECONCILIATION MISMATCH");
    expect(html).not.toContain("Fix balance");
    expect(html).toContain("2");
  });
});
