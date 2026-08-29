# Frontend Scenario Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a synthetic Scenario Lab that changes the existing clinic mock responses so the complete away, returned, possible-extra-person, and physiological-change frontend states can be demonstrated.

**Architecture:** Keep ground-truth demo controls in a separate `DemoScenarioController` interface. `MockMonitoringClient` implements that interface and derives its normal `MonitoringClient` responses from the active scenario, while production-facing UI types remain free of mock-only fields. The new `/scenarios` route runs scenarios, explains expected outcomes, and links into the unchanged resident/event screens.

**Tech Stack:** Next.js App Router, React 19, TypeScript, CSS Modules, Vitest, Testing Library, browser `localStorage`.

---

### Task 1: Typed scenario controller and fixtures

**Files:**
- Create: `apps/clinic-dashboard/src/lib/demo-scenarios/types.ts`
- Create: `apps/clinic-dashboard/src/lib/demo-scenarios/provider.tsx`
- Create: `apps/clinic-dashboard/src/lib/demo-scenarios/index.ts`
- Create: `apps/clinic-dashboard/src/mocks/scenarios.ts`
- Test: `apps/clinic-dashboard/src/mocks/mock-monitoring-client.test.ts`

- [ ] **Step 1: Write failing controller tests**

Add tests that call the not-yet-created methods and prove each scenario changes ordinary monitoring responses:

```ts
await client.applyDemoScenario("resident_away");
expect((await client.getResident("res_7f3a1c")).resident.monitoring.state).toBe("paused");

await client.applyDemoScenario("possible_multi_person");
expect((await client.listEvents()).items).toContainEqual(
  expect.objectContaining({ objectiveFamily: "Unknown anomaly", priority: "watch" }),
);

await client.applyDemoScenario("physiological_deviation");
expect((await client.listEvents()).items).toContainEqual(
  expect.objectContaining({ objectiveFamily: "Combined physiological deviation", priority: "high" }),
);
```

Also cover returned, reset, persistence after client recreation, invalid saved scenario fallback, and response clone safety.

- [ ] **Step 2: Run the focused tests and confirm red**

Run: `pnpm --dir apps/clinic-dashboard test -- mock-monitoring-client.test.ts`

Expected: failure because `applyDemoScenario` and the scenario types do not exist.

- [ ] **Step 3: Add the isolated scenario types and provider**

Define:

```ts
export type DemoScenarioId =
  | "resident_away"
  | "resident_returned"
  | "possible_multi_person"
  | "physiological_deviation";

export interface DemoScenarioController {
  listDemoScenarios(): Promise<DemoScenarioDefinition[]>;
  getActiveDemoScenario(): Promise<DemoScenarioState>;
  applyDemoScenario(scenarioId: DemoScenarioId): Promise<DemoScenarioState>;
  resetDemoScenario(): Promise<DemoScenarioState>;
}
```

The provider accepts `DemoScenarioController | null`; the hook returns `null` when demo controls are unavailable instead of making production monitoring depend on them.

- [ ] **Step 4: Add contract-valid scenario definitions and event fixtures**

`scenarios.ts` owns labels, plain-English expectations, target links, and synthetic event builders. The physiological fixture must use non-diagnostic copy:

```ts
objectiveFamily: "Combined physiological deviation",
headline: "Combined pattern change needs staff review",
confidence: {
  label: "Moderate confidence",
  dataQuality: "good",
  limitation: "This synthetic pattern is different from the resident's baseline, but it cannot identify a medical cause.",
},
```

- [ ] **Step 5: Implement `MockMonitoringClient` scenario behavior**

Store only `{ schemaVersion, activeScenarioId, appliedAt }` under `adaptive-care:demo-scenario:v1`. Derive Resident A's overview/setup state on reads, add only the active scenario event to the existing event map, and remove scenario-created events on reset. Preserve unrelated event workflow progress.

- [ ] **Step 6: Run focused tests and confirm green**

Run: `pnpm --dir apps/clinic-dashboard test -- mock-monitoring-client.test.ts`

Expected: all mock-client tests pass.

- [ ] **Step 7: Commit the scenario model**

```bash
git add apps/clinic-dashboard/src/lib/demo-scenarios apps/clinic-dashboard/src/mocks/scenarios.ts apps/clinic-dashboard/src/mocks/mock-monitoring-client.ts apps/clinic-dashboard/src/mocks/mock-monitoring-client.test.ts
git commit -m "feat: add frontend demo scenario controller"
```

### Task 2: Scenario Lab screen and navigation

**Files:**
- Create: `apps/clinic-dashboard/src/app/scenarios/page.tsx`
- Create: `apps/clinic-dashboard/src/features/scenarios/scenario-lab.tsx`
- Create: `apps/clinic-dashboard/src/features/scenarios/scenario-lab.module.css`
- Create: `apps/clinic-dashboard/src/features/scenarios/scenario-lab.test.tsx`
- Modify: `apps/clinic-dashboard/src/app/providers.tsx`
- Modify: `apps/clinic-dashboard/src/components/app-shell/app-shell.tsx`
- Modify: `apps/clinic-dashboard/src/components/app-shell/app-shell.module.css`
- Modify: `apps/clinic-dashboard/src/components/icons/icons.tsx`

- [ ] **Step 1: Write failing screen tests**

Test baseline content, running a scenario, active-result copy and target link, reset, and unavailable-controller messaging:

```ts
expect(await screen.findByRole("heading", { name: "Scenario Lab" })).toBeVisible();
await user.click(screen.getByRole("button", { name: /run resident away/i }));
expect(await screen.findByText(/monitoring is paused/i)).toBeVisible();
expect(screen.getByRole("link", { name: /open resident a/i })).toHaveAttribute("href", "/residents/res_7f3a1c");
```

- [ ] **Step 2: Run the screen tests and confirm red**

Run: `pnpm --dir apps/clinic-dashboard test -- scenario-lab.test.tsx`

Expected: failure because the route and component do not exist.

- [ ] **Step 3: Wire the provider and navigation**

Pass the same mock object into both providers:

```tsx
<MonitoringClientProvider client={monitoringClient}>
  <DemoScenarioProvider controller={monitoringClient}>{children}</DemoScenarioProvider>
</MonitoringClientProvider>
```

Add `Scenario Lab` with a simple playbook icon. Change the narrow navigation to four equal destinations without shrinking labels below readable size.

- [ ] **Step 4: Build the Scenario Lab**

Render one working sheet of scenario rows and one result rail. Every row includes its purpose, expected clinic response, safety rule, and a specific button label such as `Run resident away`. The active rail includes three expected outcomes, applied time, `Open resident` or `Open event`, and `Reset demo`.

- [ ] **Step 5: Add honest loading and unavailable states**

Use `role="status"` while loading/running and `role="alert"` when the controller is unavailable or an action fails. Never imply that the last scenario ran when persistence or application failed.

- [ ] **Step 6: Run focused tests and confirm green**

Run: `pnpm --dir apps/clinic-dashboard test -- scenario-lab.test.tsx`

Expected: all Scenario Lab component tests pass.

- [ ] **Step 7: Commit the screen**

```bash
git add apps/clinic-dashboard/src/app/scenarios apps/clinic-dashboard/src/features/scenarios apps/clinic-dashboard/src/app/providers.tsx apps/clinic-dashboard/src/components/app-shell
git commit -m "feat: add clinic scenario lab"
```

### Task 3: Cross-screen walkthrough verification

**Files:**
- Modify tests only where the scenario behavior exposes a missing regression check.
- Update: `graphify-out/`

- [ ] **Step 1: Run the complete frontend checks**

```bash
pnpm --dir apps/clinic-dashboard test
pnpm --dir apps/clinic-dashboard lint
pnpm --dir apps/clinic-dashboard typecheck
pnpm --dir apps/clinic-dashboard build
```

Expected: every command exits zero.

- [ ] **Step 2: Run the Impeccable detector once**

```bash
node /Users/rishits/.agents/skills/impeccable/scripts/detect.mjs --json \
  apps/clinic-dashboard/src/features/scenarios/scenario-lab.tsx \
  apps/clinic-dashboard/src/features/scenarios/scenario-lab.module.css \
  apps/clinic-dashboard/src/components/app-shell/app-shell.tsx \
  apps/clinic-dashboard/src/components/app-shell/app-shell.module.css
```

Expected: no unresolved banned-pattern findings.

- [ ] **Step 3: Verify the real browser journey**

At 1440px and 390px:

1. Open `/scenarios`.
2. Run resident away and open Resident A; confirm paused monitoring without a warning event.
3. Return to the lab, run possible extra person, and open the watch event; confirm low-confidence language.
4. Return, run physiological change, and open its high-priority event; confirm non-diagnostic language.
5. Reset and confirm Resident A returns to the baseline active state.
6. Confirm no horizontal clipping or browser console errors.

- [ ] **Step 4: Fix one bounded batch and reconfirm**

Batch any visible hierarchy, spacing, mobile, or accessibility defects together, then repeat the two viewport screenshots and console check once.

- [ ] **Step 5: Refresh the code graph and commit verification changes**

```bash
graphify update .
git add <exact reviewed paths>
git diff --cached --check
git commit -m "test: verify frontend scenario walkthroughs"
```
