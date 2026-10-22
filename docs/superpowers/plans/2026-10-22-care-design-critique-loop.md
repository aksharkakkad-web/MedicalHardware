# SYREN concern completion and visual critique loop

**Goal:** Make resolved concerns unmistakably completed and run four screenshot-led design/critique rounds on the clinic experience.

**Reuse verdict:** Extend the merged Native Care V4 frontend at 12d2977 (PR22). Current CareEventDetail and shared ConcernRow always render event.priority even when resolved; this is a presentation bug. Existing lifecycle handlers, immutable history and client interfaces remain authoritative. Only open remote work is backend PR20, with no apps overlap. Work is isolated on cofounder/frontend-care-design-critique.

## Responsibilities

- Designer agent owns clinic presentation, the resolved-state presentation fix, related regression tests and design documentation. It also owns browser interaction during the loop.
- Critic agent examines actual screenshots only and returns blunt, specific visual criticism. It does not edit code or operate the browser.
- Root coordinates, checks requirements/code/tests, and integrates through a PR. No additional agents are needed.

## Completion semantics

- Resolved records show a checkmark, green completion treatment and explicit Resolved text in detail and history lists.
- Original severity remains historical evidence; it must not dominate the current completed state.
- Acknowledgment, a recorded check and resolution remain distinct. Do not auto-resolve a record merely to make it green.
- Active high/critical work retains clear urgency; unavailable readings and device trouble retain separate meanings.
- Test both resolved presentation and continued urgency for unresolved records. Verify the real rendered states.

## Four rounds

For each round, the designer makes a coherent visual pass, captures fresh screenshots of the actual app and sends their absolute paths to the critic. The critic opens every image and identifies concrete defects in hierarchy, density, color, geometry, type, interactions and state clarity. The designer considers the feedback and records what changed or why a suggestion was rejected. The next round must contain real revisions, not recycled screenshots. After round four, address the final actionable findings and capture the final result.

Required coverage across the loop: overview, active concern, resolved concern detail/history, resident record, and a 390px phone view. No fake charts, invented values, marketing filler, hidden uncertainty or functionality sacrificed for a prettier screenshot. Preserve useful first-screen density and source timestamps.

Screenshots and the critique log are stored outside Git under /Users/mahin/Documents/Codex/2026-10-22/SYREN Design Critique/. Record a concise summary in the implementation handoff.

## Verification and delivery

Run the clinic tests, lint, typecheck and production build. Root checks the final diff and actual state behavior; resolve failures before delivery. Update the design system to describe the final interface. Create a PR, inspect CI/review availability, and merge under the user's standing merge authorization. Preserve the primary hardware checkout, backend PR20 and home app.
