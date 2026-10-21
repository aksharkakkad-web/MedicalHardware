import type {
  MonitoringEventDetail,
  ResidentOverviewItem,
} from "@/lib/monitoring";
import type {
  CheckOutcome,
  ResidentMeasurement,
  ResidentProfile,
} from "@/lib/workspace/types";

const priorityOrder = { critical: 0, high: 1, watch: 2 };
export function concernQueue(
  events: MonitoringEventDetail[],
  profiles: ResidentProfile[],
  areaId: string,
): MonitoringEventDetail[] {
  return events
    .filter(
      (event) =>
        event.status !== "resolved" &&
        (areaId === "all" ||
          event.priority === "high" ||
          event.priority === "critical" ||
          profiles.some(
            (profile) =>
              profile.residentId === event.resident.residentId &&
              profile.areaId === areaId,
          )),
    )
    .sort(
      (a, b) =>
        priorityOrder[a.priority] - priorityOrder[b.priority] ||
        Date.parse(a.createdAt) - Date.parse(b.createdAt),
    );
}
export function readingIsAvailable(
  measurement: ResidentMeasurement,
  resident?: ResidentOverviewItem,
): boolean {
  return (
    measurement.value !== null &&
    Number.isFinite(measurement.value) &&
    measurement.observedAt !== null &&
    measurement.quality !== "unavailable" &&
    measurement.attribution === "eligible" &&
    resident?.assignmentStatus === "active" &&
    (resident.monitoring.state === "active" ||
      resident.monitoring.state === "limited")
  );
}
export function careTime(timestamp: string | null, timeZone: string): string {
  if (!timestamp || !Number.isFinite(Date.parse(timestamp)))
    return "Time unavailable";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone,
    timeZoneName: "short",
  }).format(new Date(timestamp));
}
export const outcomeLabels: Record<CheckOutcome, string> = {
  no_concern_observed: "Checked · no concern observed",
  concern_remains: "Checked · concern remains",
  assistance_requested: "Checked · assistance requested",
  unable_to_check: "Could not complete a check",
  information_needs_review: "Room or monitoring information needs review",
  other: "Another outcome",
};
export const eventStateLabels = {
  detected: "Analysis pending",
  open: "Not acknowledged",
  acknowledged: "Acknowledged · check pending",
  checked: "Check recorded · still open",
  resolved: "Resolved",
};
export function residentName(
  profiles: ResidentProfile[],
  residentId: string,
  fallback: string,
): string {
  return (
    profiles.find((profile) => profile.residentId === residentId)?.name ??
    fallback
  );
}

export function isCareInstant(value: string): boolean {
  return (
    /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value))
  );
}
