import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

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
});
