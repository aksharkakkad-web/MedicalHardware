# Adaptive Care design system V2.1 specification

**Goal:** Replace the earlier visual system with a complete, accessible Warm Indigo system for clinic operations, while defining a quieter inherited mode for the home product.

## Approved direction

The selected direction is Warm Indigo. It combines a warm off-white canvas, white working surfaces, deep neutral text, accessible indigo actions, and distinct semantic families for positive, watch, resident risk, device and data, and unavailable states.

The existing UI is not visual authority for this redesign.

## Core changes from V2.0

- Rebuilt every semantic color pair to pass WCAG 2.2 AA for normal text.
- Removed the collision between brand teal and semantic success.
- Chose Inter Variable for all UI typography with optical sizing and tabular numerals.
- Separated resident risk, monitoring condition, confidence, device health, workflow, and freshness.
- Added responsive breakpoints and column-survival rules.
- Added keyboard, focus, screen-reader, target-size, zoom, reduced-motion, and forced-colors rules.
- Defined attention-item anatomy and deterministic queue ordering.
- Added behavior for forms, tables, sheets, dialogs, notifications, loading, empty, error, and stale states.
- Added event workflow safeguards, governance, versioning, and verification requirements.
- Defined clinic and home as separate composition modes sharing the same foundations.

## Deliverables

1. `docs/design-system.md` is the machine-readable source of truth.
2. `output/pdf/Adaptive-Care-Design-System-V2.1.pdf` is the polished visual reference.
3. No application screens change in this task.

## Acceptance criteria

- Every documented normal-text color pair has at least 4.5:1 contrast.
- The PDF contains extractable text and renders without clipping, overlap, or broken glyphs.
- The design system contains tokens, state models, component contracts, responsive rules, accessibility requirements, governance, and verification.
- The project `AGENTS.md` continues to route frontend work to `docs/design-system.md`.
- The previous system remains recoverable through Git history but no longer acts as the current source of truth.
