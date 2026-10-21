import { describe, expect, it } from "vitest";
import { DemoWorkspaceClient, type WorkspaceStorage } from "./demo-client";
const now = () => new Date("2026-10-21T15:00:00Z");
const eventId = "evt_unusual_movement_102";
function storage(): WorkspaceStorage {
  const data = new Map<string, string>();
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => {
      data.set(key, value);
    },
  };
}
describe("synthetic workspace service", () => {
  it("keeps canonical IDs, fixed observation times and unavailable attribution", async () => {
    let time = now();
    const client = new DemoWorkspaceClient({
      now: () => time,
    });
    const first = await client.snapshot();
    time = new Date("2026-10-22T15:00:00Z");
    const second = await client.snapshot();
    expect(first.residents).toHaveLength(6);
    expect(first.facility.name).toBe("Maplewood Residence");
    expect(first.sourceObservedAt).toBe(second.sourceObservedAt);
    expect(first.measurements).toEqual(second.measurements);
    expect(
      first.measurements
        .filter((m) => m.residentId === "res_4ab783")
        .every((m) => m.value === null),
    ).toBe(true);
    expect(
      first.measurements
        .filter((m) => m.residentId === "res_91be60")
        .every((m) => m.value === null),
    ).toBe(true);
  });
  it("scope cannot expand through an area filter and revoked clients see no records", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    await client.enterAdminSimulation();
    const phone = await client.approveClient({
      name: "North phone",
      areaIds: ["area_north"],
      permissions: ["record_check"],
    });
    await client.selectDemoClient(phone.clientId);
    expect((await client.snapshot()).residents).toHaveLength(3);
    await expect(client.setCurrentArea("area_garden")).rejects.toThrow(
      /coverage/i,
    );
    await expect(
      client.recordCheck("evt_device_issue_105", {
        outcome: "unable_to_check",
      }),
    ).rejects.toThrow(/coverage/i);
    await client.revokeClient(phone.clientId);
    expect((await client.snapshot()).residents).toEqual([]);
    await expect(client.acknowledgeEvent(eventId)).rejects.toThrow(/revoked/i);
  });
  it("admin logout preserves routine station access but blocks administrative mutations", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    await client.enterAdminSimulation();
    await client.leaveAdminSimulation();
    const snapshot = await client.snapshot();
    expect(snapshot.currentClient.status).toBe("approved");
    expect(snapshot.residents).toHaveLength(6);
    await expect(
      client.saveArea({
        name: "New",
      }),
    ).rejects.toThrow(/administration/i);
    await client.acknowledgeEvent(eventId);
    expect(
      (await client.snapshot()).events.find((e) => e.eventId === eventId)
        ?.status,
    ).toBe("acknowledged");
  });
  it("unable-to-check never marks checked and leaves explicit follow-up", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    await client.acknowledgeEvent(eventId);
    const check = await client.recordCheck(eventId, {
      outcome: "unable_to_check",
      note: "",
    });
    const snapshot = await client.snapshot();
    expect(check.completedCheck).toBe(false);
    expect(snapshot.events.find((e) => e.eventId === eventId)?.status).toBe(
      "acknowledged",
    );
    expect(
      snapshot.followUps.some(
        (f) => f.eventId === eventId && f.status === "open",
      ),
    ).toBe(true);
    await expect(
      client.resolveEvent(eventId, {
        outcome: "uncertain",
        actualEventLabel: "Unable to check",
        routine: false,
      }),
    ).rejects.toThrow(/check|follow.up/i);
  });
  it("retries reconcile one check and completed checks remain separate from closure", async () => {
    const saved = storage();
    const first = new DemoWorkspaceClient({
      now,
      storage: saved,
    });
    await first.acknowledgeEvent(eventId, "ack-1");
    const input = {
      outcome: "no_concern_observed" as const,
      requestId: "check-1",
    };
    const one = await first.recordCheck(eventId, input);
    const two = await first.recordCheck(eventId, input);
    expect(two.checkId).toBe(one.checkId);
    const restarted = new DemoWorkspaceClient({
      now,
      storage: saved,
    });
    const snapshot = await restarted.snapshot();
    expect(
      snapshot.checks.filter((c) => c.requestId === "check-1"),
    ).toHaveLength(1);
    expect(snapshot.events.find((e) => e.eventId === eventId)?.status).toBe(
      "checked",
    );
    await restarted.resolveEvent(eventId, {
      outcome: "false_positive",
      actualEventLabel: "Synthetic routine movement",
      routine: false,
      requestId: "close-1",
    });
    const resolved = (await restarted.snapshot()).events.find(
      (e) => e.eventId === eventId,
    );
    await expect(
      restarted.recordCheck(eventId, {
        outcome: "concern_remains",
      }),
    ).rejects.toThrow(/resolved|histor/i);
    expect(
      (await restarted.snapshot()).events.find((e) => e.eventId === eventId),
    ).toEqual(resolved);
  });
  it("conflicting or stale imports change no active records, and duplicate apply is safe", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    await client.enterAdminSimulation();
    const before = (await client.snapshot()).profiles;
    const conflict = await client.previewRosterCsv(
      "facilityResidentId,name,roomLabel,areaName\nX1,New synthetic person,Room 101,North wing",
    );
    expect(conflict.canApply).toBe(false);
    await expect(client.applyRosterImport(conflict.importId)).rejects.toThrow(
      /conflict|review/i,
    );
    expect((await client.snapshot()).profiles).toEqual(before);
    const clean = await client.previewRosterCsv(
      "facilityResidentId,name,roomLabel,areaName\nX2,New synthetic person,Room 110,North wing",
    );
    await client.applyRosterImport(clean.importId);
    await client.applyRosterImport(clean.importId);
    expect(
      (await client.snapshot()).profiles.filter(
        (p) => p.facilityResidentId === "X2",
      ),
    ).toHaveLength(1);
    const stale = await client.previewRosterCsv(
      "facilityResidentId,name,roomLabel,areaName\nX3,Another synthetic person,Room 111,North wing",
    );
    await client.saveArea({
      name: "New area",
    });
    await expect(client.applyRosterImport(stale.importId)).rejects.toThrow(
      /changed|preview/i,
    );
  });
  it("reconciles shared demo storage and reports persistent save failures honestly", async () => {
    const shared = storage();
    const a = new DemoWorkspaceClient({
      now,
      storage: shared,
    });
    const b = new DemoWorkspaceClient({
      now,
      storage: shared,
    });
    await a.acknowledgeEvent(eventId);
    await b.recordCheck(eventId, {
      outcome: "concern_remains",
      requestId: "shared-check",
    });
    expect(
      (await a.snapshot()).events.find((e) => e.eventId === eventId)?.status,
    ).toBe("checked");
    expect((await a.snapshot()).checks).toHaveLength(1);
    const broken = new DemoWorkspaceClient({
      now,
      storage: {
        getItem: () => null,
        setItem: () => {
          throw new Error("disk full");
        },
      },
    });
    await expect(broken.enterAdminSimulation()).rejects.toThrow(
      /save|storage/i,
    );
    expect((await broken.snapshot()).persistence.available).toBe(false);
  });
  it("never reports background test delivery and does not turn observations into approved care", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    const result = await client.testNotifications();
    expect(result).toMatchObject({
      status: "blocked",
      delivered: false,
    });
    const context = await client.addContext("res_7f3a1c", {
      text: "Synthetic correction",
      category: "correction",
    });
    expect(context.reviewStatus).toBe("needs_review");
    await expect(
      client.recordCheck(eventId, {
        outcome: "other",
      }),
    ).rejects.toThrow(/note|explanation/i);
  });
});
describe("workspace preservation and validation", () => {
  it("does not attribute measurements after a room transfer or relabel prior events", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    await client.enterAdminSimulation();
    const profile = (await client.snapshot()).profiles.find(
      (p) => p.residentId === "res_2c8d4f",
    )!;
    await client.saveResident({
      ...profile,
      roomLabel: "Room 110",
      effectiveAt: now().toISOString(),
    });
    const result = await client.snapshot();
    expect(
      result.measurements
        .filter((m) => m.residentId === profile.residentId)
        .every((m) => m.value === null),
    ).toBe(true);
    expect(
      result.events.find((e) => e.eventId === eventId)?.resident.roomLabel,
    ).toBe("Room 102");
    expect(result.assignmentHistory.at(-1)).toMatchObject({
      fromRoomId: "room_6a91c3",
      toRoomId: result.profiles.find(
        (p) => p.residentId === profile.residentId,
      )!.roomId,
    });
  });
  it("keeps unresolved history discoverable when a resident departs", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    await client.enterAdminSimulation();
    const profile = (await client.snapshot()).profiles.find(
      (p) => p.residentId === "res_2c8d4f",
    )!;
    await client.saveResident({
      ...profile,
      departedAt: now().toISOString(),
    });
    const result = await client.snapshot();
    expect(
      result.residents.some((r) => r.residentId === profile.residentId),
    ).toBe(false);
    expect(result.events.some((e) => e.eventId === eventId)).toBe(true);
    expect(
      result.profiles.some((p) => p.residentId === profile.residentId),
    ).toBe(true);
  });
  it("rejects reused request IDs for a different operation", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    await client.acknowledgeEvent(eventId, "same-id");
    await expect(
      client.recordCheck(eventId, {
        outcome: "no_concern_observed",
        requestId: "same-id",
      }),
    ).rejects.toThrow(/identifier/i);
  });
  it("does not claim another outcome or information review completes a resident check", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    await client.acknowledgeEvent(eventId);
    const result = await client.recordCheck(eventId, {
      outcome: "other",
      note: "Synthetic exception, unable to enter room",
    });
    expect(result.completedCheck).toBe(false);
    expect(
      (await client.snapshot()).events.find((e) => e.eventId === eventId)
        ?.status,
    ).toBe("acknowledged");
  });
  it("never overwrites unreadable saved state through a new mutation", async () => {
    let written = false;
    const client = new DemoWorkspaceClient({
      now,
      storage: {
        getItem: () => "{broken",
        setItem: () => {
          written = true;
        },
      },
    });
    await expect(client.enterAdminSimulation()).rejects.toThrow(/read|saved/i);
    expect(written).toBe(false);
  });
  it("finishes follow-up independently and requires explicit resolution", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    await client.acknowledgeEvent(eventId);
    await client.recordCheck(eventId, {
      outcome: "assistance_requested",
    });
    const followUp = (await client.snapshot()).followUps.find(
      (f) => f.eventId === eventId,
    )!;
    await client.handOverFollowUp(
      followUp.followUpId,
      "Charge team to confirm assistance",
    );
    await expect(
      client.resolveEvent(eventId, {
        outcome: "confirmed",
        actualEventLabel: "Synthetic assistance request",
        routine: false,
      }),
    ).rejects.toThrow(/follow.up/i);
    await client.completeFollowUp(
      followUp.followUpId,
      "Synthetic assistance outcome reviewed",
    );
    expect(
      (await client.snapshot()).events.find((e) => e.eventId === eventId)
        ?.status,
    ).toBe("checked");
    await client.resolveEvent(eventId, {
      outcome: "confirmed",
      actualEventLabel: "Synthetic assistance provided",
      routine: false,
    });
    expect(
      (await client.snapshot()).events.find((e) => e.eventId === eventId)
        ?.status,
    ).toBe("resolved");
  });
});
describe("stable synthetic measurement and action identity", () => {
  it("keeps per-resident estimates stable when directory order and station scope change", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    const before = await client.snapshot();
    const resident = before.profiles.find(
      (p) => p.residentId === "res_7f3a1c",
    )!;
    await client.enterAdminSimulation();
    await client.saveResident({
      ...resident,
      name: "Evelyn Brooks (synthetic)",
    });
    const after = await client.snapshot();
    expect(
      after.measurements.filter((m) => m.residentId === resident.residentId),
    ).toEqual(
      before.measurements.filter((m) => m.residentId === resident.residentId),
    );
  });
  it("does not accept a retried acknowledgment after station revocation", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    await client.acknowledgeEvent(eventId, "revoke-retry");
    await client.enterAdminSimulation();
    await client.revokeClient((await client.snapshot()).currentClient.clientId);
    await expect(
      client.acknowledgeEvent(eventId, "revoke-retry"),
    ).rejects.toThrow(/revoked/i);
  });
  it("records shared station attribution and submission time without claiming a named nurse", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    await client.acknowledgeEvent(eventId);
    const snapshot = await client.snapshot();
    const action = snapshot.events
      .find((e) => e.eventId === eventId)
      ?.actionHistory.at(-1);
    expect(action).toMatchObject({
      actorLabel: snapshot.currentClient.name,
      occurredAt: now().toISOString(),
    });
  });
});
describe("demo continuity across read-only restarts", () => {
  it("persists initial source observation time before any staff mutation", async () => {
    const saved = storage();
    const first = new DemoWorkspaceClient({
      now,
      storage: saved,
    });
    const original = await first.snapshot();
    const second = new DemoWorkspaceClient({
      now: () => new Date("2026-10-23T15:00:00Z"),
      storage: saved,
    });
    expect((await second.snapshot()).sourceObservedAt).toBe(
      original.sourceObservedAt,
    );
  });
  it("shows the recorded resolution time and station on feedback as well as workflow history", async () => {
    let time = now();
    const client = new DemoWorkspaceClient({
      now: () => time,
    });
    await client.acknowledgeEvent(eventId);
    await client.recordCheck(eventId, {
      outcome: "no_concern_observed",
    });
    time = new Date("2026-10-21T16:00:00Z");
    await client.resolveEvent(eventId, {
      outcome: "false_positive",
      actualEventLabel: "Synthetic routine",
      routine: false,
    });
    const result = await client.snapshot();
    expect(
      result.events.find((e) => e.eventId === eventId)?.feedback,
    ).toMatchObject({
      createdAt: time.toISOString(),
      submittedBy: result.currentClient.name,
    });
  });
});
describe("storage failures never advance the monitoring lifecycle", () => {
  function writableStorage() {
    const data = new Map<string, string>();
    let fail = false;
    return {
      storage: {
        getItem: (key: string) => data.get(key) ?? null,
        setItem: (key: string, value: string) => {
          if (fail) throw new Error("storage unavailable");
          data.set(key, value);
        },
      },
      setFail: (value: boolean) => {
        fail = value;
      },
    };
  }
  it("keeps acknowledgment open when the journal cannot be saved, then safely retries", async () => {
    const saved = writableStorage();
    const client = new DemoWorkspaceClient({
      now,
      storage: saved.storage,
    });
    saved.setFail(true);
    await expect(
      client.acknowledgeEvent(eventId, "transaction-ack"),
    ).rejects.toThrow(/save/i);
    expect((await client.monitoringClient.getEvent(eventId)).status).toBe(
      "open",
    );
    expect(
      (await client.snapshot()).events.find((e) => e.eventId === eventId)
        ?.status,
    ).toBe("open");
    saved.setFail(false);
    await client.acknowledgeEvent(eventId, "transaction-ack");
    expect(
      (await client.snapshot()).events.find((e) => e.eventId === eventId)
        ?.status,
    ).toBe("acknowledged");
  });
  it("keeps the event acknowledged and publishes no check when the check journal fails", async () => {
    const saved = writableStorage();
    const client = new DemoWorkspaceClient({
      now,
      storage: saved.storage,
    });
    await client.acknowledgeEvent(eventId);
    saved.setFail(true);
    await expect(
      client.recordCheck(eventId, {
        outcome: "no_concern_observed",
        requestId: "transaction-check",
      }),
    ).rejects.toThrow(/save/i);
    expect((await client.monitoringClient.getEvent(eventId)).status).toBe(
      "acknowledged",
    );
    expect((await client.snapshot()).checks).toEqual([]);
    saved.setFail(false);
    await client.recordCheck(eventId, {
      outcome: "no_concern_observed",
      requestId: "transaction-check",
    });
    expect((await client.snapshot()).checks).toHaveLength(1);
  });
  it("keeps the checked concern open and immutable feedback absent when resolution storage fails", async () => {
    const saved = writableStorage();
    const client = new DemoWorkspaceClient({
      now,
      storage: saved.storage,
    });
    await client.acknowledgeEvent(eventId);
    await client.recordCheck(eventId, {
      outcome: "no_concern_observed",
    });
    saved.setFail(true);
    await expect(
      client.resolveEvent(eventId, {
        outcome: "false_positive",
        actualEventLabel: "Synthetic routine",
        routine: false,
        requestId: "transaction-close",
      }),
    ).rejects.toThrow(/save/i);
    const result = await client.monitoringClient.getEvent(eventId);
    expect(result.status).toBe("checked");
    expect(result.feedback).toBeNull();
    saved.setFail(false);
    await client.resolveEvent(eventId, {
      outcome: "false_positive",
      actualEventLabel: "Synthetic routine",
      routine: false,
      requestId: "transaction-close",
    });
    expect(
      (await client.snapshot()).events.find((e) => e.eventId === eventId)
        ?.status,
    ).toBe("resolved");
  });
});
describe("station, assignment and follow-up provenance", () => {
  it("keeps the selected approved demo station after browser restart and logout", async () => {
    const saved = storage();
    const client = new DemoWorkspaceClient({
      now,
      storage: saved,
    });
    await client.enterAdminSimulation();
    await client.selectDemoClient("demo_phone_02");
    await client.leaveAdminSimulation();
    const restarted = new DemoWorkspaceClient({
      now,
      storage: saved,
    });
    expect((await restarted.snapshot()).currentClient.clientId).toBe(
      "demo_phone_02",
    );
    expect((await restarted.snapshot()).residents).toHaveLength(3);
    expect((await restarted.snapshot()).admin.active).toBe(false);
  });
  it("does not collapse different room labels into one stable room identity", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    await client.enterAdminSimulation();
    const first = await client.saveResident({
      name: "Synthetic First",
      facilityResidentId: "COLLISION-1",
      areaId: "area_north",
      roomLabel: "A-1",
    });
    const second = await client.saveResident({
      name: "Synthetic Second",
      facilityResidentId: "COLLISION-2",
      areaId: "area_north",
      roomLabel: "A/1",
    });
    expect(first.roomId).not.toBe(second.roomId);
  });
  it("rejects future departures and impossible calendar dates without removing an occupant", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    await client.enterAdminSimulation();
    const original = (await client.snapshot()).profiles[0];
    await expect(
      client.saveResident({
        ...original,
        departedAt: "2030-01-01T00:00:00Z",
      }),
    ).rejects.toThrow(/future/i);
    await expect(
      client.saveResident({
        ...original,
        effectiveAt: "2026-02-31T00:00:00Z",
      }),
    ).rejects.toThrow(/date|calendar/i);
    expect(
      (await client.snapshot()).residents.some(
        (r) => r.residentId === original.residentId,
      ),
    ).toBe(true);
  });
  it("retains successive handovers when a follow-up is later completed", async () => {
    const client = new DemoWorkspaceClient({
      now,
    });
    const item = await client.addFollowUp({
      residentId: "res_7f3a1c",
      text: "Synthetic follow-up",
    });
    await client.handOverFollowUp(item.followUpId, "First team handover");
    await client.handOverFollowUp(item.followUpId, "Second team handover");
    await client.completeFollowUp(item.followUpId, "Completed after review");
    const current = (await client.snapshot()).followUps.find(
      (f) => f.followUpId === item.followUpId,
    )!;
    expect(current.history?.map((entry) => entry.note)).toEqual([
      "First team handover",
      "Second team handover",
      "Completed after review",
    ]);
  });
});
describe("routine directory metadata scope", () => {
  it("returns only covered room directories and current station metadata outside administration", async () => {
    const client = new DemoWorkspaceClient({
      now,
      clientId: "demo_phone_02",
    });
    const result = await client.snapshot();
    expect(result.areas.map((area) => area.areaId)).toEqual(["area_north"]);
    expect(result.clients.map((station) => station.clientId)).toEqual([
      "demo_phone_02",
    ]);
    await client.enterAdminSimulation();
    expect((await client.snapshot()).areas).toHaveLength(2);
    await client.leaveAdminSimulation();
    expect((await client.snapshot()).areas).toHaveLength(1);
  });
});
