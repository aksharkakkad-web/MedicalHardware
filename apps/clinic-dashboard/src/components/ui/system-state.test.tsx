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
        action={{ kind: "retry_save", onClick: () => undefined }}
      />,
    );

    expect(screen.getByText(SYSTEM_STATE_CATALOG.save_failure.nextAction)).toBeVisible();
    expect(screen.getByRole("button", { name: "Retry save" })).toBeVisible();
  });

  it("rejects action props for loading and immutable resolved history at compile time", () => {
    // @ts-expect-error Loading is guidance-only and cannot receive an action.
    const invalidLoadingProps: import("./system-state").SystemStateProps = {
      state: "loading",
      action: { kind: "retry_save" as const, onClick: () => undefined },
    };
    // @ts-expect-error Resolved history is immutable and cannot receive an action.
    const invalidResolvedProps: import("./system-state").SystemStateProps = {
      state: "resolved_read_only",
      action: { kind: "retry_save" as const, onClick: () => undefined },
    };

    expect(invalidLoadingProps.state).toBe("loading");
    expect(invalidResolvedProps.state).toBe("resolved_read_only");
  });

  it("keeps guidance and ignores runtime action overrides for loading and resolved history", () => {
    const unsafeAction = {
      kind: "reopen_event",
      label: "Reopen event",
      onClick: () => undefined,
    };

    render(
      <>
        <SystemState {...({ state: "loading", action: unsafeAction } as unknown as import("./system-state").SystemStateProps)} />
        <SystemState {...({ state: "resolved_read_only", action: unsafeAction } as unknown as import("./system-state").SystemStateProps)} />
      </>,
    );

    expect(screen.getByText(SYSTEM_STATE_CATALOG.loading.nextAction)).toBeVisible();
    expect(screen.getByText(SYSTEM_STATE_CATALOG.resolved_read_only.nextAction)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Reopen event" })).not.toBeInTheDocument();
    expect(screen.queryByText("Reopen event")).not.toBeInTheDocument();
  });

  it("uses a unique stable heading id for each identical state instance", () => {
    render(
      <>
        <SystemState state="loading" />
        <SystemState state="loading" />
      </>,
    );

    const headings = screen.getAllByRole("heading", { name: "Loading" });
    expect(headings).toHaveLength(2);
    expect(headings[0]).toHaveAttribute("id");
    expect(headings[1]).toHaveAttribute("id");
    expect(headings[0].id).not.toBe(headings[1].id);
    expect(headings[0].closest("article")).toHaveAttribute("aria-labelledby", headings[0].id);
    expect(headings[1].closest("article")).toHaveAttribute("aria-labelledby", headings[1].id);
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
    expect(stateStyles).toMatch(/\.nextAction button\s*\{[\s\S]*display:\s*inline-flex/);
    expect(stateStyles).toMatch(/\.nextAction button\s*\{[\s\S]*min-height:\s*44px/);
    expect(stateStyles).toMatch(/\.nextAction button\s*\{[\s\S]*padding:\s*var\(--ac-space-2\) var\(--ac-space-3\)/);
    render(<SystemState state="possible_multi_person" />);
    expect(screen.getByRole("heading", { name: /possible multi-person/i })).toBeVisible();
  });
});
