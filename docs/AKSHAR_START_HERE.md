# Akshar — Start Here

This is the plain-language guide for driving the product and building the backend.

## How to work with Akshar

Keep planning and progress updates at a product-manager level. Focus on:

- what the feature does for the user;
- the overall product flow and business logic;
- decisions, tradeoffs, ownership, dependencies, and risks;
- what is complete, what is next, and what still needs a decision.

Do not lead with code, file-by-file detail, framework jargon, or low-level implementation unless Akshar specifically asks for it.

## Team roles

- **Akshar — backend and intelligence:** Owns how the monitoring system works behind the product: data, room/resident assignment, quality, fusion, calibration, personal baselines, anomaly and warning logic, confidence, event creation, AI context, feedback learning, and evaluation.
- **Rishit — user-facing product and frontend:** Owns how clinic staff and families experience the system: user journeys, information hierarchy, screens, interactions, language, visual design, accessibility, frontend behavior, and product usability.
- **Hardware/Firmware Engineer — device and edge system:** Owns sensor bring-up, firmware, lightweight device-side processing, packaging, buffering, connectivity, device testing, and mapping real hardware output into the shared system boundary.
- **Shared:** Product behavior where user experience meets system behavior, shared definitions, contracts, end-to-end scenarios, integration checkpoints, and major product changes.

Each person should be able to make progress independently. Independence comes from agreeing on the boundaries, not from building disconnected systems.

## The complete product loop

The product is more than an event screen. The first version should demonstrate this complete adaptive loop:

```text
Room, device, and assigned resident are set up
        ↓
The resident begins calibration
new → calibrating → partial → established
        ↓
Sensors continuously produce information
        ↓
The system checks room assignment, freshness, quality, and missing data
        ↓
Radar, thermal, and Wi-Fi CSI evidence are combined
        ↓
The system compares the current state with the resident's personal baseline
        ↓
The system finds a known pattern, a deterministic warning, or an unknown anomaly
        ↓
An event is created with priority, confidence, evidence, and limitations
        ↓
AI may explain the already-created event using resident context
        ↓
A caregiver opens and understands it
        ↓
They acknowledge and check it
        ↓
They resolve it and give feedback
        ↓
The system learns through three controlled loops
```

The three learning loops are:

1. **Fast resident memory:** Trustworthy feedback can quickly add routines and context for future explanations.
2. **Controlled personal baseline:** Confirmed normal information can gradually update what is normal for that resident. Concerning or uncertain events do not silently become normal.
3. **Offline global improvement:** Accumulated labeled examples improve the overall system only after evaluation, versioning, and deliberate release.

Calibration is part of the product, not a one-time technical setup. The system must communicate whether a resident is new, calibrating, partially understood, or established, and it must lower confidence when it lacks enough trustworthy history.

## Shared alignment already agreed

1. **First user:** Start with the clinic caregiver experience, while keeping the future home/family product separate.
2. **Complete flow:** Include setup, calibration, continuous monitoring, quality, fusion, baselines, event creation, caregiver action, feedback, and all three learning loops.
3. **Shared meanings:** The team already has definitions for event priority, confidence, unavailable data, calibration states, and resolution outcomes.
4. **First scenarios:** Normal resident, unusual movement, unknown anomaly, low-confidence event, device issue, and false alarm are a good starting set. Calibration, missing/conflicting room assignment, multi-person ambiguity, recurring routine, and recovery are added as the next scenario layer.
5. **Ownership:** Akshar owns backend and intelligence. Rishit owns the user-facing product and frontend. The hardware/firmware engineer owns the device and edge system.
6. **Success definition:** The complete product loop works first with toy data and then with real hardware data without redesigning the product or intelligence layers.
7. **Working model:** All three tracks build back-to-front in parallel. Progress on one track should not block daily progress on another.
8. **V1 room model:** Each monitored room has one assigned resident. The product does not use a wearable identity layer or try to separate multiple people; possible caregiver/visitor presence lowers confidence or makes resident-specific monitoring unavailable.

The final market, medical thresholds, LLM provider, exact sensor math, and real hardware behavior do not need to be settled before work begins.

## Three-track roadmap

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

**Hardware track**

- Confirm the planned sensor responsibilities and device-side boundaries.
- Define what the device will eventually send, including quality, timing, occupancy/interference indicators, and device health.
- Prepare a hardware bring-up checklist so work can start immediately when parts arrive.

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

**Hardware track**

- Define the device states the product must understand: online, offline, missing sensor, poor quality, buffering, retrying, and room assignment unavailable.

**Checkpoint**

The complete caregiver flow works independently on both sides against the same rules.

### Phase 3 — First convergence on toy data

**Frontend track**

- Replace the mock event source with the real backend source.
- Keep mock mode available for product development and demonstrations.
- Add clear loading, offline, empty, and failure states.

**Backend track**

- Provide the real resident, event, feedback, and device-health information needed by the product.
- Add access boundaries so users see only the residents and locations they are allowed to see.
- Make actions reliable and auditable.

**Hardware track**

- Produce device-shaped toy messages that follow the same planned boundary as the future real device.
- Validate that the planned firmware responsibilities do not leak sensor-vendor details into the product.

**Checkpoint**

The frontend connects to the real backend using toy data without redesigning the experience. The planned hardware boundary can feed the same backend later.

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

**Hardware track**

- No major dependency on this phase; continue sensor research, bench planning, and edge-processing preparation independently.

**Checkpoint**

A caregiver can understand an event, explain what actually happened, and see that feedback preserved for future context.

### Phase 5 — Simulated monitoring

**Rishit/product scenario track**

- Generate realistic scenarios for normal activity, unusual movement, physiological deviation, unknown anomaly, sensor failure, multiple people, room-assignment problems, and recovery.
- Keep the true scenario label outside the product information so the system cannot cheat.

**Backend track**

- Accept simulated radar, thermal, and Wi-Fi CSI information.
- Handle duplicates, delays, missing sensors, and device connectivity problems.
- Turn sensor-specific information into a consistent internal form.

**Hardware track**

- Refine device-shaped simulated output and expected quality signals.
- Prepare firmware modules and test fixtures that can later replace simulated producers.

**Checkpoint**

A simulated room scenario can travel through the backend and appear as a meaningful product state or event.

### Phase 6 — Monitoring intelligence

**Frontend track**

- Show calibration progress, personal trends, confidence, device health, and degraded monitoring.
- Make “unavailable” understandable rather than displaying false precision.

**Backend track**

- Combine the different sensors for the resident assigned to the monitored room.
- Learn what is normal for each resident.
- Detect known unusual patterns and unknown anomalies.
- Create confidence and deterministic warning decisions.
- Keep all prototype warning rules clearly labeled as test-only until validated.

**Hardware track**

- Define how each sensor reports availability and quality.
- Test edge-processing assumptions as parts become available without moving cloud intelligence onto the device.

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

- Replace simulated input with real ESP32-preprocessed radar, thermal, and Wi-Fi CSI information.
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

## How all three tracks work together

The three tracks meet at four shared boundaries:

1. Product behavior — what the user sees and can do.
2. Shared definitions — what an event, status, priority, confidence, and outcome mean.
3. Handoff checkpoints — mock frontend, real backend, simulated device, and real device must behave consistently at their boundaries.
4. End-to-end scenarios — the same scenario should be traceable from simulated or real room activity to the final user action and learning outcome.

Only one person should edit a shared product contract at a time. Product changes discovered by Rishit should be agreed on before Akshar hardens them. Backend limitations that affect the experience should be raised before the frontend depends on them. Hardware discoveries should change only the device boundary unless evidence proves that a product or intelligence change is necessary.

The convergence happens twice:

1. **Before hardware arrives:** Rishit's product and Akshar's backend connect using toy data and simulated device information.
2. **After hardware arrives:** The hardware engineer replaces the simulated producer with real device information. The product and intelligence layers should not need to be rebuilt.

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
