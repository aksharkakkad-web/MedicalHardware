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

  it.each([
    ["attention", "Needs attention"],
    ["away", "Away mode"],
    ["limited", "Limited view"],
    ["unavailable", "Information unavailable"],
  ] as const)("renders the %s state without a steady label", async (state, label) => {
    const client = new MockHomeMonitoringClient();
    const overview = await client.getOverview();
    overview.lovedOne.status = { ...overview.lovedOne.status, state, headline: label, summary: "This view is intentionally not reassuring." };
    client.getOverview = async () => overview;
    renderToday(client);
    expect(await screen.findByRole("heading", { name: label })).toBeInTheDocument();
    expect(screen.getByText(label, { selector: "p" })).toBeInTheDocument();
    expect(screen.queryByText("Current picture")).not.toBeInTheDocument();
  });

  it("describes changed and unavailable trends without false steady language", async () => {
    const client = new MockHomeMonitoringClient();
    const overview = await client.getOverview();
    overview.lovedOne.trends[0] = { ...overview.lovedOne.trends[0], direction: "changed" };
    overview.lovedOne.trends[1] = { ...overview.lovedOne.trends[1], direction: "unavailable", points: [1, 2, 3] };
    client.getOverview = async () => overview;
    renderToday(client);
    expect(await screen.findByRole("img", { name: /movement routine showed a meaningful change/i })).toBeInTheDocument();
    expect(screen.getByText("Not enough information yet")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /resting pattern stayed close/i })).not.toBeInTheDocument();
  });

  it("centers a single trend point instead of rendering an invalid coordinate", async () => {
    const client = new MockHomeMonitoringClient();
    const overview = await client.getOverview();
    overview.lovedOne.trends[0] = { ...overview.lovedOne.trends[0], points: [4] };
    client.getOverview = async () => overview;

    renderToday(client);

    const trend = await screen.findByRole("img", { name: /movement routine stayed close/i });
    expect(trend.querySelector("polyline")).toHaveAttribute("points", "56,28");
  });
});
