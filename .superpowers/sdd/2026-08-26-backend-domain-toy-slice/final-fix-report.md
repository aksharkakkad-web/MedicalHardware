# Final Fix Report — Backend Domain Toy Slice

## Scope and reuse decision

- Fix base: `df216724ce23bff0d37ecf08868889f1b98e5381`
- Branch: `akshar/backend-backend-foundation`
- Reuse verdict: extend the existing monitoring, calibration, event, feedback, and toy-scenario modules. No competing implementation, issue, or pull request covered this correction wave.
- Boundary held: standard-library, in-memory, synthetic domain behavior only. No transport DTOs, persistence, HTTP API, authentication, notifications, sensor processing, evidence/confidence interpretation, AI, or production thresholds were added.

## Finding 1 — Stateful end-to-end toy scenario

- **Status:** Fixed.
- **Files:** `backend/app/domain/toy_scenario.py`, `backend/app/domain/calibration.py`, `backend/app/domain/events.py`, `tests/toy_scenario/test_complete_flow.py`, `tests/calibration_domain/test_calibration.py`, `tests/event_domain/test_events.py`.
- **RED evidence:**
  - The existing scenario test first errored after the new attributable event lifecycle boundary because the disconnected story supplied no lifecycle actor/time.
  - The expanded `CompleteToyScenarioTests.test_complete_calibration_event_feedback_and_recurrence_story` then errored because `ToyScenarioResult` had no `calibration_history`.
  - Focused snapshot-integration tests for calibration and event gating errored four times because neither domain function accepted the actual `MonitoringSnapshot` object.
  - `EventFlowTests.test_event_records_resident_memory_references_without_changing_priority` errored because `record_signal()` did not accept resident memory.
- **GREEN evidence:** Each focused test passed after implementation; the final integrated domain/scenario run passed all 56 tests.
- **Decision / concern:** The ordered, aware-timestamped story now passes actual monitoring snapshots into calibration and event gating; resumes monitoring; groups and escalates signals; marks overdue; records attributable lifecycle history; resolves and feeds back; proves progress is unchanged by feedback until a separately controlled eligible window; carries memory references into a linked recurrence; partially recalibrates; and corrects memory. There is deliberately no numerical-baseline value engine, sensor fusion, evidence/confidence, or AI interpretation to assert in this slice; the scenario uses the implemented calibration progress as the honest baseline state.

## Finding 2 — Auditable event lifecycle, priority, and overdue truth

- **Status:** Fixed.
- **Files:** `backend/app/domain/events.py`, `tests/event_domain/test_events.py`, `backend/app/domain/toy_scenario.py`, `tests/toy_scenario/test_complete_flow.py`.
- **RED evidence:** The three focused history tests for human lifecycle actions, priority escalation, and overdue timestamps failed with four errors: lifecycle methods rejected the new actor/time arguments and snapshots had no `overdue_at`. A separate malformed-lifecycle focused test produced four errors because the old lifecycle methods accepted no auditable arguments at all.
- **GREEN evidence:** The same four focused test methods passed after implementation. A later TDD self-review test, `test_overdue_timestamp_cannot_precede_latest_episode_history`, first failed because an overdue timestamp could precede a grouped signal, then passed after chronological validation was added.
- **Decision / concern:** Frozen `EventAction` and `EventPriorityHistoryEntry` tuples preserve ordered immutable history. Human acknowledge/check/resolve operations require a nonblank actor and aware time. `overdue_at` is now truth, with a read-only `overdue` compatibility view. The canonical persistent event repository remains deferred by controller ruling.

## Finding 3 — Safe feedback eligibility

- **Status:** Fixed.
- **Files:** `backend/app/domain/feedback.py`, `tests/feedback_domain/test_feedback.py`.
- **RED evidence:** The three focused label/eligibility boundary tests reported two failures because labels were not normalized and a routine `UNKNOWN` false positive could be eligible without memory being updated; the non-datetime case also errored with incidental `AttributeError`.
- **GREEN evidence:** All three focused tests passed after normalization and eligibility gating; the full focused feedback module passed 11 tests.
- **Decision / concern:** Labels are normalized to a stable snake-case form. The normalized `unknown` sentinel cannot update resident memory, and baseline eligibility now additionally requires that a valid memory update occurred. A broader governed label vocabulary and feedback supersession are deferred to the persistence/API phase.

## Finding 4 — Strict presence, boolean, and quality validation

- **Status:** Fixed.
- **Files:** `backend/app/domain/_validation.py`, `backend/app/domain/monitoring.py`, `backend/app/domain/calibration.py`, `tests/monitoring_domain/test_monitoring.py`, `tests/calibration_domain/test_calibration.py`.
- **RED evidence:** Four focused monitoring validation methods reported 15 failures and 4 errors: malformed presence could fall through, truthy non-booleans were accepted, and malformed/non-finite quality values or policy bounds did not fail consistently.
- **GREEN evidence:** The same four focused methods passed; the focused monitoring module passed 10 tests and the strict calibration-flag regression also passed.
- **Decision / concern:** Shared domain helpers now coerce declared enums, require actual `bool` values, and accept only finite real quality values inside inclusive `[0, 1]` bounds. Adapter-level input normalization remains work for the later transport boundary.

## Finding 5 — Dimension-aware recalibration and setup audit

- **Status:** Fixed.
- **Files:** `backend/app/domain/calibration.py`, `tests/calibration_domain/test_calibration.py`, `backend/app/domain/toy_scenario.py`, `tests/toy_scenario/test_complete_flow.py`.
- **RED evidence:** Three focused recalibration methods reported three failures and two errors because calibration had no dimension progress, partial reset, affected-dimension validation, or attributable setup-change history.
- **GREEN evidence:** Those three focused methods passed after implementation; the focused calibration module passed 12 tests and the integrated scenario asserts movement reset while respiratory readiness remains established.
- **Decision / concern:** Legacy aggregate calibration still works. Configured dimensions add immutable readiness/counters, and recalibration records previous/new setup versions, affected dimensions, actor, aware timestamp, and reason. The dimension vocabulary is intentionally synthetic and will need hardware-informed ownership later.

## Finding 6 — Validated event boundaries

- **Status:** Fixed.
- **Files:** `backend/app/domain/_validation.py`, `backend/app/domain/events.py`, `tests/event_domain/test_events.py`.
- **RED evidence:** Three focused event-boundary methods produced eight failures and one error because blank identifiers/text, invalid priorities, naive/non-datetime timestamps, and blank lookups were accepted or leaked incidental behavior.
- **GREEN evidence:** The same three focused methods passed after centralized validation. Out-of-order signals, lifecycle actions, and overdue timestamps are also covered by focused passing regressions.
- **Decision / concern:** Resident, room, objective-family, headline, actor, and event identifiers now require nonblank strings; valid priority strings normalize to `EventPriority`; public event times require aware `datetime` values. Versioned transport DTO mapping remains deferred by ruling.

## Finding 7 — Feedback datetime boundary and dead local

- **Status:** Fixed.
- **Files:** `backend/app/domain/_validation.py`, `backend/app/domain/feedback.py`, `tests/feedback_domain/test_feedback.py`.
- **RED evidence:** `FeedbackLearningTests.test_feedback_datetime_boundaries_consistently_raise_value_error` errored when a string timestamp reached the former feedback helper and raised `AttributeError`.
- **GREEN evidence:** The focused datetime boundary test passed and the focused feedback module passed all 11 tests. The unused `found` local was removed.
- **Decision / concern:** Feedback submission and memory correction now consistently raise domain `ValueError` for non-datetime or naive timestamps. Persistent lookup and feedback revision semantics remain deferred by ruling.

## Finding 8 — Explicit synthetic/versioned toy policies

- **Status:** Fixed.
- **Files:** `backend/app/domain/monitoring.py`, `backend/app/domain/events.py`, `backend/app/domain/toy_scenario.py`, `tests/monitoring_domain/test_monitoring.py`, `tests/event_domain/test_events.py`.
- **RED evidence:** Two focused monitoring policy tests and two focused event policy tests each errored at import because no explicit policy types existed.
- **GREEN evidence:** Both focused policy pairs passed after implementation; focused monitoring and event modules passed with policy validation, version propagation, and `test_only` assertions while legacy threshold/quiet-gap entry points retained their documented defaults.
- **Decision / concern:** `SyntheticMonitoringQualityPolicy` and `SyntheticEventEpisodePolicy` are immutable, explicitly test-only, versioned, and copied into generated snapshots/events for audit. Their numeric values remain demo behavior and must not be promoted as production thresholds.

## Finding 9 — Accurate completion documentation

- **Status:** Fixed.
- **Files:** `docs/AKSHAR_START_HERE.md`.
- **RED evidence:** Base-document inspection showed the broad statement, “The approved V1 product logic now runs end-to-end with synthetic data,” without identifying unimplemented persistence/API/intelligence boundaries.
- **GREEN evidence:** The current-starting-point section now names exactly what the connected in-memory scenario proves and explicitly names persistence, HTTP/API, auth, notifications, DTO conformance, sensor processing/fusion, anomaly generation, confidence/evidence, and AI interpretation as unproved. Prose was inspected directly rather than coupled to a brittle text assertion.
- **Decision / concern:** Durable persistence and Product API contract mapping remain the next backend phase, as ruled.

## Controller-deferred boundaries

No numbered finding was deferred. The following adjacent work was deliberately not implemented:

- transport DTOs and full `docs/DATA_CONTRACT.md` conformance;
- persistent event repositories and feedback revision/supersession;
- evidence, confidence, interpretation, or AI-pending modules;
- watch auto-close without an approved trigger/timing policy;
- API, database, auth, notification delivery, sensor processing, PHI, clinical claims, or production thresholds.

## Verification and self-review

- Focused integrated command: `python3 -m unittest tests/monitoring_domain/test_monitoring.py tests/calibration_domain/test_calibration.py tests/event_domain/test_events.py tests/feedback_domain/test_feedback.py tests/toy_scenario/test_complete_flow.py -v` — PASS, 56 tests, `OK`.
- Canonical command: `python3 -m unittest discover -s tests -p 'test_*.py' -v` — PASS, 64 tests in 1.122s, 0 failures/errors, `OK`.
- `git diff --check` — PASS; no whitespace errors.
- Self-review checked immutable histories/snapshots, strict public boundaries, chronological event/setup actions, partial recalibration preservation, actual-object scenario handoffs, compatibility entry points, explicit synthetic policy markings, and controller scope. No unresolved in-scope defect was found.

## Residual concerns

- Domain state is still process-local and caller-supplied; persistence/repository truth and authorization arrive in the next ruled phase.
- The label and calibration-dimension vocabularies are minimal toy-domain values, not governed production taxonomies.
- Synthetic quiet-gap and signal-quality policy values are versioned and test-only; real thresholds require evaluation and hardware evidence.
