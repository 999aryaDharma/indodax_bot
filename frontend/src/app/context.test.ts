import { describe, expect, it } from "vitest";
import { canReadProduction, capabilityState, routeForLabel, routeForPath } from "./context";

describe("environment route boundary", () => {
  it("keeps Research routes separate from Production read models", () => {
    const research = routeForPath("/research/workbench");
    expect(research.context).toBe("Research Workbench");
    expect(research.group).toBe("Research");
    expect(canReadProduction(research)).toBe(false);
    expect(canReadProduction(routeForPath("/production/overview"))).toBe(true);
  });

  it("maps navigation labels to explicit route namespaces", () => {
    expect(routeForLabel("Portfolio").path).toBe("/production/portfolio");
    expect(routeForLabel("Tournament").path).toBe("/research/tournament");
    expect(routeForPath("/not-a-route").path).toBe("/production/overview");
  });

  it("fails closed when the backend denies read capability", () => {
    expect(capabilityState("CAPABILITY_REQUIRED")).toBe("denied");
    expect(capabilityState("IDENTITY_REQUIRED")).toBe("denied");
    expect(capabilityState(null)).toBe("allowed");
  });
});
