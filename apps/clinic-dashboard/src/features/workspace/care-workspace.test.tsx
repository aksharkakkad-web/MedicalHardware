import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";
import type { WorkspaceSnapshot } from "@/lib/workspace/types";
import {
  CareOverview,
  CareResidentDetail,
  CareEventDetail,
  CareHandover,
  CareEvents,
} from "./index";

const state = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("@/lib/workspace", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/workspace")>();
  return { ...actual, useWorkspace: () => state.value };
});
let snapshot: WorkspaceSnapshot;
const recordCheck = vi.fn();
const acknowledgeEvent = vi.fn();
const refresh = vi.fn();

beforeEach(async () => {
  const monitoring = new MockMonitoringClient(
    () => new Date("2026-10-21T15:00:00Z"),
  );
  const residents = (await monitoring.listResidentOverview()).items;
  const events = (await monitoring.listEvents()).items;
  snapshot = {
    mode: "demo",
    demoNotice: "Synthetic demonstration",
    sourceObservedAt: "2026-08-27T18:00:00Z",
    synchronizedAt: "2026-10-21T15:00:00Z",
    version: 1,
    facility: {
      facilityId: "f1",
      name: "Synthetic facility",
      timeZone: "America/Chicago",
      coverageContact: "Charge station",
      escalationContact: "Follow facility procedure",
    },
    areas: [{ areaId: "north", name: "North wing", roomIds: [] }],
    currentAreaId: "all",
    currentClient: {
      clientId: "c1",
      configurationVersion: 1,
      name: "North station",
      areaIds: ["north"],
      status: "approved",
      approvedAt: "2026-10-21T15:00:00Z",
      notificationStatus: "blocked",
      permissions: [
        "acknowledge",
        "record_check",
        "resolve_concern",
        "add_follow_up",
        "update_follow_up",
        "report_context",
      ],
    },
    clients: [],
    admin: { active: false, simulated: true },
    residents,
    events,
    profiles: residents.map((r, i) => ({
      residentId: r.residentId,
      name: `Synthetic Person ${i + 1}`,
      facilityResidentId: `S${i}`,
      areaId: "north",
      roomId: r.roomId,
      roomLabel: r.roomLabel,
      admittedAt: "2026-10-01T00:00:00Z",
      departedAt: null,
      assignmentEffectiveAt: "2026-10-01T00:00:00Z",
      synthetic: true,
    })),
    measurements: [
      {
        residentId: residents[0].residentId,
        kind: "pulse",
        label: "Pulse estimate",
        value: 72,
        unit: "bpm",
        observedAt: "2026-08-27T18:00:00Z",
        quality: "demo",
        attribution: "eligible",
        reason: "Synthetic observation",
        synthetic: true,
      },
    ],
    contexts: [],
    checks: [],
    followUps: [],
    imports: [],
    assignmentHistory: [],
    persistence: { available: true, message: "Demo records" },
    capabilities: {
      authentication: false,
      serverSync: false,
      documentExtraction: false,
      xlsxImport: false,
      backgroundNotifications: false,
    },
  };
  recordCheck.mockReset();
  acknowledgeEvent.mockReset();
  refresh.mockReset();
  state.value = {
    snapshot,
    status: "ready",
    error: null,
    client: { recordCheck, acknowledgeEvent },
    refresh,
  };
});

describe("care workspace", () => {
  it("opens the correct queue response popup without navigating or recording an action", async () => {
    const user = userEvent.setup();
    render(<CareOverview />);
    const trigger = screen.getByRole("button", { name: "Respond to Room 102" });
    expect(trigger.closest("a")).toBeNull();
    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Response & outcome" });
    expect(within(dialog).getByText("Unusual activity needs staff review")).toBeVisible();
    expect(within(dialog).getByRole("button", { name: "Acknowledge concern" })).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "Close response" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(acknowledgeEvent).not.toHaveBeenCalled();
    expect(recordCheck).not.toHaveBeenCalled();
    expect(trigger).toHaveFocus();
  });
  it("opens response actions from the detail heading instead of exposing a duplicate inline form", async () => {
    const user = userEvent.setup();
    render(<CareEventDetail eventId="evt_unusual_movement_102" />);
    expect(screen.queryByRole("button", { name: "Acknowledge concern" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Response & outcome" }));
    expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Acknowledge concern" })).toBeVisible();
  });
  it("protects an actual response draft until staff explicitly discard it", async () => {
    const user = userEvent.setup();
    snapshot.events.find((event) => event.eventId === "evt_unusual_movement_102")!.status = "acknowledged";
    render(<CareEventDetail eventId="evt_unusual_movement_102" />);
    await user.click(screen.getByRole("button", { name: "Response & outcome" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByRole("textbox", { name: "Note (optional)" }), "Unfinished synthetic note");
    await user.click(within(dialog).getByRole("button", { name: "Close response" }));
    expect(dialog).toBeVisible();
    expect(within(dialog).queryByRole("button", { name: "Save outcome" })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Keep editing" }));
    expect(within(dialog).getByRole("textbox", { name: "Note (optional)" })).toHaveValue("Unfinished synthetic note");
    await user.click(within(dialog).getByRole("button", { name: "Close response" }));
    await user.click(within(dialog).getByRole("button", { name: "Discard and close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(recordCheck).not.toHaveBeenCalled();
  });
  it("keeps the popup open while an outcome save is pending", async () => {
    const user = userEvent.setup();
    snapshot.events.find((event) => event.eventId === "evt_unusual_movement_102")!.status = "acknowledged";
    let finish!: (record: { completedCheck: boolean }) => void;
    recordCheck.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    render(<CareEventDetail eventId="evt_unusual_movement_102" />);
    await user.click(screen.getByRole("button", { name: "Response & outcome" }));
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("radio", { name: /checked · no concern observed/i }));
    await user.click(within(dialog).getByRole("button", { name: "Save outcome" }));
    expect(within(dialog).getByRole("button", { name: "Close response" })).toBeDisabled();
    fireEvent(dialog, new Event("cancel", { cancelable: true }));
    expect(dialog).toBeVisible();
    finish({ completedCheck: true });
    expect(await within(dialog).findByRole("status")).toHaveTextContent(/outcome saved/i);
  });
  it("retains a resolution draft across a changed permission and keeps unavailable actions hidden", async () => {
    const user = userEvent.setup();
    const event = snapshot.events.find((item) => item.eventId === "evt_unusual_movement_102")!;
    event.status = "checked";
    const view = render(<CareEventDetail eventId={event.eventId} />);
    await user.click(screen.getByRole("button", { name: "Response & outcome" }));
    await user.click(screen.getByRole("button", { name: "Resolve concern" }));
    await user.type(screen.getByLabelText("What actually happened?"), "Synthetic draft remains available");
    snapshot.currentClient.permissions = ["record_check"];
    view.rerender(<CareEventDetail eventId={event.eventId} />);
    expect(screen.getByRole("button", { name: "Resolve concern" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Confirm resolution" })).not.toBeInTheDocument();
    snapshot.currentClient.permissions.push("resolve_concern");
    view.rerender(<CareEventDetail eventId={event.eventId} />);
    expect(screen.getByLabelText("What actually happened?")).toBeVisible();
    expect(screen.getByLabelText("What actually happened?")).toHaveValue("Synthetic draft remains available");
    await user.click(screen.getByRole("button", { name: "Close response" }));
    expect(screen.getByRole("button", { name: "Keep editing" })).toBeVisible();
  });
  it("removes the concern details and controls if it leaves the authorized snapshot", async () => {
    const user = userEvent.setup();
    const view = render(<CareOverview />);
    await user.click(screen.getByRole("button", { name: "Respond to Room 102" }));
    snapshot.events = snapshot.events.filter((item) => item.eventId !== "evt_unusual_movement_102");
    view.rerender(<CareOverview />);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("status")).toHaveTextContent(/no longer available/i);
    expect(within(dialog).queryByText("Unusual activity needs staff review")).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Acknowledge concern" })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Close response" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it("puts a resident's unresolved care work before measurements while keeping history separate", () => {
    const event = snapshot.events.find((e) => e.eventId === "evt_unusual_movement_102")!;
    render(<CareResidentDetail residentId={event.resident.residentId} />);
    const work = screen.getByRole("region", { name: /open concerns/i });
    expect(within(work).getByRole("link", { name: new RegExp(event.headline) })).toBeVisible();
    expect(within(work).queryByText(/Previous unusual movement review/)).not.toBeInTheDocument();
    const measurements = screen.getByRole("region", { name: /last supplied measurements/i });
    expect(work.compareDocumentPosition(measurements) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
  it("filters the roster without hiding urgent concerns", async () => {
    const user = userEvent.setup();
    render(<CareOverview />);
    expect(
      screen.getByRole("heading", { name: /needs attention/i }),
    ).toBeVisible();
    await user.type(
      screen.getByRole("searchbox", { name: /find a resident or room/i }),
      "no matching resident",
    );
    expect(screen.getByText(/no residents match/i)).toBeVisible();
    expect(
      screen.getByText("Unusual activity needs staff review"),
    ).toBeVisible();
  });
  it("shows unavailable attribution instead of a resident measurement", () => {
    snapshot.residents[0].monitoring.state = "paused";
    render(
      <CareResidentDetail residentId={snapshot.residents[0].residentId} />,
    );
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.queryByText("72")).not.toBeInTheDocument();
    expect(
      screen.getByText(/historical measurements are not supplied/i),
    ).toBeVisible();
  });
  it("records an unable-to-check outcome without requesting closure or claiming a check", async () => {
    const user = userEvent.setup();
    const event = snapshot.events.find(
      (e) => e.eventId === "evt_unusual_movement_102",
    )!;
    event.status = "acknowledged";
    recordCheck.mockResolvedValue({ completedCheck: false });
    render(<CareEventDetail eventId={event.eventId} />);
    await user.click(screen.getByRole("button", { name: "Response & outcome" }));
    await user.click(
      screen.getByRole("radio", { name: /could not complete a check/i }),
    );
    await user.click(screen.getByRole("button", { name: "Save outcome" }));
    expect(recordCheck).toHaveBeenCalledWith(
      event.eventId,
      expect.objectContaining({ outcome: "unable_to_check" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      /not recorded as a completed check/i,
    );
    expect(
      screen.queryByRole("button", { name: "Confirm resolution" }),
    ).not.toBeInTheDocument();
  });
  it("keeps the entered outcome after a rejected save and does not report success", async () => {
    const user = userEvent.setup();
    const event = snapshot.events.find(
      (e) => e.eventId === "evt_unusual_movement_102",
    )!;
    event.status = "acknowledged";
    recordCheck.mockRejectedValue(
      new Error("Save could not be confirmed. Try again."),
    );
    render(<CareEventDetail eventId={event.eventId} />);
    await user.click(screen.getByRole("button", { name: "Response & outcome" }));
    await user.click(
      screen.getByRole("radio", { name: /could not complete a check/i }),
    );
    await user.click(screen.getByRole("button", { name: "Save outcome" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /save could not be confirmed/i,
    );
    expect(
      screen.getByRole("radio", { name: /could not complete a check/i }),
    ).toBeChecked();
    expect(
      screen.queryByText(/saved in demonstration/i),
    ).not.toBeInTheDocument();
  });
  it("permits explicit resolution of a canonical checked event without inventing a local check record", async () => {
    const user = userEvent.setup();
    const event = snapshot.events.find(
      (e) => e.eventId === "evt_unusual_movement_102",
    )!;
    event.status = "checked";
    render(<CareEventDetail eventId={event.eventId} />);
    await user.click(screen.getByRole("button", { name: "Response & outcome" }));
    await user.click(screen.getByRole("button", { name: "Resolve concern" }));
    expect(screen.getByRole("button", { name: "Confirm resolution" })).toBeVisible();
  });
  it("reuses one action identity after an unconfirmed outcome save", async () => {
    const user = userEvent.setup();
    const event = snapshot.events.find(
      (e) => e.eventId === "evt_unusual_movement_102",
    )!;
    event.status = "acknowledged";
    recordCheck
      .mockRejectedValueOnce(new Error("Save could not be confirmed"))
      .mockResolvedValueOnce({ completedCheck: false });
    render(<CareEventDetail eventId={event.eventId} />);
    await user.click(screen.getByRole("button", { name: "Response & outcome" }));
    await user.click(
      screen.getByRole("radio", { name: /could not complete a check/i }),
    );
    await user.click(screen.getByRole("button", { name: "Save outcome" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /save could not be confirmed/i,
    );
    await user.click(screen.getByRole("button", { name: "Save outcome" }));
    expect(recordCheck.mock.calls[0][1].requestId).toBe(
      recordCheck.mock.calls[1][1].requestId,
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      /not recorded as a completed check/i,
    );
  });
  it("keeps departed residents accessible from historical concerns without current measurements", () => {
    const event = snapshot.events.find(
      (e) => e.eventId === "evt_unusual_movement_102",
    )!;
    const profile = snapshot.profiles.find(
      (p) => p.residentId === event.resident.residentId,
    )!;
    profile.departedAt = "2026-10-20T15:00:00Z";
    snapshot.residents = snapshot.residents.filter(
      (r) => r.residentId !== profile.residentId,
    );
    render(<CareResidentDetail residentId={profile.residentId} />);
    expect(screen.getByRole("heading", { name: profile.name })).toBeVisible();
    expect(screen.getByText(/historical resident record/i)).toBeVisible();
    expect(screen.getByRole("link", { name: event.headline })).toBeVisible();
    expect(
      screen.getByText(/current resident measurements are unavailable/i),
    ).toBeVisible();
  });
  it("keeps event disposition visible when a resolved record also contains a check", async () => {
    const user = userEvent.setup();
    const event = snapshot.events.find(
      (e) => e.eventId === "evt_unusual_movement_102",
    )!;
    event.status = "resolved";
    event.overdue = true;
    snapshot.checks.push({
      checkId: "check_1",
      eventId: event.eventId,
      residentId: event.resident.residentId,
      outcome: "no_concern_observed",
      note: "",
      checkedAt: snapshot.synchronizedAt,
      recordedAt: snapshot.synchronizedAt,
      clientId: "c1",
      clientLabel: "North station",
      completedCheck: true,
      requestId: "req1",
    });
    render(<CareEvents />);
    await user.click(screen.getByRole("button", { name: /resolved history/i }));
    const row = screen.getByRole("link", { name: new RegExp(event.headline) });
    expect(within(row).getByLabelText("Resolved concern")).toHaveTextContent("Resolved");
    expect(within(row).getByText("Originally high priority")).toBeVisible();
    expect(row).toHaveAttribute("data-state", "resolved");
    expect(row).not.toHaveTextContent(/response overdue/i);
    expect(row).not.toHaveAttribute("data-priority");
    expect(within(row).queryByText("high priority", { exact: true })).not.toBeInTheDocument();
  });
  it("shows completed treatment in resident concern history without changing original priority", () => {
    const event = snapshot.events.find((e) => e.eventId === "evt_unusual_movement_102")!;
    event.status = "resolved";
    render(<CareResidentDetail residentId={event.resident.residentId} />);
    const section = screen.getByRole("region", { name: /concern records/i });
    const record = within(section).getByRole("link", { name: event.headline }).closest("li")!;
    expect(within(record).getByLabelText("Resolved concern")).toHaveTextContent("Resolved");
    expect(within(record).getByText("Originally high priority")).toBeVisible();
    expect(event.priority).toBe("high");
  });
  it("frames resolved evidence as history and omits current response instructions", () => {
    const event = snapshot.events.find((e) => e.eventId === "evt_unusual_movement_102")!;
    event.status = "resolved";
    render(<CareEventDetail eventId={event.eventId} />);
    expect(screen.getByText("Historical interpretation")).toBeVisible();
    expect(screen.getByText(event.interpretation.uncertainty)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Record at review" })).toBeVisible();
    expect(screen.getByText(event.interpretation.uncertainty!)).toBeVisible();
    expect(screen.queryByText(/a missing explanation or reading does not close this concern/i)).not.toBeInTheDocument();
    expect(screen.getByText(/preserved from the original review/i)).toBeVisible();
  });
  it("keeps checked concerns visibly unresolved until explicitly resolved", () => {
    const event = snapshot.events.find((e) => e.eventId === "evt_unusual_movement_102")!;
    event.status = "checked";
    render(<CareEventDetail eventId={event.eventId} />);
    expect(screen.queryByLabelText("Resolved concern")).not.toBeInTheDocument();
    expect(screen.getByText("high priority")).toHaveAttribute("data-priority", "high");
    expect(screen.getByLabelText("Concern response state")).toHaveTextContent("Check recorded · still open");
  });
  it("limits the roster to the selected authorized area and preserves other covered urgent work", () => {
    snapshot.currentAreaId = "south";
    snapshot.currentClient.areaIds.push("south");
    snapshot.areas.push({ areaId: "south", name: "South wing", roomIds: [] });
    snapshot.profiles[0].areaId = "south";
    render(<CareOverview />);
    const roster = screen.getByRole("table", {
      name: /residents in the selected area/i,
    });
    expect(within(roster).getAllByRole("link")).toHaveLength(1);
    expect(within(roster).getByText("Synthetic Person 1")).toBeVisible();
    expect(
      screen.getByText("Unusual activity needs staff review"),
    ).toBeVisible();
    expect(screen.getAllByText(/other covered area/i).length).toBeGreaterThan(
      0,
    );
  });
  it("does not relabel an older reading with the workspace refresh time", () => {
    render(<CareOverview />);
    const value = screen.getByText("72 bpm");
    const cell = value.closest("td")!;
    expect(cell).toHaveTextContent("Aug 27, 2026");
    expect(cell).not.toHaveTextContent("Oct 21");
  });
  it.each([false, true])(
    "shows completed follow-up history on resident records (historical=%s)",
    async (historical) => {
      const user = userEvent.setup();
      const profile = snapshot.profiles[0];
      if (historical) {
        profile.departedAt = "2026-10-20T15:00:00Z";
        snapshot.residents = snapshot.residents.filter(
          (r) => r.residentId !== profile.residentId,
        );
      }
      snapshot.followUps.push({
        followUpId: "complete_1",
        residentId: profile.residentId,
        eventId: null,
        text: "Completed assignment review",
        createdAt: "2026-10-21T14:00:00Z",
        dueAt: null,
        status: "completed",
        completionNote: null,
        completedAt: "2026-10-21T15:00:00Z",
        clientLabel: "North station",
        history: [
          {
            action: "completed",
            note: "Assignment confirmed with team",
            recordedAt: "2026-10-21T15:00:00Z",
            clientLabel: "North station",
          },
        ],
      });
      render(<CareResidentDetail residentId={profile.residentId} />);
      await user.click(screen.getByText("Completed follow-up history (1)"));
      expect(screen.getByText("Completed assignment review")).toBeVisible();
      await user.click(screen.getByText("Handover & completion history (1)"));
      expect(screen.getByText("Assignment confirmed with team")).toBeVisible();
      expect(
        screen.queryByRole("button", { name: "Mark follow-up complete" }),
      ).not.toBeInTheDocument();
    },
  );
  it("filters a custom handover interval in facility time rather than laptop time", () => {
    snapshot.contexts.push({
      contextId: "context-interval",
      residentId: snapshot.profiles[0].residentId,
      category: "observation",
      text: "Interval-specific observation",
      source: "Synthetic station",
      recordedAt: "2026-10-21T14:00:00Z",
      effectiveUntil: null,
      reviewStatus: "needs_review",
      supersedesContextId: null,
    });
    render(<CareHandover />);
    fireEvent.change(screen.getByLabelText(/^Interval start/), {
      target: { value: "2026-10-21T08:30" },
    });
    fireEvent.change(screen.getByLabelText(/^Interval end/), {
      target: { value: "2026-10-21T09:30" },
    });
    expect(screen.getByText("Interval-specific observation")).toBeVisible();
  });
  it.each(["8", "12", "24"])(
    "refreshes a rolling %s-hour handover when a new provider snapshot arrives",
    async (hours) => {
      const user = userEvent.setup();
      const { rerender } = render(<CareHandover />);
      await user.selectOptions(
        screen.getByRole("combobox", { name: "Recent activity interval" }),
        hours,
      );
      const event = snapshot.events.find(
        (item) => item.eventId === "evt_unusual_movement_102",
      )!;
      const updated: WorkspaceSnapshot = {
        ...snapshot,
        synchronizedAt: "2026-10-21T16:00:00Z",
        contexts: [
          ...snapshot.contexts,
          {
            contextId: "rolling-context",
            residentId: event.resident.residentId,
            category: "observation",
            text: "Recorded after handover opened",
            source: "Synthetic station",
            recordedAt: "2026-10-21T15:30:00Z",
            effectiveUntil: null,
            reviewStatus: "needs_review",
            supersedesContextId: null,
          },
        ],
        checks: [
          ...snapshot.checks,
          {
            checkId: "rolling-check",
            eventId: event.eventId,
            residentId: event.resident.residentId,
            outcome: "no_concern_observed",
            note: "",
            checkedAt: "2026-10-21T15:30:00Z",
            recordedAt: "2026-10-21T15:30:00Z",
            clientId: "c1",
            clientLabel: "North station",
            completedCheck: true,
            requestId: "rolling-check",
          },
        ],
      };
      state.value = { ...state.value, snapshot: updated };
      rerender(<CareHandover />);
      expect(screen.getByText("Recorded after handover opened")).toBeVisible();
      expect(
        screen.getByRole("heading", {
          name: "Outcome recorded · Synthetic Person 2",
        }),
      ).toBeVisible();
      expect(screen.getByLabelText(/^Interval end/)).toHaveValue(
        "2026-10-21T11:00",
      );
      expect(screen.getByLabelText(/^Interval start/)).toHaveValue(
        (
          {
            "8": "2026-10-21T03:00",
            "12": "2026-10-20T23:00",
            "24": "2026-10-20T11:00",
          } as Record<string, string>
        )[hours],
      );
    },
  );
  it("keeps a custom handover interval fixed through provider refresh", () => {
    const { rerender } = render(<CareHandover />);
    fireEvent.change(screen.getByLabelText(/^Interval start/), {
      target: { value: "2026-10-21T09:00" },
    });
    fireEvent.change(screen.getByLabelText(/^Interval end/), {
      target: { value: "2026-10-21T10:00" },
    });
    const updated: WorkspaceSnapshot = {
      ...snapshot,
      synchronizedAt: "2026-10-21T16:00:00Z",
      contexts: [
        ...snapshot.contexts,
        {
          contextId: "custom-context",
          residentId: snapshot.profiles[0].residentId,
          category: "observation",
          text: "Outside the fixed custom interval",
          source: "Synthetic station",
          recordedAt: "2026-10-21T15:30:00Z",
          effectiveUntil: null,
          reviewStatus: "needs_review",
          supersedesContextId: null,
        },
      ],
    };
    state.value = { ...state.value, snapshot: updated };
    rerender(<CareHandover />);
    expect(screen.getByLabelText(/^Interval start/)).toHaveValue(
      "2026-10-21T09:00",
    );
    expect(screen.getByLabelText(/^Interval end/)).toHaveValue(
      "2026-10-21T10:00",
    );
    expect(
      screen.queryByText("Outside the fixed custom interval"),
    ).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/^Interval start/), {
      target: { value: "2026-03-08T02:30" },
    });
    state.value = {
      ...state.value,
      snapshot: { ...updated, synchronizedAt: "2026-10-21T17:00:00Z" },
    };
    rerender(<CareHandover />);
    expect(screen.getByLabelText(/^Interval start/)).toHaveValue(
      "2026-03-08T02:30",
    );
    expect(
      screen.getByText(
        /recent activity is unavailable until the interval has valid times/i,
      ),
    ).toBeVisible();
  });
  it("does not turn an invalid DST interval into an empty activity report", () => {
    render(<CareHandover />);
    fireEvent.change(screen.getByLabelText(/^Interval start/), {
      target: { value: "2026-03-08T02:30" },
    });
    expect(
      screen.getByText(
        /recent activity is unavailable until the interval has valid times/i,
      ),
    ).toBeVisible();
    expect(
      screen.queryByText(/no recent activity records were returned/i),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Unusual activity needs staff review"),
    ).toBeVisible();
  });
  it("keeps view-only concerns visible without offering mutation controls even in admin mode", async () => {
    const user = userEvent.setup();
    snapshot.currentClient.permissions = [];
    snapshot.admin.active = true;
    render(<CareEventDetail eventId="evt_unusual_movement_102" />);
    await user.click(screen.getByRole("button", { name: "Response & outcome" }));
    expect(
      screen.getByRole("heading", { name: "Observed evidence" }),
    ).toBeVisible();
    expect(screen.getByText("Movement changed")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Acknowledge concern" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Add follow-up")).not.toBeInTheDocument();
    expect(
      screen.getByText(/not permitted to acknowledge concerns/i),
    ).toBeVisible();
    expect(acknowledgeEvent).not.toHaveBeenCalled();
  });
  it("allows a check grant without offering resolution", async () => {
    const user = userEvent.setup();
    snapshot.currentClient.permissions = ["record_check"];
    const event = snapshot.events.find(
      (item) => item.eventId === "evt_unusual_movement_102",
    )!;
    event.status = "checked";
    recordCheck.mockResolvedValue({ completedCheck: true });
    render(<CareEventDetail eventId={event.eventId} />);
    await user.click(screen.getByRole("button", { name: "Response & outcome" }));
    expect(screen.getByRole("button", { name: "Save outcome" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Confirm resolution" })).not.toBeInTheDocument();
    expect(
      screen.getByText(/not permitted to resolve concerns/i),
    ).toBeVisible();
    await user.click(
      screen.getByRole("radio", { name: /checked · no concern observed/i }),
    );
    await user.click(screen.getByRole("button", { name: "Save outcome" }));
    expect(recordCheck).toHaveBeenCalledWith(
      event.eventId,
      expect.objectContaining({ outcome: "no_concern_observed" }),
    );
  });
  it("keeps measurements visible without a context-report grant", () => {
    snapshot.currentClient.permissions = [];
    render(
      <CareResidentDetail residentId={snapshot.residents[0].residentId} />,
    );
    expect(screen.getByText("72")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Report context error" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/not permitted to report care context/i),
    ).toBeVisible();
  });
  it("shows follow-up records without offering update actions to a view-only station", () => {
    snapshot.currentClient.permissions = [];
    snapshot.followUps.push({
      followUpId: "view-follow-up",
      residentId: snapshot.residents[0].residentId,
      eventId: null,
      text: "Confirm assigned team",
      createdAt: snapshot.synchronizedAt,
      dueAt: null,
      status: "open",
      completionNote: null,
      completedAt: null,
      clientLabel: "North station",
    });
    render(
      <CareResidentDetail residentId={snapshot.residents[0].residentId} />,
    );
    expect(screen.getByText("Confirm assigned team")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Mark follow-up complete" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Hand over follow-up" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/not permitted to update follow-up/i),
    ).toBeVisible();
  });
  it("keeps handover counts tied to visible source work with a stated time zone", () => {
    snapshot.followUps.push({
      followUpId: "f1",
      residentId: snapshot.residents[0].residentId,
      eventId: null,
      text: "Confirm the assignment",
      createdAt: "2026-10-21T14:00:00Z",
      dueAt: "2026-10-21T16:00:00Z",
      status: "open",
      completionNote: null,
      completedAt: null,
      clientLabel: "North station",
    });
    render(<CareHandover />);
    expect(screen.getByText("Confirm the assignment")).toBeVisible();
    expect(screen.getAllByText(/America\/Chicago/).length).toBeGreaterThan(0);
    const concerns = screen.getByRole("region", {
      name: /unresolved concerns/i,
    });
    expect(within(concerns).getAllByRole("link")).toHaveLength(
      snapshot.events.filter((e) => e.status !== "resolved").length,
    );
  });
});
