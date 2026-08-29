import { render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { ResidentRecords, type ResidentRecord } from "./resident-records";

const records: ResidentRecord[] = [
  {
    id: "avery-chen",
    selected: true,
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
    expect(within(table).getByRole("columnheader", { name: "Attention priority" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Evidence" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Operations" })).toBeInTheDocument();
    expect(within(table).getAllByRole("columnheader")).toHaveLength(5);
    expect(within(table).getAllByRole("link", { name: /for Avery Chen/i })).toHaveLength(1);
    const selectedRow = within(table).getAllByRole("row")[1];
    expect(selectedRow).toHaveAttribute("aria-selected", "true");
    expect(selectedRow).toHaveTextContent("Selected record");
    expect(within(selectedRow).getByRole("link", { name: /for Avery Chen/i })).toBeInTheDocument();
  });

  it("keeps the desktop table fixed and action-visible at tablet widths", () => {
    const css = readFileSync("src/components/ui/resident-records.module.css", "utf8");

    expect(css).toMatch(/table-layout:\s*fixed/);
    expect(css).toMatch(/min-width:\s*0/);
    expect(css).not.toMatch(/\.desktopTable\s*\{[^}]*overflow-x\s*:\s*auto/);
    expect(css).not.toMatch(/\.desktopTable\s+table\s*\{[^}]*min-width\s*:\s*980px/);
    expect(css).toMatch(/\.actionColumn/);
  });

  it("shows the attribution limitation in the desktop Operations cell", () => {
    render(<ResidentRecords records={records} />);

    const table = screen.getByRole("table", { name: /synthetic resident monitoring records/i });
    const samRow = within(table).getAllByRole("row").find((row) => row.textContent?.includes("Sam Rivera"));
    expect(samRow).toBeDefined();
    expect(samRow).toHaveTextContent("Resident attribution unavailable");
    expect(samRow).toHaveTextContent(/do not guess/i);
    expect(within(samRow as HTMLElement).getByLabelText(/monitoring: possible multi-person; resident attribution unavailable/i)).toBeInTheDocument();
  });

  it("keeps mobile record facts in the required reading order and discloses device details last", () => {
    render(<ResidentRecords records={records} />);

    const mobileList = screen.getByTestId("resident-records-mobile");
    const cards = within(mobileList).getAllByRole("article");
    expect(cards).toHaveLength(records.length);

    cards.forEach((card) => {
      const orderedParts = [
        card.querySelector("[data-record-identity]"),
        card.querySelector("[data-attention-reason]"),
        card.querySelector("[data-attention-priority]"),
        card.querySelector("[data-evidence]"),
        card.querySelector("[data-workflow]"),
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
    expect(selectedCard).toHaveTextContent("Selected record");

    const evidence = cards[0].querySelector("[data-evidence]");
    expect(evidence).toHaveTextContent("Confidence");
    expect(evidence).toHaveTextContent("Freshness");
    expect(within(evidence as HTMLElement).getByLabelText(/confidence:/i)).toBeInTheDocument();
    expect(within(evidence as HTMLElement).getByLabelText(/freshness:/i)).toBeInTheDocument();
  });

  it("makes possible multi-person attribution explicitly unavailable", () => {
    render(<ResidentRecords records={records} />);

    const samCards = screen.getAllByRole("article").filter((card) => card.textContent?.includes("Sam Rivera"));
    expect(samCards).toHaveLength(1);
    expect(samCards[0]).toHaveTextContent(/resident-specific attribution is unavailable/i);
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
