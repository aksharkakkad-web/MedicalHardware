import {
  HOME_SCHEMA_VERSION,
  type HomeOverviewResponse,
  type HomeRoutinesResponse,
  type HomeUpdateDetail,
} from "@/lib/home-monitoring";

export const HOME_UPDATE_ID = "home_evt_unusual_001";

export const homeOverviewFixture: HomeOverviewResponse = {
  schemaVersion: HOME_SCHEMA_VERSION,
  generatedAt: "2026-08-28T17:42:00.000Z",
  lovedOne: {
    id: "demo_loved_one_001",
    displayLabel: "Demo loved one",
    status: {
      state: "steady",
      headline: "Monitoring looks steady",
      summary: "Your loved one is home. No important changes have been noticed in this synthetic demo.",
      lastUpdatedAt: "2026-08-28T17:42:00.000Z",
    },
    trends: [
      {
        trendId: "movement_routine",
        label: "Movement routine",
        direction: "steady",
        headline: "Close to their usual pattern",
        summary: "Today has followed a similar rhythm to recent days.",
        points: [42, 44, 43, 46, 45, 47, 46],
      },
      {
        trendId: "resting_pattern",
        label: "Resting pattern",
        direction: "steady",
        headline: "No meaningful change noticed",
        summary: "Rest periods look similar to their recent routine.",
        points: [52, 51, 53, 52, 54, 53, 53],
      },
      {
        trendId: "time_at_home",
        label: "Time at home",
        direction: "steady",
        headline: "Home today",
        summary: "The home has appeared occupied through the afternoon.",
        points: [38, 38, 39, 39, 40, 40, 40],
      },
    ],
    importantUpdate: {
      eventId: HOME_UPDATE_ID,
      headline: "An unusual movement pattern was noticed",
      summary: "It lasted briefly this morning and has not repeated.",
      occurredAt: "2026-08-28T14:18:00.000Z",
      importance: "important",
      status: "new",
    },
    recentActivity: [
      { activityId: "activity_1", label: "Monitoring returned to the usual pattern", occurredAt: "2026-08-28T14:24:00.000Z", kind: "status" },
      { activityId: "activity_2", label: "Morning routine observed", occurredAt: "2026-08-28T12:04:00.000Z", kind: "routine" },
      { activityId: "activity_3", label: "Overnight pattern completed", occurredAt: "2026-08-28T10:22:00.000Z", kind: "status" },
    ],
  },
};

export const homeUpdateFixture: HomeUpdateDetail = {
  schemaVersion: HOME_SCHEMA_VERSION,
  eventId: HOME_UPDATE_ID,
  headline: "An unusual movement pattern was noticed",
  summary: "It lasted briefly this morning and has not repeated.",
  occurredAt: "2026-08-28T14:18:00.000Z",
  importance: "important",
  status: "new",
  whatChanged: "Movement was different from the routine usually seen at this time of day.",
  observations: [
    "The change lasted for about four minutes.",
    "The usual movement pattern returned afterward.",
  ],
  limitation: "The system cannot tell the exact cause from this information alone.",
  interpretation: "This is a change worth knowing about, not a diagnosis or proof that something is wrong.",
  checkInSuggestion: "If this feels unusual for your family, a simple check-in may provide helpful context.",
  feedback: null,
};

export const homeRoutinesFixture: HomeRoutinesResponse = {
  schemaVersion: HOME_SCHEMA_VERSION,
  version: 1,
  entries: [
    {
      routineId: "routine_morning_tea",
      description: "Usually makes tea between 7:00 and 8:00 in the morning",
      status: "active",
      createdAt: "2026-08-12T15:00:00.000Z",
      retiredAt: null,
      retirementReason: null,
    },
    {
      routineId: "routine_evening_reading",
      description: "Often reads in the living room after dinner",
      status: "active",
      createdAt: "2026-08-14T18:30:00.000Z",
      retiredAt: null,
      retirementReason: null,
    },
    {
      routineId: "routine_old_lunch",
      description: "Previously ate lunch around noon",
      status: "retired",
      createdAt: "2026-07-05T16:00:00.000Z",
      retiredAt: "2026-08-02T16:00:00.000Z",
      retirementReason: "Lunch time changed",
    },
  ],
};
