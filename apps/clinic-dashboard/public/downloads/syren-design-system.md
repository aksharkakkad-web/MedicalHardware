# SYREN clinic design system

**Version:** Native Care V4 — shared staff workspace

**Primary mode:** Clinic operations

**Interface density:** Compact and readable

**Accessibility target:** WCAG 2.2 AA

Native Care helps staff answer two questions: **who needs attention now, and what is the next safe action?** Its Apple-inspired foundation uses native system typography, a soft cool-gray canvas, white grouped surfaces, restrained depth, clear blue controls, and purposeful colored anchors. Content stays crisp and opaque; navigation may use a translucent material. It states uncertainty directly and never implies a diagnosis or proof of safety.

The current user-requested direction supersedes the former Dub-derived flat ledger. Reference principles come from Apple’s [Color](https://developer.apple.com/design/human-interface-guidelines/color) and [Materials](https://developer.apple.com/design/human-interface-guidelines/materials) guidance. These are adapted CSS treatments, not native Apple SDK components or a claim to reproduce Liquid Glass.

## Foundation

`apps/clinic-dashboard/src/styles/design-tokens.css` is the canonical value-bearing source for the clinic dashboard. The home app maps the same core values in its local CSS because the apps do not import styles from one another. Clinic product CSS consumes the `--ac-*` role tokens. Page modules may set layout values, but must not invent new brand colors, radii, shadows, or font families.

| Role | Token | Value |
| --- | --- | --- |
| Canvas | `--ac-canvas` | `#f5f5f7` |
| Surface | `--ac-surface` | `#ffffff` |
| Quiet surface | `--ac-surface-quiet` | `#f1f3f6` |
| Primary ink | `--ac-text-primary` | `#1d1d1f` |
| Secondary ink | `--ac-text-secondary` | `#656972` |
| Hairline | `--ac-border-subtle` | `#e4e7ec` |
| Strong rule | `--ac-border-strong` | `#cdd3dc` |
| Action | `--ac-action` | `#0066d6` |
| Action hover | `--ac-action-hover` | `#0055b6` |

Grouped content panels use 20px corners and a subtle two-level shadow. Controls and inputs use 10px corners; popovers use 16px. Floating menus/dialogs use stronger documented overlay shadows. Full rounding is reserved for compact state markers, dots and real binary switches. Use panels to group a task, never a card for every fact. Canvas, content and navigation are intentionally distinct.

Additional roles: `--ac-chrome` is the navigation surface, `--ac-chrome-translucent` is a legible topbar layer, `--ac-surface-tint` is quiet informational context, `--ac-shadow-soft` is control depth and `--ac-shadow-action` is primary-action depth. Use role tokens rather than page-specific colors. Enabled input boundaries use `--ac-border-control` (`#8793a2`), which maintains at least 3:1 contrast against white; structural panel rules may remain lighter. Content never uses background blur. Reduced-transparency preference removes navigation blur.

## Typography

Use the platform system sans stack: `-apple-system`, `BlinkMacSystemFont`, SF Pro Text when locally available, Segoe UI, Helvetica and Arial. Do not download proprietary Apple fonts. Use the platform monospace stack only for operational identifiers and compact readings; ordinary timestamps may use system sans with tabular numerals. Page titles are 30–36px at weight 600–700, section titles 18–22px at weight 600. Operational body copy is 14px, meaningful metadata at least 12px wherever feasible. Phone inputs use 16px to avoid unintended focus zoom. Hierarchy comes from size, weight, grouping and controlled contrast.

Sentence case is the default. Keep line length near 70 characters for explanations. Prefer plain verbs: “Review event,” “Acknowledge event,” and “Save delivery preferences.”

## Spacing and layout

The base spacing rhythm is 4px. Common steps are 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, and 80px.

- Desktop shell: 232px sidebar, 68px top bar, and 32–36px page gutter.
- Desktop content: one main ledger with an optional 320–350px context rail.
- Toolbar and inputs: 40px minimum height.
- Repeated operational rows: 60–82px based on content.
- Mobile: 16px page gutter and 44px touch targets.

Use whitespace and grouped white surfaces to organize tasks. Keep repeated records inside one divided list or table rather than independent floating cards. Surface padding is generally 20–24px; preserve enough density to show the start of the resident roster on a normal laptop when three concerns are present.

## Action hierarchy

Each focused form has at most one filled electric-blue action. Ledger rows use navigation rather than repeated filled buttons. Secondary actions use a white surface and hairline border. Tertiary actions are text links or row navigation. Repeated rows do not repeat filled buttons. All controls need hover, focus-visible, pressed, disabled, and loading states. Focus uses the blue focus ring and remains visible against white and gray backgrounds.

## App shell

The desktop sidebar uses a soft gray material, a compact blue SYREN mark and small colored navigation symbols. The active destination uses a crisp white selection surface with blue text and subtle depth. The top bar identifies the facility, current view area and approved shared client. “All covered areas” is an explicit choice. Area filtering cannot hide authorized high or critical work. The primary destinations are Overview, Residents, Handover and Events. Facility tools include shared clients, directory imports and monitoring status. Administration is a separate entry; routine care has no personal staff login. A persistent demo label explains synthetic records and absent live alert delivery.

Between 761px and 1050px the sidebar becomes an intentional icon rail with accessible labels. At 760px and below, primary navigation becomes a compact four-item bar above the clinic workspace. Keep the area selector, administration entry and demonstration context readable. On narrow event detail, response controls precede the evidence and history; resident measurements retain their own leading position. The design-system route remains outside clinic chrome so it can be printed and exported.

## Tables and ledgers

Use a soft header row, horizontal hairlines within an opaque white surface, and clearly indicated record navigation. A row contains the minimum facts needed for a decision, then a chevron. Long explanations wrap; do not truncate the reason staff need to understand. Use mono text only for compact timestamps and identifiers.

On mobile, table rows become vertically ordered records:

1. resident, event, or device name;
2. current state and plain-language reason;
3. time, confidence, or assignment details;
4. workflow state;
5. one action or row navigation.

Do not hide critical facts behind hover or a desktop-only column.

## Independent status axes

Do not collapse these facts into one generic badge. A record can be high attention, low confidence, offline, stale, and open at the same time.

1. **Attention** describes resident-facing priority.
2. **Monitoring** describes whether resident-specific output is active, limited, paused, or unavailable. Presence such as away or possible multi-person is separate context that can change this state.
3. **Confidence** describes evidence quality and attribution certainty.
4. **Freshness** describes when evidence was last current.
5. **Device** describes the room unit and its sources, separate from resident health.
6. **Workflow** follows the event contract through detected, open, acknowledged, checked, and resolved.

Exact values come from `docs/DATA_CONTRACT.md` and the typed frontend client. Visual documentation must not add substitute enums.

Show only the axes that change the current decision. Healthy defaults stay neutral. Status indicators use a 6px dot and text, not colored capsules. Color always accompanies a readable label.

## Semantic color

- Green means operationally positive or currently available.
- Amber means watch, limited evidence, delayed delivery, or review needed.
- Red means resident-risk escalation or destructive validation.
- Gray describes device, delivery, stale, missing, or unavailable data conditions; a device problem is not resident risk.
- Electric blue means action, selection, and focus. It never means severity.

Use semantic color in a dot, thin leading rule, or restrained soft background. Do not flood a whole operational section with saturated color.

## Care workflow patterns

The overview leads with the most urgent unresolved work, followed by the resident ledger. The events view separates active work from permanent resolved history. Event detail presents sensor evidence first, AI interpretation second, then immutable workflow history and feedback. Resident detail keeps current attention, monitoring, assignment, setup, context, and history distinct. Device views separate device health from resident safety. Scenario Lab clearly marks synthetic local data.

Shared devices have explicit routine-action grants independently of their area coverage. A view-only station still displays authorized concerns and readings; administration does not create clinical response authority. Stale station edits require explicit review of the latest configuration before saving.

Date/time entry uses the facility zone through `FacilityTimeField`, with normal local date controls and an explicit first/second occurrence choice when clocks repeat. Nonexistent times remain invalid; staff never need to type timestamp offsets.

Resolved events remain immutable; recurrences are linked new events. Low-quality or multi-person data appears as limited or unavailable. The interface never fabricates precision or guesses which person produced a signal.

## AI and medical language

Deterministic monitoring measures anomaly evidence. AI analysis owns ordinary anomaly disposition under the current product architecture; an explicit urgent safety path may create provisional caregiver work that AI cannot suppress. The frontend renders the backend disposition and never creates urgency thresholds or independently discards an event. Unavailable analysis remains visible as pending or needing review. Label its output as an interpretation and keep the supporting evidence visible. Use “possible explanation,” “pattern,” and “needs staff review.” Do not claim diagnosis, emergency detection, or proof that a resident is safe.

Synthetic warnings and thresholds must be labeled test-only. Fixtures, screenshots, and examples contain no real PHI.

## States and accessibility

Every data surface supports loading, empty, error, retry, and unavailable states when its workflow needs them. Success feedback says what changed. Disabled actions remain legible and explain the unmet condition when needed.

Use semantic HTML, logical heading order, real buttons and links, keyboard-correct controls, accessible names, visible focus, and sufficient contrast. Respect reduced motion. At 200% zoom, text wraps without hiding actions. At 390px, there is no horizontal page overflow and every primary interaction remains reachable.

## Shared implementation contract

Reuse these shared components before adding a page-specific pattern:

- `AppShell` for desktop, collapsed, and narrow navigation;
- `Button` and `IconButton` for action hierarchy;
- `StatusPill` for a compact marker plus explicit status text;
- `StatusIndicator` and `SystemState` for explained operational state;
- `ResidentRecords` for resident ledgers;
- `FormField` for labeled input and validation;

The staff screens share `features/workspace/care-shared.tsx` and `care-workspace.module.css` for concern rows, scope explanation, headings, states and follow-up. Administration shares its own frame, section headings and save states. Extend these patterns before inventing another record treatment. The retired overview/event implementations and unused liquid-glass component were removed.

The typed `MonitoringClient` boundary, routes, hooks, fixtures, and workflow handlers are product contracts. `WorkspaceClient` composes that boundary with synthetic frontend workflow metadata; it is not a production server schema. Its provider exposes explicit capabilities and unavailable states pending coordinated backend support. Visual work must preserve them. The rendered `/design-system` route, this document, and `design-tokens.css` must describe the same system.

## Visual review criteria

Review rendered desktop and phone screens before completion. Use restrained operational hierarchy: resident and room, current work, evidence and next action. Reject decorative gradients, blur in clinical content, KPI-card walls, oversized marketing headings, fabricated trend lines, gratuitous avatars, repetitive capsules, empty feature tiles and repeated boilerplate on each row. Limited translucent navigation is allowed; content remains opaque. Keep useful facts and avoid cosmetic counters without a workflow purpose. Use the shared tokens, native type, grouped surfaces, measured spacing and natural language. Aesthetic review does not replace staff usability validation or establish WCAG conformance.
