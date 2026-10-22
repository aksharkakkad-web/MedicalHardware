# SYREN clinic design system

**Version:** Native Care V6 — shared staff workspace

**Primary mode:** Clinic operations

**Interface density:** Compact and readable

**Accessibility target:** WCAG 2.2 AA

Native Care helps staff answer two questions: **who needs attention now, and what is the next safe action?** Its foundation uses native system typography, a cool light canvas, white grouped surfaces, a deep blue-slate navigation frame and restrained blue-teal controls. Content stays crisp and opaque. It states uncertainty directly and never implies a diagnosis or proof of safety.

The current user-requested direction adapts UI/UX Pro Max's accessible healthcare/senior-care palette and operational density guidance. Its marketing-page pattern was rejected because staff need a working ledger. Retain the native typography and clarity informed by Apple’s [Color](https://developer.apple.com/design/human-interface-guidelines/color) guidance. These are CSS treatments, not native Apple SDK components. No WCAG or clinical validation follows from a skill recommendation.

## Foundation

`apps/clinic-dashboard/src/styles/design-tokens.css` is the canonical value-bearing source for the clinic dashboard. The separate home app owns its own visual layer; these clinic changes do not implicitly revise it. Clinic product CSS consumes the `--ac-*` role tokens. Page modules may set layout values, but must not invent new brand colors, radii, shadows, or font families.

| Role | Token | Value |
| --- | --- | --- |
| Canvas | `--ac-canvas` | `#f4f7f8` |
| Surface | `--ac-surface` | `#ffffff` |
| Quiet surface | `--ac-surface-quiet` | `#eef4f5` |
| Primary ink | `--ac-text-primary` | `#19333f` |
| Secondary ink | `--ac-text-secondary` | `#586b74` |
| Hairline | `--ac-border-subtle` | `#dce5e9` |
| Strong rule | `--ac-border-strong` | `#c4d1d7` |
| Action | `--ac-action` | `#086b83` |
| Action hover | `--ac-action-hover` | `#07556b` |
| Navigation | `--ac-navigation-bg` | `#173b4a` |
| Navigation text | `--ac-navigation-text` | `#e1edf2` |
| Navigation supporting text | `--ac-navigation-muted` | `#b0c7d1` |
| Navigation selection | `--ac-navigation-active-bg` | `#2b5666` |
| Navigation accent | `--ac-navigation-accent` | `#a0e1e3` |

Grouped content panels use 12px corners, a consistent quiet border and no shadow. Controls and inputs use 8px corners; popovers use 16px. Floating menus/dialogs use stronger documented overlay shadows. Full rounding is reserved for compact state markers, dots and real binary switches. Use panels to group a task, never a card for every fact. Equivalent measurement labels share one neutral color; semantic color is reserved for real state, current selection and actions. Evidence sequence numbers are plain muted numerals, and resolved rows use one explicit check/completion marker. Canvas, content and navigation are intentionally distinct.

Additional roles: `--ac-chrome` and `--ac-chrome-translucent` provide the light topbar, `--ac-navigation-*` provide the dark navigation frame, and `--ac-surface-tint` is quiet informational context. `--ac-shadow-soft` and `--ac-shadow-card` are `none`; `--ac-shadow-action` gives primary actions restrained depth. Use role tokens rather than page-specific colors. Enabled input boundaries use `--ac-border-control` (`#7b909b`), which maintains at least 3:1 contrast against white; structural panel rules may remain lighter. Content and navigation do not use background blur. Reduced-transparency preference makes the topbar opaque.

## Typography

Use the platform system sans stack: `-apple-system`, `BlinkMacSystemFont`, SF Pro Text when locally available, Segoe UI, Helvetica and Arial. Do not download proprietary Apple fonts. Use the platform monospace stack only for operational identifiers and compact readings; ordinary timestamps may use system sans with tabular numerals. Page titles are 30–36px at weight 600–700, section titles 18–22px at weight 600. Operational body copy is 14px, meaningful metadata at least 12px wherever feasible. Phone inputs use 16px to avoid unintended focus zoom. Hierarchy comes from size, weight, grouping and controlled contrast.

Sentence case is the default. Keep line length near 70 characters for explanations. Prefer plain verbs: “Review event,” “Acknowledge event,” and “Save delivery preferences.”

## Spacing and layout

The base spacing rhythm is 4px. Common steps are 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, and 80px.

- Desktop shell: 232px sidebar, 68px top bar, and 32–36px page gutter.
- Desktop content: one main ledger with an optional 320–350px context rail.
- Form fields and buttons: 44px minimum height. The compact area selector is 40px on desktop and 44px on phones.
- Repeated operational rows: 60–82px based on content.
- Mobile: 16px page gutter and 44px touch targets.

Use whitespace and grouped white surfaces to organize tasks. Keep repeated records inside one divided list or table rather than independent floating cards. Surface padding is generally 20–24px; preserve enough density to show the start of the resident roster on a normal laptop when three concerns are present.

## Action hierarchy

Each focused form has at most one filled blue-teal action. Ledger rows use navigation rather than repeated filled buttons. Secondary actions use a flat white surface and the same accessible border token as inputs and the scope selector. Tertiary actions are text links or row navigation. Repeated rows do not repeat filled buttons. All controls need hover, focus-visible, pressed, disabled, and loading states. Focus uses the blue-teal ring; navigation uses a light outline on its dark surface. Hover changes color without moving or scaling a control. Respect reduced motion.

## App shell

The desktop sidebar uses deep blue-slate with a pale cyan SYREN mark and consistent supporting navigation symbols. The active destination combines a lighter slate surface, white text and a narrow cyan inset marker. The phone marker sits below the selected destination. Light-on-dark navigation text is contrast checked separately from content. The light top bar identifies the facility, current view area and approved shared client. “All covered areas” is an explicit choice. Area filtering cannot hide authorized high or critical work. The primary destinations are Overview, Residents, Handover and Events. Facility tools include shared clients, directory imports and monitoring status. Administration is a separate entry; routine care has no personal staff login. A persistent demo label explains synthetic records and absent live alert delivery.

Between 761px and 1050px the sidebar becomes an intentional icon rail with accessible labels. At 760px and below, primary navigation becomes a compact four-item bar above the clinic workspace. Keep the area selector, administration entry and demonstration context readable. On narrow event detail, response controls precede evidence, interpretation/history and then record details. Resident detail puts actual open concerns above a compact measurement band. The phone header combines facility and demo context without repeating the area selection. The design-system route remains outside clinic chrome so it can be printed and exported.

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

Show only the axes that change the current decision. Healthy defaults stay neutral. Routine status indicators use a 6px dot and text. Resolved workflow uses an explicit green check and Resolved label, with a restrained completion marker where needed. Color always accompanies a readable label.

## Semantic color

- Green means operationally positive, currently available, or explicitly resolved workflow. A resolved check means the care workflow ended; it does not claim that the resident is healthy or safe.
- Amber means watch, limited evidence, delayed delivery, or review needed.
- Red means resident-risk escalation or destructive validation.
- Gray describes device, delivery, stale, missing, or unavailable data conditions; a device problem is not resident risk.
- Blue-teal means action, selection, and focus. Pale cyan on the navigation frame identifies the brand and current destination. Neither means severity.

Use semantic color in a dot, thin leading rule, or restrained soft background. Do not flood a whole operational section with saturated color.

## Care workflow patterns

The overview leads with the most urgent unresolved work, followed by the resident ledger. Keep the attention header compact and show the start of actual resident rows at a normal laptop height. Queues and the roster use a consistent full room locator followed by resident name; do not infer a room number from an arbitrary location label. The events view separates active work from permanent resolved history. Event detail presents sensor evidence first, AI interpretation second, then immutable workflow history and feedback. Resident detail keeps current attention, monitoring, assignment, setup, context, and history distinct. Actual open concerns precede compact supplied measurements; units and observation times remain readable. Device views separate device health from resident safety. Scenario Lab clearly marks synthetic local data.

Shared devices have explicit routine-action grants independently of their area coverage. A view-only station still displays authorized concerns and readings; administration does not create clinical response authority. Stale station edits require explicit review of the latest configuration before saving.

Date/time entry uses the facility zone through `FacilityTimeField`, with normal local date controls and an explicit first/second occurrence choice when clocks repeat. Nonexistent times remain invalid; staff never need to type timestamp offsets.

Priority and response state are separate typographic elements. Overdue response belongs in the response column with an explicit label, rather than inside a faint date string. Acknowledged or checked does not claim that a responder is physically present.

Open concern rows expose a Respond button beside the record link. Event detail exposes Response & outcome near the heading. Both open the same native modal, with current room, resident, concern and limitations, plus Record response and Resolve concern choices. Resolution requires a completed check, no outstanding event follow-up and the existing action permission. Keep the close control visible while the content scrolls, contain interaction in the modal, and restore focus to the trigger or workspace after closing. Pending saves block dismissal; actual unsaved entries require Keep editing or Discard and close. Preserve drafts through temporary eligibility changes. Successful resolution keeps the modal open with a green check and historical priority even when its queue row disappears. Closing never records a care action.

Resolved events remain immutable; recurrences are linked new events. Completed records use green/check/Resolved as the dominant state; original severity is quiet historical context and cannot continue to paint the record as a current red problem. History shows closure time and source attribution when supplied. Historical device/confidence fields are explicitly labeled at review, and original interpretation limitations remain preserved. Low-quality or multi-person data appears as limited or unavailable. The interface never fabricates precision or guesses which person produced a signal.

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

Review rendered desktop and phone screens before completion. Use restrained operational hierarchy: resident and room, current work, evidence and next action. Reject decorative gradients, background blur, KPI-card walls, oversized marketing headings, fabricated trend lines, gratuitous avatars, repetitive capsules, empty feature tiles and repeated boilerplate on each row. Keep useful facts and avoid cosmetic counters without a workflow purpose. Use the shared tokens, native type, grouped surfaces, measured spacing and natural language. Aesthetic review does not replace staff usability validation or establish WCAG conformance.
