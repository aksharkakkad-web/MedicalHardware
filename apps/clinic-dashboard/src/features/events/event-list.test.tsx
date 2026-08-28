import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { MonitoringClientProvider } from "@/lib/monitoring/provider";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";
import { EventList } from "./event-list";

function renderList() {
  const client = new MockMonitoringClient(() => new Date("2026-08-27T18:00:00.000Z"));
  function Wrapper({ children }: { children: ReactNode }) { return <MonitoringClientProvider client={client}>{children}</MonitoringClientProvider>; }
  return render(<EventList />, { wrapper: Wrapper });
}

describe("EventList", () => {
  it("filters active work, history, and search results", async () => {
    const user = userEvent.setup();
    renderList();
    expect(await screen.findByText(/unusual activity needs staff review/i)).toBeVisible();
    expect(screen.queryByText(/previous unusual movement review/i)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Resolved" }));
    expect(await screen.findByText(/previous unusual movement review/i)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "All" }));
    await user.type(screen.getByRole("textbox", { name: /search events/i }), "Room 105");
    expect(screen.getByText(/room monitoring data stopped/i)).toBeVisible();
    expect(screen.queryByText(/unusual activity needs staff review/i)).not.toBeInTheDocument();
  });
});
