import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "./app-shell";
let pathname = "/";
const selectArea = vi.fn().mockResolvedValue(undefined);
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
vi.mock("@/lib/workspace", () => ({
  useWorkspace: () => ({
    snapshot: {
      facility: { name: "Maplewood Residence" },
      areas: [
        { areaId: "west", name: "West wing" },
        { areaId: "east", name: "East wing" },
        { areaId: "private", name: "Unapproved wing" },
      ],
      currentAreaId: "west",
      currentClient: {
        name: "West station",
        areaIds: ["west", "east"],
        status: "approved",
      },
      admin: { active: false },
      mode: "demo",
    },
    status: "ready",
    client: { setCurrentArea: selectArea },
  }),
}));
describe("SYREN staff shell", () => {
  beforeEach(() => {
    pathname = "/";
    vi.clearAllMocks();
  });
  it("identifies the shared workspace without personal staff sign in", () => {
    render(
      <AppShell>
        <p>Care content</p>
      </AppShell>,
    );
    expect(screen.getByText("SYREN")).toBeVisible();
    expect(screen.getByText("Maplewood Residence")).toBeVisible();
    expect(screen.getByText("West station")).toBeVisible();
    expect(screen.getByText("Synthetic residents")).toBeVisible();
    expect(screen.getByRole("main")).toHaveTextContent("Care content");
    expect(screen.queryByText("Northstar Clinic")).not.toBeInTheDocument();
    expect(screen.queryByText("Sign in")).not.toBeInTheDocument();
  });
  it("offers only authorized area choices", async () => {
    render(
      <AppShell>
        <p>Care content</p>
      </AppShell>,
    );
    const area = screen.getByRole("combobox", { name: /monitoring area/i });
    expect(
      screen.queryByRole("option", { name: "Unapproved wing" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "All covered areas" }),
    ).toHaveValue("all");
    await userEvent.selectOptions(area, "east");
    expect(selectArea).toHaveBeenCalledWith("east");
  });
  it("links the care workflows and administrative entry", () => {
    render(
      <AppShell>
        <p>Care content</p>
      </AppShell>,
    );
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Residents" })).toHaveAttribute(
      "href",
      "/residents",
    );
    expect(screen.getByRole("link", { name: "Handover" })).toHaveAttribute(
      "href",
      "/handover",
    );
    expect(screen.getByRole("link", { name: "Events" })).toHaveAttribute(
      "href",
      "/events",
    );
    expect(
      screen.getByRole("link", { name: /administration/i }),
    ).toHaveAttribute("href", "/administration");
  });
  it("exposes keyboard access directly to the workspace", () => {
    render(
      <AppShell>
        <p>Care content</p>
      </AppShell>,
    );
    expect(
      screen.getByRole("link", { name: /skip to workspace/i }),
    ).toHaveAttribute("href", "#care-workspace");
    expect(screen.getByRole("main")).toHaveAttribute("id", "care-workspace");
  });
  it.each(["/design-system", "/design-system/colors"])(
    "keeps %s specimens outside the product shell",
    (path) => {
      pathname = path;
      render(
        <AppShell>
          <main>Specimens</main>
        </AppShell>,
      );
      expect(screen.getAllByRole("main")).toHaveLength(1);
      expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    },
  );
  it("identifies the current section on nested routes", () => {
    pathname = "/residents/res_demo";
    render(
      <AppShell>
        <p>Resident</p>
      </AppShell>,
    );
    expect(screen.getByRole("link", { name: "Residents" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveAttribute(
      "aria-current",
    );
  });
});
