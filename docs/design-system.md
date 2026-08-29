# Adaptive Care design system

**Version:** 2.1

**Direction:** Warm Indigo

**Status:** Approved foundation for new frontend work

**Primary mode:** Clinic operations

**Secondary mode:** Home and family experience

This document is the machine-readable source of truth for Adaptive Care UI work. It replaces every earlier color, type, spacing, radius, shadow, and component rule.

The system must help a staff member answer one question within two seconds:

> Which resident needs my attention right now?

The interface is calm because the work is stressful. It is dense because staff scan many residents. It is precise because missing or unreliable information can change a care decision.

## 1. Product character

Adaptive Care should feel calm, warm, technical, dense, and honest. It must never feel sleepy, decorative, cryptic, cramped, or falsely certain.

The visual identity uses warm neutral backgrounds, white working surfaces, deep indigo actions, compact typography, hairline structure, and semantic colors reserved for meaning.

Do not imitate a hospital alarm console. Do not imitate a generic pastel SaaS dashboard. Do not create a dark command center.

## 2. Product modes

### Clinic operations

Clinic screens optimize for repeated scanning, fast triage, keyboard use, clear ownership, and reliable state changes. Lists and tables are the main layout pattern.

### Home and family

The home product inherits the font, color roles, controls, focus behavior, and accessibility rules. It uses more space, fewer simultaneous facts, simpler language, and no clinic queue density.

Sharing the design system does not mean sharing page composition.

## 3. Non-negotiable rules

1. Resident risk, device health, data confidence, monitoring condition, and workflow state are separate facts.
2. Red is reserved for resident-risk escalation and destructive validation. Device failure does not become red unless policy separately marks its operational priority as high or critical.
3. Missing, stale, limited, or unavailable data never looks normal.
4. Color never carries meaning alone. Use a label and a stable icon or structural treatment.
5. The attention queue leads the clinic overview. Supporting metrics never compete with it.
6. Repeated records use lists or tables. Cards hold summaries, focused tasks, or progressive detail.
7. One decision area has one primary action and no more than two visible secondary actions.
8. Components use semantic tokens. Page CSS does not use raw hex values.
9. Every interactive component has keyboard, focus, loading, disabled, error, and responsive behavior.
10. The real rendered screen must pass visual inspection before it is complete.

## 4. Color architecture

Color has three layers:

1. **Foundation values** are the raw scales.
2. **Role tokens** describe interface jobs such as canvas, text, border, and action.
3. **Domain tokens** describe product meaning such as resident risk, device health, confidence, and workflow.

Components consume role and domain tokens. They do not consume foundation values directly.

### 4.1 Warm neutral foundation

| Token | Value | Use |
|---|---:|---|
| `warm-0` | `#FFFFFF` | Working surface |
| `warm-25` | `#FCFCFA` | Raised neutral surface |
| `warm-50` | `#F7F6F2` | Main canvas |
| `warm-100` | `#F0EFE9` | Sidebar and quiet fill |
| `warm-150` | `#E9E8E2` | Hover fill |
| `warm-200` | `#DCDBD5` | Hairline structure |
| `warm-300` | `#C8C8C1` | Strong border |
| `warm-400` | `#A0A19B` | Disabled decoration |
| `warm-500` | `#73767A` | Tertiary text, only at 14px or larger |
| `warm-600` | `#59616D` | Secondary text |
| `warm-700` | `#414851` | Strong secondary text |
| `warm-800` | `#2C3239` | Headings |
| `warm-900` | `#1F2328` | Primary text |
| `warm-950` | `#14171B` | Highest contrast ink |

### 4.2 Brand indigo foundation

| Token | Value | Use |
|---|---:|---|
| `indigo-25` | `#FBFBFF` | Faint wash |
| `indigo-50` | `#F4F4FF` | Selected background |
| `indigo-100` | `#EAEBFF` | Strong selected background |
| `indigo-200` | `#D7D9FF` | Selected border |
| `indigo-300` | `#B5B9F4` | Decorative data accent |
| `indigo-400` | `#858BE3` | Non-text accent |
| `indigo-500` | `#636AD4` | Brand mark |
| `indigo-600` | `#4D55C5` | Primary action and focus |
| `indigo-700` | `#3F46A8` | Hover and accessible brand text |
| `indigo-800` | `#333888` | Pressed action |
| `indigo-900` | `#292D6A` | Strong brand ink |

Indigo means navigation, selection, focus, or an available staff action. It never means severity.

### 4.3 Semantic families

Every semantic family contains a soft background, border, text and icon color, and strong color.

| Family | Soft | Border | Text and icon | Strong |
|---|---:|---:|---:|---:|
| Positive | `#E7F5F0` | `#A9D8C8` | `#176B57` | `#0F5746` |
| Watch | `#FFF2DD` | `#E8C58D` | `#8A4D0F` | `#6D3908` |
| Resident risk | `#FDEBED` | `#E4A0A7` | `#B4232D` | `#8F1721` |
| Device and data | `#EAF2FB` | `#AEC9E5` | `#315E91` | `#244A73` |
| Unavailable | `#EEF1F2` | `#C8D0D3` | `#4F5B66` | `#39444D` |

Approved small-text pairs exceed WCAG 2.2 AA contrast:

- positive text on positive soft: 5.71:1;
- watch text on watch soft: 6.03:1;
- resident-risk text on resident-risk soft: 5.68:1;
- device text on device soft: 5.92:1;
- unavailable text on unavailable soft: 6.12:1;
- white text on primary indigo: 6.14:1.

### 4.4 Role tokens

```css
:root {
  color-scheme: light;
  --ac-canvas: #F7F6F2;
  --ac-surface: #FFFFFF;
  --ac-surface-raised: #FCFCFA;
  --ac-surface-quiet: #F0EFE9;
  --ac-surface-hover: #E9E8E2;
  --ac-text-primary: #1F2328;
  --ac-text-secondary: #59616D;
  --ac-text-strong-secondary: #414851;
  --ac-text-disabled: #73767A;
  --ac-text-inverse: #FFFFFF;
  --ac-border-subtle: #DCDBD5;
  --ac-border-strong: #C8C8C1;
  --ac-border-interactive: #A0A19B;
  --ac-action: #4D55C5;
  --ac-action-hover: #3F46A8;
  --ac-action-pressed: #333888;
  --ac-action-soft: #F4F4FF;
  --ac-action-soft-strong: #EAEBFF;
  --ac-action-border: #D7D9FF;
  --ac-focus: #4D55C5;
  --ac-positive-bg: #E7F5F0;
  --ac-positive-border: #A9D8C8;
  --ac-positive-text: #176B57;
  --ac-positive-strong: #0F5746;
  --ac-watch-bg: #FFF2DD;
  --ac-watch-border: #E8C58D;
  --ac-watch-text: #8A4D0F;
  --ac-watch-strong: #6D3908;
  --ac-risk-bg: #FDEBED;
  --ac-risk-border: #E4A0A7;
  --ac-risk-text: #B4232D;
  --ac-risk-strong: #8F1721;
  --ac-device-bg: #EAF2FB;
  --ac-device-border: #AEC9E5;
  --ac-device-text: #315E91;
  --ac-device-strong: #244A73;
  --ac-unavailable-bg: #EEF1F2;
  --ac-unavailable-border: #C8D0D3;
  --ac-unavailable-text: #4F5B66;
  --ac-unavailable-strong: #39444D;
}
```

### 4.5 Color rules

- Normal monitoring uses primary text plus a small positive icon or word. Do not tint the whole row green.
- Critical resident risk may use a solid red action or a soft red row treatment. High risk uses the soft treatment. Both keep explicit labels.
- Device-only problems use the device family and a hardware icon. A separate priority field may elevate the item.
- Low confidence uses the device and data family with an explicit reason.
- Unavailable uses the unavailable family. Never render last-known values as current.
- Decorative supporting cards may use indigo washes. Do not use semantic colors as decoration.
- Dark mode is out of scope for V2.1. Forced-colors and high-contrast modes are required.

## 5. Typography

Use **Inter Variable** for the full product. Its text optical size supports small interface text, its tall x-height aids scanning, and its tabular numbers align times, counts, durations, and measurements.

Self-host WOFF2 files. Do not depend on a third-party font request at runtime.

```css
html {
  font-family: "Inter Variable", Inter, ui-sans-serif, system-ui, -apple-system,
    BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-optical-sizing: auto;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
}
.numeric { font-variant-numeric: tabular-nums lining-nums; }
.identifier { font-variant-numeric: tabular-nums slashed-zero; }
```

### Type scale

| Role | Size / line height | Weight | Use |
|---|---|---:|---|
| Display | 32 / 38px | 650 | Product or empty-state moments only |
| Page title | 28 / 34px | 650 | One per page |
| Major heading | 22 / 28px | 650 | Attention or detail section |
| Section heading | 18 / 24px | 650 | Panel and table groups |
| Record title | 15 / 21px | 600 | Resident, event, device |
| Body | 14 / 20px | 400 | Default reading text |
| Body strong | 14 / 20px | 550 | Important explanation |
| Label | 13 / 18px | 550 | Controls and table headings |
| Metadata | 12 / 17px | 450 | Time, room, source, secondary facts |
| Overline | 11 / 16px | 650 | Short section label only |

Do not use meaningful text smaller than 12px. Use sentence case. Long safety text wraps and remains available at 200% zoom.

## 6. Spacing and density

Use a 4px base grid.

```css
:root {
  --ac-space-0: 0;
  --ac-space-0-5: 2px;
  --ac-space-1: 4px;
  --ac-space-1-5: 6px;
  --ac-space-2: 8px;
  --ac-space-3: 12px;
  --ac-space-4: 16px;
  --ac-space-5: 20px;
  --ac-space-6: 24px;
  --ac-space-8: 32px;
  --ac-space-10: 40px;
  --ac-space-12: 48px;
  --ac-space-16: 64px;
  --ac-space-20: 80px;
}
```

- **Comfortable** is the default. Controls are 40px high and rows are 60 to 68px.
- **Compact** is an opt-in desktop preference. Controls are 36px high and rows are 48 to 56px. Text and semantic labels do not shrink.
- **Touch** activates for coarse pointers or narrow screens. Primary targets are at least 44 by 44px.

## 7. Geometry, borders, elevation, and motion

```css
:root {
  --ac-radius-xs: 4px;
  --ac-radius-sm: 6px;
  --ac-radius-control: 8px;
  --ac-radius-card: 10px;
  --ac-radius-popover: 12px;
  --ac-radius-dialog: 14px;
  --ac-radius-pill: 999px;
  --ac-shadow-card: 0 1px 2px rgb(20 23 27 / 4%);
  --ac-shadow-popover: 0 8px 24px rgb(20 23 27 / 12%), 0 2px 6px rgb(20 23 27 / 8%);
  --ac-shadow-dialog: 0 24px 64px rgb(20 23 27 / 18%), 0 6px 18px rgb(20 23 27 / 10%);
  --ac-overlay: rgb(20 23 27 / 42%);
  --ac-duration-instant: 80ms;
  --ac-duration-fast: 120ms;
  --ac-duration-standard: 160ms;
  --ac-duration-emphasis: 240ms;
  --ac-ease-standard: cubic-bezier(.2, 0, 0, 1);
  --ac-ease-exit: cubic-bezier(.4, 0, 1, 1);
}
```

Base surfaces use borders, not shadows. Shadows identify overlap. Motion explains focus, selection, loading, and saved state. Do not pulse critical rows.

## 8. Layout system

### Desktop shell

- Sidebar: 232px.
- Top bar: 56px.
- Page max width: 1600px.
- Page padding: 32px.
- Main content gap: 24px.
- Detail split: `minmax(0, 1fr) 360px`.

### Breakpoints

| Width | Behavior |
|---|---|
| 1440px and wider | Full table, context rail, 32px page padding |
| 1200 to 1439px | Full table with lower-priority columns compressed |
| 960 to 1199px | Collapsible sidebar, detail rail moves below or into sheet |
| 768 to 959px | Navigation drawer, simplified table, 24px padding |
| Below 768px | Ordered record list, full-screen filters and details, 16px padding |

Column survival order:

1. Resident and room
2. Attention reason
3. Resident risk
4. Confidence and freshness
5. Workflow state and owner
6. Primary action
7. Device detail
8. Secondary timestamps and metadata

Never hide the first six without placing the information inside the same record.

## 9. State model

Do not create one generic `status` property.

| Axis | Values |
|---|---|
| Resident risk | `critical`, `high`, `watch`, `none` |
| Monitoring condition | `active`, `away`, `paused`, `possible_multi_person`, `calibrating`, `limited`, `unavailable` |
| Data confidence | `high`, `medium`, `low`, `unavailable` |
| Device health | `online`, `degraded`, `buffering`, `retrying`, `offline`, `assignment_unavailable`, `not_yet_available` |
| Workflow | `new`, `acknowledged`, `assigned`, `checked`, `resolved`, `overdue` |
| Freshness | `current`, `delayed`, `stale`, `unknown` |

Confidence includes a reason when not high. Freshness shows relative age and makes exact time available.

Precedence:

1. Critical and high resident risk lead the hierarchy.
2. Unavailable or stale evidence stays visible beside risk.
3. Device failure never erases a resident event.
4. Workflow ownership does not lower resident risk.
5. Resolved events leave the active queue and remain immutable.
6. A recurrence creates a new linked event.

## 10. Attention item

The attention item is the main clinic component. It contains resident and room, direct reason, resident risk, confidence and explanation, freshness, device condition when relevant, workflow and owner, elapsed time, one primary next action, and overflow utilities.

Default sorting:

1. Critical risk
2. High risk
3. Overdue work
4. Oldest unacknowledged item
5. Watch items
6. Device-only operational items

Background refresh must not move the row under the pointer or keyboard focus. Announce meaningful queue changes in a polite live region.

## 11. Application shell

- Navigation stays quiet and uses icon plus text.
- Keep clinic navigation to six or fewer top-level destinations.
- Active navigation uses indigo text, icon, and a soft indigo background.
- Keep synthetic-data labeling visible in demo builds.
- Use one page-width banner for global outages.
- Do not repeat an alert in the top bar, banner, and page content.

## 12. Buttons

Primary uses deep indigo with white text. Secondary uses a white surface and strong border. Ghost is transparent until hover. Destructive uses soft red and risk text; solid red is reserved for confirmed destructive or critical workflow action.

Required states are default, hover, pressed, focus-visible, loading, disabled, success, and error. Loading retains label and width. Disabled actions explain why when the reason is not obvious.

## 13. Inputs and forms

- Labels remain visible. Placeholder text is an example, never the label.
- Default controls are 40px high. Text areas show at least three lines.
- State required and optional fields in words.
- Place validation beside the field and add an error summary for long forms.
- Failed submissions preserve valid input.
- Disabled and read-only look and behave differently.
- Use native semantics before custom ARIA.

Required components are text field, search, textarea, select, combobox, checkbox, radio group, switch, date/time input, and segmented control.

## 14. Tables and operational lists

- Use native table structure on wide layouts and an accessible caption.
- Sort buttons live inside headers and announce direction.
- Tab reaches sortable headers, primary links, checkboxes, and actions, not inert cells.
- Search and common filters share one toolbar with no more than five exposed actions.
- Active filters appear as removable chips with Clear all.
- Empty, filtered-empty, loading, error, and stale are different states.
- Missing values say Not measured, Not applicable, Unavailable, or Stale.
- Never show blank or zero as a substitute for missing data.
- Do not make a whole row clickable when it contains nested actions.

## 15. Panels, sheets, dialogs, and popovers

Use a non-modal desktop split panel for quick inspection when the queue must remain visible. On narrow screens use a modal sheet or full-screen dialog with focus trap, Escape support, labelled title and description, and focus return.

Detail order is identity, attention summary, risk and confidence, freshness and device health, evidence, workflow history, and actions.

Use popovers only for light filters and utility previews. Consequential actions use dialogs.

## 16. Feedback and system messages

| Scope | Pattern |
|---|---|
| Whole service | One page-width banner |
| One panel or section | Inline message |
| One field | Field error and description |
| Short saved confirmation | Toast plus live-region announcement |
| Consequential decision | Dialog |

Do not use a toast as the only record of a critical failure. Do not duplicate a local validation error in a page banner.

## 17. Loading, empty, error, and stale

- Initial loading uses a skeleton with stable headers and approximate rows.
- Genuine empty explains what the absence means.
- Filtered empty offers Clear filters.
- Error keeps useful context, names the problem, and offers Retry.
- Stale keeps the last successful values visible, labels their age and cause, and qualifies actions that need current evidence.

Never replace stale data with zero, normal, or a fresh-looking skeleton.

## 18. Event workflow

- **Acknowledge** records actor and time without lowering risk.
- **Assign** shows the responsible staff member and preserves reassignment history.
- **Check** records that the resident was checked without automatically resolving.
- **Resolve** requires an outcome and records actor and time. High and critical resolution requires confirmation. Resolved records are read-only.
- **Feedback** separates staff observation from AI interpretation and sensor evidence.

Every save supports pending feedback, duplicate-action protection, failure recovery, and server-conflict refresh.

## 19. Accessibility contract

WCAG 2.2 AA is the release floor.

- Normal text is at least 4.5:1.
- Large text is at least 3:1.
- Required control boundaries, icons, and states are at least 3:1.
- Focus uses a 2px solid indigo ring with a 2px offset and is never obscured.
- Primary touch targets are at least 44 by 44px.
- Dense desktop controls never fall below 24px and maintain sufficient spacing.
- Status uses words plus icons or structure.
- Screen readers receive meaningful changes, not every polling refresh.
- The main flow works by keyboard.
- At 200% zoom, risk, reason, freshness, owner, and action remain present.
- At 400% zoom, content reflows except genuine data tables.
- Reduced motion removes transforms and workflow movement.
- Forced-colors mode preserves borders, focus, icons, and labels.

## 20. Icons

Use one outlined icon family with 1.75 to 2px strokes and sizes of 16, 18, 20, or 24px. Icon-only buttons require names and tooltips.

Semantic roles:

- critical: alert octagon;
- high: alert triangle;
- watch: eye or clock;
- device issue: signal off or hardware icon;
- low confidence: question in circle;
- active or resolved: check circle;
- stale: clock with an explicit Stale label.

Do not use medical symbols to imply diagnosis.

## 21. Data visualization

Use a chart only when it answers a comparison or trend question faster than text. “4 of 6 online” is better than a donut.

Every chart includes a plain-language summary and accessible data table. Missing and stale data are explicit. Tooltips are keyboard reachable. Charts remain clear in grayscale and print.

## 22. Content rules

Write direct operational language.

Good:

- “Resident B needs review.”
- “Monitoring unavailable. Room device has been offline for 12 minutes.”
- “Low confidence because room occupancy is unclear.”
- “Saved. Event assigned to Maya Chen.”

Avoid false reassurance, unsupported diagnoses, vague errors, and unexplained technical words.

Label AI interpretation as interpretation. Keep sensor evidence, deterministic warnings, AI text, and staff notes visually separate.

## 23. Page recipes

- **Clinic overview:** compact header, attention queue, resident inventory, then coverage and device context.
- **Residents:** header, search and filters, operational table, detail panel or route.
- **Resident detail:** identity, current monitoring truth, attention and actions, evidence, device context, history, settings.
- **Events:** header, queue controls, priority list, detail, workflow actions, immutable history.
- **Devices:** fleet summary, device list, health, assignment, last contact, limitations, recovery history.
- **Scenario lab:** one ordered scenario list and one result panel with synthetic provenance.
- **Home overview:** one plain-language answer, latest meaningful update, simple trends, and routine context.

## 24. Component ownership

Build shared Adaptive Care components around accessible behavior primitives. Radix Primitives is the preferred base for dialog, popover, tooltip, select, tabs, and menu behavior. It does not provide product styling or meaning.

Each shared component documents purpose, anatomy, variants, state matrix, token mapping, keyboard behavior, screen-reader behavior, responsive behavior, content rules, and tests.

Do not copy vendor components into pages and restyle them independently.

## 25. Governance

- The frontend and product experience owner owns the design system.
- Safety semantics and shared data meaning require review with the relevant contract owner.
- New tokens require a repeated need across at least two components or screens.
- Page-specific hex colors, radii, spacing values, and status labels are prohibited.
- Breaking changes increment the version and include migration notes.
- Deprecated tokens remain aliases for one migration release.
- Every release records added, changed, deprecated, and removed items.
- Exceptions name the reason, owner, and removal condition.

## 26. Verification checklist

Before merging UI work:

- The primary question is clear within two seconds.
- Risk is separate from device health, confidence, freshness, and workflow.
- Missing data never appears normal.
- Every used color pair passes contrast checks.
- Keyboard flow completes the main action.
- Focus is visible and restored after overlays.
- Loading, empty, error, stale, disabled, and success states are tested.
- Long and translated text wraps safely.
- Desktop, tablet, narrow, 200% zoom, and coarse-pointer layouts are inspected.
- Grayscale preserves priority.
- Reduced motion and forced colors remain usable.
- No page-local design values were introduced.

## 27. Research basis

The system uses principles from current primary documentation, not copied screenshots:

- [Inter typeface](https://rsms.me/inter/)
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [Radix color roles](https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale)
- [Radix accessibility](https://www.radix-ui.com/primitives/docs/overview/accessibility)
- [Carbon data table](https://carbondesignsystem.com/components/data-table/usage/)
- [Adobe Spectrum table](https://spectrum.adobe.com/page/table/)
- [USWDS table](https://designsystem.digital.gov/components/table/)
- [GOV.UK notification banner](https://design-system.service.gov.uk/components/notification-banner/)

## 28. Final rule

The new UI should look quiet at rest and unmistakable when action is required. If a styling decision does not help staff understand priority, truth, ownership, or the next action, remove it.
