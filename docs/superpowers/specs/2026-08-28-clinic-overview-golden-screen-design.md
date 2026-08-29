# Clinic Overview Golden Screen Design

## Goal

Turn the clinic Overview into the visual standard for the rest of the product: calm, clear, trustworthy, and polished enough for a professional healthcare software company.

The approved visual reference is `docs/design-references/clinic-overview-concept.png`. It guides composition, color, spacing, hierarchy, and density. It is not a new product specification and must not replace existing working behavior.

## What stays the same

- Keep every existing icon and icon component unchanged.
- Keep the typed frontend client, routes, links, resident data, event data, and honest loading/error/empty states.
- Keep the safety language and product boundaries from the PRD and data contract.
- Do not add backend work, new dependencies, invented clinical claims, or fake health measurements.

## Visual direction

- Use a warm, nearly white canvas with crisp white content surfaces.
- Use cobalt blue for the main action and navigation emphasis.
- Use restrained red only for urgent attention, amber for limited confidence, and green for healthy status.
- Create more breathing room, stronger alignment, calmer borders, and a clear reading order.
- Prefer one continuous resident sheet over a pile of disconnected cards.
- Make the page feel like an operational clinic workspace, not a generic analytics template.

## Page composition

1. A calm shared shell with a clear sidebar, compact top bar, and unchanged icons.
2. A strong page introduction explaining what the clinic should focus on now.
3. One attention banner showing the real number of residents needing attention and linking to the most important event.
4. A roomy resident sheet preserving all existing rows, states, and navigation.
5. A narrow context rail showing coverage and device health calculated only from the residents already returned by the client.
6. Responsive behavior that stacks cleanly on small screens without hiding important actions.

## Acceptance criteria

- The Overview closely follows the approved reference's color, spacing, hierarchy, and composition.
- Existing icons are not replaced or edited.
- No existing route, resident action, event action, or truthful state is lost.
- Context figures are derived from existing client data and never fabricated.
- The page works at a 1440px desktop width and a 390px phone width without horizontal overflow.
- Shared-shell changes remain usable on the Events and Scenario Lab screens.
- Frontend tests, lint, typecheck, and production build pass.
- The rendered page is reviewed visually and refined before completion.

## Non-goals

- Redesigning every clinic screen in this pass.
- Connecting to the unfinished real backend.
- Changing contracts, fixtures, medical logic, or the icon set.
- Adding decorative charts that do not help a clinic worker decide what to do next.
