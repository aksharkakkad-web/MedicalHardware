import { describe, expect, it } from "vitest";
import { formatTimestamp } from "./device-format";
describe("facility device times", () => {
  it("uses the facility zone with an explicit zone label", () => {
    expect(formatTimestamp("2026-10-21T20:00:00Z", "America/Chicago")).toContain("3:00 PM CDT");
  });
  it("keeps absent or invalid timestamps unavailable", () => {
    expect(formatTimestamp(null, "America/Chicago")).toBe("No update yet");
    expect(formatTimestamp("invalid", "America/Chicago")).toBe("No update yet");
  });
});
