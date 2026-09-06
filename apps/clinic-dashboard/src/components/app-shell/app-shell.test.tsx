import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

let pathname = "/";

vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

const stylesheet = readFileSync(resolve(import.meta.dirname, "app-shell.module.css"), "utf8");

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
    expect(screen.getAllByText("Northstar Clinic")).toHaveLength(1);
    expect(screen.getByText("Care operations workspace")).toBeVisible();
    expect(screen.getByText("Synthetic records only")).toBeVisible();
    expect(screen.queryByText("Synthetic demo data")).not.toBeInTheDocument();
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
    expect(screen.getByRole("main").className).not.toMatch(/overviewMain/);
  });

  it("locks an intentional accessible collapsed sidebar before mobile navigation", () => {
    expect(stylesheet).toMatch(/@media \(min-width: 761px\) and \(max-width: 1050px\)/);
    expect(stylesheet).toContain("grid-template-columns: var(--ac-sidebar-collapsed-width) minmax(0, 1fr)");
    expect(stylesheet).toMatch(/\.navLink > span,[\s\S]*clip-path: inset\(50%\);/);
    expect(stylesheet).toMatch(/@media \(max-width: 760px\)/);
  });

  it("scopes the supplied compact visual system to clinic chrome", () => {
    expect(stylesheet).toContain("grid-template-columns: var(--ac-sidebar-width) minmax(0, 1fr)");
    expect(stylesheet).toContain("background: var(--ac-canvas)");
    expect(stylesheet).toContain("background: var(--ac-surface)");
    expect(stylesheet).toContain("color: var(--ac-action)");
  });
});
