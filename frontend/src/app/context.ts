export type AppContext = "Production Main" | "Research Workbench" | "System";

export type AppRoute = { path: string; label: string; group: string; context: AppContext };

export const routes: AppRoute[] = [
  { path: "/production/overview", label: "System Overview", group: "Overview", context: "Production Main" },
  ...[
    ["Operations", "operations"], ["Portfolio", "portfolio"], ["Positions", "positions"],
    ["Orders", "orders"], ["Risk", "risk"], ["Reconciliation", "reconciliation"],
  ].map(([label, slug]) => ({ path: `/production/${slug}`, label, group: "Production", context: "Production Main" }) as AppRoute),
  ...[
    ["Workbench", "workbench"], ["Strategies", "strategies"], ["Models", "models"],
    ["Experiments", "experiments"], ["Candidates", "candidates"], ["Tournament", "tournament"],
  ].map(([label, slug]) => ({ path: `/research/${slug}`, label, group: "Research", context: "Research Workbench" }) as AppRoute),
  ...[
    ["Market Data", "market-data"], ["Infrastructure", "infrastructure"], ["Logs", "logs"], ["Audit", "audit"],
  ].map(([label, slug]) => ({ path: `/system/${slug}`, label, group: "System", context: "System" }) as AppRoute),
];

export function routeForPath(path: string): AppRoute {
  return routes.find((route) => route.path === path) ?? routes[0];
}

export function routeForLabel(label: string): AppRoute {
  return routes.find((route) => route.label === label) ?? routes[0];
}

export function mobileRoutes(context: AppContext): AppRoute[] {
  return routes.filter((route) => route.context === context);
}

export function canReadProduction(route: AppRoute): boolean {
  return route.path === "/production/overview";
}

export function capabilityState(code: string | null): "allowed" | "denied" | "unknown" {
  if (code === "CAPABILITY_REQUIRED" || code === "IDENTITY_REQUIRED" || code === "FORBIDDEN" || code === "PRODUCTION_READ_FORBIDDEN") return "denied";
  if (code !== null) return "unknown";
  return "allowed";
}
