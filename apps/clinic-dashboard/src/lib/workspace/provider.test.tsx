import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { WorkspaceProvider, useWorkspace } from "./provider";
import { DemoWorkspaceClient } from "./demo-client";
function Consumer() {
  const { snapshot, status, error, client, refresh } = useWorkspace();
  return (
    <>
      <p>{status}</p>
      {error && <p role="alert">{error}</p>}
      <p>
        {
          snapshot?.events.find((e) => e.eventId === "evt_unusual_movement_102")
            ?.status
        }
      </p>
      <p>{snapshot?.residents.length ?? "No records"}</p>
      <button
        onClick={() => void client.acknowledgeEvent("evt_unusual_movement_102")}
      >
        Acknowledge
      </button>
      <button onClick={() => void refresh()}>Refresh</button>
    </>
  );
}
describe("workspace provider", () => {
  it("publishes mutations through subscription using the same canonical event", async () => {
    const client = new DemoWorkspaceClient();
    render(
      <WorkspaceProvider client={client}>
        <Consumer />
      </WorkspaceProvider>,
    );
    await screen.findByText("ready");
    expect(screen.getByText("open")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Acknowledge"));
    await screen.findByText("acknowledged");
    expect(screen.getByText("6")).toBeInTheDocument();
  });
  it("removes the old snapshot on refresh failure and recovers on retry", async () => {
    const client = new DemoWorkspaceClient();
    render(
      <WorkspaceProvider client={client}>
        <Consumer />
      </WorkspaceProvider>,
    );
    await screen.findByText("ready");
    vi.spyOn(client, "snapshot").mockRejectedValueOnce(
      new Error("Saved demo state is unavailable"),
    );
    await userEvent.click(screen.getByText("Refresh"));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Saved demo state is unavailable",
    );
    expect(screen.getByText("No records")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Refresh"));
    await waitFor(() =>
      expect(screen.queryByRole("alert")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("6")).toBeInTheDocument();
  });
});
