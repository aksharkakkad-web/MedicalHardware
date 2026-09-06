# Adaptive Care design system

**Version:** Care Ledger V2

**Primary mode:** Clinic operations

**Interface density:** Compact and readable

**Accessibility target:** WCAG 2.2 AA

Care Ledger helps staff answer two questions: **who needs attention now, and what is the next safe action?** Its Dub-derived visual foundation uses a white canvas, neutral black type, gray alternate surfaces, hairline rules, and electric blue only for brand and interaction. It states uncertainty directly and never implies a diagnosis or proof of safety.

## Foundation

`apps/clinic-dashboard/src/styles/design-tokens.css` is the canonical value-bearing source for the clinic dashboard. The home app maps the same core values in its local CSS because the apps do not import styles from one another. Clinic product CSS consumes the `--ac-*` role tokens. Page modules may set layout values, but must not invent new brand colors, radii, shadows, or font families.

| Role | Token | Value |
| --- | --- | --- |
| Canvas | `--ac-canvas` | `#ffffff` |
| Surface | `--ac-surface` | `#ffffff` |
| Quiet surface | `--ac-surface-quiet` | `#f5f5f5` |
| Primary ink | `--ac-text-primary` | `#171717` |
| Secondary ink | `--ac-text-secondary` | `#737373` |
| Hairline | `--ac-border-subtle` | `#e5e5e5` |
| Strong rule | `--ac-border-strong` | `#d4d4d4` |
| Action | `--ac-action` | `#2563eb` |
| Action hover | `--ac-action-hover` | `#1d4ed8` |

Resting sections have no shadow. Floating menus and dialogs may use the documented overlay shadows. Cards use 12px corners, buttons use 8px, and inputs use 6px. Full rounding is reserved for status tags, dots, and real binary switches.

## Typography

Use Geist Sans for interface text and Geist Mono for timestamps, identifiers, and operational readings. Page titles are 30–36px at weight 600–650. Section titles are 18–24px at weight 500–650. Operational body copy is 13–14px; meaningful metadata is never smaller than 11px and should be 12px whenever space permits. Weight creates the hierarchy, while color and size remain restrained.

Sentence case is the default. Keep line length near 70 characters for explanations. Prefer plain verbs: “Review event,” “Acknowledge event,” and “Save delivery preferences.”

## Spacing and layout

The base spacing rhythm is 4px. Common steps are 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, and 80px.

- Desktop shell: 208px sidebar, 56px top bar, and 32–40px page gutter.
- Desktop content: one main ledger with an optional 320–350px context rail.
- Toolbar and inputs: 40px minimum height.
- Repeated operational rows: 60–82px based on content.
- Mobile: 16px page gutter and 44px touch targets.

Use whitespace and rules to group related facts. A border should usually replace a container. Cards are reserved for a focused action, summary, or secondary rail; repeated records belong in a table or divided list.

## Action hierarchy

Each view has one filled electric-blue action. Secondary actions use a white surface and hairline border. Tertiary actions are text links or row navigation. Repeated rows do not repeat filled buttons. All controls need hover, focus-visible, pressed, disabled, and loading states. Focus uses the blue focus ring and remains visible against white and gray backgrounds.

## App shell

The desktop sidebar is quiet and compact. The active destination uses a pale blue field with blue icon and text. The top bar identifies the clinic without competing with page content.

Between 761px and 1050px the sidebar becomes an intentional icon rail with accessible labels. At 760px and below, primary navigation becomes a compact four-item bar above the clinic workspace. The design-system route remains outside clinic chrome so it can be printed and exported.

## Tables and ledgers

Use a muted header row, horizontal hairlines, and whole-row navigation. A row contains the minimum facts needed for a decision, then a chevron. Long explanations wrap; do not truncate the reason staff need to understand. Use mono text only for compact timestamps and identifiers.

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

Resolved events remain immutable; recurrences are linked new events. Low-quality or multi-person data appears as limited or unavailable. The interface never fabricates precision or guesses which person produced a signal.

## AI and medical language

AI may explain a structured anomaly evidence packet. It does not monitor telemetry and cannot suppress deterministic warnings. Label its output as an interpretation and keep the supporting evidence visible. Use “possible explanation,” “pattern,” and “needs staff review.” Do not claim diagnosis, emergency detection, or proof that a resident is safe.

Synthetic warnings and thresholds must be labeled test-only. Fixtures, screenshots, and examples contain no real PHI.

## States and accessibility

Every data surface supports loading, empty, error, retry, and unavailable states when its workflow needs them. Success feedback says what changed. Disabled actions remain legible and explain the unmet condition when needed.

Use semantic HTML, logical heading order, real buttons and links, keyboard-correct controls, accessible names, visible focus, and sufficient contrast. Respect reduced motion. At 200% zoom, text wraps without hiding actions. At 390px, there is no horizontal page overflow and every primary interaction remains reachable.

## Shared implementation contract

Reuse these shared components before adding a page-specific pattern:

- `AppShell` for desktop, collapsed, and narrow navigation;
- `Button` and `IconButton` for action hierarchy;
- `StatusPill` for a dot plus status text;
- `StatusIndicator` and `SystemState` for explained operational state;
- `AttentionItem` for prioritized work;
- `ResidentRecords` for resident ledgers;
- `FormField` for labeled input and validation;
- `LiquidGlassCard` only as its retained compatibility name; it renders as a flat bordered surface in Care Ledger.

The typed `MonitoringClient` boundary, routes, hooks, fixtures, and workflow handlers are product contracts. Visual work must preserve them. The rendered `/design-system` route, this document, and `design-tokens.css` must describe the same system.
