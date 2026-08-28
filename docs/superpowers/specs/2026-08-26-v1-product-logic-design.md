# V1 Product Logic Design

**Status:** Approved product foundation; Phase 5 intelligence details are superseded by `2026-08-28-phase5-monitoring-intelligence-design.md`
**Date:** 2026-08-26
**Scope:** Clinic-first V1 using toy data first, then real radar, thermal, and Wi-Fi CSI data

## Purpose

Define how the complete product behaves from room setup through calibration, monitoring, events, caregiver action, feedback, learning, and hardware integration. This document focuses on product behavior and decision logic, not implementation details.

## Team model

- **Akshar** owns backend behavior and intelligence: quality, fusion, calibration, baselines, anomaly and warning logic, confidence, events, AI context, feedback learning, and evaluation.
- **Rishit** owns the user-facing product: clinic and home journeys, information hierarchy, language, interactions, visual design, accessibility, and frontend behavior.
- **Hardware/Firmware Engineer** owns the device and edge system: sensor bring-up, firmware, lightweight preprocessing, timing, packaging, buffering, connectivity, and hardware validation.
- Shared product rules and contracts are agreed once so all three tracks can progress independently.

## Locked V1 assumptions

- The clinic caregiver is the first user.
- Each monitored room has one assigned resident.
- The system does not identify or separate multiple people.
- Radar, thermal, and Wi-Fi CSI are the core sensing inputs.
- Frontend and backend converge on toy data before hardware arrives.
- Real hardware later replaces the toy telemetry producer without rebuilding the product or intelligence layers.
- Development uses synthetic residents and synthetic/test data.

## Complete product loop

1. A room, device, and resident assignment are created.
2. The monitoring setup receives a version so later physical changes can be audited.
3. The resident begins calibration.
4. The system continuously checks presence, room suitability, freshness, sensor quality, missing data, and device health.
5. Suitable radar, thermal, and Wi-Fi CSI evidence is aligned and fused.
6. Current behavior is compared with the resident's available baseline.
7. Broad unusual patterns open a numerical anomaly episode and produce rich revisioned evidence.
8. Strong urgent deterministic evidence may create a provisional event immediately; other meaningful episodes receive selective AI interpretation first.
9. Deterministic policy uses the evidence and validated interpretation to decide whether caregiver work is warranted. AI cannot hide, downgrade, or cancel a deterministic warning.
10. A caregiver acknowledges, checks, resolves, and optionally explains what happened.
11. Trusted feedback may update resident memory quickly, make selected normal data eligible for controlled baseline learning, and add a labeled example to offline evaluation.
12. Future monitoring uses the updated context without silently rewriting safety behavior.

## Room presence and monitoring suitability

The product distinguishes four practical states:

- **Resident present / monitoring active:** Resident-specific measurements, baseline comparison, and event logic may run subject to quality.
- **Resident away:** Show an awareness state and timeline entry. Resident-specific measurements are unavailable and baseline learning pauses. This is not a health warning.
- **Possible multiple people / monitoring limited:** Show that another person may be present. Pause baseline learning and lower or remove resident-specific measurements.
- **Assignment or monitoring unavailable:** Show an operational problem until the room, resident, or device assignment is repaired.

If an extremely unusual room-level pattern occurs while multiple people may be present, the system may create a low-confidence room-activity event asking staff to verify. It must not claim that a resident-specific value came from the assigned resident.

## Calibration behavior

Calibration states remain:

`new → calibrating → partial → established`

- Data collection and device-health monitoring begin immediately.
- During `new` and `calibrating`, broad obvious patterns may be detected, but personalized conclusions are limited and visibly lower-confidence.
- Extreme-value warnings require strong signal quality and a versioned rule. Prototype rules are labeled synthetic/test-only until validated.
- `partial` means some personalized dimensions have enough trustworthy data while others remain unavailable or provisional.
- `established` means enough eligible data exists for the intended personalized comparisons; it does not imply clinical validation.
- Bad-quality, resident-away, possible-multiple-person, concerning-event, and unresolved-anomaly windows are excluded from baseline learning.
- Calibration advances because of sufficient eligible coverage, not merely elapsed calendar time.

## Recalibration and setup changes

A monitoring setup change is recorded when the resident changes rooms, the device moves materially, a core sensor is replaced, or the room layout changes enough to affect sensing.

- Resident history, feedback, and semantic memory remain attached to the resident.
- Physical-sensing baseline dimensions affected by the setup change return to `calibrating` or `partial`.
- Unaffected, still-valid resident context may remain available.
- The dashboard provides an explicit setup-change/recalibration action and shows why recalibration started.

## Event creation, grouping, and recurrence

- Numerical anomaly lifecycle (`candidate → active → recovering → closed`) is separate from caregiver event lifecycle.
- `detected` is an internal candidate state; `open` is the first user-visible event state.
- Related signals inside a configurable quiet-time gap update one active event episode.
- A recurrence after that gap creates a new event linked to prior related events.
- A resolved event remains immutable and is not reopened. A new recurrence becomes a new linked event.
- Repeated related events display a pattern indicator such as frequency over a recent period.
- Original evidence, interpretation, priority history, and human actions remain auditable.

## Event lifecycle and overdue behavior

The core user journey is:

`open → acknowledged → checked → resolved`

- `watch` awareness items may auto-close when the condition returns to normal, but remain in history.
- `high` and `critical` events never silently expire.
- Unacknowledged high/critical events become visibly overdue and may escalate according to configurable policy.
- Resolution outcomes are `confirmed`, `false_positive`, or `uncertain`.

## Priority and confidence

Priority is a policy decision informed by:

- objective severity of the observed change;
- confidence and signal quality;
- duration and rate of change;
- agreement between sensors;
- deviation from available personal baseline;
- recurrence or worsening;
- room suitability and missing information.

Priority and confidence are separate. A potentially serious pattern with weak attribution may still request verification while clearly stating uncertainty.

Product meanings:

- **Watch:** Awareness or review item; may be grouped, summarized, hidden, or auto-closed by settings.
- **High:** Needs timely staff attention; always visible in the dashboard and may use configured notifications.
- **Critical:** Needs immediate staff attention; cannot be hidden in the dashboard. Delivery channels remain administrator-configurable.

Exact medical thresholds are not invented during V1 software development.

## Notifications

- Notification preferences are configurable by authorized administrators.
- Watch items may be muted, grouped, or summarized.
- High events remain visible even if external notification channels are reduced.
- Critical events remain visible and prominent; administrators configure delivery channels rather than removing the event from the product.
- Notification delivery and acknowledgment are auditable.

## Feedback trust and correction

- V1 assumes authenticated clinic dashboard operators are authorized and their submitted feedback is trusted.
- Every feedback and memory change records the actor, time, source event, and version.
- Authorized operators can correct earlier feedback or mark it outdated without deleting history.
- The original event and its evidence never change after feedback.

## Resident memory settings

The resident dashboard provides a simple editable area for:

- normal routines;
- common assisted movements;
- typical absence periods;
- relevant contextual notes;
- incorrect or outdated memories;
- change history.

The dashboard is the editing experience, but the memory is part of the shared resident record so every authorized product view uses consistent context.

## Three learning loops

### Fast resident memory

Trusted routines and context may update quickly and can inform future explanations and active-learning questions.

### Controlled personal baseline

Only eligible, trustworthy normal data updates numerical baselines gradually. Feedback may make a specific window eligible, but never directly rewrites the baseline or warning thresholds.

### Offline global improvement

Labeled events enter an evaluation dataset. System-wide filters, fusion, anomaly logic, classifiers, or AI instructions change only through an evaluated, versioned, reviewed release.

## Operational problems versus resident events

Device offline, missing sensors, stale data, low quality, assignment problems, and monitoring ambiguity are operational states or events. They remain separate from resident-health events and are presented differently in the clinic product.

## First complete toy-data scenario

1. Create one synthetic resident, room, device, and assignment.
2. Progress through `new`, `calibrating`, `partial`, and `established` using eligible toy data.
3. Show resident-away awareness and resume monitoring after return.
4. Show monitoring limited while a caregiver may be present.
5. Produce an unusual-movement anomaly episode after monitoring becomes suitable again.
6. Build rich evidence, run selective AI interpretation, and let deterministic policy create the caregiver event; urgent synthetic evidence bypasses AI delay.
7. A caregiver acknowledges, checks, and resolves the event as a false positive caused by an assisted transfer.
8. Resident memory records the routine.
9. The numerical baseline does not immediately rewrite itself; only the eligible confirmed-normal window may influence a later controlled update.
10. A later similar event references the routine while preserving deterministic warning behavior.
11. Repeated events show a recurrence indicator and remain separate auditable occurrences.

## Final delivery roadmap

1. Lock this product logic and synchronize contracts.
2. Create contract-valid toy scenarios covering every state above.
3. Rishit builds the clinic product against toy information.
4. Akshar builds the resident, monitoring, calibration, event, feedback, memory, and intelligence behavior against the same rules.
5. The hardware engineer prepares the device boundary, health states, and hardware bring-up independently.
6. Frontend and backend converge using toy sensor data.
7. Add fusion, baseline, anomaly, confidence, notification, and learning behavior incrementally through the complete scenario.
8. Run reproducible evaluation across normal, abnormal, degraded, away, visitor, recurring, and recovery scenarios.
9. Replace toy telemetry with real device telemetry and trigger setup-specific recalibration.
10. Validate product comprehension, alert burden, reliability, and measured monitoring performance before a controlled pilot.

## Deliberately deferred decisions

- Exact sensor feature calculations and sampling rates
- Exact medical or clinical warning thresholds
- Exact calibration coverage requirements
- Exact quiet-time, overdue, and escalation durations
- Final notification channels and timing
- Final LLM provider/model
- Final storage-retention periods
- Final commercial wedge and compliance program

These values remain configurable and must be chosen through hardware evidence, user research, safety review, or pilot requirements rather than guessed during initial software development.
