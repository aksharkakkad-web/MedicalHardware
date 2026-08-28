import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { HomeMonitoringClientProvider, type HomeMonitoringClient } from "@/lib/home-monitoring";
import { MockHomeMonitoringClient } from "@/mocks/mock-home-monitoring-client";
import { UpdateDetail } from "./update-detail";

function renderUpdate(client: HomeMonitoringClient = new MockHomeMonitoringClient()) {
  return render(<HomeMonitoringClientProvider client={client}><UpdateDetail eventId="home_evt_unusual_001" /></HomeMonitoringClientProvider>);
}

describe("UpdateDetail", () => {
  it("explains the update without clinic controls or fake certainty", async () => {
    renderUpdate();
    expect(await screen.findByRole("heading", { name: /unusual movement pattern/i })).toBeInTheDocument();
    expect(screen.getByText(/cannot tell the exact cause/i)).toBeInTheDocument();
    expect(screen.getByText(/not a diagnosis/i)).toBeInTheDocument();
    expect(screen.queryByText(/acknowledge|resolve|escalate|confidence/i)).not.toBeInTheDocument();
  });

  it("saves a simple family explanation and switches to a summary", async () => {
    const user = userEvent.setup();
    renderUpdate();
    await screen.findByRole("heading", { name: /unusual movement pattern/i });
    await user.click(screen.getByRole("radio", { name: /this was expected/i }));
    await user.type(screen.getByLabelText(/anything else/i), "Evening stretching");
    await user.click(screen.getByRole("checkbox", { name: /remember this as part/i }));
    await user.click(screen.getByRole("button", { name: /save explanation/i }));
    expect(await screen.findByText(/explanation saved/i)).toBeInTheDocument();
    expect(screen.getByText("Evening stretching")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /save explanation/i })).not.toBeInTheDocument();
  });

  it("shows missing and failed states honestly", async () => {
    const missing = new MockHomeMonitoringClient();
    missing.getUpdate = async () => null;
    const view = renderUpdate(missing);
    expect(await screen.findByRole("heading", { name: /could not be found/i })).toBeInTheDocument();
    view.unmount();

    const failed = new MockHomeMonitoringClient();
    failed.getUpdate = async () => { throw new Error("offline"); };
    renderUpdate(failed);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/could not load/i));
  });
});
