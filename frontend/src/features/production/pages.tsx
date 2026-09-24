import type { ReactNode } from "react";
import { ArrowClockwise } from "@phosphor-icons/react";
import { Button } from "@cloudflare/kumo";
import type {
  ApiEnvelope, AuditView, OrdersView, PortfolioView, PositionsView,
  ProductionOverview, ReconciliationView, ReleaseView, ResourceEvidence, RiskView,
} from "../../api/types";
import { formatAge, formatWitaTimestamp } from "../../app/time";

export type ReadState = "loading" | "ready" | "unavailable" | "error" | "empty" | "denied";
type PageProps<T> = {
  response: ApiEnvelope<T> | null;
  state: ReadState;
  message: string | null;
  now: Date;
  reload: () => void;
};
type OrdersPageProps = PageProps<OrdersView> & { loadMore: () => void; loadingMore: boolean };

function StatusValue({ label, value }: { label: string; value: string | number | null }) {
  const text = value === null ? "UNAVAILABLE" : String(value);
  const tone = ["HALTED", "CRITICAL", "MISMATCH", "UNVERIFIED"].includes(text) ? "critical"
    : ["WARNING", "STALE", "PARTIAL"].includes(text) ? "warning"
      : text === "RECOVERY" ? "recovery" : text === "HEALTHY" || text === "VERIFIED" ? "good" : "unknown";
  return <div className="status-cell"><span className="status-label">{label}</span><span className={`status-value ${tone}`}><i aria-hidden="true" />{text}</span></div>;
}

function PageLayout({ title, summary, state, message, reload, children }: {
  title: string; summary: string; state: ReadState; message: string | null; reload: () => void; children: ReactNode;
}) {
  return <main className="workspace">
    <header className="page-heading"><div><h1>{title}</h1><p>{summary}</p></div>
      {state !== "denied" && <Button variant="secondary" size="sm" onClick={reload} disabled={state === "loading"}><ArrowClockwise size={15} /> Refresh</Button>}
    </header>
    {state === "loading" && <div className="read-notice" role="status">Loading authoritative Production data…</div>}
    {state === "unavailable" && <div className="read-notice" role="status"><strong>Production source unavailable</strong><p>Values remain hidden until the owning Production service provides current evidence.</p></div>}
    {state === "empty" && <div className="read-notice" role="status"><strong>No Production snapshot</strong><p>The API reported an empty result. No account values were inferred.</p></div>}
    {state === "denied" && <div className="read-notice is-critical" role="alert"><strong>Production read access denied</strong><p>The backend denied this identity. No account values or controls are available.</p></div>}
    {state === "error" && <div className="read-notice is-critical" role="alert"><strong>Could not load Production data</strong><p>{message}</p><Button variant="secondary" onClick={reload}>Try again</Button></div>}
    {state === "ready" && children}
    <footer className="workspace-foot">Production Main is live. This dashboard is read-only; backend safeguards retain order authority.</footer>
  </main>;
}

function Evidence({ evidence, now, children }: { evidence: ResourceEvidence; now: Date; children: ReactNode }) {
  const available = evidence.status === "AVAILABLE" || evidence.status === "PARTIAL";
  return <section className={`data-panel evidence-${evidence.status.toLowerCase()}`}>
    <div className="panel-heading"><h2>Production evidence</h2><StatusValue label="Source state" value={evidence.status} /></div>
    {!available && <p className="resource-reason">{evidence.reason?.replaceAll("_", " ") ?? "The source did not provide authoritative values."}</p>}
    {available && children}
    <dl className="evidence-details">
      <dt>Source</dt><dd>{evidence.source}</dd>
      <dt>Freshness</dt><dd>{evidence.freshness}</dd>
      <dt>Source updated</dt><dd>{evidence.source_updated_at ? `${formatWitaTimestamp(evidence.source_updated_at)} WITA · age ${formatAge(evidence.source_updated_at, now)}` : "UNAVAILABLE"}</dd>
      <dt>Observed</dt><dd>{evidence.as_of ? `${formatWitaTimestamp(evidence.as_of)} WITA` : "UNAVAILABLE"}</dd>
      <dt>Source revision</dt><dd>{evidence.source_revision ?? "UNAVAILABLE"}</dd>
      {evidence.reason && available && <><dt>Note</dt><dd>{evidence.reason.replaceAll("_", " ")}</dd></>}
    </dl>
  </section>;
}

function Table<T>({ columns, rows, rowKey, emptyLabel }: {
  columns: { label: string; value: (row: T) => ReactNode }[];
  rows: T[]; rowKey: (row: T) => string; emptyLabel: string;
}) {
  return <div className="table-scroll"><table className="read-table">
    <thead><tr>{columns.map((column) => <th scope="col" key={column.label}>{column.label}</th>)}</tr></thead>
    <tbody>{rows.length ? rows.map((row) => <tr key={rowKey(row)}>{columns.map((column) => <td data-label={column.label} key={column.label}>{column.value(row)}</td>)}</tr>)
      : <tr className="empty-row"><td colSpan={columns.length}>{emptyLabel}</td></tr>}</tbody>
  </table></div>;
}

function Facts({ items }: { items: { label: string; value: ReactNode }[] }) {
  return <dl className="resource-facts">{items.map((item) => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl>;
}

export function OverviewPage({ response, state, message, now, reload }: PageProps<ProductionOverview>) {
  const data = state === "ready" ? response?.data : undefined;
  const critical = data !== undefined && (data.mode === "HALTED" || data.risk_status === "HALTED"
    || data.market_health === "CRITICAL" || data.venue_health === "CRITICAL"
    || (data.unknown_orders_count !== null && data.unknown_orders_count > 0));
  return <PageLayout title="System Overview" summary="Live Production health and safety state · read-only" state={state} message={message} reload={reload}>
    {data && <>
      <section className={`safety-line ${critical ? "is-critical" : ""}`} aria-live="polite">
        <span className="safety-symbol" aria-hidden="true">{critical ? "!" : "i"}</span>
        <div><strong>{critical ? "Critical Production state detected" : "Production Main · live account"}</strong>
          <p>{critical ? "Inspect the affected service. Existing live order authority remains with backend safeguards." : "Status values come from Production-owned services; this surface cannot submit or modify orders."}</p>
        </div>
      </section>
      <section className="status-strip" aria-label="Production service status">
        <StatusValue label="Execution mode" value={data.mode} /><StatusValue label="Venue" value={data.venue_health} />
        <StatusValue label="Market data" value={data.market_health} /><StatusValue label="Reconciliation" value={data.reconciliation_status} />
        <StatusValue label="Unknown orders" value={data.unknown_orders_count} /><StatusValue label="Risk" value={data.risk_status} />
        <StatusValue label="Release" value={data.release_id} />
      </section>
      <section className="data-panel"><div className="panel-heading"><h2>Snapshot provenance</h2></div>
        <Facts items={[
          { label: "Observed · WITA", value: `${formatWitaTimestamp(response!.as_of)} · age ${formatAge(response!.as_of, now)}` },
          { label: "Source", value: response!.provenance.source },
          { label: "Source revision", value: response!.source_revision },
          { label: "Request ID", value: response!.request_id },
        ]} />
      </section>
    </>}
  </PageLayout>;
}

export function PortfolioPage({ response, state, message, now, reload }: PageProps<PortfolioView>) {
  const view = state === "ready" ? response?.data : undefined;
  return <PageLayout title="Portfolio" summary="Authoritative Indodax balances · no cross-asset mark inferred" state={state} message={message} reload={reload}>
    {view && <Evidence evidence={view.evidence} now={now}>
      {view.balance_authority === "AVAILABLE" && <>
        <Facts items={[
          { label: `${view.quote_currency?.toUpperCase() ?? "Quote"} available`, value: view.quote_available ?? "UNAVAILABLE" },
          { label: `${view.quote_currency?.toUpperCase() ?? "Quote"} on hold`, value: view.quote_hold ?? "UNAVAILABLE" },
          { label: "Equity mark", value: view.equity ?? "UNAVAILABLE · no authoritative mark" },
        ]} />
        <h3 className="subsection-heading">Balances by currency</h3>
        <Table columns={[
          { label: "Currency", value: (row) => row.currency.toUpperCase() },
          { label: "Available", value: (row) => row.available },
          { label: "On hold", value: (row) => row.hold },
          { label: "Total", value: (row) => row.total },
        ]} rows={view.balances} rowKey={(row) => row.currency} emptyLabel="No balance rows were returned." />
      </>}
      {view.balance_authority !== "AVAILABLE" && <p className="resource-reason">Balance authority is unavailable.</p>}
    </Evidence>}
  </PageLayout>;
}

export function PositionsPage({ response, state, message, now, reload }: PageProps<PositionsView>) {
  const view = state === "ready" ? response?.data : undefined;
  return <PageLayout title="Positions" summary="Production position state · source authority shown per snapshot" state={state} message={message} reload={reload}>
    {view && <Evidence evidence={view.evidence} now={now}>
      {view.financial_authority === "AVAILABLE" ? <Table columns={[
        { label: "Pair", value: (row) => row.pair.toUpperCase() },
        { label: "Base quantity", value: (row) => row.base_qty },
        { label: "Cost basis", value: (row) => row.cost_basis },
      ]} rows={view.data} rowKey={(row) => row.pair} emptyLabel="No open positions were returned." />
        : <p className="resource-reason">Financial position authority is unavailable; position values are hidden.</p>}
    </Evidence>}
  </PageLayout>;
}

export function OrdersPage({ response, state, message, now, reload, loadMore, loadingMore }: OrdersPageProps) {
  const view = state === "ready" ? response?.data : undefined;
  const canLoadMore = view?.total !== null && view?.total !== undefined && view.data.length < view.total;
  return <PageLayout title="Orders" summary="OMS and venue identity · UNKNOWN state is explicit" state={state} message={message} reload={reload}>
    {view && <Evidence evidence={view.evidence} now={now}>
      <Table columns={[
        { label: "OMS order", value: (row) => row.internal_order_id },
        { label: "Venue order", value: (row) => row.venue_order_id ?? "UNAVAILABLE" },
        { label: "Pair", value: (row) => row.pair.toUpperCase() },
        { label: "Side", value: (row) => row.side.toUpperCase() },
        { label: "Quantity", value: (row) => row.desired_qty },
        { label: "Filled", value: (row) => row.filled_qty },
        { label: "State", value: (row) => row.state === "UNKNOWN" ? <span className="order-unknown">UNKNOWN · venue truth unresolved</span> : row.state },
      ]} rows={view.data} rowKey={(row) => row.internal_order_id} emptyLabel="No order records were returned." />
      <div className="table-footer"><span>{view.total === null ? "Total count unavailable" : `${view.data.length} of ${view.total} orders`}</span>
        {canLoadMore && <Button variant="secondary" size="sm" onClick={loadMore} disabled={loadingMore}>{loadingMore ? "Loading…" : "Load more orders"}</Button>}
      </div>
    </Evidence>}
  </PageLayout>;
}

export function ReconciliationPage({ response, state, message, now, reload }: PageProps<ReconciliationView>) {
  const view = state === "ready" ? response?.data : undefined;
  const mismatch = view?.healthy === false || (view?.mismatch_count !== null && (view?.mismatch_count ?? 0) > 0);
  return <PageLayout title="Reconciliation" summary="Production reconciliation evidence · no repair controls" state={state} message={message} reload={reload}>
    {view && <Evidence evidence={view.evidence} now={now}>
      <section className={`safety-line ${mismatch ? "is-critical" : ""}`} aria-live="polite">
        <div><strong>{mismatch ? "RECONCILIATION MISMATCH" : view.healthy === true ? "HEALTHY" : "UNKNOWN"}</strong>
          <p>{mismatch ? "New order submission is governed by the live backend safety gate. Inspect evidence before any operator action." : "The current read model does not provide a mismatch detail list."}</p>
        </div>
      </section>
      <Facts items={[
        { label: "Reconciliation", value: view.healthy === null ? "UNKNOWN" : view.healthy ? "HEALTHY" : "MISMATCH" },
        { label: "Mismatch count", value: view.mismatch_count ?? "UNKNOWN" },
      ]} />
    </Evidence>}
  </PageLayout>;
}

export function RiskPage({ response, state, message, now, reload }: PageProps<RiskView>) {
  const view = state === "ready" ? response?.data : undefined;
  return <PageLayout title="Risk Monitor" summary="Risk state and active safeguards · values reported by Production" state={state} message={message} reload={reload}>
    {view && <Evidence evidence={view.evidence} now={now}>
      <section className={`safety-line ${view.status === "HALTED" ? "is-critical" : ""}`}>
        <div><strong>{view.status === "HALTED" ? "HALTED" : "Risk state UNKNOWN"}</strong>
          <p>{view.status === "HALTED" ? "The Production risk authority reports a halt." : "No risk-limit snapshot is available; UNKNOWN is not a healthy state."}</p>
        </div>
      </section>
      <Facts items={[
        { label: "Kill switch", value: view.kill_switch_active === null ? "UNKNOWN" : view.kill_switch_active ? "ACTIVE" : "INACTIVE" },
        { label: "Utilization · as reported", value: view.utilization ?? "UNAVAILABLE" },
        { label: "Drawdown · as reported", value: view.drawdown ?? "UNAVAILABLE" },
      ]} />
    </Evidence>}
  </PageLayout>;
}

export function ReleasesPage({ response, state, message, now, reload }: PageProps<ReleaseView>) {
  const view = state === "ready" ? response?.data : undefined;
  return <PageLayout title="Releases" summary="Immutable Production release identity and verification state" state={state} message={message} reload={reload}>
    {view && <Evidence evidence={view.evidence} now={now}>
      <Facts items={[
        { label: "Release", value: view.release_id ?? "UNAVAILABLE" },
        { label: "Release source", value: view.status },
        { label: "Verification", value: view.verified === null ? "UNKNOWN" : view.verified ? "VERIFIED" : "UNVERIFIED" },
      ]} />
    </Evidence>}
  </PageLayout>;
}

const auditFields = ["timestamp", "actor", "action", "entity", "result", "correlation_id", "source"] as const;

export function AuditPage({ response, state, message, now, reload }: PageProps<AuditView>) {
  const view = state === "ready" ? response?.data : undefined;
  const event = view?.last_event;
  return <PageLayout title="Audit Trail" summary="Latest Production audit evidence · immutable event source" state={state} message={message} reload={reload}>
    {view && <Evidence evidence={view.evidence} now={now}>
      {event && <Facts items={auditFields.flatMap((field) => {
        const value = event[field];
        if (typeof value !== "string" && typeof value !== "number" && typeof value !== "boolean") return [];
        const display = field === "timestamp" && typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/i.test(value)
          ? `${formatWitaTimestamp(value)} WITA` : String(value);
        return [{ label: field.replaceAll("_", " "), value: display }];
      })} />}
      {!event && <p className="resource-reason">The audit source did not provide a latest event.</p>}
    </Evidence>}
  </PageLayout>;
}
