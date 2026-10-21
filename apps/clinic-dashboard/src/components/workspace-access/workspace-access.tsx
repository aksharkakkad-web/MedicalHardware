"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useWorkspace } from "@/lib/workspace";
import { DeviceList } from "@/features/devices/device-list";
import { MonitoringSetup } from "@/features/setup/monitoring-setup";
import { DeviceDetail } from "@/features/devices/device-detail";
import styles from "./workspace-access.module.css";

/** UI route guard for the synthetic client. Production authorization belongs on the server. */
export function WorkspaceAccess({
  residentId,
  requireAdmin = false,
  legacySetup = false,
  children,
}: {
  residentId?: string;
  requireAdmin?: boolean;
  legacySetup?: boolean;
  children: ReactNode;
}) {
  const { snapshot, status } = useWorkspace();
  if (status === "loading") return <p role="status">Loading shared access…</p>;
  if (
    !snapshot ||
    status === "error" ||
    snapshot.currentClient.status !== "approved" ||
    (residentId &&
      !snapshot.profiles.some((profile) => profile.residentId === residentId))
  ) {
    return (
      <section className={styles.state} role="alert">
        <h1>This record is unavailable</h1>
        <p>
          It may be outside this shared device’s coverage. Return to the
          workspace or ask an administrator to review access.
        </p>
        <Link href="/">Return to overview</Link>
      </section>
    );
  }
  if (requireAdmin && !snapshot.admin.active)
    return (
      <section className={styles.state}>
        <h1>Administration is required</h1>
        <p>
          Room setup and notification configuration affect shared monitoring.
          Open administration to review these settings.
        </p>
        <Link href="/administration">Open administration</Link>
        <p className={styles.note}>
          This demonstration simulates administrator access. It does not provide
          real sign-in or server authorization.
        </p>
      </section>
    );
  if (
    legacySetup &&
    residentId &&
    (snapshot.profiles.find((profile) => profile.residentId === residentId)
      ?.departedAt ||
      snapshot.assignmentHistory.some(
        (item) =>
          item.residentId === residentId && item.fromRoomId !== item.toRoomId,
      ))
  )
    return (
      <section className={styles.state} role="alert">
        <h1>Current setup is unavailable</h1>
        <p>
          The new assignment needs monitoring validation. Previous room
          calibration cannot establish readiness for this assignment.
        </p>
        <Link href={`/residents/${residentId}`}>Return to resident record</Link>
      </section>
    );
  return children;
}

export function ScopedDeviceList() {
  const { snapshot } = useWorkspace();
  return (
    <WorkspaceAccess>
      <DeviceList
        timeZone={snapshot?.facility.timeZone}
        authorizedResidentIds={
          snapshot?.residents
            .filter((resident) => resident.assignmentStatus === "active")
            .map((resident) => resident.residentId) ?? []
        }
      />
    </WorkspaceAccess>
  );
}
export function ScopedDeviceDetail({ deviceId }: { deviceId: string }) {
  const { snapshot } = useWorkspace();
  return (
    <WorkspaceAccess>
      <DeviceDetail
        deviceId={deviceId}
        timeZone={snapshot?.facility.timeZone}
        authorizedResidentIds={
          snapshot?.residents
            .filter((resident) => resident.assignmentStatus === "active")
            .map((resident) => resident.residentId) ?? []
        }
      />
    </WorkspaceAccess>
  );
}

export function ScopedMonitoringSetup({ residentId }: { residentId: string }) {
  const { snapshot } = useWorkspace();
  return (
    <WorkspaceAccess residentId={residentId} requireAdmin legacySetup>
      <MonitoringSetup
        residentId={residentId}
        timeZone={snapshot?.facility.timeZone}
      />
    </WorkspaceAccess>
  );
}
