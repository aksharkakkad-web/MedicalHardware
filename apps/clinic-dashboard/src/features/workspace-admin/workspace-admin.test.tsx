import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DemoWorkspaceClient, WorkspaceProvider } from "@/lib/workspace";
import {
  DirectoryImport,
  FacilityAdmin,
  ResidentAdministration,
  StationSettings,
} from "./index";

function mount(view: React.ReactNode, client = new DemoWorkspaceClient()) {
  render(<WorkspaceProvider client={client}>{view}</WorkspaceProvider>);
  return client;
}

describe("workspace administration", () => {
  it("saves facility details and leaves routine station approval intact after administrator logout", async () => {
    const user = userEvent.setup();
    const client = mount(<FacilityAdmin />);
    const original = await client.snapshot();
    await user.click(
      await screen.findByRole("button", { name: "Enter demo administration" }),
    );
    const name = await screen.findByRole("textbox", { name: /Facility name/ });
    await user.clear(name);
    await user.type(name, "Prairie House");
    await user.click(screen.getByRole("button", { name: "Save facility" }));
    expect(
      await screen.findByText("Facility details saved in this demo."),
    ).toBeVisible();
    expect((await client.snapshot()).facility.name).toBe("Prairie House");
    await user.click(
      screen.getByRole("button", { name: "Leave demo administration" }),
    );
    await waitFor(async () =>
      expect((await client.snapshot()).admin.active).toBe(false),
    );
    expect((await client.snapshot()).currentClient).toEqual(
      original.currentClient,
    );
    expect(
      screen.queryByRole("button", { name: "Save facility" }),
    ).not.toBeInTheDocument();
  });

  it("validates a roster preview before any resident is created, then explicitly applies a valid roster", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient();
    await client.enterAdminSimulation();
    const before = await client.snapshot();
    mount(<DirectoryImport />, client);
    const csv = await screen.findByRole("textbox", { name: "CSV contents" });
    const area = before.areas.find((item) =>
      before.currentClient.areaIds.includes(item.areaId),
    )!;
    await user.type(
      csv,
      `facilityResidentId,name,roomLabel,areaName\nNEW-1,Synthetic Resident,999,${area.name}\nNEW-1,Duplicate Resident,998,${area.name}`,
    );
    await user.click(screen.getByRole("button", { name: "Review roster" }));
    expect(
      await screen.findByRole("button", { name: "Apply reviewed roster" }),
    ).toBeDisabled();
    expect((await client.snapshot()).profiles).toHaveLength(
      before.profiles.length,
    );
    await user.clear(csv);
    await user.type(
      csv,
      `facilityResidentId,name,roomLabel,areaName\nNEW-1,Synthetic Resident,999,${area.name}`,
    );
    await user.click(screen.getByRole("button", { name: "Review roster" }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Apply reviewed roster" }),
      ).toBeEnabled(),
    );
    expect((await client.snapshot()).profiles).toHaveLength(
      before.profiles.length,
    );
    await user.click(
      screen.getByRole("button", { name: "Apply reviewed roster" }),
    );
    expect(
      await screen.findByText("Roster applied to this demo workspace."),
    ).toBeVisible();
    expect(
      (await client.snapshot()).profiles.some(
        (item) => item.facilityResidentId === "NEW-1",
      ),
    ).toBe(true);
  });

  it("does not call a blocked local notification check a delivered notification", async () => {
    const user = userEvent.setup();
    mount(<StationSettings />);
    await user.click(
      await screen.findByRole("button", {
        name: "Check notification readiness",
      }),
    );
    const result = await screen.findByRole("status");
    expect(
      within(result).getByText(/No notification was delivered/),
    ).toBeVisible();
    expect(
      screen.queryByText(/^Notification delivered$/),
    ).not.toBeInTheDocument();
  });

  it("saves a manually entered resident with an actual care-area identity", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient();
    await client.enterAdminSimulation();
    mount(<FacilityAdmin />, client);
    await user.type(
      await screen.findByRole("textbox", { name: /^Resident name/ }),
      "Synthetic New Resident",
    );
    await user.type(
      screen.getByRole("textbox", { name: /^Facility resident identifier/ }),
      "DEMO-MANUAL",
    );
    await user.type(
      screen.getByRole("textbox", { name: /^Room label/ }),
      "990",
    );
    const assignmentTime = screen.getByLabelText(/^Assignment date and time/);
    expect(assignmentTime).toHaveAttribute("type", "datetime-local");
    fireEvent.change(assignmentTime, { target: { value: "2026-10-21T09:00" } });
    await user.click(
      screen.getByRole("button", { name: "Save resident record" }),
    );
    expect(
      await screen.findByText(
        "Resident record saved in this demo. Assignment history is retained.",
      ),
    ).toBeVisible();
    expect(
      (await client.snapshot()).profiles.find(
        (item) => item.facilityResidentId === "DEMO-MANUAL",
      )?.assignmentEffectiveAt,
    ).toBe("2026-10-21T14:00:00.000Z");
  });

  it("saves station coverage and removes resident access when current approval is revoked", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient();
    await client.enterAdminSimulation();
    const original = await client.snapshot();
    mount(<StationSettings />, client);
    const station = await screen.findByRole("article", {
      name: `Station ${original.currentClient.name}`,
    });
    const name = within(station).getByRole("textbox", {
      name: /^Station name:/,
    });
    await user.clear(name);
    await user.type(name, "West shared tablet");
    for (const area of original.areas) {
      const box = within(station).getByRole("checkbox", {
        name: area.name,
      }) as HTMLInputElement;
      if (box.checked !== (area.areaId === original.areas[0].areaId))
        await user.click(box);
    }
    await user.click(
      within(station).getByRole("button", { name: "Save station changes" }),
    );
    expect(await screen.findByText("Station settings saved.")).toBeVisible();
    const updated = await client.snapshot();
    expect(updated.currentClient.name).toBe("West shared tablet");
    expect(updated.currentClient.areaIds).toEqual([original.areas[0].areaId]);
    const renamed = screen.getByRole("article", {
      name: "Station West shared tablet",
    });
    await user.click(
      within(renamed).getByRole("button", { name: "Revoke approval" }),
    );
    await user.click(
      within(renamed).getByRole("button", { name: "Confirm revocation" }),
    );
    await waitFor(async () =>
      expect((await client.snapshot()).currentClient.status).toBe("revoked"),
    );
    expect((await client.snapshot()).residents).toHaveLength(0);
    expect(screen.getByText("Revoked — resident access blocked")).toBeVisible();
  });

  it("preserves facility details when a save fails instead of showing a success", async () => {
    const user = userEvent.setup();
    const values = new Map<string, string>();
    let rejectWrites = false;
    const client = new DemoWorkspaceClient({
      storage: {
        getItem: (key) => values.get(key) ?? null,
        setItem: (key, value) => {
          if (rejectWrites) throw new Error("Storage full");
          values.set(key, value);
        },
      },
    });
    await client.enterAdminSimulation();
    const before = await client.snapshot();
    mount(<FacilityAdmin />, client);
    const input = await screen.findByRole("textbox", {
      name: /^Facility name/,
    });
    await user.clear(input);
    await user.type(input, "Unsaved name");
    rejectWrites = true;
    await user.click(screen.getByRole("button", { name: "Save facility" }));
    expect(
      await screen.findByText(/Demo storage could not save this change/),
    ).toBeVisible();
    expect(
      screen.queryByText("Facility details saved in this demo."),
    ).not.toBeInTheDocument();
    expect((await client.snapshot()).facility.name).toBe(before.facility.name);
  });

  it("saves a plain-language facility time-zone selection as the actual zone", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient();
    await client.enterAdminSimulation();
    mount(<FacilityAdmin />, client);
    const input = await screen.findByRole("combobox", {
      name: /^Facility time zone/,
    });
    await user.selectOptions(
      input,
      screen.getByRole("option", { name: "Eastern — Detroit" }),
    );
    await user.click(screen.getByRole("button", { name: "Save facility" }));
    await screen.findByText("Facility details saved in this demo.");
    expect((await client.snapshot()).facility.timeZone).toBe("America/Detroit");
  });

  it("preserves a facility's existing zone outside the suggested US choices", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient();
    await client.enterAdminSimulation();
    const current = (await client.snapshot()).facility;
    await client.updateFacility({ ...current, timeZone: "Europe/London" });
    mount(<FacilityAdmin />, client);
    const select = await screen.findByRole("combobox", {
      name: /^Facility time zone/,
    });
    expect(select).toHaveValue("Europe/London");
    expect(
      within(select).getByRole("option", {
        name: "London — current facility setting",
      }),
    ).toHaveProperty("selected", true);
    await user.click(screen.getByRole("button", { name: "Save facility" }));
    await screen.findByText("Facility details saved in this demo.");
    expect((await client.snapshot()).facility.timeZone).toBe("Europe/London");
  });

  it("maps custom CSV columns and blocks an occupied-room conflict before apply", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient();
    await client.enterAdminSimulation();
    const before = await client.snapshot();
    const occupant = before.profiles[0];
    const area = before.areas.find((item) => item.areaId === occupant.areaId)!;
    mount(<DirectoryImport />, client);
    await user.type(
      await screen.findByRole("textbox", { name: "CSV contents" }),
      `Identity,Person,Location,Wing\nNEW-CONFLICT,Synthetic Conflict,${occupant.roomLabel},${area.name}`,
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Resident identifier column" }),
      "Identity",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Resident name column" }),
      "Person",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Room column" }),
      "Location",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Care area column" }),
      "Wing",
    );
    await user.click(screen.getByRole("button", { name: "Review roster" }));
    expect(
      await screen.findByText("Assignment conflict with an existing occupant."),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Apply reviewed roster" }),
    ).toBeDisabled();
    expect((await client.snapshot()).profiles).toEqual(before.profiles);
    await user.type(screen.getByRole("textbox", { name: "CSV contents" }), " ");
    expect(
      screen.getByText(
        "The source or mapping changed. Review the roster again before applying.",
      ),
    ).toBeVisible();
  });

  it("prevents source and mapping changes while a roster preview is in flight", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient();
    await client.enterAdminSimulation();
    let finish: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      finish = resolve;
    });
    const original = client.previewRosterCsv.bind(client);
    vi.spyOn(client, "previewRosterCsv").mockImplementation(async (...args) => {
      await gate;
      return original(...args);
    });
    mount(<DirectoryImport />, client);
    const input = await screen.findByRole("textbox", { name: "CSV contents" });
    const contents =
      "facilityResidentId,name,roomLabel,areaName\nRACE-1,Synthetic First,991,North wing";
    await user.type(input, contents);
    await user.click(screen.getByRole("button", { name: "Review roster" }));
    expect(input).toBeDisabled();
    expect(
      screen.getByRole("combobox", { name: "Room column" }),
    ).toBeDisabled();
    await user.type(input, "changed");
    expect(input).toHaveValue(contents);
    finish!();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Apply reviewed roster" }),
      ).toBeEnabled(),
    );
    expect(screen.getByText("Synthetic First")).toBeVisible();
    expect(input).toBeEnabled();
  });

  it("saves manually sourced context as a new record needing review", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient();
    await client.enterAdminSimulation();
    mount(<ResidentAdministration residentId="res_7f3a1c" />, client);
    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Context category" }),
      "preference",
    );
    await user.type(
      screen.getByRole("textbox", { name: /Context detail/ }),
      "Synthetic preference for a quiet explanation.",
    );
    await user.type(
      screen.getByRole("textbox", { name: /Source description/ }),
      "Synthetic resident interview",
    );
    await user.type(
      screen.getByLabelText("Source date (optional)"),
      "2026-10-20",
    );
    const expiry = screen.getByLabelText("Context expires (optional)");
    expect(expiry).toHaveAttribute("type", "datetime-local");
    fireEvent.change(expiry, { target: { value: "2026-10-23T15:00" } });
    await user.click(
      screen.getByRole("button", { name: "Save context for review" }),
    );
    expect(
      await screen.findByText(
        "Context saved in this demo. Review is still needed; no clinical plan or notification policy was changed.",
      ),
    ).toBeVisible();
    const saved = (await client.snapshot()).contexts.find(
      (item) => item.text === "Synthetic preference for a quiet explanation.",
    );
    expect(saved).toMatchObject({
      category: "preference",
      reviewStatus: "needs_review",
      source: "Synthetic resident interview · source date 2026-10-20",
      effectiveUntil: "2026-10-23T20:00:00.000Z",
    });
    expect(
      screen.getByText("Notification policy is not connected"),
    ).toBeVisible();
  });

  it("does not expose resident administration or context outside station coverage", async () => {
    const client = new DemoWorkspaceClient({ clientId: "demo_phone_02" });
    await client.enterAdminSimulation();
    mount(<ResidentAdministration residentId="res_d0e519" />, client);
    expect(
      await screen.findByText("Resident administration is unavailable"),
    ).toBeVisible();
    expect(screen.queryByText("Ruth Palmer")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save context for review" }),
    ).not.toBeInTheDocument();
  });

  it("adds a correction without replacing its original source record", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient();
    await client.enterAdminSimulation();
    const prior = (await client.snapshot()).contexts.find(
      (item) => item.residentId === "res_7f3a1c",
    )!;
    mount(<ResidentAdministration residentId="res_7f3a1c" />, client);
    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Context category" }),
      "correction",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: /^Record to correct/ }),
      prior.contextId,
    );
    await user.type(
      screen.getByRole("textbox", { name: /Context detail/ }),
      "Synthetic correction awaiting confirmation.",
    );
    await user.type(
      screen.getByRole("textbox", { name: /Source description/ }),
      "Synthetic administrator report",
    );
    await user.click(
      screen.getByRole("button", { name: "Save context for review" }),
    );
    await screen.findByText(
      "Context saved in this demo. Review is still needed; no clinical plan or notification policy was changed.",
    );
    const contexts = (await client.snapshot()).contexts;
    expect(contexts.find((item) => item.contextId === prior.contextId)).toEqual(
      prior,
    );
    expect(
      contexts.find(
        (item) => item.text === "Synthetic correction awaiting confirmation.",
      ),
    ).toMatchObject({
      supersedesContextId: prior.contextId,
      reviewStatus: "needs_review",
    });
  });

  it("locks facility draft fields until their pending save finishes", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient();
    await client.enterAdminSimulation();
    let finish: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      finish = resolve;
    });
    const original = client.updateFacility.bind(client);
    vi.spyOn(client, "updateFacility").mockImplementation(async (...args) => {
      await gate;
      return original(...args);
    });
    mount(<FacilityAdmin />, client);
    const name = await screen.findByRole("textbox", { name: /^Facility name/ });
    await user.clear(name);
    await user.type(name, "Saved facility draft");
    await user.click(screen.getByRole("button", { name: "Save facility" }));
    expect(name).toBeDisabled();
    expect(
      screen.getByRole("combobox", { name: /^Facility time zone/ }),
    ).toBeDisabled();
    await user.type(name, " later draft");
    expect(name).toHaveValue("Saved facility draft");
    finish!();
    await screen.findByText("Facility details saved in this demo.");
    expect((await client.snapshot()).facility.name).toBe(
      "Saved facility draft",
    );
    expect(name).toBeEnabled();
  });

  it("locks station naming and coverage controls until their pending save finishes", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient();
    await client.enterAdminSimulation();
    const before = await client.snapshot();
    let finish: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      finish = resolve;
    });
    const original = client.updateClient.bind(client);
    vi.spyOn(client, "updateClient").mockImplementation(async (...args) => {
      await gate;
      return original(...args);
    });
    mount(<StationSettings />, client);
    const article = await screen.findByRole("article", {
      name: `Station ${before.currentClient.name}`,
    });
    const name = within(article).getByRole("textbox", {
      name: /^Station name:/,
    });
    await user.clear(name);
    await user.type(name, "Saved station draft");
    await user.click(
      within(article).getByRole("button", { name: "Save station changes" }),
    );
    expect(name).toBeDisabled();
    for (const box of within(article).getAllByRole("checkbox"))
      expect(box).toBeDisabled();
    await user.type(name, " later draft");
    expect(name).toHaveValue("Saved station draft");
    finish!();
    await screen.findByText("Station settings saved.");
    expect((await client.snapshot()).currentClient.name).toBe(
      "Saved station draft",
    );
    expect(name).toBeEnabled();
  });

  it("records a resident departure using the facility local date and time", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient({
      now: () => new Date("2026-10-21T20:00:00Z"),
    });
    await client.enterAdminSimulation();
    mount(<FacilityAdmin />, client);
    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Resident record" }),
      "res_7f3a1c",
    );
    fireEvent.change(screen.getByLabelText(/^Assignment date and time/), {
      target: { value: "2026-10-21T09:00" },
    });
    const departure = screen.getByLabelText(
      "Departure date and time (optional)",
    );
    expect(departure).toHaveAttribute("type", "datetime-local");
    fireEvent.change(departure, { target: { value: "2026-10-21T10:00" } });
    await user.click(
      screen.getByRole("button", { name: "Save resident record" }),
    );
    await screen.findByText(
      "Resident record saved in this demo. Assignment history is retained.",
    );
    const after = await client.snapshot();
    expect(
      after.profiles.find((item) => item.residentId === "res_7f3a1c")
        ?.departedAt,
    ).toBe("2026-10-21T15:00:00.000Z");
    expect(
      after.residents.some((item) => item.residentId === "res_7f3a1c"),
    ).toBe(false);
  });

  it("requires the chosen repeated local expiration before context can save", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient();
    await client.enterAdminSimulation();
    mount(<ResidentAdministration residentId="res_7f3a1c" />, client);
    await user.type(
      await screen.findByRole("textbox", { name: /Context detail/ }),
      "Synthetic time-limited context.",
    );
    await user.type(
      screen.getByRole("textbox", { name: /Source description/ }),
      "Synthetic context example",
    );
    fireEvent.change(screen.getByLabelText("Context expires (optional)"), {
      target: { value: "2026-11-01T01:30" },
    });
    expect(
      screen.getByRole("radio", { name: /First occurrence/ }),
    ).toBeVisible();
    expect(
      screen.getByRole("radio", { name: /Second occurrence/ }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Save context for review" }),
    );
    await waitFor(async () =>
      expect(
        (await client.snapshot()).contexts.some(
          (item) => item.text === "Synthetic time-limited context.",
        ),
      ).toBe(false),
    );
    await user.click(screen.getByRole("radio", { name: /Second occurrence/ }));
    await user.click(
      screen.getByRole("button", { name: "Save context for review" }),
    );
    await screen.findByText(
      "Context saved in this demo. Review is still needed; no clinical plan or notification policy was changed.",
    );
    expect(
      (await client.snapshot()).contexts.find(
        (item) => item.text === "Synthetic time-limited context.",
      )?.effectiveUntil,
    ).toBe("2026-11-01T07:30:00.000Z");
  });

  it("approves a view-only station by default without granting response actions", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient();
    await client.enterAdminSimulation();
    const before = await client.snapshot();
    mount(<StationSettings />, client);
    await user.type(
      await screen.findByRole("textbox", { name: /^New station name/ }),
      "Directory display",
    );
    const coverage = screen.getByRole("group", {
      name: "Coverage for the new station",
    });
    await user.click(
      within(coverage).getByRole("checkbox", { name: before.areas[0].name }),
    );
    const actions = screen.getByRole("group", {
      name: "Permitted actions for the new station",
    });
    expect(within(actions).getAllByRole("checkbox")).toHaveLength(6);
    for (const checkbox of within(actions).getAllByRole("checkbox"))
      expect(checkbox).not.toBeChecked();
    await user.click(
      screen.getByRole("button", { name: "Approve demo station" }),
    );
    await screen.findByText("Shared station approved in this demo.");
    const station = (await client.snapshot()).clients.find(
      (item) => item.name === "Directory display",
    )!;
    expect(station.permissions).toEqual([]);
    expect(station.areaIds).toEqual([before.areas[0].areaId]);
    await client.selectDemoClient(station.clientId);
    expect((await client.snapshot()).residents.length).toBeGreaterThan(0);
    await expect(
      client.acknowledgeEvent("evt_unusual_movement_102"),
    ).rejects.toThrow(/permission|permitted|allowed/i);
  });

  it("reduces action permissions without changing the station name or coverage", async () => {
    const user = userEvent.setup();
    const client = new DemoWorkspaceClient();
    await client.enterAdminSimulation();
    const before = await client.snapshot();
    mount(<StationSettings />, client);
    const station = await screen.findByRole("article", {
      name: `Station ${before.currentClient.name}`,
    });
    const actions = within(station).getByRole("group", {
      name: `Permitted actions: ${before.currentClient.name}`,
    });
    for (const checkbox of within(actions).getAllByRole("checkbox")) {
      if (
        (checkbox as HTMLInputElement).checked &&
        checkbox.parentElement?.textContent !== "Acknowledge concerns"
      )
        await user.click(checkbox);
    }
    await user.click(
      within(station).getByRole("button", { name: "Save station changes" }),
    );
    await screen.findByText("Station settings saved.");
    const after = await client.snapshot();
    expect(after.currentClient.permissions).toEqual(["acknowledge"]);
    expect(after.currentClient.name).toBe(before.currentClient.name);
    expect(after.currentClient.areaIds).toEqual(before.currentClient.areaIds);
    expect(after.residents).toHaveLength(before.residents.length);
    await client.acknowledgeEvent("evt_unusual_movement_102");
    await expect(
      client.recordCheck("evt_unusual_movement_102", {
        outcome: "no_concern_observed",
      }),
    ).rejects.toThrow(/permission|permitted|allowed/i);
  });

  it("preserves a station draft but requires current settings to be loaded after another tab reduces permissions", async () => {
    const user = userEvent.setup();
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => {
        values.set(key, value);
      },
    };
    const client = new DemoWorkspaceClient({ storage });
    const otherTab = new DemoWorkspaceClient({ storage });
    await client.enterAdminSimulation();
    await otherTab.enterAdminSimulation();
    const before = (await client.snapshot()).currentClient;
    mount(<StationSettings />, client);
    const station = await screen.findByRole("article", {
      name: `Station ${before.name}`,
    });
    const name = within(station).getByRole("textbox", {
      name: /^Station name:/,
    });
    await user.clear(name);
    await user.type(name, "Unsaved station rename");

    await otherTab.updateClient({ ...before, permissions: ["acknowledge"] });
    fireEvent.focus(window);
    const reload = await within(station).findByRole("button", {
      name: "Load current station settings",
    });
    expect(within(station).getByText(/Station settings changed/)).toBeVisible();
    expect(name).toHaveValue("Unsaved station rename");
    expect(
      within(station).getByRole("button", { name: "Save station changes" }),
    ).toBeDisabled();
    expect((await client.snapshot()).currentClient.permissions).toEqual([
      "acknowledge",
    ]);

    await user.click(reload);
    expect(name).toHaveValue(before.name);
    expect(
      within(station).getByRole("checkbox", { name: "Acknowledge concerns" }),
    ).toBeChecked();
    expect(
      within(station).getByRole("checkbox", { name: "Record resident checks" }),
    ).not.toBeChecked();
    await user.clear(name);
    await user.type(name, "Reviewed station rename");
    await user.click(
      within(station).getByRole("button", { name: "Save station changes" }),
    );
    await within(station).findByText("Station settings saved.");
    expect((await client.snapshot()).currentClient).toMatchObject({
      name: "Reviewed station rename",
      areaIds: before.areaIds,
      permissions: ["acknowledge"],
    });
    expect(
      within(station).queryByRole("button", {
        name: "Load current station settings",
      }),
    ).not.toBeInTheDocument();
  });

  it("rejects a stale station save if another tab changes permissions while saving", async () => {
    const user = userEvent.setup();
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => {
        values.set(key, value);
      },
    };
    const client = new DemoWorkspaceClient({ storage });
    const otherTab = new DemoWorkspaceClient({ storage });
    await client.enterAdminSimulation();
    await otherTab.enterAdminSimulation();
    const before = (await client.snapshot()).currentClient;
    let finish: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      finish = resolve;
    });
    const original = client.updateClient.bind(client);
    vi.spyOn(client, "updateClient").mockImplementation(async (...args) => {
      await gate;
      return original(...args);
    });
    mount(<StationSettings />, client);
    const station = await screen.findByRole("article", {
      name: `Station ${before.name}`,
    });
    const name = within(station).getByRole("textbox", {
      name: /^Station name:/,
    });
    await user.clear(name);
    await user.type(name, "Stale station rename");
    await user.click(
      within(station).getByRole("button", { name: "Save station changes" }),
    );
    await otherTab.updateClient({ ...before, permissions: [] });
    finish!();

    expect(await within(station).findByRole("alert")).toHaveTextContent(
      /Station settings changed/,
    );
    expect(name).toHaveValue("Stale station rename");
    expect((await client.snapshot()).currentClient).toMatchObject({
      name: before.name,
      areaIds: before.areaIds,
      permissions: [],
    });
    expect(
      within(station).queryByText("Station settings saved."),
    ).not.toBeInTheDocument();
    await user.click(
      within(station).getByRole("button", {
        name: "Load current station settings",
      }),
    );
    expect(name).toHaveValue(before.name);
    for (const checkbox of within(station)
      .getByRole("group", { name: `Permitted actions: ${before.name}` })
      .querySelectorAll("input"))
      expect(checkbox).not.toBeChecked();
  });
});
