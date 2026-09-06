import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ExportActions } from "./export-actions";

describe("ExportActions", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("offers the current PDF and editable source as downloads", () => {
    render(<ExportActions />);

    expect(screen.getByRole("link", { name: "Download PDF" })).toHaveAttribute(
      "href",
      "/downloads/adaptive-care-clear-signal-design-system.pdf",
    );
    expect(screen.getByRole("link", { name: "Download text guide" })).toHaveAttribute(
      "href",
      "/downloads/adaptive-care-design-system.md",
    );
  });

  it("opens the browser print dialog for a fresh PDF", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    render(<ExportActions />);

    await userEvent.click(screen.getByRole("button", { name: "Print / Save as PDF" }));

    expect(print).toHaveBeenCalledOnce();
  });
});
