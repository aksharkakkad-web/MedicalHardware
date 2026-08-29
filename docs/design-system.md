# Adaptive Care Design System
Version: 1.0
Status: LOCKED
Scope: Entire Adaptive Care product UI — Overview, Residents, Resident Detail, Events, Devices, Scenario Lab, Settings, dialogs, forms, empty states, loading states, and future screens.

---

## 0. Core Product Feel

Adaptive Care should feel like a **premium clinical operations command center**.

The product is:
- calm
- precise
- operational
- trustworthy
- modern
- dense enough for serious work
- easy to scan under time pressure

The product is **not**:
- a generic SaaS analytics dashboard
- a playful health/wellness app
- futuristic AI software
- glassmorphism
- gradient-heavy
- over-rounded
- shadow-heavy
- card-heavy
- decorative

Reference direction:
- 70% Verkada / Samsara operational clarity
- 20% Sentry / Linear density and polish
- 10% modern clinical restraint

The primary design rule:

> Important operational information must become obvious before decorative design becomes noticeable.

---

# 1. Non-Negotiable UI Laws

These rules apply to every screen.

1. Use **Geist Sans** throughout the product.
2. Use only the colors defined in this file.
3. Blue is for brand and interaction.
4. Green, amber, red, and gray are reserved for system state.
5. Never use semantic colors decoratively.
6. Use only the spacing scale defined below.
7. Use only the radius scale defined below.
8. Prefer borders over shadows.
9. Healthy states must be visually quieter than abnormal states.
10. Repeated entities belong in lists/tables, not grids of cards.
11. Every screen must have one clear primary information hierarchy.
12. One section should normally have only one visually dominant primary CTA.
13. Do not invent page-specific component styles when a shared component can be reused.
14. Entire rows should be clickable where a row represents one navigable entity.
15. Avoid truncating important operational text when layout can reasonably accommodate it.
16. Never add gradients, glow, glass effects, oversized illustrations, or decorative animation to application UI.
17. Do not redesign functionality while polishing visuals unless there is a documented UX problem.
18. New design decisions must be made at the design-system level, not ad hoc inside a page.

---

# 2. Color System

## Brand

| Token | Hex | Usage |
|---|---|---|
| `brand-50` | `#EFF6FF` | selected navigation, subtle brand tint |
| `brand-100` | `#DBEAFE` | subtle hover/highlight |
| `brand-200` | `#BFDBFE` | rare stronger tint |
| `brand-500` | `#2F6FED` | secondary brand use |
| `brand-600` | `#155EEF` | primary button, active controls, links |
| `brand-700` | `#004EEB` | primary hover |
| `brand-800` | `#00359E` | pressed/dark brand state |

Primary brand color: **#155EEF**

---

## Neutrals

| Token | Hex | Usage |
|---|---|---|
| `gray-0` | `#FFFFFF` | primary surfaces |
| `gray-25` | `#FCFCFD` | subtle elevated surface |
| `gray-50` | `#F9FAFB` | hover / subtle section |
| `gray-75` | `#F7F8FA` | application background |
| `gray-100` | `#F2F4F7` | disabled/subtle status backgrounds |
| `gray-200` | `#E4E7EC` | default border |
| `gray-300` | `#D0D5DD` | stronger border |
| `gray-400` | `#98A2B3` | tertiary text/icons |
| `gray-500` | `#667085` | secondary text |
| `gray-600` | `#475467` | strong secondary text |
| `gray-700` | `#344054` | labels |
| `gray-800` | `#1D2939` | dark UI text |
| `gray-900` | `#171A21` | primary text |

Application background: **#F7F8FA**
Primary surface: **#FFFFFF**
Primary text: **#171A21**

---

## Semantic Status Colors

### Success / Healthy
- foreground: `#147D5A`
- strong: `#10704F`
- background: `#ECFDF3`
- border: `#ABEFC6`

### Warning / Limited / Watch
- foreground: `#A15C00`
- strong: `#854A00`
- background: `#FFFAEB`
- border: `#FEDF89`

### Danger / Needs Attention / Critical
- foreground: `#C4322B`
- strong: `#A82A24`
- background: `#FEF3F2`
- border: `#FECDCA`

### Neutral / Unavailable / Paused
- foreground: `#667085`
- strong: `#475467`
- background: `#F2F4F7`
- border: `#D0D5DD`

### Informational
Use brand blue:
- foreground: `#155EEF`
- background: `#EFF6FF`
- border: `#BFDBFE`

---

# 3. Semantic Color Rules

Use:

- Blue → interactive, selected, navigational
- Green → healthy/online/active
- Amber → limited/watch/degraded
- Red → action required / critical / destructive
- Gray → paused/unavailable/non-operational but not necessarily dangerous

Never:
- make a decorative icon green
- make a stat card purple simply to create variety
- use multiple arbitrary accent colors
- use semantic status colors for branding
- use red for harmless notifications

Color should reinforce hierarchy, never create it by itself.

---

# 4. Typography

## Font Family

Primary:
```css
font-family: "Geist", "Inter", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
```

Use Geist throughout product UI.

Do not introduce another UI font.

---

## Type Scale

| Role | Size | Weight | Line Height | Letter Spacing |
|---|---:|---:|---:|---:|
| Display | 40px | 600 | 48px | -0.025em |
| Page title | 32px | 600 | 38px | -0.025em |
| Large metric | 28px | 600 | 34px | -0.02em |
| Section title | 18px | 600 | 26px | -0.01em |
| Card title | 15px | 600 | 22px | -0.005em |
| Body | 14px | 400 | 21px | 0 |
| Body strong | 14px | 500 | 21px | 0 |
| Table primary | 14px | 500 | 20px | 0 |
| Table secondary | 12px | 400 | 18px | 0 |
| Label | 12px | 500 | 18px | 0.01em |
| Metadata | 12px | 400 | 18px | 0 |
| Button | 14px | 500 | 20px | 0 |
| Overline | 11px | 600 | 16px | 0.06em |

Allowed weights:
- 400
- 500
- 600

Avoid 700+ in product UI.

---

# 5. Spacing

The only allowed spacing scale:

```text
4
8
12
16
24
32
48
64
```

CSS variables:

```css
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-6: 24px;
--space-8: 32px;
--space-12: 48px;
--space-16: 64px;
```

Rules:
- Default page padding: `32px`
- Standard card padding: `20px–24px`
- Table horizontal cell padding: `16px`
- Form field gap: `16px`
- Section-to-section gap: `24px–32px`
- Related control gap: `8px–12px`
- Icon-to-label gap: `8px`

Avoid arbitrary spacing such as 19px, 27px, 35px.

---

# 6. Radius

Allowed radius tokens:

```css
--radius-xs: 4px;
--radius-sm: 6px;
--radius-md: 8px;
--radius-lg: 12px;
--radius-pill: 999px;
```

Usage:
- Tiny utility elements: 4px
- Compact controls: 6px
- Buttons / inputs / dropdowns: 8px
- Cards / panels / dialogs: 12px
- Status badges: pill

Never use giant 20–32px radii in operational UI.

---

# 7. Borders

Default border:
```css
border: 1px solid #E4E7EC;
```

Strong border:
```css
border: 1px solid #D0D5DD;
```

Focus ring:
```css
box-shadow: 0 0 0 3px rgba(21, 94, 239, 0.14);
border-color: #155EEF;
```

Dividers:
```css
border-color: #E4E7EC;
```

Prefer dividers and whitespace over nested boxes.

---

# 8. Shadows / Elevation

Most surfaces should use **no visible shadow**.

Level 0 — base card:
```css
box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
```

Level 1 — dropdown/popover:
```css
box-shadow:
  0 4px 8px -2px rgba(16, 24, 40, 0.08),
  0 2px 4px -2px rgba(16, 24, 40, 0.05);
```

Level 2 — modal/dialog:
```css
box-shadow:
  0 16px 32px -8px rgba(16, 24, 40, 0.14),
  0 4px 8px -2px rgba(16, 24, 40, 0.06);
```

Never:
- use large soft shadows on every card
- combine thick borders and heavy shadows
- use colored/glowing shadows

---

# 9. Application Shell

Desktop structure:

```text
┌──────── Sidebar 240px ────────┬─────────────────────────────────────────────┐
│                               │ Topbar 64px                                 │
│ Logo                          ├─────────────────────────────────────────────┤
│ Navigation                    │                                             │
│                               │ Main content                                │
│                               │ 32px page padding                           │
│                               │                                             │
│ Facility / account            │                                             │
└───────────────────────────────┴─────────────────────────────────────────────┘
```

### Sidebar
Width: `240px`

Background: `#FFFFFF`
Right border: `1px solid #E4E7EC`

Navigation item:
- height: 40–44px
- radius: 8px
- horizontal padding: 12px
- gap: 10px
- icon: 18px

Inactive:
- icon: `#667085`
- text: `#475467`

Hover:
- background: `#F9FAFB`

Active:
- background: `#EFF6FF`
- text/icon: `#155EEF`
- optional 2px left brand indicator

Do not use full saturated blue active navigation backgrounds unless there is a strong product reason.

### Topbar
Height: `64px`
Background: white
Bottom border: `#E4E7EC`

Keep it quiet.

Topbar is for:
- facility/workspace
- search
- global alerts
- account
- system/demo state

Do not duplicate status banners already shown elsewhere.

---

# 10. Page Structure

Standard page anatomy:

```text
PageHeader
    overline / breadcrumb (optional)
    title
    supporting sentence
    primary action

Primary operational content

Secondary operational content

Tertiary / historical / utility content
```

Page title should not dominate the viewport.

Recommended:
- 32px title
- 8px title-to-description gap
- 24–32px header-to-content gap

Every page must answer:

> What should the user notice first?

If the answer is unclear, the hierarchy is wrong.

---

# 11. Buttons

Height:
- standard: `40px`
- compact: `36px`
- large: `44px` only when needed

Radius: `8px`

Horizontal padding:
- compact: 12px
- standard: 16px

### Primary
```css
background: #155EEF;
color: #FFFFFF;
border: 1px solid #155EEF;
```

Hover:
```css
background: #004EEB;
```

### Secondary
```css
background: #FFFFFF;
color: #344054;
border: 1px solid #D0D5DD;
```

Hover:
```css
background: #F9FAFB;
```

### Ghost
No default border/background.

Hover:
```css
background: #F2F4F7;
```

### Destructive
Use only for actually destructive action.

```css
background: #C4322B;
color: #FFFFFF;
```

Do not make every CTA blue.

---

# 12. Inputs / Search / Selects

Height: `40px`
Radius: `8px`
Border: `#D0D5DD`
Background: white
Text: `#171A21`
Placeholder: `#98A2B3`

Focus:
- blue border
- subtle 3px focus ring

Disabled:
- background `#F9FAFB`
- text `#98A2B3`

Search icons: 16px

Do not use oversized search fields unless search is the primary page action.

---

# 13. Icons

Use **Lucide** icons only.

Sizes:
- inline: 16px
- buttons: 16px
- sidebar: 18px
- major status: 20–24px

Stroke:
- 1.75–2px

Never mix icon libraries in one interface.

Avoid icons when plain text is clearer.

---

# 14. Status System

Adaptive Care has four basic state levels:

## Healthy
Examples:
- Active
- Online
- No issues

Treatment:
- small green dot or subtle green text
- green badge only when explicit labeling is useful
- visually quiet

## Warning
Examples:
- Limited
- Watch
- Assignment issue

Treatment:
- amber dot or subtle amber pill
- medium emphasis

## Critical
Examples:
- Needs attention
- High priority
- Critical event

Treatment:
- red pill
- subtle tinted row/background when useful
- strong but not visually chaotic

## Neutral / Unavailable
Examples:
- Paused
- Unavailable
- Away

Treatment:
- gray status
- low emphasis

Information hierarchy:

```text
Healthy        ░
Neutral        ░░
Warning        ░░░
Critical       █████
```

---

# 15. Status Badge Specification

Height: `24px`
Horizontal padding: `8px`
Gap: `6px`
Font: `12px / 500`
Radius: pill

Default structure:

```text
● Label
```

Do not use badges for plain metadata.

Good:
- Needs attention
- Watch
- Unavailable

Bad:
- Room 102
- Updated 8:31
- Resident
- Monitoring data

---

# 16. Cards

Default card:

```css
background: #FFFFFF;
border: 1px solid #E4E7EC;
border-radius: 12px;
box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
```

Padding: `20px–24px`

Cards are for grouping related information.

Do not create a card simply because an item exists.

Avoid:
- four giant cards for four numbers
- different colored cards for visual variety
- icons with pastel bubbles everywhere
- nested cards inside cards

---

# 17. Metrics

Metrics should be compact.

Preferred:

```text
Monitoring coverage
4 of 6 active
67%
```

Not:

```text
┌─────────────────┐
│ giant icon      │
│                 │
│       67%       │
│                 │
│ COVERAGE        │
└─────────────────┘
```

Metrics support operational content. They should rarely dominate it.

---

# 18. Tables / Operational Lists

This is a core Adaptive Care component.

### Table anatomy

- header: 40px
- row: 60–64px
- horizontal cell padding: 16px
- subtle row dividers
- no zebra striping
- no heavy outer grid
- whole row clickable where appropriate

Header:
- 12px / 500
- `#667085`

Primary row text:
- 14px / 500
- `#171A21`

Secondary:
- 12px / 400
- `#667085`

Hover:
```css
background: #F9FAFB;
```

Selected:
```css
background: #EFF6FF;
```

Critical row:
```css
background: rgba(254, 243, 242, 0.6);
border-left: 3px solid #C4322B;
```

Warning row:
```css
border-left: 3px solid #D97706;
```

Healthy rows should have no colored left border.

Preferred resident row:

```text
Resident B        Room 102        ● Active        Needs attention       8:31 PM      >
                                   Streaming       Unusual activity
```

Avoid putting every cell into a pill.

---

# 19. Alert / Attention Queue

Attention items are the most important operational UI.

Use a dedicated alert banner only when it summarizes actionable events.

Example:

```text
⚠ 3 residents need attention
High-priority events require review.

Resident B    Unusual activity
Resident F    Assignment conflict
Resident E    Device offline

[Review queue →]
```

Rules:
- red is used only for actual action-required states
- avoid enormous red backgrounds
- keep banner height compact
- summary → examples → action
- avoid duplicating the exact same summary elsewhere on the same screen

---

# 20. Resident Detail Page

The same system must support resident records.

Recommended structure:

```text
Resident Header
Resident B · Room 102
Current monitoring state
Primary attention state
Quick actions

Tabs
Overview | Events | Monitoring | Devices | History

Primary content
Operational timeline / current status

Secondary context
Resident metadata / device assignment
```

Do not create an entirely different aesthetic for detail pages.

---

# 21. Events Page

Primary UI:
- filter bar
- event table / event queue
- severity
- resident/room
- event type
- time
- state
- assignee/action
- drill-in

Use color sparingly.

Severity must be readable without relying solely on color.

---

# 22. Device Page

Device state hierarchy:
- Online
- Limited
- Offline
- Unavailable

Use the same semantic system as resident monitoring.

Do not create a separate visual language for devices.

---

# 23. Forms

Labels above inputs.

Structure:

```text
Label
Input
Optional helper/error text
```

Field gap: 16px
Section gap: 24px

Errors:
- red border
- red message
- concise explanation

Do not rely on placeholder text as the label.

---

# 24. Tabs

Height: 36–40px.

Preferred style:
- plain text
- bottom border / underline active state
- blue active text

Avoid giant pill tabs unless the context specifically benefits from them.

---

# 25. Dialogs / Sheets

Use a dialog for:
- confirmation
- small focused form
- short critical workflow

Use a side sheet for:
- event preview
- resident quick view
- contextual detail without losing the queue

Do not force every detail workflow into navigation.

---

# 26. Empty States

Empty states should be useful and quiet.

Good:

```text
No events need attention
All monitored residents are currently clear.
```

Optional small secondary action.

Avoid:
- giant illustrations
- confetti
- excessive marketing copy

---

# 27. Loading States

Use skeletons that mimic the actual layout.

Do not use a full-page spinner for normal data loading.

Operational screens should preserve layout during loading.

---

# 28. Hover / Focus / Pressed States

Every interactive element must have:
- default
- hover
- focus-visible
- active/pressed
- disabled where relevant

Default transitions:
```css
transition-duration: 150ms;
transition-timing-function: ease-out;
```

---

# 29. Motion

Allowed:
- 150ms hover
- 180ms dropdown/popover
- 200ms dialog/sheet
- subtle opacity and position changes

Avoid:
- bounce
- spring-heavy motion
- cards flying into view
- animated gradients
- decorative background animation

This is operations software.

---

# 30. Density Rules

Adaptive Care should be moderately dense.

Good:
- 6–10 useful rows visible without scrolling on common desktop screens
- actions compact
- secondary metadata visible but quiet
- related information grouped tightly

Bad:
- giant whitespace between all elements
- 120px-tall table rows
- dashboard cards consuming most of the viewport
- huge page headings

---

# 31. Data Visualization

Only use charts when a chart answers a real question.

Allowed:
- compact progress bars
- donut/ring only for simple composition when more readable than text
- timelines
- sparklines for meaningful trends

Avoid:
- decorative charts
- charts whose content can be expressed more clearly as `4 of 6 online`
- rainbow series colors

---

# 32. Responsive Rules

Primary target: desktop operations.

Breakpoints:
- ≥ 1440px: full layout
- 1024–1439px: compressed desktop
- 768–1023px: tablet / sidebar collapses
- < 768px: mobile adaptation only where product requirements demand it

Desktop first, but never allow:
- clipped columns
- unreadable table text
- horizontal collisions
- hidden actions without replacement

At narrower widths:
1. reduce secondary columns
2. collapse low-value metadata
3. move contextual analytics below primary content
4. preserve alerts and primary actions

---

# 33. Accessibility

Minimum requirements:
- WCAG AA contrast for normal text
- visible keyboard focus
- semantic status cannot rely only on color
- buttons/controls have accessible names
- interactive hit areas ≥ 36px, preferably 40px
- table rows must remain keyboard reachable if clickable
- use semantic HTML first

Do not lower text contrast for aesthetics.

---

# 34. Writing / UX Copy Style

Operational copy should be concise.

Good:
- Needs attention
- Unusual activity detected
- Device offline
- Monitoring unavailable
- Assignment needs review
- Last updated 8:31 PM

Bad:
- Something appears to have gone wrong with this resident's monitoring setup
- We noticed a potentially unusual event that may require your attention

Use specific nouns and verbs.

---

# 35. Component Inventory

Build and reuse these primitives.

```text
AppShell
Sidebar
Topbar
PageHeader
PageSection

Button
IconButton
Input
SearchInput
Select
Dropdown
Checkbox
Radio
Tabs
Tooltip
Popover

Card
Metric
Divider

StatusDot
StatusBadge
SeverityBadge
AlertBanner

FilterBar
DataTable
TableRow
Pagination
EmptyState
Skeleton

Dialog
Sheet
Toast

ResidentRow
ResidentHeader
ResidentStatus
EventRow
EventPreview
DeviceRow
DeviceStatus
AttentionQueue
```

Before creating a new component, check whether one of these can be extended.

---

# 36. 21st.dev / External Component Rule

External components may be used for implementation quality.

They may NOT define the Adaptive Care visual system.

When importing a component:
1. preserve useful behavior
2. replace its colors with Adaptive Care tokens
3. replace its radius with Adaptive Care tokens
4. replace its spacing with Adaptive Care spacing
5. use Geist
6. use Lucide
7. normalize borders/shadows
8. remove decorative effects
9. make it visually indistinguishable from native Adaptive Care components

Do not install a full dashboard template and treat it as the product design.

---

# 37. Anti-Patterns

Never introduce these without explicit design-system revision:

- gradients in application UI
- glassmorphism
- giant rounded cards
- pastel rainbow cards
- excessive pill badges
- multiple icon styles
- card-per-metric layouts
- giant hero-style page headers
- heavy drop shadows
- low-contrast gray text
- random status colors
- arbitrary spacing values
- arbitrary radii
- decorative illustrations in core operations screens
- giant charts used as filler
- duplicate information panels
- tiny text links floating inside tables
- horizontal table overflow at normal desktop widths
- hidden/truncated critical information
- separate visual systems per page

---

# 38. Design Decision Framework

When making any UI decision, ask in this order:

### 1. What is the user's primary task?
Example:
"Which resident needs my attention?"

### 2. What information is necessary to make that decision?
Show that first.

### 3. What is abnormal?
Give abnormal states more emphasis.

### 4. What is normal?
Make normal information quieter.

### 5. Is this repeated data?
Use a table/list.

### 6. Is this supporting context?
Use a compact card or secondary region.

### 7. Is this an action?
Use an established button/link pattern.

### 8. Does a shared component already exist?
Reuse it.

### 9. Does this require a new token/pattern?
If yes, update the design system first.

---

# 39. Visual QA Checklist

Every screen must be visually reviewed after implementation.

Check:

## Hierarchy
- Is the most important information obvious in under 2 seconds?
- Is there one clear primary focus?
- Are secondary panels genuinely secondary?

## Alignment
- Are columns aligned?
- Are card edges aligned?
- Are icons optically centered?
- Are headings aligned to content?

## Spacing
- Does everything use the standard scale?
- Are similar relationships spaced consistently?
- Is anything inexplicably floating?

## Typography
- Correct type role?
- Correct weight?
- Correct line height?
- No random font sizes?

## Color
- Semantic colors used correctly?
- Too much blue?
- Healthy states quieter than alerts?
- Sufficient contrast?

## Components
- Consistent button height?
- Consistent inputs?
- Consistent badge size?
- Consistent card radius?
- Consistent border treatment?

## Tables
- No clipped columns?
- No unnecessary pills?
- Primary data easy to scan?
- Row actions obvious?
- Important descriptions not truncated unnecessarily?

## States
- hover
- focus
- active
- loading
- empty
- error
- disabled

## Responsive
Review at minimum:
- 1440px
- 1280px
- 1024px

---

# 40. Screenshot Iteration Rule

Do not call a screen finished because:
- it compiles
- tests pass
- it resembles the design in code

Required loop:

```text
Inspect existing screen
→ identify primary user task
→ implement using this design system
→ run application
→ capture screenshot
→ inspect screenshot visually
→ list visible defects
→ fix defects
→ capture again
→ repeat until production-quality
```

UI quality must be judged from the rendered product.

---

# 41. Grayscale Test

Occasionally inspect the page in grayscale.

The screen should still communicate:
- primary hierarchy
- important action
- grouped information
- interactive elements
- abnormal vs normal through structure/text/icons

If hierarchy disappears without color, the design relies too heavily on color.

---

# 42. "Looks Premium" Test

Premium does NOT mean:
- more effects
- more shadows
- more whitespace
- more animation

Premium means:
- precise spacing
- clean typography
- restrained color
- consistent geometry
- deliberate hierarchy
- strong states
- zero visual accidents
- zero arbitrary decisions
- high information clarity

---

# 43. Locked CSS Token Starter

```css
:root {
  /* Brand */
  --brand-50: #EFF6FF;
  --brand-100: #DBEAFE;
  --brand-200: #BFDBFE;
  --brand-500: #2F6FED;
  --brand-600: #155EEF;
  --brand-700: #004EEB;
  --brand-800: #00359E;

  /* Neutral */
  --gray-0: #FFFFFF;
  --gray-25: #FCFCFD;
  --gray-50: #F9FAFB;
  --gray-75: #F7F8FA;
  --gray-100: #F2F4F7;
  --gray-200: #E4E7EC;
  --gray-300: #D0D5DD;
  --gray-400: #98A2B3;
  --gray-500: #667085;
  --gray-600: #475467;
  --gray-700: #344054;
  --gray-800: #1D2939;
  --gray-900: #171A21;

  /* Semantic */
  --success: #147D5A;
  --success-strong: #10704F;
  --success-bg: #ECFDF3;
  --success-border: #ABEFC6;

  --warning: #A15C00;
  --warning-strong: #854A00;
  --warning-bg: #FFFAEB;
  --warning-border: #FEDF89;

  --danger: #C4322B;
  --danger-strong: #A82A24;
  --danger-bg: #FEF3F2;
  --danger-border: #FECDCA;

  --neutral-status: #667085;
  --neutral-status-strong: #475467;
  --neutral-status-bg: #F2F4F7;
  --neutral-status-border: #D0D5DD;

  /* Application */
  --background: #F7F8FA;
  --surface: #FFFFFF;
  --surface-subtle: #F9FAFB;
  --text-primary: #171A21;
  --text-secondary: #667085;
  --text-tertiary: #98A2B3;
  --border: #E4E7EC;
  --border-strong: #D0D5DD;
  --primary: #155EEF;
  --primary-hover: #004EEB;
  --primary-subtle: #EFF6FF;

  /* Radius */
  --radius-xs: 4px;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-pill: 999px;

  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --space-12: 48px;
  --space-16: 64px;

  /* Layout */
  --sidebar-width: 240px;
  --topbar-height: 64px;
  --page-padding: 32px;

  /* Motion */
  --duration-fast: 150ms;
  --duration-medium: 180ms;
  --duration-slow: 200ms;

  /* Elevation */
  --shadow-card: 0 1px 2px rgba(16, 24, 40, 0.04);
  --shadow-popover:
    0 4px 8px -2px rgba(16, 24, 40, 0.08),
    0 2px 4px -2px rgba(16, 24, 40, 0.05);
  --shadow-dialog:
    0 16px 32px -8px rgba(16, 24, 40, 0.14),
    0 4px 8px -2px rgba(16, 24, 40, 0.06);
}
```

---

# 44. Permanent Codex Rule

Add this to the project's `AGENTS.md` or equivalent global project instructions:

```md
## Adaptive Care UI Design System

All frontend work MUST conform to `/docs/design-system.md`.

Treat the design system as the source of truth for:
- typography
- color
- spacing
- radius
- shadows
- borders
- layout
- component styling
- status semantics
- interaction states
- responsive behavior

Do not introduce a new font, color, spacing value, radius, shadow, icon style, status treatment, or component pattern unless the existing system cannot reasonably support the requirement.

Prefer extending shared components over adding page-specific styling.

When importing external components (including 21st.dev or shadcn examples), preserve useful behavior but normalize all visual styling to the Adaptive Care design system.

For UI work:
1. inspect the existing rendered page
2. identify the primary user task
3. implement using shared primitives and design-system tokens
4. render the actual application
5. capture a screenshot
6. visually inspect hierarchy, spacing, alignment, typography, truncation, responsiveness, and state clarity
7. fix visible defects
8. repeat until production-quality

Do not stop merely because the code compiles or tests pass.

The intended product feel is:
"premium clinical operations command center — calm, precise, trustworthy, modern, and operational."

Healthy states should be visually quiet.
Warnings should have moderate emphasis.
Action-required states should dominate appropriately.

Avoid generic SaaS dashboard patterns, excessive cards, decorative gradients, heavy shadows, giant radii, rainbow accents, and unnecessary animation.
```

---

# 45. Screen-by-Screen Revamp Prompt

Use this prompt with Codex for each screen:

```md
Revamp ONLY the [SCREEN NAME] screen using `/docs/design-system.md` as the authoritative visual system.

Do not redesign other pages.

Before modifying code:
1. inspect the current implementation and shared frontend architecture
2. open the existing screen in the browser
3. capture or inspect its current rendered state
4. identify the primary user task on this screen
5. identify the visible UI/UX problems

Then improve the screen while preserving its real functionality.

Prioritize:
1. information hierarchy
2. scanability
3. operational clarity
4. precise spacing/alignment
5. consistent typography
6. reusable components
7. obvious status semantics
8. polished interaction states
9. responsive behavior
10. accessibility

Use existing shared primitives where possible.
If a shared primitive is inadequate, improve the shared primitive rather than creating page-specific styling.

You may use shadcn or 21st.dev components when they materially improve implementation quality, but normalize them completely to `/docs/design-system.md`.

Do not:
- invent new colors
- invent new radii
- invent arbitrary spacing
- introduce another icon library
- introduce gradients
- add decorative animation
- make every piece of information a card
- make every status a large pill
- change underlying product behavior without a UX reason

After the first implementation:
1. run the application
2. inspect the actual rendered screen
3. check it at 1440px, 1280px, and 1024px
4. critically identify visual defects
5. fix them
6. repeat the screenshot inspection loop until the result is production-quality

At completion, report:
- what changed
- what shared components changed
- whether any design-system token needed modification
- remaining UI issues, if any

Do not continue to another page.
```

---

# 46. Final Rule

The design system is considered successful when the team can build a new Adaptive Care page without inventing a new visual language.

When uncertain, choose:
- simpler
- quieter
- more consistent
- easier to scan
- more operational

over:
- more decorative
- more novel
- more colorful
- more animated
- more "designed"
