import { useEffect, useState } from "react";
import { Pulse, ArrowClockwise, Circle, Compass, Gauge, ListBullets, ShieldCheck } from "@phosphor-icons/react";
import { Button } from "@cloudflare/kumo";
import { ControlPlaneError, getProductionOverview } from "../api/client";
import type { ApiEnvelope, ProductionOverview } from "../api/types";

type ViewState = "loading" | "ready" | "unavailable" | "error" | "empty";

const groups = [
  { name: "Overview", items: [{ label: "System Overview", icon: Gauge }] },
    { name: "Production", items: [
    { label: "Operations", icon: Pulse }, { label: "Portfolio", icon: Circle },
    { label: "Positions", icon: ListBullets }, { label: "Orders", icon: ListBullets },
    { label: "Risk", icon: ShieldCheck }, { label: "Reconciliation", icon: Compass },
  ] },
  { name: "Research", items: [
    { label: "Workbench", icon: Compass }, { label: "Strategies", icon: ListBullets },
    { label: "Models", icon: Circle }, { label: "Experiments", icon: Pulse },
    { label: "Candidates", icon: ShieldCheck }, { label: "Tournament", icon: Gauge },
  ] },
  { name: "System", items: [
    { label: "Market Data", icon: Pulse }, { label: "Infrastructure", icon: Gauge },
    { label: "Logs", icon: ListBullets }, { label: "Audit", icon: ShieldCheck },
  ] },
];
const mobileItems = [
  { label: "System Overview", icon: Gauge, short: "Overview" },
  { label: "Orders", icon: ListBullets, short: "Orders" },
  { label: "Risk", icon: ShieldCheck, short: "Risk" },
  { label: "Infrastructure", icon: Pulse, short: "System" },
];

function Status({ label, value }: { label: string; value: string | number | null }) {
  const text = value === null ? "UNAVAILABLE" : label === "Unknown orders" && typeof value === "number" && value > 0 ? `${value} UNKNOWN` : String(value);
  const tone = text === "HEALTHY" ? "good" : text === "CRITICAL" || text === "HALTED" || text === "MISMATCH" ? "critical" : text === "WARNING" || text === "STALE" ? "warning" : text === "RECOVERY" ? "recovery" : text === "UNAVAILABLE" || text === "UNKNOWN" || text.endsWith(" UNKNOWN") ? "unknown" : "neutral";
  return <div className="status-cell"><span className="status-label">{label}</span><span className={`status-value ${tone}`}><i aria-hidden="true" />{text}</span></div>;
}

function hasCriticalState(data: ProductionOverview | undefined): boolean {
  return data !== undefined && (
    data.execution_mode === "HALTED"
    || [data.market, data.venue, data.reconciliation, data.risk].some((state) => state === "CRITICAL" || state === "MISMATCH")
    || (data.unknown_orders !== null && data.unknown_orders > 0)
  );
}

function formatWita(value: string | Date): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Makassar",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).format(value instanceof Date ? value : new Date(value));
}

function Overview({ snapshot, reload, state, message }: {
  snapshot: ApiEnvelope<ProductionOverview> | null;
  reload: () => void;
  state: ViewState;
  message: string | null;
}) {
  const data = snapshot?.status === "UNAVAILABLE" ? undefined : snapshot?.data;
  const critical = hasCriticalState(data);
  return <main className="workspace">
    <div className="page-heading"><div><h1>System Overview</h1><p>Production Main · read-only service state</p></div>
      <Button variant="secondary" size="sm" onClick={reload}><ArrowClockwise size={15} /> Refresh</Button>
    </div>
    <section className="safety-line" aria-live="polite">
      <span className={`safety-symbol ${critical ? "critical" : ""}`}><ShieldCheck size={17} /></span>
      <div><strong className={critical ? "critical" : ""}>{critical ? "Critical Production state detected" : state === "ready" || state === "empty" ? "Read-only control plane" : "No authoritative Production snapshot"}</strong>
        <p>{critical ? "Review the affected service state before any operator action. New order authority remains controlled by backend safeguards." : state === "ready" || state === "empty" ? "This surface observes backend-owned state. It cannot submit or modify orders." : "Operational values remain unavailable until the Production API returns an authoritative snapshot."}</p>
      </div>
    </section>
    <section className="status-strip" aria-label="Production service status">
      <Status label="Execution mode" value={data?.execution_mode ?? null} />
      <Status label="Venue" value={data?.venue ?? null} />
      <Status label="Market data" value={data?.market ?? null} />
      <Status label="Reconciliation" value={data?.reconciliation ?? null} />
      <Status label="Unknown orders" value={data?.unknown_orders ?? null} />
      <Status label="Risk" value={data?.risk ?? null} />
      <Status label="Release" value={data?.release_id ?? null} />
    </section>
    {state === "loading" && <p className="notice" role="status">Loading Production state…</p>}
    {state === "unavailable" && <section className="empty-state" role="status"><h2>Production API is not connected</h2><p>No operational values are shown until the backend provides an authoritative snapshot.</p></section>}
    {state === "empty" && <section className="empty-state" role="status"><h2>Production snapshot is empty</h2><p>The API explicitly reported an empty snapshot. No operational values were inferred.</p></section>}
    {state === "error" && <section className="empty-state error-state" role="alert"><h2>Could not load Production state</h2><p>{message}</p><Button variant="secondary" onClick={reload}>Try again</Button></section>}
    <section className="evidence-line"><span>Snapshot · WITA</span><span>{snapshot?.as_of ? formatWita(snapshot.as_of) : "—"}</span><span>Source revision</span><span>{snapshot?.source_revision ?? "—"}</span><span>Request</span><span>{snapshot?.request_id ?? "—"}</span></section>
    <footer className="workspace-foot">UI is an observability surface. Backend services remain authoritative for balances, orders, risk and reconciliation.</footer>
  </main>;
}

export function App() {
  const [snapshot, setSnapshot] = useState<ApiEnvelope<ProductionOverview> | null>(null);
  const [state, setState] = useState<ViewState>("loading");
  const [message, setMessage] = useState<string | null>(null);
  const [active, setActive] = useState("System Overview");
  const activeGroup = groups.find((group) => group.items.some((item) => item.label === active))?.name ?? "Overview";
  const contextName = activeGroup === "Research" ? "Research Workbench" : activeGroup === "System" ? "System" : "Production Main";

  async function reload() {
    setSnapshot(null); setState("loading"); setMessage(null);
    try {
      const result = await getProductionOverview();
      setSnapshot(result);
      setState(result.status === "UNAVAILABLE" ? "unavailable" : result.status === "EMPTY" ? "empty" : "ready");
    } catch (error) {
      setState("error");
      setMessage(error instanceof ControlPlaneError ? `${error.message} Request ${error.requestId ?? "unknown"}.` : "Unexpected API error.");
    }
  }

  useEffect(() => { void reload(); }, []);

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">IS</span><span>Indodax Systematic<small>Control Plane</small></span></div>
      <div className="context-switch"><span className="context-dot" aria-hidden="true" />{contextName}</div>
      <nav aria-label="Main navigation">{groups.map((group) => <section className="nav-group" key={group.name}>
        <h2>{group.name}</h2>{group.items.map(({ label, icon: Icon }) => <button key={label} className={`nav-item ${active === label ? "selected" : ""}`} onClick={() => setActive(label)} type="button"><Icon size={16} weight="regular" /><span>{label}</span></button>)}
      </section>)}</nav>
      <div className="operator"><span className="operator-avatar">OP</span><span>Operator<small>Read-only session</small></span><span className="operator-state" aria-hidden="true" /></div>
    </aside>
    <nav className="mobile-nav" aria-label="Quick navigation">
      {mobileItems.map(({ label, icon: Icon, short }) => <button type="button" key={label} className={active === label ? "active" : ""} onClick={() => setActive(label)} aria-current={active === label ? "page" : undefined}><Icon size={17} /><span>{short}</span></button>)}
    </nav>
    <div className="main-column">
      <header className="global-bar"><div className="crumb"><span>{activeGroup}</span><span>/</span><strong>{active}</strong></div><div className="global-states"><span><i className="live-dot" /> API {state === "ready" || state === "empty" ? "CONNECTED" : state === "loading" ? "CONNECTING" : "UNAVAILABLE"}</span><time aria-label={`WITA (UTC+8), ${formatWita(new Date())}`} title="Asia/Makassar (UTC+8)">WITA {formatWita(new Date())}</time></div></header>
      {active === "System Overview" ? <Overview snapshot={snapshot} reload={() => void reload()} state={state} message={message} /> : <main className="workspace"><div className="page-heading"><div><h1>{active}</h1><p>{contextName} · read-only</p></div></div><section className="empty-state"><h2>Page not available in this build</h2><p>This view will appear when its {contextName} read model and route are implemented. No fixture data is substituted.</p></section></main>}
    </div>
  </div>;
}
