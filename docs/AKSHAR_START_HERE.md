# Akshar — Start Here

This is the plain-language guide for driving the product and building the backend.

## How to work with Akshar

Keep planning and progress updates at a product-manager level. Focus on:

- what the feature does for the user;
- the overall product flow and business logic;
- decisions, tradeoffs, ownership, dependencies, and risks;
- what is complete, what is next, and what still needs a decision.

Do not lead with code, file-by-file detail, framework jargon, or low-level implementation unless Akshar specifically asks for it.

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

## Before either track starts

Both founders should agree on these items first:

1. **First user:** Start with the clinic caregiver experience, while keeping the future home/family product separate.
2. **First complete flow:** An event appears, is understood, acknowledged, checked, resolved, and receives feedback.
3. **Shared language:** Agree on what event priority, confidence, unavailable data, and resolution outcomes mean.
4. **First scenarios:** Normal resident, unusual movement, unknown anomaly, low-confidence event, device issue, and false alarm.
5. **Contract freeze:** Use the existing V1 event, resident, feedback, and device-health shapes as the first shared agreement.
6. **Ownership:** Akshar owns backend and intelligence. The frontend/product cofounder owns the clinic and home experiences, mock client, and scenario simulator. Shared product and contract decisions require agreement.
7. **Success definition:** The first release is successful when a caregiver can complete the full event flow using either mock data or the real API without the experience being redesigned.

The final market, medical thresholds, LLM provider, exact sensor math, and real hardware behavior do not need to be settled before work begins.

## Two-track roadmap

### Phase 1 — Product and project foundation

**Shared product work**

- Confirm the first caregiver journey and the words used to describe events.
- Agree on the first six scenarios and what the user should understand in each one.
- Freeze the first version of shared product rules.

**Frontend track**

- Establish the basic visual language and navigation for the clinic product.
- Create the clinic app shell and a replaceable mock data source.

**Backend track**

- Establish the backend, database, tests, and product health checks.
- Represent residents, rooms, devices, events, feedback, and device health.

**Checkpoint**

Both sides can describe the same resident and event in the same way.

### Phase 2 — First complete event experience

**Frontend track**

- Build the resident overview, event list, event detail, priority, confidence, and evidence views.
- Build acknowledge, check, resolve, and feedback interactions using realistic mock information.
- Show missing data, uncertainty, and device problems clearly.

**Backend track**

- Store residents and events.
- Support the event journey: `detected → open → acknowledged → checked → resolved`.
- Prevent invalid actions and preserve the original event evidence.
- Store the resolution outcome and who took the action.

**Checkpoint**

The complete caregiver flow works independently on both sides against the same rules.

### Phase 3 — Connect frontend and backend

**Frontend track**

- Replace the mock event source with the real backend source.
- Keep mock mode available for product development and demonstrations.
- Add clear loading, offline, empty, and failure states.

**Backend track**

- Provide the real resident, event, feedback, and device-health information needed by the product.
- Add access boundaries so users see only the residents and locations they are allowed to see.
- Make actions reliable and auditable.

**Checkpoint**

The frontend connects to the real backend without redesigning the experience.

### Phase 4 — Feedback and understandable explanations

**Frontend track**

- Make feedback take only a few interactions.
- Present the system's explanation, alternatives, and uncertainty in clear language.
- Show a useful event even when the AI explanation is late or unavailable.

**Backend track**

- Store confirmed, false-positive, and uncertain outcomes with provenance.
- Build resident memory from trustworthy feedback.
- Add AI explanations only after an event already exists.
- Keep deterministic warnings independent from AI availability or opinion.

**Checkpoint**

A caregiver can understand an event, explain what actually happened, and see that feedback preserved for future context.

### Phase 5 — Simulated monitoring

**Frontend/product simulator track**

- Generate realistic scenarios for normal activity, unusual movement, physiological deviation, unknown anomaly, sensor failure, multiple people, RFID ambiguity, and recovery.
- Keep the true scenario label outside the product information so the system cannot cheat.

**Backend track**

- Accept simulated radar, thermal, Wi-Fi CSI, and RFID information.
- Handle duplicates, delays, missing sensors, and device connectivity problems.
- Turn sensor-specific information into a consistent internal form.

**Checkpoint**

A simulated room scenario can travel through the backend and appear as a meaningful product state or event.

### Phase 6 — Monitoring intelligence

**Frontend track**

- Show calibration progress, personal trends, confidence, device health, and degraded monitoring.
- Make “unavailable” understandable rather than displaying false precision.

**Backend track**

- Combine the different sensors and resolve resident identity using RFID evidence.
- Learn what is normal for each resident.
- Detect known unusual patterns and unknown anomalies.
- Create confidence and deterministic warning decisions.
- Keep all prototype warning rules clearly labeled as test-only until validated.

**Checkpoint**

Normal scenarios stay mostly quiet, meaningful simulated changes create understandable events, and weak data visibly lowers confidence.

### Phase 7 — Home/family product

**Frontend track**

- Build a separate, simpler home experience focused on “Are they okay?”
- Reuse shared product information without copying the clinic workflow or visual style.

**Backend track**

- Provide a home-appropriate view of the same resident and event information.
- Keep clinic operations, permissions, and sensitive context out of the home experience.

**Checkpoint**

Clinic staff and families receive different experiences from the same core monitoring engine.

### Phase 8 — Evaluation and product learning

**Frontend/product track**

- Test whether users understand events, confidence, and required actions.
- Record confusion, unnecessary steps, and alert-fatigue risks.

**Backend track**

- Replay the scenario library consistently.
- Measure missed events, false alerts, response time, confidence quality, sensor contribution, and improvement from personalization.

**Checkpoint**

The team can compare versions using evidence instead of impressions.

### Phase 9 — Real hardware

**Frontend track**

- Add setup, connectivity, sensor-health, and calibration experiences discovered during hardware testing.
- Keep the main caregiver flow unchanged.

**Backend and hardware track**

- Replace simulated input with real ESP32-preprocessed radar, thermal, Wi-Fi CSI, and RFID information.
- Calibrate quality and confidence using real observations.
- Feed real hardware failures into the existing device-health experience.

**Checkpoint**

Real hardware replaces the simulator without rewriting the event, feedback, AI, or frontend experience.

### Phase 10 — Pilot readiness

**Shared product work**

- Choose the first commercial wedge using customer interviews.
- Define the pilot workflow, support model, notification policy, and success measures.
- Complete the required privacy, security, access, retention, and compliance review before real clinical use.

**Checkpoint**

The product is understandable, measurable, supportable, and safe enough for a controlled pilot using appropriately authorized data.

## How both tracks work together

The two sides meet at four shared boundaries:

1. Product behavior — what the user sees and can do.
2. Shared definitions — what an event, status, priority, confidence, and outcome mean.
3. Handoff checkpoints — mock frontend and real backend must behave the same way.
4. End-to-end scenarios — the same scenario should be traceable from simulated room activity to the final user action.

Only one person should edit a shared product contract at a time. Product changes discovered in the frontend should be agreed on before the backend hardens them, and backend limitations that affect the experience should be raised before the frontend depends on them.

## Parallel tracks that run throughout

- **Customer discovery:** learn the buyer, user, painful events, current alternatives, false-alert tolerance, pricing, and pilot interest.
- **Research:** test whether sensor fusion, personal baselines, and feedback actually improve the system.
- **Safety and privacy:** avoid medical claims, real PHI in development, invented thresholds, and unnecessary identifying information.
- **Quality:** keep the product testable, replayable, observable, and understandable when parts fail.

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

The repository currently contains the product requirements, architecture, contracts, and build plan. The first backend slice now defines and tests the event lifecycle.

The next step is to wrap that behavior with a real API and database, then connect the first UI flow.

## Source-of-truth documents

- `docs/PRD.md` — what the product should do
- `docs/ARCHITECTURE.md` — how the major pieces connect
- `docs/DATA_CONTRACT.md` — the shared language between frontend, backend, simulator, and hardware
- `docs/BUILD_PLAN.md` — the detailed build sequence
- `docs/TEAM_OWNERSHIP.md` — who owns each part
