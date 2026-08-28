# Clinic Dashboard Completion and Redesign

## Goal

Turn the existing clinic demo into a complete, believable staff workflow: see the clinic at a glance, find attention items, inspect one resident, handle an event, and confirm the result. The interface should feel calm, precise, and premium without hiding uncertainty or pretending to diagnose anyone.

The user explicitly approved unattended execution and asked for an Apple-like, professional direction. That is the design approval for this specification.

## Product boundary

- This work stays inside Rishit's clinic-frontend lane.
- Screens consume the typed `MonitoringClient`; components never import fixtures.
- Data remains synthetic and is labelled as such.
- The UI says what the sensors observed, not what medically happened.
- Backend, firmware, hardware, shared schemas, and the separate home app are not changed.

## Chosen visual direction: Calm Care Folio

The interface borrows the useful idea from a well-organized care-plan folio: a stable index at the left, one clear sheet of work in the middle, and deeper evidence behind the current item. It combines that with native Apple-platform qualities: quiet surfaces, excellent type hierarchy, gentle material separation, generous room around important information, and motion only when it explains state.

Seven grounded directions were considered:

1. Nursing-station whiteboard — strong scanability, but too visually busy.
2. Apple Health/settings — calm and familiar, but too generic alone.
3. Airport operations board — excellent fixed-column scanning, but impersonal.
4. Care-plan folio — selected; human, layered, and suited to progressive detail.
5. Lab instrument readout — precise, but too technical for everyday caregivers.
6. Hotel floor/concierge board — useful room metaphor, but weak for event evidence.
7. Museum archive — elegant hierarchy, but too passive for urgent work.

The assigned seed was direction 4, recorded with seed key `1d7b2559`. Challengers reinforced, but did not replace, it: split-flap boards support fixed-column event rows; data-art references support numerical restraint; material references support subtle layering. Dark coded systems and decorative motion were rejected because they reduce calmness and clarity.

## Information architecture

The clinic console has three real destinations:

- **Overview:** clinic-level attention, monitoring coverage, and every resident.
- **Events:** a searchable and filterable queue of open and historical events.
- **Resident detail:** the current room assignment, monitoring truth, device health, and linked event history for one resident.

Event detail remains the action workspace. Staff can acknowledge, record a check, resolve with feedback, and review permanent history. Every screen links naturally to the next screen; there are no dead “coming soon” navigation items.

## Core interaction flow

1. Staff open Overview and immediately see whether anyone needs attention.
2. They select an attention row or open the Events queue.
3. They open the event and see the next required action beside the evidence.
4. They acknowledge, check, then resolve with a plain-language outcome.
5. The event becomes immutable history and the overview updates.
6. They can open the resident at any time to understand room, device, and monitoring context.

## Visual system

- Warm near-white canvas with true-white working surfaces.
- Charcoal text, cool gray secondary text, and thin neutral dividers.
- A restrained cobalt accent for selection and actions.
- Amber and red only for attention; green only for confirmed healthy/resolved state.
- 8px spacing rhythm, 12–20px corner radii, and low soft shadows.
- System-first typography with compact labels and large titles only where hierarchy needs them.
- Simple consistent SVG icons with round strokes; no letter placeholders.
- Tables become stacked cards on small screens; the main action remains reachable.

## Required states

- Loading, empty, and error states on fetched screens.
- Active, limited, paused, unavailable, and ambiguous monitoring.
- Online, degraded, and offline devices.
- Open, acknowledged, checked, and resolved events.
- Pending/unavailable AI interpretation clearly separated from deterministic warnings.
- Keyboard focus, accessible labels, useful status text, and reduced-motion support.

## Acceptance criteria

- Overview, event queue, resident detail, and event detail all exist and link together.
- Event filters and search work with the mock client.
- The event action journey still persists locally and updates other screens.
- No component reaches directly into fixtures.
- Desktop and narrow mobile layouts remain readable and operable.
- Unit tests, lint, typecheck, and production build pass.
- The real app is visually reviewed at desktop and mobile sizes before delivery.
