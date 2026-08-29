# Resident Context and Preferences Design

## Goal

Give clinic staff one resident settings workspace where they can maintain useful routine/context notes and choose future notification delivery preferences without changing calibration, warning rules, or permanent event history.

## Product behavior

The route is `/residents/[residentId]/settings`. It has two clear sections inside one workspace:

- **Resident context:** show active and retired entries with provenance, memory version, and timestamps. Staff can add a note, correct an active note with a reason, or retire an active note with a reason. Corrections preserve the original entry and create a linked replacement. Nothing is deleted.
- **Notification preferences:** edit delivery choices for `watch`, `high`, `critical`, `away`, `return`, `limited`, and `unavailable`. High and critical events always remain visible in the clinic dashboard; these switches control future delivery only. A resident with no saved preferences gets an honest first-save state.

The workspace is linked from resident detail. It remains mock-backed and saves to browser storage through `MonitoringClient`, using contract-shaped types and expected-version checks so the later API client can replace the mock without redesigning components.

## States and safety rules

- Loading, unavailable, saved, unsaved, saving, validation, stale-version, active-entry, retired-entry, feedback-sourced, and operator-sourced states are visible and testable.
- Memory and notification preferences are separate from numerical calibration.
- Memory actions never edit event history, calibration, warning thresholds, or global behavior.
- Notification switches never hide high or critical events from the dashboard.
- All names and entries are synthetic. No real resident information or medical claims are used.
- Every mutation sends the currently displayed version and rejects stale edits.

## Information design

The screen extends the existing Calm Care Folio system. The primary column is a chronological context ledger; the narrower side column is a quiet notification control sheet. Version and provenance appear as compact metadata, not decorative statistics. On phones, context comes first and delivery settings follow. Native buttons, checkboxes, text fields, and visible focus states remain keyboard accessible.

## Implementation boundary

- Extend `MonitoringClient` and `MockMonitoringClient`.
- Add frontend-owned contract-shaped types and fixture factories under the existing monitoring/mock folders.
- Add focused components under `features/resident-settings/` and a Next.js route.
- Add resident-detail navigation and component/client tests.
- Do not connect the real backend, edit backend code, change shared API schemas, send notifications, or build the home app.

## Acceptance criteria

- Staff can add, correct, and retire synthetic resident context, and audit history remains visible.
- Staff can save all contract-defined notification delivery choices.
- First-save and stale-version behavior match the documented contract.
- Saved mock state survives client recreation and browser refresh.
- Desktop and 390px layouts are usable with no browser errors.
- Clinic tests, lint, typecheck, and production build pass.
