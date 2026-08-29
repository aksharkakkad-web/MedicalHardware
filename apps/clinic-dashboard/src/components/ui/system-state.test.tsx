import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  SYSTEM_STATE_CATALOG,
  SYSTEM_STATE_KEYS,
  SystemState,
  SystemStateCatalog,
  SystemLifecycle,
  SystemFeedback,
  type SystemStateKey,
} from "./system-state";

const stateStyles = readFileSync(
  resolve(import.meta.dirname, "system-state.module.css"),
  "utf8",
);

describe("SystemState catalog", () => {
  it("contains every canonical operational state exactly once", () => {
    expect(SYSTEM_STATE_KEYS).toEqual([
      "calibrating",
      "partial_baseline",
      "resident_away",
      "resident_returned",
      "possible_multi_person",
      "device_degraded",
      "device_offline",
      "buffering",
      "retrying",
      "missing_assignment",
      "unknown_anomaly",
      "ai_interpretation_pending",
      "ai_interpretation_unavailable",
      "loading",
      "genuine_empty",
      "filtered_empty",
      "stale_data",
      "save_failure",
      "conflicting_update",
      "overdue_work",
      "resolved_read_only",
      "recurrence_new_linked_event",
    ] satisfies readonly SystemStateKey[]);
    expect(Object.keys(SYSTEM_STATE_CATALOG)).toEqual(SYSTEM_STATE_KEYS);
  });

  it("gives every state the four operational facts plus provenance and semantics", () => {
    for (const key of SYSTEM_STATE_KEYS) {
      const definition = SYSTEM_STATE_CATALOG[key];
      expect(definition.title, key).toBeTruthy();
      expect(definition.known, key).toBeTruthy();
      expect(definition.limited, key).toBeTruthy();
      expect(definition.whyItMatters, key).toBeTruthy();
      expect(definition.nextAction, key).toBeTruthy();
      expect(definition.category, key).toBeTruthy();
      expect(definition.provenance, key).toBeTruthy();
      expect(definition.semantic, key).toMatch(/^(positive|info|caution|risk|limited|neutral)$/);
    }
  });

  it("renders explicit safety copy for uncertainty and operational boundaries", () => {
    render(<SystemStateCatalog />);

    expect(screen.getAllByText(/resident-specific baseline learning is paused/i)).not.toHaveLength(0);
    expect(screen.getByText(/resident-specific attribution is unavailable/i)).toBeVisible();
    expect(screen.getByText(/do not guess which person/i)).toBeVisible();
    expect(screen.getAllByText(/device health is separate from resident attention/i)).not.toHaveLength(0);
    expect(screen.getAllByText(/does not fabricate current data/i)).not.toHaveLength(0);
    expect(screen.getAllByText(/unknown anomaly/i)).not.toHaveLength(0);
    expect(screen.getByText(/never a diagnosis/i)).toBeVisible();
    expect(screen.getAllByText(/deterministic warning remains visible and actionable/i)).not.toHaveLength(0);
    expect(screen.getByText(/resolved history remains immutable/i)).toBeVisible();
    expect(screen.getAllByText(/new linked event/i)).not.toHaveLength(0);
  });

  it("keeps the static catalog non-interactive and does not announce it as live", () => {
    render(<SystemStateCatalog />);

    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(screen.queryAllByRole("status")).toHaveLength(0);
    expect(screen.getByText(/loading state; current operational details are not available yet/i)).toBeVisible();
    expect(screen.getByTestId("system-state-loading-skeleton")).toHaveAttribute("aria-hidden", "true");
  });

  it("supports a real action only when supplied by the caller", () => {
    render(
      <SystemState
        state="save_failure"
        action={{ label: "Retry save", href: "/retry" }}
      />,
    );

    expect(screen.getByRole("link", { name: "Retry save" })).toHaveAttribute("href", "/retry");
  });

  it("renders lifecycle immutability and recurrence as separate work", () => {
    render(<SystemLifecycle />);

    expect(screen.getByRole("heading", { name: /event lifecycle/i })).toBeVisible();
    expect(screen.getByText(/open · new/i)).toBeVisible();
    expect(screen.getByText(/acknowledged/i)).toBeVisible();
    expect(screen.getAllByText(/investigating/i)).not.toHaveLength(0);
    expect(screen.getByText(/overdue/i)).toBeVisible();
    expect(screen.getByText(/resolved read-only/i)).toBeVisible();
    expect(screen.getByText(/never reopen resolved history/i)).toBeVisible();
    expect(screen.getAllByText(/new linked event/i)).not.toHaveLength(0);
    expect(screen.getAllByText(/high and critical events never silently expire/i)).not.toHaveLength(0);
  });

  it("renders system feedback with accessible static loading treatment", () => {
    render(<SystemFeedback />);

    const feedback = screen.getByRole("region", { name: /system feedback/i });
    expect(within(feedback).getByText(/skeleton loading/i)).toBeVisible();
    expect(within(feedback).getAllByText(/genuine empty/i)).not.toHaveLength(0);
    expect(within(feedback).getAllByText(/filtered empty/i)).not.toHaveLength(0);
    expect(within(feedback).getByText(/stale refresh/i)).toBeVisible();
    expect(within(feedback).getByText(/retryable save failure/i)).toBeVisible();
    expect(within(feedback).getAllByText(/conflict recovery/i)).not.toHaveLength(0);
    expect(within(feedback).queryAllByRole("status")).toHaveLength(0);
  });

  it("keeps long guidance readable and honors forced-color semantics", () => {
    expect(stateStyles).toMatch(/.state/);
    expect(stateStyles).toMatch(/font-size:\s*(?:var\(--ac-font-size-(?:body|metadata|label)\)|(?:12|13|14)px)/);
    expect(stateStyles).toContain("@media (forced-colors: active)");
    expect(stateStyles).toMatch(/overflow-wrap:\s*anywhere/);
    render(<SystemState state="possible_multi_person" />);
    expect(screen.getByRole("heading", { name: /possible multi-person/i })).toBeVisible();
  });
});
