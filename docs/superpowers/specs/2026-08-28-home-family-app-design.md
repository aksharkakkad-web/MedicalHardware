# Home and Family App Design

## Goal

Build the first complete mock-backed Adaptive Care Home experience as a separate production frontend. A family member can understand one loved one’s current monitoring state, view simple trends, open an important update, explain what happened, and add or retire normal routines.

## Product separation

- The home app lives in `apps/home-app` with its own product, design, routes, client, fixtures, tests, and runtime.
- It shares monitoring semantics but does not import clinic components, clinic fixtures, staff workflows, device administration, room assignment, calibration, or audit history.
- The frontend uses `HomeMonitoringClient`; later API wiring replaces `MockHomeMonitoringClient` without redesigning components.
- All fixtures are synthetic and all important limitations remain explicit.

## Routes

### `/` — Today

- One plain current-status answer for the loved one.
- A clear explanation that monitoring is support, not a safety guarantee.
- A continuous three-row trend sheet for movement routine, resting pattern, and time at home.
- The most important recent update with a direct link to its explanation.
- A small recent-activity list and direct routine action.

### `/updates/[eventId]` — Family update detail

- Family-safe headline and time.
- “What changed,” “What we noticed,” and “What we cannot tell” sections.
- No clinic confidence percentage, raw sensors, acknowledge/check/resolve buttons, or staff audit trail.
- A simple check-in suggestion that does not replace emergency services.
- Feedback choices: expected, not expected, or unsure; optional plain-language note; optional normal-routine confirmation.
- Saved feedback becomes a permanent read-only summary for this demo visit and browser storage.

### `/routines` — Routines and context

- Add a useful normal routine in one sentence.
- Show active routines before retired history.
- Retire outdated context without deleting it.
- Explain that routines help future explanations but do not directly change warning rules or guarantee outcomes.

## Typed client and mock behavior

`HomeMonitoringClient` exposes only family-safe read/write methods:

- `getHomeOverview()`
- `getHomeUpdate(eventId)`
- `submitHomeFeedback(eventId, input)`
- `getHomeRoutines()`
- `addHomeRoutine(input)`
- `retireHomeRoutine(routineId, input)`

The mock client returns clones, uses expected-version checks for routines, persists feedback/routines locally, rejects invalid text, and safely falls back when stored demo data is malformed.

## Visual direction

The independent home system uses the **Morning Window** direction in `apps/home-app/DESIGN.md`: warm daylight canvas, soft white sheets, sky-blue actions, worded semantic states, spacious typography, one calm answer first, and no clinic-like density.

## Acceptance

- Complete click-through across Today → update detail → feedback and Today → routines → add/retire.
- Normal, important update, limited, away, unavailable, empty, loading, and error language is supported by the client/component structure.
- Desktop and 390px mobile layouts are visually reviewed.
- Keyboard semantics, focus, live confirmations, and readable text are present.
- Tests, lint, typecheck, and production build pass.

## Non-goals

- Real authentication, family permissions, notifications, backend wiring, or hardware telemetry.
- Clinic controls or clinic data exposure.
- Medical advice, diagnosis, emergency triage, or safety guarantees.
