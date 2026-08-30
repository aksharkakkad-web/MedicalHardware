import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

let pathname = "/";

vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

describe("AppShell", () => {
  it("gives the active overview workspace a clear structure", () => {
    render(
      <AppShell>
        <p>Residents content</p>
      </AppShell>,
    );

    expect(
      screen.getByRole("navigation", { name: /clinic navigation/i }),
    ).toBeVisible();
    expect(screen.getByRole("main")).toHaveTextContent("Residents content");
    expect(screen.getByLabelText("Current clinic workspace")).toHaveTextContent("Northstar Clinic");
    expect(screen.getByText("Care operations workspace")).toBeVisible();
    expect(screen.getByText("Synthetic records only")).toBeVisible();
    expect(screen.getByRole("link", { name: /overview/i })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("links to the complete event queue without dead navigation", () => {
    render(
      <AppShell>
        <p>Residents content</p>
      </AppShell>,
    );

    expect(screen.getByRole("link", { name: /events/i })).toHaveAttribute("href", "/events");
    expect(screen.queryByText("Soon")).not.toBeInTheDocument();
  });

  it.each(["/design-system", "/design-system/colors"]) (
    "renders %s children directly without clinic chrome or a nested main landmark",
    (designSystemPath) => {
      pathname = designSystemPath;

      render(
        <AppShell>
          <main id="design-system-content">Design system specimens</main>
        </AppShell>,
      );

      expect(screen.getByText("Design system specimens")).toBeInTheDocument();
      expect(screen.queryByRole("navigation", { name: /clinic navigation/i })).not.toBeInTheDocument();
      expect(screen.getAllByRole("main")).toHaveLength(1);
      expect(screen.getByRole("main")).toHaveAttribute("id", "design-system-content");
    },
  );

  it("keeps clinic chrome for ordinary routes", () => {
    pathname = "/events";

    render(
      <AppShell>
        <p>Events content</p>
      </AppShell>,
    );

    expect(screen.getByRole("navigation", { name: /clinic navigation/i })).toBeVisible();
    expect(screen.getByRole("main")).toHaveTextContent("Events content");
  });
});
