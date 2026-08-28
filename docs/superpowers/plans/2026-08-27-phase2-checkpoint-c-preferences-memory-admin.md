# Phase 2 Checkpoint C — Preferences and Resident-Memory Administration

**Status:** Complete
**Owner:** Akshar — backend and intelligence  
**Goal:** Give authorized clinic staff safe, resident-specific controls over notification noise and learned resident context, with complete version and audit history.

## Product outcome

At the end of this checkpoint, an authorized operator can:

1. view the current notification and awareness preferences for one resident;
2. change future delivery preferences for watch, high, and critical events;
3. change future awareness delivery for away, return, limited, and unavailable monitoring states;
4. view the resident memory already learned from feedback;
5. add a resident routine or context entry directly;
6. correct an inaccurate entry by retiring it and creating a linked replacement;
7. retire an outdated entry without deleting its history.

Preferences affect future notification delivery and noise only. Notification delivery itself is later scope. High and critical events always remain visible in the clinic dashboard regardless of delivery preferences. Resident memory remains separate from numerical calibration and cannot directly edit warning thresholds or safety logic.

## Frozen behavior

### Notification and awareness preferences

- A preference set belongs to exactly one tenant-owned resident.
- Each saved change creates the next immutable version.
- A resident with no saved preference history returns an honest `not_yet_available` response.
- The first update expects version `0`; later updates must name the current version.
- Stale versions return a conflict and preserve the newer choice.
- Event delivery toggles cover `watch`, `high`, and `critical`.
- Awareness delivery toggles cover `away`, `return`, `limited`, and `unavailable`.
- Turning off high or critical delivery never hides the event from the clinic dashboard.
- Phase 2 stores preferences but does not send notifications.

### Resident-memory administration

- Directly added entries record the operator, time, and `operator` source.
- Feedback-created entries retain their feedback source.
- Add creates one new active entry and one new memory version.
- Correct retires the selected active entry, creates a linked active replacement, and creates one new memory version.
- Retire marks an active entry retired with actor, time, and reason in one new memory version.
- Retired entries cannot be corrected or retired again.
- No endpoint deletes a memory entry or old memory snapshot.
- Every command names the expected current memory version; stale commands return a conflict.
- Memory edits do not change past events, feedback records, calibration, or safety policy.

### Shared mutation guarantees

- Every mutation requires the development tenant/actor context, `Idempotency-Key`, schema version `1.0`, and an explicit UTC timestamp.
- Same-key/same-request replays return the original response without duplicate versions or audit rows.
- Same-key/different-request reuse returns `idempotency_conflict`.
- Product change, version history, idempotency result, and audit record commit atomically.
- Cross-tenant access is indistinguishable from a missing resident or entry.

## Public clinic surface

- `GET /v1/residents/{resident_id}/notification-preferences`
- `PUT /v1/residents/{resident_id}/notification-preferences`
- existing `GET /v1/residents/{resident_id}/memory`
- `POST /v1/residents/{resident_id}/memory/entries`
- `POST /v1/residents/{resident_id}/memory/entries/{entry_id}/correct`
- `POST /v1/residents/{resident_id}/memory/entries/{entry_id}/retire`

## Implementation sequence

### Task 1 — Freeze the shared contract

- Add exact preference and memory-admin request/response examples to `docs/DATA_CONTRACT.md` as V1.6.
- Add strict contract tests for schema version, booleans, UTC timestamps, expected versions, blank text, and contradictory missing-data responses.
- Keep changes additive so Rishit's existing mock client remains valid.

### Task 2 — Prove domain rules first

- Add failing rule tests for preference creation/update, stale versions, chronology, and dashboard-visibility protection.
- Add failing rule tests for manual memory add, linked correction, retirement, stale versions, chronology, provenance, and immutable history.
- Extend the existing feedback-created memory behavior instead of creating a second memory system.

### Task 3 — Add durable version history

- Add a migration for resident preference versions and the memory provenance/correction link fields.
- Add tenant-safe models, mappers, and repositories.
- Prove append-only versions, strict reconstruction, current-version reads, tenant isolation, and restart durability.

### Task 4 — Expose preference reads and updates

- Add the preference query and command services.
- Add GET and PUT routes under the resident.
- Commit the preference version, idempotency result, and audit row in one transaction.
- Prove honest missing data, exact responses, conflicts, replay, rollback, and cross-tenant behavior.

### Task 5 — Expose memory administration

- Add memory add/correct/retire command services using the existing resident-memory repository.
- Add the three resident routes.
- Return the complete new memory snapshot after each command.
- Prove provenance, correction links, immutable older versions, conflicts, replay, rollback, and cross-tenant behavior.

### Task 6 — Product acceptance and restart story

- Seed synthetic preference and resident-memory examples without PHI.
- Add a plain-language `python3 -m backend.app.checkpoints.preferences_memory` command.
- Walk through changing notification noise, protecting dashboard visibility, adding context, correcting it, retiring it, and confirming all history survives restart.

### Task 7 — Checkpoint review and merge

- Run focused tests, full backend tests, compatibility tests, compile/diff checks, and the clinic frontend regression suite.
- Run an independent review for product invariants, tenant isolation, chronology, concurrency, atomicity, and contract accuracy.
- Update `CURRENT_STAGE`, `PHASE_GATES`, `BUILD_PLAN`, the Phase 2 review index, and a founder-readable Checkpoint C review.
- Update Graphify after code changes.
- Open a PR, reach Greptile 5/5 with zero unresolved actionable comments, squash-merge, verify from clean `main`, and begin Checkpoint D.

## Non-goals

- Sending email, SMS, push, pager, or other notifications.
- Hiding high or critical events from the clinic dashboard.
- Production authentication or role design.
- Family/home notification policies or real-data permissions.
- LLM memory rewriting, active-learning prompts, numerical baseline updates, or global model learning.
- Real medical thresholds, clinical claims, or hardware integration.

## Completion proof

Checkpoint C is complete only when the API story, restart story, full automated suite, independent review, source-of-truth docs, and merge gate all pass. Checkpoint D is then the only remaining Phase 2 backend checkpoint.
