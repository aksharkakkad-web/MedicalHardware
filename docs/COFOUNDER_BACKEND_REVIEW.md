# Cofounder Backend Review

**Review date:** August 28, 2026
**Audience:** Founders and product reviewers
**Current decision:** The Phase 2 backend runway remains complete and ready for
frontend connection. The Phase 5 backend monitoring-intelligence lane is also
complete on deterministic synthetic normalized fixtures. The shared frontend,
hardware, Phase 6 ingestion, and real-world product gates remain open.

## Executive verdict

Akshar has completed the backend foundation that manages residents, rooms,
devices, monitoring availability, calibration state, caregiver events,
feedback, resident context, settings, history, and auditability. He has also
completed the normalized-fixture intelligence path that turns synthetic
quality-controlled features into baseline comparisons, anomaly evidence,
validated deterministic fake-AI interpretation, policy decisions, and
idempotent caregiver work.

The complete downstream caregiver workflow is working:

```text
An event already exists
→ it enters the clinic attention queue
→ staff see its resident, room, priority, and status
→ staff acknowledge, check, resolve, and give feedback
→ the event leaves active work but remains in history
→ related resident context and every change survive restart
```

The normalized-fixture upstream monitoring-intelligence workflow is now
implemented:

```text
synthetic normalized features
→ quality, missingness, agreement, and contradiction
→ personal numerical baseline and learning guard
→ anomaly episode and evidence revision
→ validated fake-AI interpretation or objective fallback
→ deterministic disposition
→ existing caregiver event workflow
```

Therefore, the backend is ready for frontend convergence and for a separate
Phase 6 producer to drive the same normalized boundary. It is not ready to
claim real physiological or movement detection from hardware. The detailed
Phase 5 evidence is in `docs/PHASE_5_BACKEND_REVIEW.md`.

## What has been implemented

### 1. Durable product foundation

- Product state is stored in a migrated file-backed database instead of being
  lost when the application stops.
- Public backend operations use one versioned Product API.
- Important actions record the clinic, operator, time, version, and audit
  history.
- Exact retrying of an action is safe and does not repeat its effects.
- An outdated screen cannot silently overwrite a newer change.
- A failed multi-part operation rolls back instead of leaving partial state.
- One clinic cannot read or manipulate another clinic's information.
- Missing and inaccessible records look the same, avoiding tenant disclosure.

### 2. Resident and room behavior

- V1 supports one assigned resident per room.
- RFID and wearable identity are not used.
- Current and historical room/resident assignments are preserved.
- A resident with no monitoring history is shown as not yet available rather
  than missing or normal.
- Possible multiple-person presence limits resident-specific monitoring. The
  system does not guess which person produced a signal.

### 3. Monitoring availability and awareness

The backend can represent and explain:

- active monitoring;
- resident away;
- resident return;
- limited monitoring;
- possible multiple-person presence;
- unavailable monitoring; and
- monitoring that has not started yet.

Away, return, limited, and unavailable periods are preserved in an awareness
timeline. Leaving the room is awareness, not an emergency warning.

These states currently come from synthetic scenarios or future producers. The
backend does not yet infer them from live sensor signals.

### 4. Calibration and setup changes

- Calibration progress is tracked by sensing dimension.
- Away, visitor, unreliable, concerning, and unresolved-anomaly windows are
  prevented from teaching the personal baseline.
- An authorized setup change can restart only the affected calibration area.
- Unaffected calibration progress and all earlier history remain intact.
- Setup-change retries and conflicting versions are handled safely.

The Phase 2 calibration workflow and bookkeeping remain intact. Phase 5 now
also implements the synthetic normalized-fixture numerical baseline learner;
real raw/device observation ingestion and production threshold validation are
later work.

### 5. Device assignment and health

- Devices can be listed and assigned to rooms.
- Assignment history is preserved.
- Device state supports online, offline, degraded, buffering, retrying,
  assignment unavailable, and not yet available.
- Per-source limitations can explain which sensing input is reduced.
- Unhealthy or missing device information makes monitoring honestly limited or
  unavailable instead of normal.
- Device recovery restores the latest otherwise-valid resident monitoring
  view without rewriting resident history.
- A device problem remains operational information and does not automatically
  become a resident diagnosis or event.

### 6. Event domain and caregiver workflow

- Events preserve resident, room, priority, confidence fields, timestamps,
  lifecycle state, recurrence links, action history, priority history, and
  feedback.
- Supported priorities are watch, high, and critical.
- Supported caregiver states include open, acknowledged, checked, and
  resolved.
- Invalid lifecycle jumps and impossible chronology are rejected.
- A resolved event remains immutable.
- A later recurrence creates a new linked event instead of rewriting the
  resolved event.
- Repeated patterns can be shown through recurrence links.
- High and critical work cannot be hidden from the dashboard by notification
  preferences.

### 7. Clinic attention queue

The backend exposes a clinic-wide event queue that:

- defaults to active caregiver work;
- keeps resolved history available separately;
- filters by status, priority, resident, and room;
- supports multiple selected statuses and priorities;
- rejects ambiguous repeated single-value filters;
- orders unresolved work before resolved history;
- orders critical before high before watch;
- orders overdue work before non-overdue work;
- uses recent activity and stable identifiers for deterministic ordering;
- loads large result sets page by page without skipping or duplicating events;
- binds page cursors to the clinic and selected filters; and
- does not reveal whether another clinic owns a filtered resident or room.

This is a filter for organizing events that already exist. It is not the
signal-processing filter that detects anomalies.

### 8. Feedback and resident context

- Caregiver feedback is stored with its source and history.
- Feedback can make a synthetic learning window eligible or ineligible under
  the current test-only policy.
- Authorized staff can add resident context directly.
- Staff can correct an inaccurate entry by retiring it and creating a linked
  replacement.
- Staff can retire outdated context without deleting its history.
- Resident context remains separate from numerical calibration, event
  evidence, warning thresholds, and global behavior.

### 9. Preferences

- Each resident can store future delivery choices for watch, high, and
  critical events.
- Awareness delivery choices cover away, return, limited, and unavailable.
- Old preference versions remain auditable.
- High and critical events remain on the clinic dashboard even when external
  delivery is disabled.
- Actual phone, email, push, or other notification delivery is not built.

### 10. Stable frontend boundary

- The generated API description matches the running backend.
- API changes that drift from the committed contract fail automated checks.
- Error responses and important public operation names remain stable across
  development and clean CI environments.
- The frontend can compose the resident overview from resident identity,
  resident status, and the complete active event queue.
- Database implementation details do not need to enter frontend code.

## Complete product flow that is proven today

The automated founder walkthrough performs this story:

1. Create two assigned rooms and residents.
2. Show one resident with active monitoring and an online device.
3. Show the newer resident honestly as not yet available.
4. Preserve awareness and selective recalibration history.
5. Create synthetic critical, high, and watch events for the correct
   residents.
6. Return those events in caregiver-attention order across multiple pages.
7. Acknowledge, check, and resolve an event.
8. Remove the resolved event from active work while preserving resolved
   history.
9. Record caregiver feedback and separate operator-entered resident context.
10. Disable delivery preferences and prove urgent dashboard work remains
    visible.
11. Restart the application against the same database.
12. Confirm residents, assignments, devices, monitoring state, events,
    actions, settings, context, and histories remain correct.

## Anomaly detection: exact status

### Implemented

- Normalized observations, quality/missingness, deterministic aligned frames,
  robust personal baselines, learning guards, anomaly episodes, evidence
  packets, monitoring degradation, and the synthetic fall-like fast path.
- Situation-specific skills, bounded resident context, deterministic fake
  provider, provenance/claim validation, and objective fallback.
- Deterministic disposition, confidence/priority separation, urgent bypass,
  idempotent event bridging, acknowledgment suppression, recovery, and linked
  recurrence.
- A 24-scenario canonical replay with computed metrics and a nonzero-on-failure
  founder checkpoint.

### Not implemented

- Receiving or persisting a continuous stream of real or simulated edge
  telemetry; that is Phase 6.
- Raw/vendor radar, thermal, or Wi-Fi CSI parsing and conversion.
- Production thresholds, production confidence calibration, and real-world
  priority validation.
- Validated clinical or physiological warning thresholds.
- A live production AI provider and its real latency/cost/reliability evidence.

The normalized intelligence flow is complete without changing the event
workflow. Phase 6 must add edge-telemetry ingestion through this boundary,
without moving raw streams into the Phase 5 engine.

### Phase 5 measured replay

The canonical synthetic run measured 24 scenarios, 7/7 declared meaningful
captures, zero false packets and zero false caregiver events
across 24 declared scenario exposure units, zero baseline contamination across
57 learning windows, and zero duplicate events across 10 event signal groups.
Interpretation results were 12 attempted, 10 valid, 1 rejected, and 1
unavailable. The urgent fall-like scenario created provisional caregiver work
with no AI attempt. A nonurgent request used explicitly selected resident
context, and the repository restart hydrated the complete anomaly-to-event
lineage. Two fresh replay commands emitted the same 40,362 bytes. Exposure
units are fixture weights, not elapsed resident-days or operating-time rates.
These are engineering-fixture measurements, not clinical or hardware claims.

## Verification and review evidence

The preserved Phase 2 merge evidence remains:

- 373 passing backend tests: the 372 Checkpoint D cases plus one final
  cross-framework API-contract regression added before merge;
- 85 passing detailed domain subtests;
- 77 passing compatibility tests;
- a complete two-resident restart walkthrough ending in
  `CHECKPOINT D READY`;
- deterministic generated API verification with no drift;
- database migration, rollback, retry, concurrency, tenant-isolation, and
  restart checks;
- clinic frontend mock tests, linting, type checking, and production build;
- independent implementation and final reviews with no remaining Critical or
  Important findings; and
- a required 5/5 merge review with zero unresolved actionable comments.

The merged Phase 2 backend handoff is pull request
[#10](https://github.com/aksharkakkad-web/MedicalHardware/pull/10), merge
commit `81319ecb9a2c7b5120108ddbf0558a184b999c16`.

## What has not been proven

- The real clinic frontend connected to the Product API.
- A complete browser-level caregiver journey using real backend responses.
- Real sensor or hardware input.
- End-to-end sensor-to-event detection.
- Detection accuracy, false-alert rate, or missed-event rate.
- Clinical meaning or clinical safety.
- Real notification delivery.
- Production authentication and role permissions.
- Mature family/home real-data permissions.
- Production database and cloud deployment behavior.
- Large-clinic performance and long-term load.
- Operational monitoring, backups, retention, and disaster recovery.
- Privacy, security, compliance, and controlled-pilot readiness.

## Reviewer recommendation

**Approved for the next checkpoint:** connect the clinic frontend to the real
backend using toy data without redesigning the agreed product behavior.

**Not approved for:** claims that the system detects real anomalies, monitors
real residents, or is ready for clinical use.

The next shared review should demonstrate this visible journey through
Rishit's real clinic interface:

1. load residents and their current monitoring/device states;
2. load the complete active attention queue;
3. open an event and preserve its history;
4. acknowledge, check, resolve, and give feedback;
5. edit preferences and resident context;
6. show honest loading, missing, limited, unavailable, and failure states; and
7. repeat the journey after a backend restart.

Akshar's next separate backend responsibility is Phase 6 simulated telemetry
ingestion through the normalized boundary that real hardware will eventually
use. Rishit's frontend convergence and hardware validation remain independently
owned and are not claimed complete here.

## Related source-of-truth documents

- Current project status: `docs/CURRENT_STAGE.md`
- Product behavior: `docs/PRD.md`
- System and intelligence boundaries: `docs/ARCHITECTURE.md`
- Data and API contract: `docs/DATA_CONTRACT.md`
- Phase roadmap and exit gates: `docs/PHASE_GATES.md`
- Detailed backend Checkpoint D review:
  `docs/PHASE_2_CHECKPOINT_D_REVIEW.md`
- Frontend connection instructions: `docs/PHASE_2_FRONTEND_API_HANDOFF.md`
- Phase 5 backend monitoring review: `docs/PHASE_5_BACKEND_REVIEW.md`
