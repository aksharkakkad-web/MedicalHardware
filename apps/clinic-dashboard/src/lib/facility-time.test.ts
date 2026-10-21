import { describe, expect, it } from "vitest";
import { facilityDateTimeCandidates, facilityDateTimeInputValue } from "./facility-time";
describe("facility wall-clock conversion", () => {
  it("shows the supplied ISO instant in the facility zone, never the browser zone", () => {
    expect(facilityDateTimeInputValue("2026-10-21T15:37:22.149Z", "America/Chicago")).toBe("2026-10-21T10:37");
    expect(facilityDateTimeInputValue("2026-10-21T15:37:22Z", "Asia/Tokyo")).toBe("2026-10-22T00:37");
  });
  it("converts a unique Chicago local time to its actual UTC instant", () => {
    expect(facilityDateTimeCandidates("2026-10-21T09:00", "America/Chicago")).toEqual(["2026-10-21T14:00:00.000Z"]);
  });
  it("rejects the nonexistent Chicago spring-forward hour", () => {
    expect(facilityDateTimeCandidates("2026-03-08T02:30", "America/Chicago")).toEqual([]);
    expect(facilityDateTimeCandidates("2026-03-08T03:30", "America/Chicago")).toEqual(["2026-03-08T08:30:00.000Z"]);
  });
  it("returns both Chicago repeated-hour instants in chronological order", () => {
    expect(facilityDateTimeCandidates("2026-11-01T01:30", "America/Chicago")).toEqual(["2026-11-01T06:30:00.000Z", "2026-11-01T07:30:00.000Z"]);
  });
  it("does not roll impossible dates into another month or infer a timezone", () => {
    expect(facilityDateTimeCandidates("2026-02-31T09:00", "America/Chicago")).toEqual([]);
    expect(facilityDateTimeCandidates("2026-02-29T09:00", "UTC")).toEqual([]);
    expect(facilityDateTimeCandidates("2028-02-29T09:00", "UTC")).toEqual(["2028-02-29T09:00:00.000Z"]);
    expect(facilityDateTimeCandidates("2026-10-21T24:00", "UTC")).toEqual([]);
    expect(facilityDateTimeInputValue("2026-02-31T09:00:00Z", "UTC")).toBe("");
    expect(facilityDateTimeInputValue("2026-10-21T09:00", "UTC")).toBe("");
  });
  it("supports UTC and explicit-offset instants without browser-local parsing", () => {
    expect(facilityDateTimeCandidates("2026-10-21T09:00", "UTC")).toEqual(["2026-10-21T09:00:00.000Z"]);
    expect(facilityDateTimeInputValue("2026-10-21T09:00:00-05:00", "UTC")).toBe("2026-10-21T14:00");
    expect(facilityDateTimeCandidates("2026-10-21T09:00", "Invalid/Zone")).toEqual([]);
  });
});
