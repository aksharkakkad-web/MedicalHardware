# Adaptive Care design system

**Version:** Clear Signal V3.0
**Status:** Canonical source of truth for clinic and home frontend work
**Primary mode:** Clinic operations

Clear Signal helps a care team answer one question quickly: **which resident
needs attention, and what is the next safe action?** It is calm, direct, dense
enough for scanning, and honest about uncertainty. It is not a diagnosis or an
emergency-response promise.

## 1. One token namespace

The shared stylesheet at
`apps/clinic-dashboard/src/styles/design-tokens.css` is the only value-bearing
design-token source. New product code uses `--ac-*` role tokens; page CSS must
not define raw color, spacing, radius, shadow, or motion values. A component
may alias a legacy name during the one-release migration, but aliases point to
`--ac-*` values and are not new design decisions.

### Core roles

| Token | Value | Use |
| --- | --- | --- |
| `--ac-canvas` | `#fbfaf8` | Page and app canvas |
| `--ac-surface` | `#ffffff` | Cards, forms, tables |
| `--ac-surface-raised` | `#fbfcff` | Lifted or selected surface |
| `--ac-text-primary` | `#111827` | Decisions and headings |
| `--ac-text-secondary` | `#536174` | Supporting copy and metadata |
| `--ac-border-subtle` | `#dde4ef` | Hairline structure |
| `--ac-action` | `#175cd3` | Primary interaction and focus |
| `--ac-info-accent` | `#55acff` | Informational/device support |
| `--ac-brand-accent` | `#7357d8` | Brand moments only |
| `--ac-positive-accent` | `#76d6b1` | Positive support only |

The stylesheet also defines the complete semantic, type, spacing, radius,
shadow, and motion scales. Use the named role rather than copying a value.

## 2. Color permissions

Color must be paired with text, iconography, or structure; it never carries
meaning alone.

- **Blue** (`--ac-action-*`) means an available interaction, selection, or
  focus state.
- **Sky** (`--ac-info-accent` and device/data roles) means information,
  telemetry, or a limitation in evidence.
- **Violet** (`--ac-brand-accent`) is a brand accent only. It is never a risk,
  warning, confidence, or device-severity color.
- **Mint** (`--ac-positive-accent`) is positive support and decoration, not a
  substitute for operational status.
- **Green** (`--ac-positive-*`) means operationally positive/current.
- **Amber** (`--ac-watch-*`) means watch, limited coverage, or review needed.
- **Red** (`--ac-risk-*`) means resident-risk escalation or destructive
  validation. Device failure is not automatically red.
- **Gray** (`--ac-unavailable-*`) means unavailable, stale, missing, or
  otherwise not-current evidence.

Keep the whole row neutral by default. Use a soft semantic treatment only when
the state needs attention, and always state the reason.

## 3. Six independent status axes

Never collapse these facts into one generic “status” badge. A record can be
high attention, low confidence, offline, stale, and still have an open
workflow at the same time.

1. **Attention:** critical, high, watch, or none. Describes resident-facing
   priority and caregiver urgency.
2. **Monitoring:** active, away, possible multi-person, paused, calibrating,
   or unavailable. Describes whether resident attribution is usable.
3. **Confidence:** high, medium, low, or unavailable. Describes evidence
   quality and attribution certainty.
4. **Freshness:** current, delayed, stale, or unknown. Describes when evidence
   was last current; last-known values must not look live.
5. **Device:** healthy, degraded, offline, or maintenance. Describes the room
   unit and sources, not the resident.
6. **Workflow:** new, acknowledged, investigating, or resolved. Describes the
   work lifecycle; resolved history remains immutable.

Use explicit unavailable copy when data cannot support a claim. Suspected
multi-person periods lower confidence or make resident-specific output
unavailable; the interface must not guess attribution.

## 4. Typography

Use **Geist Sans** for interface and display text and **Geist Mono** for
timestamps, identifiers, measurements, and operational readings. Both are
loaded by the Next root layout and exposed through `--ac-font-sans` and
`--ac-font-mono`.

The default body role is 14px/20px. Metadata is 12px/17px and overlines are
11px/16px; do not use meaningful text below 12px. Use sentence case, clear
labels, tabular numerals for readings, and wrapping text at 200% zoom.

## 5. Density, geometry, and motion

Use the four-pixel `--ac-space-*` scale. Comfortable controls are at least
40px high; touch and narrow layouts use 44×44px targets. Use the named
`--ac-radius-*`, `--ac-shadow-*`, and `--ac-duration-*` roles. Motion should
clarify state changes, use the standard easing token, and respect
`prefers-reduced-motion`.

Repeated records use lists or tables on desktop. Cards hold summaries, focused
tasks, or progressive detail. One decision area has one primary action and no
more than two visible secondary actions.

### Mobile record order

Below 768px, each resident/event record becomes an ordered card. Keep this DOM
and reading order:

1. resident name and room;
2. attention reason and priority;
3. confidence and freshness;
4. workflow state;
5. one primary action;
6. device/source details in a native disclosure when needed.

Do not hide critical facts behind hover, a tooltip, or a desktop-only column.

## 6. Evidence and product language

Show the truth stack in this order when relevant:

1. sensor evidence and data quality;
2. deterministic warning or event policy;
3. optional AI interpretation, clearly labelled as interpretation;
4. staff observation and workflow outcome.

AI explains structured evidence and cannot suppress deterministic warnings.
Specific patterns are possible interpretations, not diagnoses. Synthetic
thresholds and warnings must be labelled test-only.

## 7. Accessibility floor

Target WCAG 2.2 AA. Text and controls need a reliable contrast pair; do not
use color alone. Every interactive control has a visible `:focus-visible`
state, a keyboard path, a disabled/loading/error state where applicable, and a
44×44px touch target on narrow or coarse-pointer layouts. Keep one main
landmark, provide skip navigation for long pages, preserve logical DOM order,
support forced colors, and respect reduced motion. Status text and important
updates must be available to assistive technology without relying on animation.

## 8. Migration and governance

`--brand-*`, `--gray-*`, `--color-*`, status, spacing, radius, duration, and
shadow names remain as aliases for one release only. They are defined in
`design-tokens.css` and map to an explicit, frozen `--ac-legacy-*`
compatibility tier so existing screens retain their pre-V3.0 appearance. New
code must not use or add this tier. Remove legacy consumers after migration
and then delete the aliases and frozen values in the next intentional
design-system release.

Warm Indigo and Inter are retired directions, not active rules. Changes to
roles, semantic permissions, typography, or status meaning require updating
this document and the canonical stylesheet together, plus focused token tests.
