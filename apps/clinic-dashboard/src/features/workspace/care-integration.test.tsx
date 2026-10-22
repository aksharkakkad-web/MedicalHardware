import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { DemoWorkspaceClient, WorkspaceProvider } from "@/lib/workspace";
import { CareEventDetail, CareOverview, CareResidentDetail } from "./index";

const eventId = "evt_unusual_movement_102";
function start(
  client = new DemoWorkspaceClient({
    now: () => new Date("2026-10-21T15:00:00Z"),
  }),
) {
  render(
    <WorkspaceProvider client={client}>
      <CareEventDetail eventId={eventId} />
    </WorkspaceProvider>,
  );
  return client;
}
describe("care workflows with the workspace service", () => {
  it("keeps resolution confirmation open after a queue row disappears and restores focus to the workspace", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient({ now: () => new Date("2026-10-21T15:00:00Z") });
    await client.acknowledgeEvent(eventId, "queue-test-ack");
    await client.recordCheck(eventId, { outcome: "no_concern_observed", note: "Synthetic check", requestId: "queue-test-check" });
    render(<WorkspaceProvider client={client}><main id="care-workspace"><CareOverview /></main></WorkspaceProvider>);
    await user.click(await screen.findByRole("button", { name: "Respond to Room 102" }));
    const dialog = screen.getByRole("dialog", { name: "Response & outcome" });
    await user.click(within(dialog).getByRole("button", { name: "Resolve concern" }));
    await user.selectOptions(within(dialog).getByLabelText("Resolution outcome"), "uncertain");
    await user.type(within(dialog).getByLabelText("What actually happened?"), "Synthetic review; cause remains uncertain.");
    await user.selectOptions(within(dialog).getByLabelText("Was this a usual routine?"), "no");
    await user.click(within(dialog).getByRole("button", { name: "Confirm resolution" }));
    expect(await within(dialog).findByLabelText("Resolved concern")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Respond to Room 102" })).not.toBeInTheDocument();
    expect(within(dialog).getByText("Originally high priority")).toBeVisible();
    expect(dialog.querySelector('[data-priority="high"]')).toBeNull();
    await user.click(within(dialog).getByRole("button", { name: "Close response" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveFocus();
  });
  it("keeps unable-to-check work open with durable follow-up after acknowledging", async () => {
    const user = userEvent.setup();
    const client = start();
    await user.click(await screen.findByRole("button", { name: "Response & outcome" }));
    await user.click(
      await screen.findByRole("button", { name: "Acknowledge concern" }),
    );
    await user.click(
      await screen.findByRole("radio", { name: /could not complete a check/i }),
    );
    await user.click(screen.getByRole("button", { name: "Save outcome" }));
    expect(
      await screen.findByText(
        /not recorded as a completed check\. the concern/i,
      ),
    ).toBeVisible();
    const state = await client.snapshot();
    expect(state.events.find((e) => e.eventId === eventId)?.status).toBe(
      "acknowledged",
    );
    expect(
      state.followUps.some((f) => f.eventId === eventId && f.status === "open"),
    ).toBe(true);
    expect(screen.getByRole("button", { name: "Resolve concern" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Close response" }));
    expect(
      screen.getByRole("button", { name: "Mark follow-up complete" }),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Confirm resolution" })).not.toBeInTheDocument();
  });
  it("requires explicit resolution after a successful check and retains resolved history", async () => {
    const user = userEvent.setup();
    const client = start();
    await user.click(await screen.findByRole("button", { name: "Response & outcome" }));
    await user.click(
      await screen.findByRole("button", { name: "Acknowledge concern" }),
    );
    await user.click(
      await screen.findByRole("radio", {
        name: /checked · no concern observed/i,
      }),
    );
    await user.click(screen.getByRole("button", { name: "Save outcome" }));
    await waitFor(async () =>
      expect(
        (await client.snapshot()).events.find((e) => e.eventId === eventId)
          ?.status,
      ).toBe("checked"),
    );
    await user.click(screen.getByRole("button", { name: "Resolve concern" }));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Resolution outcome" }),
      "false_positive",
    );
    await user.type(
      screen.getByRole("textbox", { name: "What actually happened?" }),
      "Synthetic routine movement reviewed.",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Was this a usual routine?" }),
      "yes",
    );
    await user.click(screen.getByRole("button", { name: "Confirm resolution" }));
    const completion = await within(screen.getByRole("dialog")).findByLabelText("Resolved concern");
    expect(completion).toBeVisible();
    expect(completion).toHaveTextContent("Resolved");
    expect(completion.querySelector("svg")).not.toBeNull();
    expect(within(screen.getByRole("dialog")).getByText("Originally high priority")).toBeVisible();
    expect(document.querySelector('[data-priority="high"]')).toBeNull();
    expect(
      (await client.snapshot()).events.find((e) => e.eventId === eventId)
        ?.status,
    ).toBe("resolved");
    expect(
      screen.queryByRole("button", { name: "Save outcome" }),
    ).not.toBeInTheDocument();
  });
  it("keeps a completed follow-up and its dated handover history inspectable", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient({
      now: () => new Date("2026-10-21T15:00:00Z"),
    });
    const event = (await client.snapshot()).events.find(
      (item) => item.eventId === eventId,
    )!;
    const followUp = await client.addFollowUp({
      residentId: event.resident.residentId,
      eventId,
      text: "Confirm alternate room coverage",
    });
    await client.handOverFollowUp(
      followUp.followUpId,
      "Review with the incoming team",
    );
    start(client);
    await user.click(
      await screen.findByRole("button", { name: "Mark follow-up complete" }),
    );
    await user.click(
      await screen.findByText("Completed follow-up history (1)"),
    );
    const heading = screen.getByText("Confirm alternate room coverage");
    const item = heading.closest("li")!;
    expect(
      within(item).getByText("Completed · Maplewood shared station"),
    ).toBeVisible();
    await user.click(
      within(item).getByText("Handover & completion history (2)"),
    );
    expect(
      within(item).getByText("Review with the incoming team"),
    ).toBeVisible();
    expect(
      within(item).getByText(/Completed · Oct 21, 2026, 10:00 AM CDT/),
    ).toBeVisible();
    expect(
      within(item).queryByRole("button", { name: "Mark follow-up complete" }),
    ).not.toBeInTheDocument();
    expect(
      within(item).queryByRole("button", { name: "Hand over follow-up" }),
    ).not.toBeInTheDocument();
  });
  it("records an earlier check in the facility time zone", async () => {
    const user = userEvent.setup();
    const client = start();
    await user.click(await screen.findByRole("button", { name: "Response & outcome" }));
    await user.click(
      await screen.findByRole("button", { name: "Acknowledge concern" }),
    );
    await user.click(
      await screen.findByRole("radio", {
        name: /checked · no concern observed/i,
      }),
    );
    await user.click(screen.getByText("Record a different check time"));
    fireEvent.change(screen.getByLabelText("Actual check time"), {
      target: { value: "2026-10-21T09:30" },
    });
    await user.click(screen.getByRole("button", { name: "Save outcome" }));
    await waitFor(async () =>
      expect((await client.snapshot()).checks[0]?.checkedAt).toBe(
        "2026-10-21T14:30:00.000Z",
      ),
    );
  });
  it("saves a follow-up due time as a Chicago instant", async () => {
    const user = userEvent.setup();
    const client = start();
    await user.click(await screen.findByRole("button", { name: "Response & outcome" }));
    await user.click(await screen.findByText("Add follow-up"));
    await user.type(
      screen.getByLabelText("What needs to happen next?"),
      "Confirm alternate coverage",
    );
    fireEvent.change(screen.getByLabelText("Follow-up due time (optional)"), {
      target: { value: "2026-10-21T11:30" },
    });
    await user.click(screen.getByRole("button", { name: "Save follow-up" }));
    await waitFor(async () =>
      expect(
        (await client.snapshot()).followUps.find(
          (f) => f.text === "Confirm alternate coverage",
        )?.dueAt,
      ).toBe("2026-10-21T16:30:00.000Z"),
    );
  });
  it("shows a source-backed hospice goal without turning it into notification suppression", async () => {
    const client = new DemoWorkspaceClient({
      now: () => new Date("2026-10-21T15:00:00Z"),
    });
    const snapshot = await client.snapshot();
    const record = snapshot.contexts.find(
      (c) => c.category === "hospice" || c.category === "care_goal",
    )!;
    render(
      <WorkspaceProvider client={client}>
        <CareResidentDetail residentId={record.residentId} />
      </WorkspaceProvider>,
    );
    expect(await screen.findByText(record.text)).toBeVisible();
    expect(screen.getByText(`Source: ${record.source}`)).toBeVisible();
    expect(
      screen.getByText(
        /hospice context does not by itself change or stop notifications/i,
      ),
    ).toBeVisible();
  });
});
