# Adaptive Care Home

## Platform

Responsive web application, designed mobile-first and usable on desktop.

## User

A family member checking on one loved one or household. They are not clinic staff and should not need medical or technical knowledge.

## Purpose

Answer “How are things going?” calmly and honestly, show meaningful changes without raw sensor overload, explain important events in family-safe language, and let the family add normal routines or clarify what happened.

## Positioning

Adaptive Care Home is a quiet connection to a loved one’s monitoring—not a hospital dashboard, diagnosis tool, emergency replacement, or promise that someone is safe.

## Core jobs

- Understand the current monitoring state in a few seconds.
- See simple movement and resting-pattern summaries.
- Notice an important recent update without facing a clinic work queue.
- Understand what the system observed and what it could not determine.
- Explain an expected routine, false alarm, or uncertain event.
- Add and maintain useful household routines over time.

## Boundaries

- The home app never exposes clinic acknowledgment, assignment, calibration, device-administration, or staff-audit controls.
- Monitoring limitations and unavailable data stay explicit.
- Important updates never claim a diagnosis or a confirmed cause.
- The UI never says a loved one is definitely safe.
- All current data and profiles are synthetic.
- Components use a typed `HomeMonitoringClient`; they do not import fixture files.
- `HomeMonitoringClient` returns app-private presentation models, not new Product API wire schemas. A future real client must adapt the published domain contract into these family-safe views.
- Family permissions and real API wiring come later behind the same interface.

## Product principles

- Lead with one plain answer, then let the family look deeper.
- Prefer human descriptions over sensor names and raw numbers.
- Keep ordinary days quiet and important changes unmistakable.
- Say what is unknown without sounding broken or alarming.
- Make feedback simple, reversible where possible, and visibly saved.
- Use warm, personal language without becoming cute or patronizing.

## Accessibility

Every meaning uses words in addition to color. Controls support keyboard navigation, visible focus, zoomed text, reduced motion, and comfortable touch targets.
