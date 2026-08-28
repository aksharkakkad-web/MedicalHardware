import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HomeMonitoringClientProvider, type HomeMonitoringClient } from "@/lib/home-monitoring";
import { MockHomeMonitoringClient } from "@/mocks/mock-home-monitoring-client";
import { Today } from "./today";

function renderToday(client: HomeMonitoringClient = new MockHomeMonitoringClient()) {
  return render(<HomeMonitoringClientProvider client={client}><Today /></HomeMonitoringClientProvider>);
}

describe("Today", () => {
  it("answers the main question and shows trends and useful paths", async () => {
    renderToday();
    expect(await screen.findByRole("heading", { name: "Monitoring looks steady" })).toBeInTheDocument();
    expect(screen.getAllByTestId("trend-row")).toHaveLength(3);
    expect(screen.getByRole("link", { name: /understand this update/i })).toHaveAttribute("href", "/updates/home_evt_unusual_001");
    expect(screen.getByRole("link", { name: /manage routines/i })).toHaveAttribute("href", "/routines");
    expect(screen.getByText(/does not promise that everything is okay/i)).toBeInTheDocument();
  });

  it("shows a truthful loading state", () => {
    const client = new MockHomeMonitoringClient();
    client.getOverview = () => new Promise<never>(() => {});
    renderToday(client);
    expect(screen.getByRole("status")).toHaveTextContent(/bringing today into view/i);
  });

  it("shows a retryable error", async () => {
    const client = new MockHomeMonitoringClient();
    client.getOverview = async () => { throw new Error("offline"); };
    renderToday(client);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/could not load/i));
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});
