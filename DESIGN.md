---
name: "Adaptive Care Clinic Console"
description: "A calm care folio that turns monitoring uncertainty into clear staff attention and action."
colors:
  canvas: "#f7f6f2"
  surface: "#ffffff"
  ink: "#1d1d1f"
  text-muted: "#636366"
  text-soft: "#6e6e73"
  divider: "#dedee3"
  cobalt-action: "#075bd8"
  cobalt-wash: "#edf4ff"
  cobalt-border: "#c9dcfb"
  neutral-status-ink: "#52605b"
  neutral-status-bg: "#f2f4f3"
  healthy-status-ink: "#12604d"
  healthy-status-bg: "#e4f3ed"
  attention-status-ink: "#875006"
  attention-status-bg: "#fff2d9"
  critical-status-ink: "#9f2d25"
  critical-status-bg: "#ffebe8"
  unavailable-status-ink: "#59635f"
  unavailable-status-bg: "#ecefed"
typography:
  display:
    fontFamily: "var(--font-geist-sans), Arial, Helvetica, sans-serif"
    fontSize: "clamp(2rem, 4vw, 2.8rem)"
    fontWeight: 660
    lineHeight: 1
    letterSpacing: "-0.055em"
  headline:
    fontFamily: "var(--font-geist-sans), Arial, Helvetica, sans-serif"
    fontSize: "1.15rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  title:
    fontFamily: "var(--font-geist-sans), Arial, Helvetica, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  body:
    fontFamily: "var(--font-geist-sans), Arial, Helvetica, sans-serif"
    fontSize: "0.9rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "var(--font-geist-sans), Arial, Helvetica, sans-serif"
    fontSize: "0.72rem"
    fontWeight: 650
    lineHeight: 1.4
    letterSpacing: "normal"
rounded:
  control: "0.75rem"
  card: "1rem"
  pill: "999px"
spacing:
  xs: "0.25rem"
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1rem"
  xl: "1.25rem"
  2xl: "1.5rem"
  3xl: "2rem"
components:
  button-primary:
    backgroundColor: "{colors.cobalt-action}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "0.7rem 1rem"
    height: "2.8rem"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "1.25rem"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0.7rem"
  status-pill:
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0.25rem 0.65rem"
    height: "1.75rem"
---

# Design System: Adaptive Care Clinic Console

## Overview

**Creative North Star: "Calm Care Folio"**

Adaptive Care behaves like a well-kept care-plan folio: a stable index, one clear working sheet, and deeper evidence immediately behind the item in focus. The interface is calm but not passive. Warm paper and quiet white surfaces lower visual noise so attention, uncertainty, and the next staff action remain unmistakable.

The system is compact enough for an operational console but leaves deliberate room around consequential information. Native-feeling controls, restrained motion, and progressive detail make the product feel precise without implying medical certainty.

**Key Characteristics:**

- Warm paper canvas with crisp white working sheets.
- Cobalt reserved for selection, navigation, focus, and staff action.
- Semantic states pair words and dots with color; color never carries meaning alone.
- Compact fixed-column scanning on wide screens, stacked records on narrow screens.
- Soft folio layering through hairline borders, gentle shadows, and occasional sheet edges.

## Colors

The palette is nearly neutral at rest. Cobalt supplies interaction, while amber, red, green, and gray are reserved for operational meaning.

### Primary

- **Action Cobalt:** The single interaction voice for selected navigation, links, primary actions, focus, and evidence markers.
- **Cobalt Wash:** The quiet selected-state surface behind active navigation, compact actions, and selected choices.
- **Cobalt Border:** A low-contrast boundary for demo labels, selection, and text selection.

### Secondary

- **Healthy Evergreen:** Confirms active monitoring, available sources, healthy devices, and resolved work.
- **Attention Amber:** Marks limited data, watch states, acknowledged work, and other conditions requiring awareness rather than alarm.
- **Critical Brick:** Marks high-priority, critical, overdue, offline, and validation states.

### Neutral

- **Warm Canvas:** The persistent page field behind all work.
- **Working White:** The primary surface for panels, lists, controls, and the sidebar material.
- **Clinic Ink:** Primary text and selected labels.
- **Quiet Gray:** Supporting copy, timestamps, and secondary metadata.
- **Soft Gray:** Tertiary icons and low-emphasis metadata.
- **Hairline Divider:** Structural borders, row separators, and grouped facts.
- **Unavailable Gray:** States where monitoring or evidence cannot support a precise conclusion.

### Named Rules

**The One Action Voice Rule.** Cobalt means navigation, selection, focus, or an available staff action; it does not decorate neutral information.

**The Meaning Needs Words Rule.** Every semantic color is accompanied by a direct text label and, where useful, a dot or boundary.

**The Quiet Normal Rule.** Normal and healthy rooms remain visually calm; amber and red appear only when the underlying state earns attention.

## Typography

**Display Font:** Geist (with Arial, Helvetica, and sans-serif fallbacks)

**Body Font:** Geist (with Arial, Helvetica, and sans-serif fallbacks)

**Character:** One system-first sans serif keeps the console native-feeling and highly legible. Tight title tracking creates confident hierarchy; body copy and labels remain plain, compact, and direct.

### Hierarchy

- **Display** (660, `clamp(2rem, 4vw, 2.8rem)`, 1): Page titles only, with strongly tightened tracking.
- **Headline** (700, `1.15rem`, 1.2): Major panel or event headings where one section must lead.
- **Title** (650, `0.95rem`, 1.2): Panel names, workspace identity, and compact section hierarchy.
- **Body** (400, `0.9rem`, 1.5): Explanations and monitoring context, usually constrained to about 42–48rem.
- **Label** (650, `0.72rem`, 1.4): Statuses, column labels, room labels, timestamps, and other scan-level metadata.

### Named Rules

**The Title Budget Rule.** Large type identifies the page or event; operational rows and panels rely on compact titles instead of competing headlines.

**The Plain Evidence Rule.** Sensor evidence, limitations, and staff actions use sentence case and readable line spacing rather than display styling.

## Layout

The desktop shell uses a fixed 15.5rem navigation index and a fluid workspace. The working area is capped at 94rem and padded with a responsive 1.5–3rem gutter. Primary screens move from page context to the highest-attention item and then to the complete resident or event list.

Dense records use stable columns and 5.2–5.45rem rows on wide screens. Detail workspaces use an approximately 1.7:0.75 primary-to-side-column split, with the next-action rail held in view where space allows. At 900–1100px, detail columns collapse. At 700–940px, tables drop secondary columns or become compact record cards. At 760px, the left index becomes a two-destination top navigation; at 600px and below, toolbars and headers stack.

Spacing follows a 4px sub-grid with an 8px working rhythm. Panels typically sit 1rem apart and carry 1–1.25rem internal padding. Important sections receive 1.5–2rem of separation; metadata stays tightly grouped at 0.25–0.5rem.

**The Attention-Then-Inventory Rule.** A screen presents urgent work before the full resident or event inventory, then preserves a direct path into evidence and action.

**The Collapse by Importance Rule.** Narrow layouts remove secondary columns before they compress primary labels, statuses, or the next staff action.

## Elevation & Depth

Depth is a restrained hybrid of tonal layering, hairline borders, and one ambient card shadow. Translucent white navigation surfaces use blur to separate persistent chrome from the warm canvas. Primary event sheets add a shallow paper edge beneath the panel, reinforcing the folio metaphor without making the workspace decorative.

### Shadow Vocabulary

- **Ambient Card** (`0 1px 2px rgb(0 0 0 / 4%), 0 10px 32px rgb(0 0 0 / 5%)`): White panels, resident/event collections, and the high-attention banner.
- **Action Lift** (`0 3px 10px rgb(7 91 216 / 18%)`): Primary workflow buttons only.
- **Selected Segment** (`0 1px 4px rgb(0 0 0 / 10%)`): The active option inside a segmented filter.
- **Focus Halo** (`0 0 0 3px rgb(7 91 216 / 22%)`): Keyboard focus paired with a 2px cobalt outline and 3px offset.

### Named Rules

**The Folio Layer Rule.** Depth clarifies persistent chrome, a working sheet, or an active control; it never exists as ornamental floating-card scenery.

**The Motion Explains State Rule.** Short 150–160ms transitions support hover and selection; longer 360–520ms animations are reserved for acknowledged, checked, and resolved workflow changes and are removed under reduced motion.

## Shapes

The form language uses gently curved controls (0.75rem), soft rectangular cards (1rem), and fully rounded status pills (999px). Hairline borders define structure. Circles are reserved for semantic dots, alert marks, evidence nodes, and timeline markers. The recurring paper-under-paper edge may appear beneath primary evidence sheets, but not beneath every container.

**The Soft Geometry Rule.** Operational containers stay rectangular and aligned; rounded corners soften the console without turning it into a collection of bubbles.

## Components

### Buttons

- **Shape:** Full-width workflow buttons use the control radius and a minimum 2.8rem height.
- **Primary:** Working White text on Action Cobalt with 0.7rem 1rem padding and a restrained action lift.
- **Focus / Disabled:** Keyboard focus uses the shared outline and halo. Saving actions remain visible at 62% opacity and show a wait cursor.
- **Compact Action:** Inline review links use Cobalt Wash, smaller padding, and a tighter 0.55rem corner.

### Chips

- **Style:** Status pills pair a 0.42rem current-color dot with matching semantic text, a current-color border, and a light semantic background.
- **State:** Neutral, healthy, attention, critical, and unavailable variants preserve the same shape and typography so meaning changes without layout shift.

### Cards / Containers

- **Corner Style:** Soft rectangular cards use the card radius.
- **Background:** Working White on Warm Canvas; tinted surfaces are reserved for attention or selected state.
- **Shadow Strategy:** Ambient Card plus a hairline divider. Primary event sheets may add the shallow folio edge.
- **Internal Padding:** 1–1.25rem for working panels; dense list rows use about 0.8rem vertically and 1.1rem horizontally.

### Inputs / Fields

- **Style:** Working White fields use a Hairline Divider stroke, control radius, and 0.7rem padding.
- **Focus:** The shared cobalt outline and halo remain visible for keyboard navigation.
- **Selected Choice:** Radio-card and inline options shift their border to Action Cobalt and their background to Cobalt Wash.
- **Error / Disabled:** Validation is direct Critical Brick text; disabled workflow actions retain their label and reduce opacity.

### Navigation

The desktop index is a translucent white rail with compact icon-and-label rows. Inactive destinations use Quiet Gray; hover adds a cool neutral wash, and the active destination uses Action Cobalt on Cobalt Wash. On narrow screens the index becomes two equal top-navigation cells while the brand lockup and footer recede.

### Resident and Event Records

Rows use stable columns, hairline separation, compact labels, and semantic pills. Hover changes only the row surface. On small screens, secondary device and timestamp data recede before resident identity, monitoring truth, attention, or the disclosure action.

### Versioned Context Records

Versioned staff context stays in one continuous white sheet, with active entries first and compact source, status, time, and author metadata surrounding the readable statement. Correct and retire remain quiet outlined row actions. Retired text is muted and struck through, while its reason remains visible; historical information is visually de-emphasized, never removed or disguised as current.

### Settings and Safety Boundaries

Preference groups use full-width rows with a direct label, one-line consequence, and the switch aligned at the far edge. Group legends are compact uppercase scan labels. A nearby Cobalt Wash note names any invariant the switch cannot change, so the control's scope is understood before staff save it. On narrow screens, the settings rail stacks below the primary record and two-part boundary notes become one vertical sequence.

### Event Workflow Sheet

Evidence uses a vertical sequence of cobalt-ringed nodes, while the next-action panel remains adjacent and sticky on wide screens. Acknowledge, check, and resolve transitions briefly change border, surface, or position to confirm the saved state; resolved work becomes a permanent summary rather than an editable active event.

## Do's and Don'ts

### Do:

- **Do** lead with the next caregiver decision, then reveal evidence, quality, device context, and history progressively.
- **Do** keep synthetic-data labeling visible in persistent chrome.
- **Do** pair every semantic color with words and preserve unavailable or limited states as explicit states.
- **Do** place a control's immutable safety boundary beside the control in a quiet Cobalt Wash note; never leave staff to infer what a switch cannot change.
- **Do** use the shared 0.75rem control radius, 1rem card radius, hairline borders, and ambient shadow for new operational surfaces.
- **Do** preserve keyboard focus and reduced-motion behavior in every new control or transition.

### Don't:

- **Don't** use cobalt, amber, red, or green as decoration; each color has an operational job.
- **Don't** replace uncertainty with precise-looking numbers, diagnoses, or reassuring empty space.
- **Don't** create equal-weight card mosaics that hide the attention-to-action path.
- **Don't** shrink primary labels or staff actions to preserve secondary table columns on narrow screens.
- **Don't** add heavy gradients, dark command-center styling, decorative motion, or extra floating layers to this quiet folio world.
