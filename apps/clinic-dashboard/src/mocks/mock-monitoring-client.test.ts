import { describe, expect, it } from "vitest";
import { MockMonitoringClient } from "./mock-monitoring-client";

describe("MockMonitoringClient", () => {
  it("returns five synthetic residents covering honest monitoring states", async () => {
    const result = await new MockMonitoringClient().listResidentOverview();

    expect(result.items).toHaveLength(5);
    expect(result.items.map((item) => item.monitoring.state)).toEqual(
      expect.arrayContaining(["active", "paused", "limited", "unavailable"]),
    );
    expect(
      result.items.some((item) => item.attention.priority === "high"),
    ).toBe(true);
    expect(result.items.every((item) => item.schemaVersion === "1.0")).toBe(
      true,
    );
  });

  it("returns a clone that cannot mutate later responses", async () => {
    const client = new MockMonitoringClient();
    const firstResult = await client.listResidentOverview();

    firstResult.items[0].displayLabel = "Mutated label";

    const nextResult = await client.listResidentOverview();

    expect(nextResult.items[0].displayLabel).not.toBe("Mutated label");
  });
});
