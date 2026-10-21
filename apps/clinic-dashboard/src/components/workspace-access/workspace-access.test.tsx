import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  WorkspaceAccess,
  ScopedDeviceList,
  ScopedDeviceDetail,
} from "./workspace-access";
vi.mock("@/features/devices/device-list", () => ({
  DeviceList: ({
    authorizedResidentIds,
  }: {
    authorizedResidentIds: string[];
  }) => <p>Visible rooms: {authorizedResidentIds.join(", ")}</p>,
}));
vi.mock("@/features/devices/device-detail", () => ({
  DeviceDetail: ({
    authorizedResidentIds,
  }: {
    authorizedResidentIds: string[];
  }) => <p>Visible rooms: {authorizedResidentIds.join(", ")}</p>,
}));
let admin = false;
let status = "ready";
let moved = false;
vi.mock("@/lib/workspace", () => ({
  useWorkspace: () => ({
    status,
    snapshot: {
      admin: { active: admin },
      facility: { timeZone: "America/Chicago" },
      profiles: [
        { residentId: "authorized" },
        { residentId: "transferred" },
        { residentId: "departed" },
      ],
      residents: [
        { residentId: "authorized", assignmentStatus: "active" },
        { residentId: "transferred", assignmentStatus: "missing" },
      ],
      assignmentHistory: moved
        ? [{ residentId: "authorized", fromRoomId: "old", toRoomId: "new" }]
        : [],
      currentClient: { status: "approved" },
    },
  }),
}));
describe("legacy route workspace access", () => {
  beforeEach(() => {
    admin = false;
    status = "ready";
    moved = false;
  });
  it.each(["list", "detail"])(
    "keeps historical assignments out of the current device %s",
    (view) => {
      render(
        view === "list" ? (
          <ScopedDeviceList />
        ) : (
          <ScopedDeviceDetail deviceId="room-unit" />
        ),
      );
      expect(screen.getByText("Visible rooms: authorized")).toBeVisible();
      expect(
        screen.queryByText(
          /Visible rooms:.*transferred|Visible rooms:.*departed/,
        ),
      ).not.toBeInTheDocument();
    },
  );
  it("does not mount content for an out-of-coverage resident", () => {
    render(
      <WorkspaceAccess residentId="elsewhere">
        <p>Private resident data</p>
      </WorkspaceAccess>,
    );
    expect(screen.queryByText("Private resident data")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "outside this shared device’s coverage",
    );
  });
  it("requires administration for setup changes while ordinary care stays accessible", () => {
    render(
      <WorkspaceAccess residentId="authorized" requireAdmin>
        <p>Setup editor</p>
      </WorkspaceAccess>,
    );
    expect(screen.queryByText("Setup editor")).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open administration" }),
    ).toHaveAttribute("href", "/administration");
  });
  it("does not show old setup readiness after a room transfer", () => {
    admin = true;
    moved = true;
    render(
      <WorkspaceAccess residentId="authorized" requireAdmin legacySetup>
        <p>Established calibration</p>
      </WorkspaceAccess>,
    );
    expect(
      screen.queryByText("Established calibration"),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "new assignment needs monitoring validation",
    );
  });
  it("allows an authorized simulated administrator", () => {
    admin = true;
    render(
      <WorkspaceAccess residentId="authorized" requireAdmin>
        <p>Setup editor</p>
      </WorkspaceAccess>,
    );
    expect(screen.getByText("Setup editor")).toBeVisible();
  });
  it("does not mount content before scope is available", () => {
    status = "loading";
    render(
      <WorkspaceAccess>
        <p>Care content</p>
      </WorkspaceAccess>,
    );
    expect(screen.queryByText("Care content")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading shared access",
    );
  });
});
