import { useEffect, useState } from "react";
import { Pulse, ArrowClockwise, Circle, Compass, Gauge, ListBullets, ShieldCheck } from "@phosphor-icons/react";
import { Button } from "@cloudflare/kumo";
import { ControlPlaneError, getProductionOverview, overviewDataForDisplay } from "../api/client";
import type { ApiEnvelope, ProductionOverview } from "../api/types";
import { canReadProduction, capabilityState, mobileRoutes, routeForPath, routes } from "./context";
import { formatAge, formatWitaClock, formatWitaTimestamp } from "./time";
import { ProductionReadPage } from "../features/production/route";

type ViewState = "loading" | "ready" | "unavailable" | "error" | "empty" | "denied";
const icons: Record<string, typeof Gauge> = {
  "System Overview": Gauge, Operations: Pulse, Portfolio: Circle, Positions: ListBullets, Orders: ListBullets,
  Risk: ShieldCheck, Reconciliation: Compass, Releases: Gauge, "Audit Trail": ShieldCheck, Workbench: Compass, Strategies: ListBullets, Models: Circle,
  Experiments: Pulse, Candidates: ShieldCheck, Tournament: Gauge, "Market Data": Pulse,
  Infrastructure: Gauge, Logs: ListBullets, "System Audit": ShieldCheck,
};

function Status({ label, value }: { label: string; value: string | number | null }) {
  const text = value === null ? "UNAVAILABLE" : label === "Unknown orders" && typeof value === "number" && value > 0 ? `${value} UNKNOWN` : String(value);
  const tone = text === "HEALTHY" ? "good" : text === "CRITICAL" || text === "HALTED" || text === "MISMATCH" ? "critical" : text === "WARNING" || text === "STALE" || text === "PARTIAL" ? "warning" : text === "RECOVERY" ? "recovery" : text === "UNAVAILABLE" || text === "UNKNOWN" || text.endsWith(" UNKNOWN") ? "unknown" : "neutral";
  return <div className="status-cell"><span className="status-label">{label}</span><span className={`status-value ${tone}`}><i aria-hidden="true" />{text}</span></div>;
}

function hasCriticalState(data: ProductionOverview | undefined): boolean {
  return data !== undefined && (data.mode === "HALTED" || data.risk_status === "HALTED"
    || [data.market_health, data.venue_health, data.reconciliation_status].some((state) => state === "CRITICAL")
    || (data.unknown_orders_count !== null && data.unknown_orders_count > 0));
}

function ProductionOverviewPage({ snapshot, reload, state, message, now }: {
  snapshot: ApiEnvelope<ProductionOverview> | null; reload: () => void; state: ViewState; message: string | null; now: Date;
}) {
  const data = snapshot ? overviewDataForDisplay(snapshot) : undefined;
  const critical = hasCriticalState(data);
  return <main className="workspace">
    <div className="page-heading"><div><h1>System Overview</h1><p>Production Main · live runtime status · read-only view</p></div>
      {state !== "denied" && <Button variant="secondary" size="sm" onClick={reload}><ArrowClockwise size={15} /> Refresh</Button>}
    </div>
    <section className="safety-line" aria-live="polite">
      <span className={`safety-symbol ${critical ? "critical" : ""}`}><ShieldCheck size={17} /></span>
      <div><strong className={critical ? "critical" : ""}>{critical ? "Critical Production state detected" : state === "ready" || state === "empty" ? "Live Production · read-only control plane" : "Production account state unavailable"}</strong>
        <p>{critical ? "Review the affected service state. Order authority remains controlled by the live backend safeguards." : state === "ready" || state === "empty" ? "Operational truth comes from Production services. This surface cannot submit or modify orders." : "No account or operational values are shown without an authoritative Production snapshot."}</p>
      </div>
    </section>
    <section className="status-strip" aria-label="Production service status">
      <Status label="Execution mode" value={data?.mode ?? null} /><Status label="Venue" value={data?.venue_health ?? null} />
      <Status label="Market data" value={data?.market_health ?? null} /><Status label="Reconciliation" value={data?.reconciliation_status ?? null} />
      <Status label="Unknown orders" value={data?.unknown_orders_count ?? null} /><Status label="Risk" value={data?.risk_status ?? null} />
      <Status label="Release" value={data?.release_id ?? null} />
    </section>
    {state === "loading" && <p className="notice" role="status">Loading authoritative Production state…</p>}
    {state === "unavailable" && <section className="empty-state" role="status"><h2>Production read service unavailable</h2><p>Live account and service values remain hidden until the authoritative backend responds.</p></section>}
    {state === "empty" && <section className="empty-state" role="status"><h2>Production snapshot is empty</h2><p>The API explicitly reported an empty snapshot. No live account values were inferred.</p></section>}
    {state === "denied" && <section className="empty-state error-state" role="alert"><h2>Production read access denied</h2><p>The backend denied this identity. No account values or controls are available.</p></section>}
    {state === "error" && <section className="empty-state error-state" role="alert"><h2>Could not load Production state</h2><p>{message}</p><Button variant="secondary" onClick={reload}>Try again</Button></section>}
    <section className="evidence-line"><span>Snapshot · WITA</span><span>{snapshot?.as_of ? `${formatWitaTimestamp(snapshot.as_of)} (age ${formatAge(snapshot.as_of, now)})` : "—"}</span><span>Source revision</span><span>{snapshot?.source_revision ?? "—"}</span><span>Request</span><span>{snapshot?.request_id ?? "—"}</span></section>
    <footer className="workspace-foot">Production backend owns live balances, orders, risk and reconciliation. This UI is read-only.</footer>
  </main>;
}

function ContextPage({ context, label }: { context: string; label: string }) {
  const research = context === "Research Workbench";
  const production = context === "Production Main";
  const title = research ? "Research data service unavailable" : production ? "Production read view not implemented" : "System page not available in this build";
  const description = research
    ? "The Research read API is not connected. Production balances, orders and health are never used as Research data. Shadow agents and tournament portfolios remain isolated."
    : production
      ? "This Production read page is not part of this build. Live account values are not inferred or copied from another page; use the existing Production system as the authority."
      : "This System view has not been implemented yet. No Production account or Research runtime data is substituted.";
  return <main className="workspace">
    <div className="page-heading"><div><span className={`context-kicker ${research ? "research" : ""}`}>{context}</span><h1>{label}</h1><p>{research ? "Isolated research runtime · no Production account access" : production ? "Live Production account · read-only control plane" : "System observability · separate from Production account authority"}</p></div></div>
    <section className={`empty-state boundary-state ${research ? "research-boundary" : ""}`} role="status">
      <h2>{title}</h2>
      <p>{description}</p>
      {research && <span className="boundary-label">PRODUCTION ACCOUNT DATA · NOT AVAILABLE IN RESEARCH</span>}
    </section>
  </main>;
}

const byGroup = (group: string) => routes.filter((route) => route.group === group);
const mobileLabels: Record<string, string> = {
  "System Overview": "Overview", Operations: "Ops", Reconciliation: "Recon",
  "Market Data": "Market", Infrastructure: "Infra",
};

export function App() {
  const [path, setPath] = useState(() => routeForPath(window.location.pathname).path);
  const [snapshot, setSnapshot] = useState<ApiEnvelope<ProductionOverview> | null>(null);
  const [state, setState] = useState<ViewState>("loading");
  const [message, setMessage] = useState<string | null>(null);
  const [now, setNow] = useState(() => new Date());
  const active = routeForPath(path);

  function navigate(nextPath: string) {
    const route = routeForPath(nextPath);
    window.history.pushState({}, "", route.path);
    setPath(route.path);
  }

  async function reload() {
    if (!canReadProduction(active)) return;
    setSnapshot(null); setState("loading"); setMessage(null);
    try {
      const result = await getProductionOverview();
      setSnapshot(result);
      setState(result.status === "UNAVAILABLE" ? "unavailable" : result.status === "EMPTY" ? "empty" : "ready");
    } catch (error) {
      const code = error instanceof ControlPlaneError ? error.code : null;
      if (capabilityState(code) === "denied") setState("denied");
      else {
        setState("error");
        setMessage(error instanceof ControlPlaneError ? `${error.message} Request ${error.requestId ?? "unknown"}.` : "Unexpected API error.");
      }
    }
  }

  useEffect(() => {
    const onPopState = () => setPath(routeForPath(window.location.pathname).path);
    window.addEventListener("popstate", onPopState);
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => { window.removeEventListener("popstate", onPopState); window.clearInterval(timer); };
  }, []);

  useEffect(() => {
    setSnapshot(null); setMessage(null);
    if (canReadProduction(active)) void reload();
    else setState("unavailable");
  }, [path]);

  const quickRoutes = mobileRoutes(active.context);

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">IS</span><span>Indodax Systematic<small>Control Plane</small></span></div>
      <div className={`context-switch ${active.group === "Research" ? "research-context" : ""}`}><span className="context-dot" aria-hidden="true" />{active.context}</div>
      <nav aria-label="Main navigation">{["Overview", "Production", "Research", "System"].map((group) => <section className="nav-group" key={group}>
        <h2>{group}</h2>{byGroup(group).map(({ label, path: target }) => {
          const Icon = icons[label] ?? Gauge;
          return <button key={label} className={`nav-item ${active.label === label ? "selected" : ""}`} onClick={() => navigate(target)} type="button" aria-current={active.label === label ? "page" : undefined}><Icon size={16} weight="regular" /><span>{label}</span></button>;
        })}
      </section>)}</nav>
      <div className="operator"><span className="operator-avatar">OP</span><span>Operator<small>Read-only session</small></span><span className="operator-state" aria-hidden="true" /></div>
    </aside>
    <nav className="mobile-nav" aria-label={`${active.context} quick navigation`}>
      {quickRoutes.map(({ label, path: target }) => {
        const Icon = icons[label] ?? Gauge;
        return <button type="button" key={label} className={active.label === label ? "active" : ""} onClick={() => navigate(target)} aria-current={active.label === label ? "page" : undefined}><Icon size={18} /><span>{mobileLabels[label] ?? label}</span></button>;
      })}
    </nav>
    <div className="main-column">
      <header className="global-bar"><div className="crumb"><span>{active.group}</span><span>/</span><strong>{active.label}</strong></div><div className="global-states"><span><i className="live-dot" />{active.group === "Research" ? "RESEARCH · ISOLATED" : active.group === "System" ? "SYSTEM" : "PRODUCTION · LIVE"}</span><time aria-label={`WITA (UTC+8), ${formatWitaClock(now)}`} title="Asia/Makassar (UTC+8)">WITA {formatWitaClock(now)}</time></div></header>
      {canReadProduction(active)
        ? active.label === "System Overview" || active.label === "Operations"
          ? <ProductionOverviewPage snapshot={snapshot} reload={() => void reload()} state={state} message={message} now={now} />
          : <ProductionReadPage label={active.label} now={now} />
        : <ContextPage context={active.context} label={active.label} />}
    </div>
  </div>;
}
