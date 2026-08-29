# Clinic Overview Golden Screen Implementation Plan

**Goal:** Make the clinic Overview the polished visual foundation for the remaining frontend while preserving all working behavior.

**Architecture:** Continue using the existing typed monitoring client and resident components. Compute small operational summaries inside the Overview from already-loaded resident data. Limit shared changes to the shell and visual tokens needed to support the approved direction.

**Reference:** `docs/design-references/clinic-overview-concept.png`

## 1. Protect behavior with focused tests

- Update Overview and shell tests only where the revised interface introduces new user-visible labels or summaries.
- Preserve coverage for loading, error, empty, resident navigation, and urgent-event navigation.

## 2. Refine the shared clinic shell

- Improve sidebar, top bar, content width, spacing, selected navigation state, and responsive behavior.
- Reuse the existing icon components without changing `icons.tsx`.
- Spot-check Overview, Events, and Scenario Lab after the shared change.

## 3. Recompose the Overview

- Build the page introduction and real-data attention banner.
- Keep the resident sheet as the main work surface.
- Add a narrow coverage/device-health rail using values derived from resident data.
- Keep all honest unavailable, paused, limited, and unknown states visible.

## 4. Polish resident rows and mobile layout

- Improve typography, spacing, status alignment, hover/focus states, and action clarity.
- Convert the resident sheet into a readable stacked layout on small screens.
- Keep touch targets and keyboard focus easy to use.

## 5. Verify and iterate

- Run the focused tests, lint, typecheck, and production build.
- Inspect the real page at 1440px and 390px, exercise the main links, and check for console errors.
- Review shared-shell screens for regressions, fix problems, and save final screenshots.
