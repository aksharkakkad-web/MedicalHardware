import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { StatusIndicatorProps } from "./status-indicator";
import { StatusIndicator } from "./status-indicator";

describe("StatusIndicator", () => {
  it("explains that stale evidence is limited by the last current update", () => {
    render(
      <StatusIndicator
        axis="freshness"
        value="stale"
        lastCurrentUpdate="08:42:18"
      />,
    );

    expect(screen.getByRole("status")).toHaveAccessibleName(/stale/i);
    expect(screen.getByText("Stale")).toBeVisible();
    expect(screen.getByText(/last current update: 08:42:18/i)).toBeVisible();
  });

  it("never implies resident attribution during possible multi-person presence", () => {
    render(
      <StatusIndicator axis="monitoring" value="possible_multi_person" />,
    );

    expect(screen.getByText("Monitoring possible multi-person")).toBeVisible();
    expect(
      screen.getByText(/resident-specific attribution is unavailable/i),
    ).toBeVisible();
    expect(screen.getByText(/do not guess which person caused a signal/i)).toBeVisible();
  });

  it("keeps the semantic value visible instead of relying on color", () => {
    render(<StatusIndicator axis="device" value="offline" />);

    expect(screen.getByText("Offline device")).toBeVisible();
    expect(screen.getByText(/room unit is not currently reporting/i)).toBeVisible();
  });

  it("provides an accessible label and description", () => {
    render(<StatusIndicator axis="attention" value="high" />);

    const status = screen.getByRole("status");
    expect(status).toHaveAccessibleName(/high attention priority/i);
    expect(status).toHaveAccessibleDescription(/priority for caregiver review/i);
  });

  it("exposes an axis-specific value without a generic tone escape hatch", () => {
    const valid: StatusIndicatorProps = {
      axis: "confidence",
      value: "low",
    };
    expect(valid).toMatchObject({ axis: "confidence", value: "low" });

    const invalidGenericTone: StatusIndicatorProps = {
      axis: "attention",
      value: "high",
      // @ts-expect-error Generic tone props are intentionally not part of this API.
      tone: "critical",
    };
    expect(invalidGenericTone).toBeDefined();
  });
});
