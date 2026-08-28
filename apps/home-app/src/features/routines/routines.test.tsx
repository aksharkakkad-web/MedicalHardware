import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { HomeMonitoringClientProvider, type HomeMonitoringClient } from "@/lib/home-monitoring";
import { MockHomeMonitoringClient } from "@/mocks/mock-home-monitoring-client";
import { Routines } from "./routines";

function renderRoutines(client: HomeMonitoringClient = new MockHomeMonitoringClient()) {
  return render(<HomeMonitoringClientProvider client={client}><Routines /></HomeMonitoringClientProvider>);
}

describe("Routines", () => {
  it("shows active routines and preserved retired history", async () => {
    renderRoutines();
    expect(await screen.findByRole("heading", { name: /keep everyday context current/i })).toBeInTheDocument();
    expect(screen.getByText(/makes tea/i)).toBeInTheDocument();
    await userEvent.click(screen.getByText(/past routines/i));
    expect(screen.getByText(/previously ate lunch/i)).toBeInTheDocument();
  });

  it("adds a trimmed routine and confirms the change", async () => {
    const user = userEvent.setup();
    renderRoutines();
    await screen.findByText(/makes tea/i);
    await user.type(screen.getByRole("textbox", { name: /describe one routine/i }), "  Takes a walk after lunch  ");
    await user.click(screen.getByRole("button", { name: /add routine/i }));
    expect(await screen.findByText("Takes a walk after lunch")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/routine added/i);
  });

  it("retires a routine with a reason without deleting history", async () => {
    const user = userEvent.setup();
    renderRoutines();
    await screen.findByText(/makes tea/i);
    await user.click(screen.getAllByRole("button", { name: /no longer current/i })[0]);
    await user.type(screen.getByLabelText(/why is this no longer current/i), "Schedule changed");
    await user.click(screen.getByRole("button", { name: /move to past routines/i }));
    expect(screen.getByRole("status")).toHaveTextContent(/moved to past routines/i);
    await user.click(screen.getByText("Past routines"));
    expect(screen.getByText("Schedule changed")).toBeInTheDocument();
  });

  it("keeps a retire form open when the reason is missing", async () => {
    const user = userEvent.setup();
    renderRoutines();
    await screen.findByText(/makes tea/i);
    await user.click(screen.getAllByRole("button", { name: /no longer current/i })[0]);
    await user.click(screen.getByRole("button", { name: /move to past routines/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/short reason/i);
    expect(screen.getByLabelText(/why is this no longer current/i)).toBeInTheDocument();
  });

  it("shows load failures without inventing routines", async () => {
    const client = new MockHomeMonitoringClient();
    client.getRoutines = async () => { throw new Error("offline"); };
    renderRoutines(client);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/could not load/i));
  });
});
