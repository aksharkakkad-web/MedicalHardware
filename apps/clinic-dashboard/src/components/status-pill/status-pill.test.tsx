import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusPill } from "./status-pill";

describe("StatusPill", () => {
  it("always shows a written status instead of relying on color", () => {
    render(<StatusPill label="Monitoring active" tone="healthy" />);

    expect(screen.getByText("Monitoring active")).toBeVisible();
  });
});
