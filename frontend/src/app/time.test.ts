import { describe, expect, it } from "vitest";
import { formatAge, formatWitaClock, formatWitaTimestamp } from "./time";

describe("operator time display", () => {
  const asOf = "2026-09-23T12:00:00Z";

  it("converts clocks and complete snapshot timestamps to WITA", () => {
    expect(formatWitaClock(new Date(asOf))).toBe("20:00:00");
    expect(formatWitaTimestamp(asOf)).toBe("23/09/2026, 20:00:00");
  });

  it("shows snapshot age and future timestamps explicitly", () => {
    expect(formatAge(asOf, new Date("2026-09-23T12:00:05Z"))).toBe("5s ago");
    expect(formatAge(asOf, new Date("2026-09-23T11:59:00Z"))).toBe("in 1m");
  });
});
