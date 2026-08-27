# Clinic Dashboard Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the production-quality clinic dashboard foundation and one polished, mock-backed resident overview.

**Architecture:** Create one independent Next.js App Router application under `apps/clinic-dashboard`. Pages obtain data through a typed `MonitoringClient` provider; only `MockMonitoringClient` imports synthetic fixtures. UI modules consume stable frontend view models and never import fixtures or backend/database types directly.

**Tech Stack:** Next.js, React, TypeScript, pnpm, CSS variables, Vitest, Testing Library, ESLint

---

### Task 1: Bootstrap the clinic application

**Files:**
- Create: `apps/clinic-dashboard/package.json`
- Create: `apps/clinic-dashboard/next.config.ts`
- Create: `apps/clinic-dashboard/tsconfig.json`
- Create: `apps/clinic-dashboard/eslint.config.mjs`
- Create: `apps/clinic-dashboard/vitest.config.ts`
- Create: `apps/clinic-dashboard/src/test/setup.ts`
- Create: `apps/clinic-dashboard/src/app/layout.tsx`
- Create: `apps/clinic-dashboard/src/app/page.tsx`
- Create: `apps/clinic-dashboard/src/app/globals.css`

- [x] **Step 1: Scaffold the Next.js application**

Run:

```bash
pnpm create next-app@latest apps/clinic-dashboard --ts --eslint --app --src-dir --use-pnpm --no-tailwind --import-alias '@/*'
```

Expected: `apps/clinic-dashboard` exists and pnpm installs the generated dependencies.

- [x] **Step 2: Add focused testing tools**

Run:

```bash
pnpm --dir apps/clinic-dashboard add -D vitest jsdom @vitejs/plugin-react @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

Expected: test dependencies appear in `apps/clinic-dashboard/package.json` and `pnpm-lock.yaml` is updated.

- [x] **Step 3: Add stable scripts to `package.json`**

Use these scripts:

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  }
}
```

- [x] **Step 4: Configure Vitest**

Create `vitest.config.ts`:

```ts
import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
```

Create `src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [x] **Step 5: Verify the empty application**

Run:

```bash
pnpm --dir apps/clinic-dashboard lint
pnpm --dir apps/clinic-dashboard typecheck
pnpm --dir apps/clinic-dashboard build
```

Expected: all commands exit successfully.

- [x] **Step 6: Commit the bootstrap**

```bash
git add apps/clinic-dashboard
git commit -m "chore: bootstrap clinic dashboard"
```

### Task 2: Define the monitoring boundary and mock client

**Files:**
- Create: `apps/clinic-dashboard/src/lib/monitoring/types.ts`
- Create: `apps/clinic-dashboard/src/lib/monitoring/client.ts`
- Create: `apps/clinic-dashboard/src/lib/monitoring/index.ts`
- Create: `apps/clinic-dashboard/src/mocks/residents.ts`
- Create: `apps/clinic-dashboard/src/mocks/mock-monitoring-client.ts`
- Test: `apps/clinic-dashboard/src/mocks/mock-monitoring-client.test.ts`

- [x] **Step 1: Write the failing mock-client test**

```ts
import { describe, expect, it } from "vitest";
import { MockMonitoringClient } from "./mock-monitoring-client";

describe("MockMonitoringClient", () => {
  it("returns synthetic residents covering honest monitoring states", async () => {
    const result = await new MockMonitoringClient().listResidentOverview();

    expect(result.items).toHaveLength(5);
    expect(result.items.map((item) => item.monitoring.state)).toEqual(
      expect.arrayContaining(["active", "paused", "limited", "unavailable"]),
    );
    expect(result.items.some((item) => item.attention.priority === "high")).toBe(true);
    expect(result.items.every((item) => item.schemaVersion === "1.0")).toBe(true);
  });
});
```

- [x] **Step 2: Run the test and confirm it fails**

Run:

```bash
pnpm --dir apps/clinic-dashboard test -- src/mocks/mock-monitoring-client.test.ts
```

Expected: FAIL because the mock client does not exist.

- [x] **Step 3: Define the view models and client interface**

Create `types.ts` with explicit unions for:

```ts
export type MonitoringState = "active" | "limited" | "paused" | "unavailable";
export type AttentionPriority = "none" | "watch" | "high" | "critical";
export type DeviceStatus = "online" | "degraded" | "offline" | "unknown";

export interface ResidentOverviewItem {
  schemaVersion: "1.0";
  residentId: string;
  displayLabel: string;
  roomId: string;
  roomLabel: string;
  assignmentStatus: "active" | "missing" | "conflicting";
  monitoring: {
    state: MonitoringState;
    reason: string;
    lastUpdatedAt: string;
  };
  attention: {
    priority: AttentionPriority;
    headline: string;
    openEventCount: number;
  };
  device: {
    status: DeviceStatus;
    label: string;
  };
}

export interface ResidentOverviewResponse {
  schemaVersion: "1.0";
  generatedAt: string;
  items: ResidentOverviewItem[];
}
```

Create `client.ts`:

```ts
import type { ResidentOverviewResponse } from "./types";

export interface MonitoringClient {
  listResidentOverview(): Promise<ResidentOverviewResponse>;
}
```

- [x] **Step 4: Implement fixtures and `MockMonitoringClient`**

Create five fully synthetic records: active/normal, active/high attention, resident away/paused, possible multi-person/limited, and device problem/unavailable. The mock client returns cloned records so UI code cannot mutate the fixture source.

```ts
import type { MonitoringClient } from "@/lib/monitoring";
import type { ResidentOverviewResponse } from "@/lib/monitoring/types";
import { residentOverviewFixture } from "./residents";

export class MockMonitoringClient implements MonitoringClient {
  async listResidentOverview(): Promise<ResidentOverviewResponse> {
    return structuredClone(residentOverviewFixture);
  }
}
```

- [x] **Step 5: Run focused tests**

Run:

```bash
pnpm --dir apps/clinic-dashboard test -- src/mocks/mock-monitoring-client.test.ts
```

Expected: PASS.

- [x] **Step 6: Commit the monitoring boundary**

```bash
git add apps/clinic-dashboard/src/lib apps/clinic-dashboard/src/mocks
git commit -m "feat: add clinic monitoring client boundary"
```

### Task 3: Add the provider and honest asynchronous states

**Files:**
- Create: `apps/clinic-dashboard/src/lib/monitoring/provider.tsx`
- Create: `apps/clinic-dashboard/src/features/residents/use-resident-overview.ts`
- Test: `apps/clinic-dashboard/src/features/residents/use-resident-overview.test.tsx`

- [x] **Step 1: Write failing tests for load, success, and retry**

Create a controllable test client and verify the hook begins in `loading`, stores successful items, exposes an error message on rejection, and calls the client again when `retry()` is used.

```ts
expect(result.current.status).toBe("loading");
await waitFor(() => expect(result.current.status).toBe("success"));
expect(result.current.items).toHaveLength(5);
```

- [x] **Step 2: Run the focused test and confirm it fails**

```bash
pnpm --dir apps/clinic-dashboard test -- src/features/residents/use-resident-overview.test.tsx
```

Expected: FAIL because the provider and hook do not exist.

- [x] **Step 3: Implement the client provider**

```tsx
"use client";

import { createContext, useContext } from "react";
import type { MonitoringClient } from "./client";

const MonitoringClientContext = createContext<MonitoringClient | null>(null);

export function MonitoringClientProvider({
  client,
  children,
}: Readonly<{ client: MonitoringClient; children: React.ReactNode }>) {
  return (
    <MonitoringClientContext.Provider value={client}>
      {children}
    </MonitoringClientContext.Provider>
  );
}

export function useMonitoringClient(): MonitoringClient {
  const client = useContext(MonitoringClientContext);
  if (!client) throw new Error("MonitoringClientProvider is missing");
  return client;
}
```

- [x] **Step 4: Implement the resident-overview hook**

The hook must use an explicit state union:

```ts
type ResidentOverviewState =
  | { status: "loading"; items: [] }
  | { status: "success"; items: ResidentOverviewItem[] }
  | { status: "error"; items: []; message: string };
```

It loads on mount, ignores results after unmount, and exposes `retry()`.

- [x] **Step 5: Run the focused test and commit**

```bash
pnpm --dir apps/clinic-dashboard test -- src/features/residents/use-resident-overview.test.tsx
git add apps/clinic-dashboard/src/lib/monitoring apps/clinic-dashboard/src/features/residents
git commit -m "feat: add clinic monitoring provider"
```

Expected: tests pass and the commit succeeds.

### Task 4: Build the clinic shell and visual system

**Files:**
- Modify: `apps/clinic-dashboard/src/app/globals.css`
- Modify: `apps/clinic-dashboard/src/app/layout.tsx`
- Create: `apps/clinic-dashboard/src/components/app-shell/app-shell.tsx`
- Create: `apps/clinic-dashboard/src/components/app-shell/app-shell.module.css`
- Create: `apps/clinic-dashboard/src/components/status-pill/status-pill.tsx`
- Create: `apps/clinic-dashboard/src/components/status-pill/status-pill.module.css`
- Test: `apps/clinic-dashboard/src/components/app-shell/app-shell.test.tsx`

- [x] **Step 1: Write a failing shell accessibility test**

```tsx
render(<AppShell><p>Residents content</p></AppShell>);
expect(screen.getByRole("navigation", { name: /clinic navigation/i })).toBeVisible();
expect(screen.getByRole("main")).toHaveTextContent("Residents content");
expect(screen.getByRole("link", { name: /residents/i })).toHaveAttribute("aria-current", "page");
```

- [x] **Step 2: Run the test and confirm it fails**

```bash
pnpm --dir apps/clinic-dashboard test -- src/components/app-shell/app-shell.test.tsx
```

- [x] **Step 3: Implement design tokens and the responsive shell**

Define CSS variables for canvas, surface, text, muted text, border, accent, healthy, attention, critical, radii, shadows, and focus ring. Build a desktop sidebar and compact mobile header. Residents is the active link; Events, Devices, and Settings are visibly marked “Soon” and are not clickable dead routes.

- [x] **Step 4: Implement `StatusPill`**

The component accepts a visible label and a semantic tone: `neutral`, `healthy`, `attention`, `critical`, or `unavailable`. It always renders text in addition to color.

- [x] **Step 5: Run tests, lint, and typecheck**

```bash
pnpm --dir apps/clinic-dashboard test
pnpm --dir apps/clinic-dashboard lint
pnpm --dir apps/clinic-dashboard typecheck
```

Expected: all commands pass.

- [x] **Step 6: Commit the shell**

```bash
git add apps/clinic-dashboard/src/app apps/clinic-dashboard/src/components
git commit -m "feat: add clinic dashboard shell"
```

### Task 5: Build the resident overview

**Files:**
- Modify: `apps/clinic-dashboard/src/app/page.tsx`
- Create: `apps/clinic-dashboard/src/app/providers.tsx`
- Create: `apps/clinic-dashboard/src/features/residents/resident-overview.tsx`
- Create: `apps/clinic-dashboard/src/features/residents/resident-overview.module.css`
- Create: `apps/clinic-dashboard/src/features/residents/resident-card.tsx`
- Create: `apps/clinic-dashboard/src/features/residents/resident-card.module.css`
- Test: `apps/clinic-dashboard/src/features/residents/resident-overview.test.tsx`

- [x] **Step 1: Write failing resident-overview tests**

Verify that the screen:

```tsx
expect(await screen.findByRole("heading", { name: /resident overview/i })).toBeVisible();
expect(screen.getByText("Resident A")).toBeVisible();
expect(screen.getByText(/possible visitor/i)).toBeVisible();
expect(screen.getByText(/device offline/i)).toBeVisible();
expect(screen.getByText(/needs attention/i)).toBeVisible();
```

Add separate tests for loading, empty, and failed-client states. The failed state must expose a Retry button.

- [x] **Step 2: Run the test and confirm it fails**

```bash
pnpm --dir apps/clinic-dashboard test -- src/features/residents/resident-overview.test.tsx
```

- [x] **Step 3: Implement providers and page composition**

Instantiate `MockMonitoringClient` once in `providers.tsx`, wrap the application with `MonitoringClientProvider`, and render `AppShell` around the page content.

- [x] **Step 4: Implement overview summaries and resident cards**

Sort cards by attention priority, then room label. Display high-attention count, active count, and limited/paused/unavailable count. Each card includes resident label, room, monitoring state, plain-language reason, attention headline, device state when relevant, and last-updated time.

- [x] **Step 5: Implement loading, empty, and error presentations**

Loading uses neutral skeleton cards with an accessible loading label. Empty says no resident information is available. Error says current information could not be loaded and offers Retry; none of these states imply that residents are safe.

- [x] **Step 6: Run focused and full checks**

```bash
pnpm --dir apps/clinic-dashboard test
pnpm --dir apps/clinic-dashboard lint
pnpm --dir apps/clinic-dashboard typecheck
pnpm --dir apps/clinic-dashboard build
```

Expected: all commands pass.

- [x] **Step 7: Commit the resident overview**

```bash
git add apps/clinic-dashboard
git commit -m "feat: build mock-backed resident overview"
```

### Task 6: Browser verification and repository handoff

**Files:**
- Modify if necessary: `apps/clinic-dashboard/src/**`
- Modify: `AGENTS.md` only if canonical frontend commands are missing after bootstrap

- [x] **Step 1: Start the real app**

```bash
pnpm --dir apps/clinic-dashboard dev
```

Expected: the app reports a local URL and loads successfully.

- [x] **Step 2: Verify desktop behavior**

At a desktop viewport, inspect the overview, navigation, all five mock states, loading/empty/error presentations, keyboard focus, and browser console. Fix any product or responsive defects found.

- [x] **Step 3: Verify mobile behavior**

At a mobile viewport, confirm navigation remains usable, cards do not overflow, labels remain readable, and tap targets are comfortably sized. Fix any defects found.

- [x] **Step 4: Run the final check set**

```bash
pnpm --dir apps/clinic-dashboard test
pnpm --dir apps/clinic-dashboard lint
pnpm --dir apps/clinic-dashboard typecheck
pnpm --dir apps/clinic-dashboard build
git diff --check
```

Expected: every command succeeds and browser console has no errors.

- [x] **Step 5: Update documentation only where verified**

If the new commands are not already recorded, add the exact passing frontend commands to `AGENTS.md`. Do not change product requirements or shared contracts.

- [x] **Step 6: Commit final fixes and verified commands**

```bash
git add apps/clinic-dashboard AGENTS.md
git commit -m "test: verify clinic dashboard foundation"
```

Expected: a clean branch containing only the scoped frontend foundation, its tests, and verified command documentation.
