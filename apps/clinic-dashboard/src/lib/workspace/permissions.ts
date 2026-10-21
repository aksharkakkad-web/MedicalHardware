import type { WorkspacePermission, WorkspaceSnapshot } from "./types";

export const WORKSPACE_PERMISSIONS: readonly WorkspacePermission[] = [
  "acknowledge",
  "record_check",
  "resolve_concern",
  "add_follow_up",
  "update_follow_up",
  "report_context",
];

/** Routine grant only. Simulated administration never bypasses clinical action grants. */
export function hasWorkspacePermission(
  snapshot: WorkspaceSnapshot | null,
  permission: WorkspacePermission,
): boolean {
  return (
    snapshot?.currentClient.status === "approved" &&
    Array.isArray(snapshot.currentClient.permissions) &&
    snapshot.currentClient.permissions.includes(permission)
  );
}
