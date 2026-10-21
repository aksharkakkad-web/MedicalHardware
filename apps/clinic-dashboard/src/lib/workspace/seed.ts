import { WORKSPACE_PERMISSIONS } from "./permissions";
import type {
  CareArea,
  ContextRecord,
  Facility,
  FollowUp,
  ResidentProfile,
  SharedClient,
} from "./types";
export const coreResidentIds = [
  "res_7f3a1c",
  "res_2c8d4f",
  "res_91be60",
  "res_4ab783",
  "res_d0e519",
  "res_assignment_review",
];
const roomIds = [
  "room_b14e2d",
  "room_6a91c3",
  "room_3d72ab",
  "room_85cd20",
  "room_1f64b8",
  "assignment_conflict",
];
const names = [
  "Evelyn Brooks",
  "Arthur Chen",
  "Miriam Ellis",
  "Daniel Ortiz",
  "Ruth Palmer",
  "Joan Wallace",
];
export function seedWorkspace(at: string) {
  const facility: Facility = {
    facilityId: "demo_maplewood",
    name: "Maplewood Residence",
    timeZone: "America/Chicago",
    coverageContact: "Shared station · follow facility coverage procedure",
    escalationContact: "Charge team · use the facility-approved contact route",
  };
  const areas: CareArea[] = [
    {
      areaId: "area_north",
      name: "North wing",
      roomIds: roomIds.slice(0, 3),
    },
    {
      areaId: "area_garden",
      name: "Garden wing",
      roomIds: roomIds.slice(3),
    },
  ];
  const clients: SharedClient[] = [
    {
      clientId: "demo_station_01",
      name: "Maplewood shared station",
      areaIds: areas.map((a) => a.areaId),
      permissions: [...WORKSPACE_PERMISSIONS],
      configurationVersion: 1,
      status: "approved",
      approvedAt: at,
      notificationStatus: "not_configured",
    },
    {
      clientId: "demo_phone_02",
      name: "North shared phone",
      areaIds: ["area_north"],
      permissions: WORKSPACE_PERMISSIONS.filter(
        (permission) => permission !== "resolve_concern",
      ),
      configurationVersion: 1,
      status: "approved",
      approvedAt: at,
      notificationStatus: "not_configured",
    },
  ];
  const profiles: ResidentProfile[] = coreResidentIds.map(
    (residentId, index) => ({
      residentId,
      name: names[index],
      facilityResidentId: `DEMO-${101 + index}`,
      areaId: index < 3 ? "area_north" : "area_garden",
      roomId: roomIds[index],
      roomLabel: index === 5 ? "Assignment review" : `Room ${101 + index}`,
      admittedAt: "2026-09-01T14:00:00Z",
      departedAt: null,
      assignmentEffectiveAt: "2026-10-01T14:00:00Z",
      synthetic: true,
    }),
  );
  const contexts: ContextRecord[] = [
    {
      contextId: "ctx_preference_a",
      residentId: coreResidentIds[0],
      category: "preference",
      text: "Prefers a brief explanation before a routine room check.",
      source: "Synthetic resident preference interview",
      recordedAt: "2026-10-18T15:00:00Z",
      effectiveUntil: null,
      reviewStatus: "demo_reviewed",
      supersedesContextId: null,
    },
    {
      contextId: "ctx_routine_b",
      residentId: coreResidentIds[1],
      category: "preference",
      text: "Usually attends the afternoon activity group; confirm current circumstances with the resident.",
      source: "Synthetic care-team handover",
      recordedAt: "2026-10-19T15:00:00Z",
      effectiveUntil: null,
      reviewStatus: "demo_reviewed",
      supersedesContextId: null,
    },
    {
      contextId: "ctx_hospice_e",
      residentId: coreResidentIds[4],
      category: "hospice",
      text: "Synthetic hospice context: comfort goals reviewed in this demonstration. Responsible service: Maple Hospice (fictional). Contact through the facility charge team. This context does not suppress notifications or establish treatment orders.",
      source: "Synthetic care plan example · no real clinical authorization",
      recordedAt: "2026-10-20T15:00:00Z",
      effectiveUntil: null,
      reviewStatus: "demo_reviewed",
      supersedesContextId: null,
    },
  ];
  const followUps: FollowUp[] = [
    {
      followUpId: "followup_device_105",
      residentId: coreResidentIds[4],
      eventId: "evt_device_issue_105",
      text: "Check the room monitoring gap with the charge team and confirm alternate observation coverage.",
      createdAt: at,
      dueAt: null,
      status: "open",
      completionNote: null,
      completedAt: null,
      clientLabel: "Synthetic handover example",
    },
  ];
  return {
    facility,
    areas,
    clients,
    profiles,
    contexts,
    followUps,
  };
}
