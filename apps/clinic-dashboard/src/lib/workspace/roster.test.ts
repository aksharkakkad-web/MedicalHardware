import { describe, expect, it } from "vitest";
import { parseRosterCsv } from "./roster";
import { DemoWorkspaceClient } from "./demo-client";
describe("local demo roster review", () => {
  it("parses quoted commas, escaped quotes and CRLF without interpreting cell content", () => {
    expect(
      parseRosterCsv(
        '\uFEFFName,ID\r\n"Doe, Alex",DEMO-1\r\n"A ""nickname""",=1+1\r\n',
      ),
    ).toEqual({
      headers: ["Name", "ID"],
      rows: [
        ["Doe, Alex", "DEMO-1"],
        ['A "nickname"', "=1+1"],
      ],
    });
  });
  it("rejects malformed quotes, duplicate headers and actual demo limits", () => {
    expect(() => parseRosterCsv('Name,ID\n"unfinished')).toThrow(/quote/i);
    expect(() => parseRosterCsv("Name,name\nA,1")).toThrow(/unique/i);
    expect(() => parseRosterCsv("x".repeat(100001))).toThrow(/100,000/);
    expect(() =>
      parseRosterCsv(
        "Name\n" +
          Array.from(
            {
              length: 101,
            },
            () => "A",
          ).join("\n"),
      ),
    ).toThrow(/100/);
  });
  it("maps selected columns and requires every duplicate row to remain blocked", async () => {
    const client = new DemoWorkspaceClient({
      now: () => new Date("2026-10-21T15:00:00Z"),
    });
    await client.enterAdminSimulation();
    const result = await client.previewRosterCsv(
      "Person,Identifier,Location,Wing\nNew synthetic person,X2,Room 110,North wing\nNew synthetic person,X2,Room 111,North wing",
      "roster.csv",
      {
        name: "Person",
        facilityResidentId: "Identifier",
        roomLabel: "Location",
        areaName: "Wing",
      },
    );
    expect(result.canApply).toBe(false);
    expect(result.rows.every((row) => row.action === "blocked")).toBe(true);
  });
});
