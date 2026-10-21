import type { ClinicDevice, ClinicDeviceStatus } from "@/lib/monitoring";
import type { StatusTone } from "@/components/status-pill/status-pill";

export const deviceStatusPresentation: Record<ClinicDeviceStatus, { label: string; tone: StatusTone }> = {
  online: { label: "Online", tone: "healthy" },
  degraded: { label: "Limited", tone: "attention" },
  offline: { label: "Offline", tone: "unavailable" },
  buffering: { label: "Buffering", tone: "attention" },
  retrying: { label: "Retrying", tone: "attention" },
  unavailable: { label: "Not set up", tone: "unavailable" },
};

export const sourceTone: Record<ClinicDevice["sources"][number]["status"], StatusTone> = {
  available: "healthy",
  limited: "attention",
  unavailable: "unavailable",
};

export const sourceStatusLabel: Record<ClinicDevice["sources"][number]["status"], string> = {
  available: "Available",
  limited: "Limited",
  unavailable: "Unavailable",
};

export function formatTimestamp(value: string | null, timeZone?: string): string {
  if (!value || !Number.isFinite(Date.parse(value))) return "No update yet";
  return new Intl.DateTimeFormat("en-US", {
    timeZone,
    timeZoneName: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function availabilityLabel(value: ClinicDevice["health"]["dataAvailability"]): string {
  return {
    available: "Available",
    limited: "Limited",
    unavailable: "Unavailable",
    not_yet_available: "Not available yet",
  }[value];
}

export function setupLabel(value: ClinicDevice["setup"]["state"]): string {
  return {
    ready: "Setup ready",
    calibrating: "Calibrating",
    needs_attention: "Setup check needed",
    not_started: "Setup not started",
  }[value];
}
