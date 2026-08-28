# Frontend Scenario Lab Design

## Goal

Add a synthetic, frontend-only Scenario Lab that lets a product walkthrough deliberately place Resident A into four important states: away, returned, possible extra person, and physiological pattern change. The lab makes the existing clinic screens demonstrable before real telemetry is connected.

## Product boundary

- This is a UI walkthrough tool, not the production telemetry simulator.
- Scenario names and ground truth stay inside the demo controller and never enter production monitoring types.
- The normal clinic UI continues to read only `MonitoringClient` domain responses.
- No backend, database, shared API contract, clinical threshold, or diagnostic claim changes.
- Every surface remains clearly labeled as synthetic demo data.

## Architecture

Create a separate typed `DemoScenarioController` beside, not inside, `MonitoringClient`. `MockMonitoringClient` implements both interfaces and stores the selected scenario in browser storage. A small provider exposes the demo controller only to the Scenario Lab. This keeps future `ApiMonitoringClient` work clean: production monitoring does not need fake scenario endpoints.

When a scenario is activated, `MockMonitoringClient` derives its ordinary resident, event, and setup responses from the selected demo state. Existing screens therefore show the result without importing fixtures or scenario data. Resetting restores the baseline fixtures.

## Scenario behavior

### Resident away

- Resident A becomes `paused` with a plain explanation that the resident is away.
- Calibration history is preserved while new learning is paused.
- No warning event is created.
- The result links to Resident A.

### Resident returned

- Resident A becomes `active` again.
- Resident-specific monitoring and eligible learning can resume.
- No warning event is created merely because the resident returned.
- The result links to Resident A.

### Possible extra person

- Resident A becomes `limited` because attribution is ambiguous.
- A watch-level `unknown_anomaly` event explains that staff should confirm room occupancy.
- Resident-specific evidence is limited or unavailable; the UI never guesses who caused the pattern.
- The result links to the event.

### Physiological pattern change

- Resident A remains assigned and monitored, with a high-priority synthetic event.
- Evidence says that combined non-diagnostic patterns differ from the resident's personal baseline without inventing medical thresholds.
- Copy explicitly says this is not a diagnosis and requires a staff check.
- The result links to the event.

## Screen design

Add `/scenarios` to the clinic navigation as `Scenario Lab`.

The page follows the established Calm Care Folio system:

1. A clear title and test-only boundary note.
2. A primary walkthrough sheet with four stacked scenario rows, not an equal-weight marketing card grid.
3. Each row explains what staff will see, what safety rule remains true, and provides one `Run scenario` action.
4. A sticky result rail shows the active scenario, three expected product outcomes, and the next `Open resident` or `Open event` action.
5. A quiet `Reset demo` action restores baseline fixtures.
6. On narrow screens, the result rail stacks below the scenario list and all actions remain at least 44 pixels high.

## State and errors

- Initial state reports `Baseline demo` when no scenario is active.
- A running action disables scenario controls and announces progress.
- Success identifies the active scenario and its affected screen.
- Storage failure still updates the current browser session and shows a plain limitation.
- Unknown saved values safely fall back to baseline.

## Testing and acceptance

- Controller tests cover all four scenarios, reset, persistence, invalid stored data, and clone safety.
- Component tests cover baseline, running a scenario, result navigation, reset, loading, and error states.
- Existing overview, resident, event, setup, and settings tests remain green.
- Lint, typecheck, and production build pass.
- Desktop and 390px mobile browser checks confirm the main run/open/reset journey with no console errors.

## Non-goals

- Generating radar, thermal, or Wi-Fi telemetry packets.
- Calling backend ingestion or exposing scenario endpoints in production.
- Simulating every PRD scenario in this first lab screen.
- Diagnosing a condition or presenting invented medical numbers.
