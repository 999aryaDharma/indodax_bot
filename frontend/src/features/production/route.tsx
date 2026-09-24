import { useCallback, useEffect, useRef, useState } from "react";
import { ControlPlaneError, getProductionAudit, getProductionOrdersPage, getProductionPortfolio, getProductionPositions, getProductionReconciliation, getProductionRelease, getProductionRisk } from "../../api/client";
import type { ApiEnvelope, AuditView, OrdersView, PortfolioView, PositionsView, ReconciliationView, ReleaseView, RiskView } from "../../api/types";
import { capabilityState } from "../../app/context";
import { AuditPage, OrdersPage, PortfolioPage, PositionsPage, ReconciliationPage, ReleasesPage, RiskPage } from "./pages";
import type { ReadState } from "./pages";

type Data = PortfolioView | PositionsView | OrdersView | ReconciliationView | RiskView | ReleaseView | AuditView;
type Envelope = ApiEnvelope<Data>;

export function ProductionReadPage({ label, now }: { label: string; now: Date }) {
  const [response, setResponse] = useState<Envelope | null>(null);
  const [state, setState] = useState<ReadState>("loading");
  const [message, setMessage] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const generation = useRef(0);

  const load = useCallback(async (signal?: AbortSignal) => {
    const currentGeneration = ++generation.current;
    setResponse(null); setMessage(null); setLoadingMore(false); setState("loading");
    try {
      const result = label === "Portfolio" ? await getProductionPortfolio(signal)
        : label === "Positions" ? await getProductionPositions(signal)
          : label === "Orders" ? await getProductionOrdersPage(0, 50, signal)
            : label === "Reconciliation" ? await getProductionReconciliation(signal)
              : label === "Risk" ? await getProductionRisk(signal)
                : label === "Releases" ? await getProductionRelease(signal) : await getProductionAudit(signal);
      if (signal?.aborted || currentGeneration !== generation.current) return;
      setResponse(result as Envelope);
      setState(result.status === "UNAVAILABLE" ? "unavailable" : result.status === "EMPTY" ? "empty" : "ready");
    } catch (error) {
      if (signal?.aborted || currentGeneration !== generation.current) return;
      const code = error instanceof ControlPlaneError ? error.code : null;
      setState(capabilityState(code) === "denied" ? "denied" : "error");
      setMessage(error instanceof ControlPlaneError ? `${error.message} Request ${error.requestId ?? "unknown"}.` : "Unexpected API error.");
    }
  }, [label]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function loadMore() {
    const view = response?.data;
    if (label !== "Orders" || !view || !("total" in view) || view.total === null) return;
    const currentGeneration = generation.current;
    const sourceRevision = view.evidence.source_revision;
    if (sourceRevision === null) {
      setMessage("The Orders source did not provide a stable revision. Refresh before loading another page.");
      return;
    }
    setLoadingMore(true);
    try {
      const page = await getProductionOrdersPage(view.data.length, 50);
      if (currentGeneration !== generation.current) return;
      if (page.data.evidence.source_revision !== sourceRevision) {
        setMessage("The Orders snapshot changed during pagination. Refresh to load a consistent page.");
        return;
      }
      setResponse((current) => current && "total" in current.data && current.data.evidence.source_revision === sourceRevision
        ? { ...page, data: { ...page.data, data: [...current.data.data, ...page.data.data] } as Data } : current);
    } catch (error) {
      if (currentGeneration !== generation.current) return;
      setMessage(error instanceof ControlPlaneError ? `${error.message} Request ${error.requestId ?? "unknown"}.` : "Could not load more orders.");
    } finally { if (currentGeneration === generation.current) setLoadingMore(false); }
  }

  const common = { response, state, message, now, reload: () => void load() };
  if (label === "Portfolio") return <PortfolioPage {...common} response={response as ApiEnvelope<PortfolioView> | null} />;
  if (label === "Positions") return <PositionsPage {...common} response={response as ApiEnvelope<PositionsView> | null} />;
  if (label === "Orders") return <OrdersPage {...common} response={response as ApiEnvelope<OrdersView> | null} loadMore={() => void loadMore()} loadingMore={loadingMore} />;
  if (label === "Reconciliation") return <ReconciliationPage {...common} response={response as ApiEnvelope<ReconciliationView> | null} />;
  if (label === "Risk") return <RiskPage {...common} response={response as ApiEnvelope<RiskView> | null} />;
  if (label === "Releases") return <ReleasesPage {...common} response={response as ApiEnvelope<ReleaseView> | null} />;
  return <AuditPage {...common} response={response as ApiEnvelope<AuditView> | null} />;
}
