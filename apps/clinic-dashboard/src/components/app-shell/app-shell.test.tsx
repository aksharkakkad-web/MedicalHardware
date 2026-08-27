import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "./app-shell";

describe("AppShell", () => {
  it("gives the active residents workspace a clear structure", () => {
    render(
      <AppShell>
        <p>Residents content</p>
      </AppShell>,
    );

    expect(
      screen.getByRole("navigation", { name: /clinic navigation/i }),
    ).toBeVisible();
    expect(screen.getByRole("main")).toHaveTextContent("Residents content");
    expect(screen.getByRole("link", { name: /residents/i })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("labels unfinished destinations without linking to dead pages", () => {
    render(
      <AppShell>
        <p>Residents content</p>
      </AppShell>,
    );

    expect(screen.queryByRole("link", { name: /events/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /devices/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /settings/i })).not.toBeInTheDocument();
    expect(screen.getAllByText("Soon")).toHaveLength(3);
  });
});
