import { render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { ResidentRecords, type ResidentRecord } from "./resident-records";
import { getStatusAxisLabel, getStatusLabel } from "./status-indicator";

const records: ResidentRecord[] = [
  {
    id: "avery-chen",
    interaction: "selected",
    residentName: "Avery Chen",
    room: "Room 214",
    attentionReason: "Unexpected movement needs review",
    attention: "high",
    monitoring: "active",
    confidence: "low",
    freshness: { value: "delayed" },
    device: "degraded",
    workflow: "investigating",
    primaryAction: { label: "Review record", href: "/residents/avery-chen" },
    deviceDetails: "Radar and thermal are reporting; Wi-Fi CSI is delayed.",
    lastObserved: "38 seconds ago",
  },
  {
    id: "jordan-lee",
    residentName: "Jordan Lee",
    room: "Room 108",
    attentionReason: "Resident-away period needs a coverage check",
    attention: "watch",
    monitoring: "away",
    confidence: "unavailable",
    freshness: { value: "stale", lastCurrentUpdate: "08:38:12" },
    device: "healthy",
    workflow: "acknowledged",
    primaryAction: { label: "Open record", href: "/residents/jordan-lee" },
    deviceDetails: "All three room sources are reporting.",
    lastObserved: "4 minutes ago",
  },
  {
    id: "sam-rivera",
    residentName: "Sam Rivera",
    room: "Room 302",
    attentionReason: "Multiple people may be present in the room",
    attention: "none",
    monitoring: "possible_multi_person",
    confidence: "unavailable",
    freshness: { value: "unknown" },
    device: "healthy",
    workflow: "new",
    primaryAction: { label: "Review record", href: "/residents/sam-rivera" },
    deviceDetails: "Room sources are reporting, but resident attribution is unavailable.",
    lastObserved: "Last current update unknown",
  },
];

describe("ResidentRecords", () => {
  it("renders a semantic desktop table from the shared records array", () => {
    render(<ResidentRecords records={records} />);

    const table = screen.getByRole("table", { name: /synthetic resident monitoring records/i });
    expect(within(table).getAllByRole("row")).toHaveLength(records.length + 1);
    expect(within(table).getByRole("columnheader", { name: "Resident" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Attention" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Monitoring" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Updated" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Open record" })).toBeInTheDocument();
    expect(within(table).getAllByRole("columnheader")).toHaveLength(5);
    expect(within(table).getAllByRole("link", { name: /for Avery Chen/i })).toHaveLength(1);
    const selectedRow = within(table).getAllByRole("row")[1];
    expect(selectedRow).toHaveAttribute("aria-selected", "true");
    expect(selectedRow).not.toHaveTextContent("Selected record");
    expect(within(selectedRow).getByRole("link", { name: /for Avery Chen/i })).toBeInTheDocument();
  });

  it("keeps the desktop table fixed and action-visible at tablet widths", () => {
    const css = readFileSync("src/components/ui/resident-records.module.css", "utf8");

    expect(css).toMatch(/table-layout:\s*fixed/);
    expect(css).toMatch(/min-width:\s*0/);
    expect(css).not.toMatch(/\.desktopTable\s*\{[^}]*overflow-x\s*:\s*auto/);
    expect(css).not.toMatch(/\.desktopTable\s+table\s*\{[^}]*min-width\s*:\s*980px/);
    expect(css).toMatch(/\.actionColumn/);
    expect(css).toMatch(/\.recordIdentity\s*\{[^}]*min-width:\s*0/);
    expect(css).toMatch(/height:\s*60px/);
    expect(css).toMatch(/\.rowAction\s*\{[^}]*width:\s*32px/);
    expect(css).toMatch(/\.rowAction\s*\{[^}]*height:\s*32px/);
    expect(css).toMatch(/\.desktopTable tbody tr:hover/);
    expect(css).toMatch(/\.desktopTable tbody tr\[aria-selected="true"\]/);
  });

  it("keeps default facts neutral without adding positive markers", () => {
    const css = readFileSync("src/components/ui/resident-records.module.css", "utf8");

    expect(css).toMatch(/\.compactStatus\[data-emphasis="quiet"\] \{ color: var\(--ac-text-secondary\); \}/);
    expect(css).toMatch(/\.compactStatus\[data-emphasis="quiet"\] \.statusDot \{ display: none; \}/);
    expect(css).not.toMatch(/\[data-axis="monitoring"\]\[data-value="active"\] \.statusDot \{ background: var\(--ac-positive-text\); \}/);
  });

  it("omits default confidence and freshness from the decision row", () => {
    const healthyRecord: ResidentRecord = {
      ...records[0],
      id: "healthy-default",
      residentName: "Taylor Morgan",
      attention: "none",
      monitoring: "active",
      confidence: "high",
      freshness: { value: "current" },
    };

    render(<ResidentRecords records={[healthyRecord]} />);

    const table = screen.getByRole("table", { name: /synthetic resident monitoring records/i });
    expect(table).toHaveTextContent("No priority");
    expect(table).toHaveTextContent("Monitoring active");
    expect(table).not.toHaveTextContent("High confidence");
    expect(table).not.toHaveTextContent("Current");
    expect(within(table).getByLabelText(/attention: no attention priority/i)).toHaveAttribute("data-emphasis", "quiet");
    expect(within(table).getByLabelText(/monitoring: monitoring active/i)).toHaveAttribute("data-emphasis", "quiet");

    const mobile = screen.getByTestId("resident-records-mobile");
    expect(mobile).not.toHaveTextContent("High confidence");
    expect(mobile).not.toHaveTextContent("Current");
  });

  it("uses canonical StatusIndicator labels in compact table cells", () => {
    expect(getStatusLabel({ axis: "attention", value: "high" })).toBe("High attention priority");
    expect(getStatusLabel({ axis: "monitoring", value: "active" })).toBe("Monitoring active");
    expect(getStatusLabel({ axis: "confidence", value: "unavailable" })).toBe("Confidence unavailable");

    render(<ResidentRecords records={records} />);
    const table = screen.getByRole("table", { name: /synthetic resident monitoring records/i });
    expect(table).toHaveTextContent("High");
    expect(table).toHaveTextContent("Monitoring");
    expect(table).toHaveTextContent("Confidence");
    expect(within(table).getByLabelText(`${getStatusAxisLabel("attention")}: ${getStatusLabel({ axis: "attention", value: "high" })}`)).toBeInTheDocument();
  });

  it("names each mobile detail disclosure for its resident", () => {
    render(<ResidentRecords records={records} />);

    const summaries = within(screen.getByTestId("resident-records-mobile")).getAllByText(/More details for/i);
    expect(summaries).toHaveLength(records.length);
    records.forEach((record) => {
      expect(screen.getByText(`More details for ${record.residentName}`)).toBeInTheDocument();
    });
  });

  it("keeps the desktop queue concise during possible multi-person presence", () => {
    render(<ResidentRecords records={records} />);

    const table = screen.getByRole("table", { name: /synthetic resident monitoring records/i });
    const samRow = within(table).getAllByRole("row").find((row) => row.textContent?.includes("Sam Rivera"));
    expect(samRow).toBeDefined();
    expect(samRow).toHaveTextContent("Multi-person possible");
    expect(samRow).toHaveTextContent("Confidence unavailable");
    expect(samRow).not.toHaveTextContent(/do not guess/i);
    expect(within(samRow as HTMLElement).getByLabelText(/monitoring: monitoring possible multi-person/i)).toBeInTheDocument();
  });

  it("keeps mobile decision facts concise and discloses secondary detail last", () => {
    render(<ResidentRecords records={records} />);

    const mobileList = screen.getByTestId("resident-records-mobile");
    const cards = within(mobileList).getAllByRole("article");
    expect(cards).toHaveLength(records.length);
    records.forEach((record) => {
      expect(within(mobileList).getByRole("article", { name: `${record.residentName}, ${record.room}` })).toBeInTheDocument();
    });

    cards.forEach((card) => {
      const orderedParts = [
        card.querySelector("[data-record-identity]"),
        card.querySelector("[data-attention-reason]"),
        card.querySelector("[data-evidence]"),
        card.querySelector("[data-primary-action]"),
        card.querySelector("details"),
      ];

      expect(orderedParts.every(Boolean)).toBe(true);
      const indexes = orderedParts.map((part) => Array.from(card.querySelectorAll("*" )).indexOf(part as Element));
      expect(indexes).toEqual([...indexes].sort((a, b) => a - b));
      expect(card.querySelector("details")?.previousElementSibling).toHaveAttribute("data-primary-action");
    });

    const selectedCard = cards.find((card) => card.textContent?.includes("Avery Chen"));
    expect(selectedCard).toHaveAttribute("data-interaction", "selected");
    expect(selectedCard).not.toHaveTextContent("Selected record");

    const evidence = cards[0].querySelector("[data-evidence]");
    expect(evidence).toHaveTextContent("Monitoring active");
    expect(evidence).toHaveTextContent("Low confidence");
    expect(evidence).toHaveTextContent("Delayed");
    expect(Array.from(evidence?.querySelectorAll("[data-axis]") ?? []).map((status) => status.getAttribute("data-axis"))).toEqual([
      "monitoring",
      "confidence",
      "freshness",
    ]);
    expect(within(evidence as HTMLElement).getByLabelText(/monitoring:/i)).toBeInTheDocument();
    expect(within(evidence as HTMLElement).getByLabelText(/confidence:/i)).toBeInTheDocument();
    expect(within(evidence as HTMLElement).getByLabelText(/freshness:/i)).toBeInTheDocument();
  });

  it("makes possible multi-person attribution explicitly unavailable", () => {
    render(<ResidentRecords records={records} />);

    const samCards = screen.getAllByRole("article").filter((card) => card.textContent?.includes("Sam Rivera"));
    expect(samCards).toHaveLength(1);
    expect(samCards[0]).toHaveTextContent(/multi-person possible/i);
    expect(within(samCards[0]).getByLabelText(/confidence: confidence unavailable/i)).toBeInTheDocument();
    expect(samCards[0]).not.toHaveTextContent(/monitoring active/i);
  });

  it("gives every primary action an accessible resident-specific name", () => {
    render(<ResidentRecords records={records} />);

    records.forEach((record) => {
      expect(screen.getAllByRole("link", { name: new RegExp(`${record.primaryAction.label} for ${record.residentName}`, "i") })).toHaveLength(2);
    });
  });
});
