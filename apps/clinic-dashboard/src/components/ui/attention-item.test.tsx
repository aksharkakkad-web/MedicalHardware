import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AttentionItem, type AttentionRecord } from "./attention-item";

const record: AttentionRecord = {
  id: "sam-rivera-room-302",
  residentName: "Sam Rivera",
  room: "Room 302",
  attentionReason: "Multiple people may be present in the room",
  attention: "high",
  monitoring: "possible_multi_person",
  confidence: "unavailable",
  freshness: { value: "stale", lastCurrentUpdate: "08:42:18" },
  device: "healthy",
  workflow: "investigating",
  elapsed: "12 min open",
  observedContext: "Room sources are reporting, but attribution is not usable.",
  deviceDetails: "Radar, thermal, and Wi-Fi CSI sources are reporting.",
  primaryAction: { label: "Review record", href: "/residents/sam-rivera" },
};

// @ts-expect-error Possible multi-person monitoring requires unavailable confidence.
const invalidMultiPersonRecord: AttentionRecord = { ...record, confidence: "high" };
void invalidMultiPersonRecord;

describe("AttentionItem", () => {
  it("renders each status axis independently in a semantic reading order", () => {
    render(<AttentionItem record={record} />);

    const item = screen.getByRole("article", { name: /Sam Rivera.*Room 302/i });
    const axes = within(item).getAllByTestId(/attention-item-axis-/).map((axis) => axis.getAttribute("data-axis"));
    expect(axes).toEqual(["attention", "monitoring", "confidence", "freshness", "device", "workflow"]);
    expect(within(item).getByText("High attention priority")).toBeVisible();
    expect(within(item).getByText("Confidence unavailable")).toBeVisible();
    expect(within(item).getByText("Stale")).toBeVisible();
    expect(within(item).getByText("Healthy device")).toBeVisible();
    expect(within(item).getByText("Workflow investigating")).toBeVisible();
  });

  it("makes multi-person attribution unavailable without guessing", () => {
    render(<AttentionItem record={record} />);

    const item = screen.getByRole("article", { name: /Sam Rivera.*Room 302/i });
    expect(item).toHaveTextContent(/resident-specific attribution is unavailable/i);
    expect(item).toHaveTextContent(/do not guess which person caused this signal/i);
    expect(item).not.toHaveTextContent(/resident is being monitored normally/i);
  });

  it("normalizes malformed runtime multi-person confidence to unavailable", () => {
    const malformedRecord = { ...record, confidence: "high" } as unknown as AttentionRecord;
    render(<AttentionItem record={malformedRecord} />);

    const item = screen.getByRole("article", { name: /Sam Rivera.*Room 302/i });
    expect(within(item).getByText("Confidence unavailable")).toBeVisible();
    expect(within(item).queryByText("High confidence")).not.toBeInTheDocument();
    expect(item).toHaveTextContent(/resident-specific attribution is unavailable/i);
    expect(item).toHaveTextContent(/do not guess which person caused this signal/i);
  });

  it("gives the one resident-specific primary action a unique accessible name", () => {
    render(<AttentionItem record={record} />);

    const item = screen.getByRole("article", { name: /Sam Rivera.*Room 302/i });
    const action = within(item).getByRole("link", { name: "Review record for Sam Rivera" });
    expect(action).toHaveAttribute("href", "/residents/sam-rivera");
    expect(action).toHaveAttribute("data-primary-action");
    expect(within(item).getAllByRole("link")).toHaveLength(1);
  });

  it("keeps supplied observed context and avoids diagnostic claims", () => {
    render(<AttentionItem record={record} />);

    expect(screen.getByText(record.observedContext as string)).toBeVisible();
    expect(document.body.textContent).not.toMatch(/diagnos|heart attack|stroke|seizure/i);
  });
});
