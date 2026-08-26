# Akshar — Start Here

This is the plain-language guide for driving the product and building the backend.

## Your role

You are not only writing backend code. You are the person making sure the whole product flow makes sense:

1. Decide what the caregiver or family member needs to see.
2. Decide what action they can take.
3. Decide what the system should remember afterward.
4. Turn those decisions into backend behavior, data, and APIs.

The frontend/product owner turns the same decisions into screens. You do not need to own the visual design, but you should help define the behavior the screens represent.

## The first product flow

Keep the first version focused on one complete loop:

```text
Something unusual happens
        ↓
The system creates an event
        ↓
A caregiver opens and understands it
        ↓
They acknowledge and check it
        ↓
They resolve it and give feedback
        ↓
The system remembers what happened
```

Every later feature should make this loop more useful, more trustworthy, or easier to complete.

## Roadmap

### 1. Agree on the experience

Decide the first event flow, what “high priority” means for the prototype, what evidence is shown, and what feedback a caregiver can provide.

### 2. Build the foundation

Set up the backend, database, tests, and basic health check.

### 3. Build the event system

Support the event journey:

`detected → open → acknowledged → checked → resolved`

Store the resident, room, event headline, evidence references, confidence, and resolution outcome.

### 4. Connect the first UI

The frontend can use mock data while you build the real event API. Later it should switch to the real API without redesigning the screens.

### 5. Add simulated sensing

Use fake radar, thermal, Wi-Fi CSI, and RFID input to test normal behavior, unusual behavior, missing sensors, and multiple people.

### 6. Add the intelligence

Build personal baselines, unusual-pattern detection, confidence, device health, and deterministic warnings.

### 7. Add feedback and AI explanation

Save caregiver feedback and resident context. Let the AI explain an existing event, but never let it create, hide, or cancel a safety event.

### 8. Measure the system

Replay scenarios and measure missed events, false alerts, confidence, response time, and feedback quality.

### 9. Add real hardware

Replace simulated sensor input with the real device. The event and product flow should remain unchanged.

Customer interviews run alongside every step. They can change which problems we prioritize, but they should not casually change the core system boundaries.

## Product decisions to make before adding a feature

Ask:

- Who is this for: clinic staff or family?
- What problem does it solve for them?
- What should they see first?
- What action should they take?
- What happens if the data is missing or uncertain?
- What should the system remember?
- How will we know the feature helped?

If we cannot answer those questions, the feature is not ready to build.

## Current starting point

The repository currently contains the product requirements, architecture, contracts, and build plan. The first backend slice now defines and tests the event lifecycle in `backend/app/domain/events.py`.

The next step is to wrap that behavior with a real API and database, then connect the first UI flow.

## Source-of-truth documents

- `docs/PRD.md` — what the product should do
- `docs/ARCHITECTURE.md` — how the major pieces connect
- `docs/DATA_CONTRACT.md` — the shared language between frontend, backend, simulator, and hardware
- `docs/BUILD_PLAN.md` — the detailed build sequence
- `docs/TEAM_OWNERSHIP.md` — who owns each part
