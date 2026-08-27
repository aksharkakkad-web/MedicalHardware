# Clinic Dashboard Foundation Design

**Date:** August 27, 2026

**Owner:** Rishit — frontend and product experience

**Status:** Ready for founder review

## Goal

Build the real, production-quality foundation of the clinic dashboard and prove it with one polished resident-overview screen powered by contract-valid mock data.

This is the first usable slice of the final clinic application. It is not a throwaway prototype, but it is also not the entire clinic product.

## User outcome

A clinic operator can open the app and quickly understand:

- which residents are currently okay;
- which residents need attention;
- whether monitoring is active, limited, paused, or unavailable;
- whether the device or room assignment is causing a limitation;
- when information was last updated.

The operator cannot yet open a complete event-detail workflow or perform acknowledge/check/resolve/feedback actions in this slice.

## Scope

### Included

- `apps/clinic-dashboard/` as an independent Next.js and TypeScript application;
- pnpm-based local development commands;
- a responsive clinic app shell with sidebar, header, main content area, and mobile navigation;
- a small reusable visual system using CSS variables for color, type, spacing, radius, shadow, and status meaning;
- accessible foundations for buttons, cards, status labels, skeleton loading, empty states, and error messages;
- typed frontend domain models derived from the existing contract semantics;
- a `MonitoringClient` interface used by UI code;
- a `MockMonitoringClient` implementation;
- a provider/hook boundary that supplies the active client to screens;
- one contract-valid resident-overview fixture set;
- one polished resident-overview route;
- focused unit/component tests;
- lint, typecheck, test, and production-build commands;
- desktop and mobile browser verification.

### Excluded

- changes to `backend/`, API contracts, database code, or sensor logic;
- live `ApiMonitoringClient` network calls;
- authentication or production permissions;
- full resident detail, event detail, trends, settings, or feedback screens;
- acknowledge/check/resolve behavior;
- the home/family app;
- real hardware or simulated telemetry ingestion;
- deployment.

## Visual direction

The dashboard should feel calm, clear, and operational rather than futuristic or hospital-alarming.

- Use a warm neutral canvas with high-contrast dark text.
- Use green/teal for healthy or active states, amber for attention/limited states, and red only for high or critical urgency.
- Use large readable labels and plain-language explanations instead of dense technical tables.
- Make the most important question easy to answer: “Who needs attention right now?”
- Use color together with text and icons so meaning never depends on color alone.
- Keep motion subtle and functional: navigation, loading, and state changes only.

## Information architecture

The initial shell reserves stable navigation destinations without pretending they are finished:

1. Residents — active in this slice.
2. Events — visible as a future destination but not implemented.
3. Devices — visible as a future destination but not implemented.
4. Settings — visible as a future destination but not implemented.

Unfinished destinations must be clearly disabled or marked as coming later; they must not lead to blank or broken screens.

## Resident overview

The page contains:

1. A page heading and a simple summary of how many residents need attention.
2. Small summary cards for active monitoring, limited/paused monitoring, and open high-priority attention.
3. A resident list or card grid optimized for quick scanning.
4. Each resident item shows:
   - display label;
   - room label;
   - monitoring state;
   - current attention state;
   - short plain-language reason when monitoring is limited, paused, or unavailable;
   - last-updated time;
   - device-health summary when relevant.
5. Loading, empty, and recoverable error states using the same page structure.

No clinical measurement is shown unless its quality is explicit. This first slice may omit physiological measurements entirely rather than show misleading sample precision.

## Frontend architecture

```text
Resident overview page
        ↓ asks for resident summaries
Monitoring client provider/hook
        ↓ uses one interface
MonitoringClient
        ↓ current implementation
MockMonitoringClient
        ↓ returns
Contract-valid resident fixtures
```

Screens and components never import fixture files directly. Only the mock client knows where fixtures live. A later `ApiMonitoringClient` will implement the same interface and replace the mock client without changing the resident-overview components.

## Suggested module boundaries

```text
apps/clinic-dashboard/
├── src/app/                  # routes and app shell
├── src/components/           # shared visual components
├── src/features/residents/   # resident overview feature
├── src/lib/monitoring/       # models, client interface, provider
├── src/mocks/                # mock client and fixtures
└── tests/                    # focused frontend tests
```

Each module has one job:

- routes arrange complete pages;
- components provide reusable visual pieces;
- the residents feature owns resident-specific display logic;
- monitoring owns stable data meanings and client access;
- mocks provide development-only data and behavior.

## Initial mock scenarios

The first fixture set includes enough variety to test honest status communication:

- one resident with active monitoring and no attention needed;
- one resident with a high-priority open event;
- one resident away, with monitoring paused;
- one resident with possible multiple-person presence and limited monitoring;
- one resident unavailable because of a device or assignment problem.

Mock records use synthetic names and identifiers only. They contain no real personal or medical information.

## Error and uncertainty behavior

- Loading shows the page structure with neutral placeholders.
- An empty result explains that no residents are available; it does not imply everybody is safe.
- A recoverable client error explains that the dashboard could not load current information and offers a retry.
- Stale information visibly shows its last-updated time.
- Limited, paused, and unavailable states explain why resident-specific output is restricted.
- Unknown states remain unknown; the UI never invents a normal or safe result.

## Testing and verification

The slice is complete only when all of the following pass:

- lint;
- TypeScript typecheck;
- focused tests for the mock client and resident-overview states;
- production build;
- desktop browser walkthrough;
- mobile browser walkthrough;
- no browser console errors;
- keyboard navigation and visible focus checks;
- loading, empty, error, active, paused, limited, unavailable, and high-attention states visibly checked.

## Acceptance criteria

1. The clinic app starts locally with one documented command.
2. The resident overview is polished and understandable on desktop and mobile.
3. UI components receive data only through the typed monitoring-client boundary.
4. The mock client returns contract-compatible semantics and synthetic data.
5. Honest uncertainty states are as understandable as the normal state.
6. No backend, home-app, hardware, clinical-threshold, or production-auth work enters this slice.
7. Replacing the mock client with a future API client will not require redesigning the page.
8. All listed automated and browser checks pass, or any unavailable check is reported plainly.

## Implementation approach decision

Use one independent Next.js application with local, feature-based modules and a small custom visual system. This keeps the first slice understandable and avoids adding a monorepo abstraction or shared component package before a second frontend actually needs one.

The alternative of building the full clinic dashboard now is rejected because it would mix the foundation, event workflow, device experience, and feedback experience into one large review. The alternative of building only invisible plumbing is rejected because it would not prove the product foundation works for an actual user.
