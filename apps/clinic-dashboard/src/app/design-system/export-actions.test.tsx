import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ExportActions } from "./export-actions";

describe("ExportActions", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("offers the current editable guide as a download", () => {
    render(<ExportActions />);

    expect(screen.getByRole("link", { name: "Download text guide" })).toHaveAttribute(
      "href",
      "/downloads/syren-design-system.md",
    );
  });

  it("opens the browser print dialog for a fresh PDF", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    render(<ExportActions />);

    await userEvent.click(screen.getByRole("button", { name: "Print / Save as PDF" }));

    expect(print).toHaveBeenCalledOnce();
  });
});
