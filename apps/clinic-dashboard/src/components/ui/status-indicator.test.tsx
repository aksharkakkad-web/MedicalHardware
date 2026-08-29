import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { StatusIndicatorProps } from "./status-indicator";
import { StatusIndicator } from "./status-indicator";

const statusStyles = readFileSync(
  resolve(import.meta.dirname, "status-indicator.module.css"),
  "utf8",
);

describe("StatusIndicator", () => {
  it("uses active monitoring wording for the active value", () => {
    render(<StatusIndicator axis="monitoring" value="active" />);

    expect(screen.getByText("Monitoring active")).toBeVisible();
    expect(screen.queryByText("Monitoring current")).not.toBeInTheDocument();
  });

  it("is presentational by default and announces only when opted in", () => {
    const { rerender } = render(
      <StatusIndicator axis="monitoring" value="active" />,
    );

    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    rerender(<StatusIndicator axis="monitoring" value="active" announce />);
    expect(screen.getByRole("status")).toBeVisible();
  });

  it("explains that stale evidence is limited by the last current update", () => {
    render(
      <StatusIndicator
        axis="freshness"
        value="stale"
        lastCurrentUpdate="08:42:18"
        announce
      />,
    );

    expect(screen.getByRole("status")).toHaveAccessibleName(/freshness.*stale/i);
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
    render(<StatusIndicator axis="attention" value="high" announce />);

    const status = screen.getByRole("status");
    expect(status).toHaveAccessibleName(/attention.*high attention priority/i);
    expect(status).toHaveAccessibleDescription(/priority for caregiver review/i);
  });

  it("uses a neutral treatment when there is no attention priority", () => {
    render(<StatusIndicator axis="attention" value="none" />);

    const indicator = screen
      .getByText("No attention priority")
      .closest("[data-axis=attention]");
    expect(indicator).toHaveAttribute("data-semantic", "neutral");
  });

  it("keeps no-attention styling on general neutral roles", () => {
    const neutralRule =
      statusStyles.match(/\.indicator\[data-semantic="neutral"\]\s*\{([^}]*)\}/)?.[1] ?? "";

    expect(neutralRule).toContain("--ac-border-subtle");
    expect(neutralRule).toContain("--ac-text-primary");
    expect(neutralRule).toContain("--ac-surface");
    expect(neutralRule).not.toContain("--ac-unavailable");
  });

  it("keeps reusable descriptions free of specimen-only wording", () => {
    render(
      <>
        <StatusIndicator axis="attention" value="none" />
        <StatusIndicator axis="monitoring" value="active" />
      </>,
    );

    expect(document.body.textContent).not.toMatch(/synthetic example/i);
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

    const invalidCurrentUpdate: StatusIndicatorProps = {
      axis: "freshness",
      value: "current",
      // @ts-expect-error Only stale freshness accepts the last current update.
      lastCurrentUpdate: "08:42:18",
    };
    expect(invalidCurrentUpdate).toBeDefined();

    const invalidDelayedUpdate: StatusIndicatorProps = {
      axis: "freshness",
      value: "delayed",
      // @ts-expect-error Only stale freshness accepts the last current update.
      lastCurrentUpdate: "08:42:18",
    };
    expect(invalidDelayedUpdate).toBeDefined();

    const invalidUnknownUpdate: StatusIndicatorProps = {
      axis: "freshness",
      value: "unknown",
      // @ts-expect-error Only stale freshness accepts the last current update.
      lastCurrentUpdate: "08:42:18",
    };
    expect(invalidUnknownUpdate).toBeDefined();
  });
});
