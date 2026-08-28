# Contactless Adaptive Care Platform — Product Requirements Document

**Status:** Pre-build source of truth
**Audience:** Founders, Codex, engineering collaborators, future research/clinical advisors
**Version:** 1.5
**Purpose:** Define what the product is, what V1 must do, and what is intentionally left flexible until hardware testing and customer discovery.

---

## 1. Product Summary

We are building a low-cost, privacy-preserving monitoring platform that continuously observes a person without requiring an RGB camera or daily interaction from the person being monitored.

The core room system combines:

- 60 GHz mmWave radar
- MLX90640 32×24 thermal sensing
- ESP32-S3 Wi-Fi CSI / RF sensing

The embedded device is intentionally **small and efficient, not dumb**. It performs lightweight per-sensor preprocessing locally so huge raw streams do not need to be uploaded continuously. It can convert raw sensor output into compact usable measurements/features, remove obvious junk, downsample/compress, timestamp/package data, buffer during network loss, and retry uploads.

The device does **not** perform the main intelligence pipeline: no cross-sensor fusion, personal baseline modeling, anomaly/event decisions, LLM reasoning, or feedback learning. Those remain in the cloud.

The cloud combines the compact edge telemetry into useful resident-level measurements and events. Python-based processing validates and fuses the modalities, learns a personal baseline, detects anomalies and hard warning conditions, and assigns confidence. For non-urgent anomalies, an LLM is called selectively on a rich structured evidence packet before deterministic policy decides whether caregiver work is warranted. Strong urgent deterministic evidence may create a provisional event first and receive LLM enrichment afterward. Caregivers or families can then provide quick feedback, which improves resident context and later detection quality in a controlled way.

### One-line product thesis

> **Passive multimodal sensing + personal baselines + selective AI interpretation + human feedback = smarter monitoring that gets more personalized over time.**

---

## 2. Problem

Care environments need better visibility into residents and patients without adding constant human observation, intrusive cameras, uncomfortable cables, or devices that people must remember to charge and wear.

Existing monitoring approaches can have one or more of these problems:

- expensive room infrastructure or clinical monitoring equipment;
- dependence on cameras;
- wearable charging or compliance friction;
- single-sensor false positives;
- generic thresholds that do not reflect an individual's normal routine;
- alerts that show numbers without explaining what may have happened;
- little structured learning from caregiver feedback.

Our hypothesis is that inexpensive complementary sensors can be fused in software to create a useful monitoring system at materially lower hardware cost, while personalization and feedback reduce unnecessary alerts over time.

**Cost advantage is a hypothesis until validated with real BOM and competitor pricing. Do not make unsupported numeric cost claims.**

---

## 3. Product Principles

1. **Passive by default.** The core product should work without the monitored person pressing buttons, using a phone, or remembering a daily workflow.
2. **No RGB camera.** Privacy-preserving sensing is part of the product promise.
3. **Sensor fusion over sensor sprawl.** Do not add redundant core sensors unless testing proves a specific gap.
4. **Edge efficiency, cloud intelligence.** Do lightweight raw-to-usable conversion locally; keep cross-sensor reasoning and learning centrally.
5. **Personal, not generic.** The system learns what is normal for each person.
6. **Recall matters more than precision, but alert fatigue is unacceptable.** The system should favor not missing meaningful events while still actively reducing false positives.
7. **LLM for interpretation, not sensor math.** Numerical/feature processing measures; the LLM explains meaning.
8. **Uncertainty is a valid output.** The system must be allowed to say it is unsure.
9. **Human feedback is product functionality, not an afterthought.** Feedback should take seconds, not become paperwork.
10. **Controlled learning.** Feedback may improve memory and baselines, but safety behavior does not silently rewrite itself after every click.
11. **Modular hardware/software boundaries.** Hardware-specific formats may change without forcing a rewrite of the product.

---

## 4. Target Environments and Market Strategy

The first commercial wedge is **not yet locked**. We will use customer discovery and pilot conversations to decide where the pain, buying process, willingness to pay, and implementation feasibility are strongest.

Potential markets include:

- nursing homes;
- assisted living;
- rehabilitation;
- hospitals;
- home healthcare;
- direct-to-consumer family monitoring.

The product and data model should therefore avoid assumptions that only make sense for one facility type.

### Customer discovery questions

We need to learn:

- Which events cause the most operational pain today?
- How are residents monitored now?
- What creates the most false alarms?
- Which measurements or workflows are actually valuable?
- What would a facility or family pay for?
- Who is the buyer and who is the daily user?
- What integration, privacy, liability, and procurement barriers matter most?
- Is the strongest wedge safety, staffing efficiency, passive vitals, peace of mind, or another problem?

---

## 5. Two Product Surfaces

The same core monitoring engine supports **two separate products**. They share underlying technology but should not be treated as one connected user experience.

### 5.1 Clinic / Care Facility Product

Designed for staff managing multiple monitored people.

Primary jobs:

- see which residents are normal versus need attention;
- view and prioritize events;
- understand why an event was raised;
- see sensor/device health;
- acknowledge, check, and resolve events;
- provide quick structured feedback;
- review resident trends and history;
- see calibration/baseline status;
- see room assignment and monitoring-ambiguity status when relevant;
- understand confidence and data quality.

### 5.2 Home / Family Product

Designed for family members monitoring one loved one or household.

Primary jobs:

- answer "Are they okay?" simply;
- show meaningful trends without overwhelming raw sensor data;
- surface important events;
- let a family member explain normal routines or false alarms;
- learn routines and personal context over time;
- provide peace of mind rather than a hospital-style alarm console.

### Product separation rule

Clinic and home should have separate permissions, workflows, visual language, and notification policies. Sharing the monitoring engine does **not** mean exposing clinic operational data to families by default.

---

## 5A. UI/UX-First Development Philosophy

The first software experience should be built **from the user interface backward**. This does not mean creating throwaway static mockups. The clinic dashboard and home app should be built as the real production frontends, but initially powered by contract-valid mock data.

### Rules

- Define shared product/data contracts first.
- Build the real pages, components, states, and interactions against fixtures that follow those contracts.
- The UI may invent **example values**, but it must not invent **new data shapes** outside `DATA_CONTRACT.md`.
- Put mock data behind a replaceable frontend data-source/client layer.
- Later replace the mock provider with the real backend API without redesigning the UI.
- UI work should cover normal, abnormal, uncertain, unavailable, calibrating, device-failure, and LLM-unavailable states before the backend is complete.
- Product decisions discovered during UI work should feed back into the PRD/contracts before backend code hardens them.

### Desired progression

```text
CONTRACTS
    ↓
REAL UI/UX + MOCK DATA
    ↓
BACKEND/API IMPLEMENTS SAME CONTRACTS
    ↓
SIMULATOR + PROCESSING FILLS REAL VALUES
    ↓
REAL HARDWARE REPLACES SIMULATOR
```

The goal is to see and test the product early while ensuring the UI work is not disposable.

---

## 6. Core Hardware Scope

The ordered/core V1 hardware architecture is fixed for the initial build:

### 60 GHz mmWave radar

Intended inputs/research targets include:

- chest/body micro-motion;
- distance;
- movement;
- heart-rate-related signal/trend;
- respiratory-rate-related signal/trend;
- HRV research signal if raw data supports it;
- position and sudden-movement evidence.

### MLX90640 thermal array

Provides a low-resolution 32×24 thermal map for:

- person localization;
- temperature trend;
- human-versus-object evidence;
- position/floor/bed-related evidence.

It is **not** treated as a clinical core-temperature measurement.

### ESP32-S3 Wi-Fi CSI / RF sensing

Provides Wi-Fi channel-state/RF information that may support:

- presence;
- movement;
- respiration-related patterns;
- body-motion/position information;
- additional supporting physiological or localization features.

CSI is a complementary modality. The processing implementation may use RuView concepts or code, but the product architecture must not depend on one specific CSI library.

### ESP32-S3 role

The ESP32/edge layer should remain lightweight, but it should reduce raw-data volume before cloud upload. It may:

- acquire radar, thermal, and CSI data;
- perform per-sensor raw-to-usable conversion;
- remove obvious invalid/junk samples;
- calculate compact per-sensor measurements/features where practical;
- downsample, aggregate, or compress high-volume streams;
- attach device/source identifiers and sequence/time metadata;
- package/batch compact telemetry;
- optionally retain/upload bounded raw/debug windows for development and replay;
- buffer temporarily during network loss;
- retry uploads;
- report basic device/transport health.

It should **not** perform cross-sensor fusion, personal baseline modeling, anomaly/event decisions, LLM reasoning, or feedback learning.
### V1 room and resident assignment

V1 intentionally supports **one assigned resident per monitored room** and does not include a resident wearable or separate identity-reader layer.

The backend maps each monitoring device to one room and each monitored room to one assigned resident. Radar, thermal, and CSI observations from that room are attributed to the assigned resident only while the room remains suitable for single-person monitoring.

Caregivers, visitors, or other people may still enter the room. If sensing indicates possible multi-person presence or attribution is otherwise ambiguous, the system must lower confidence or mark resident-specific measurements unavailable. V1 does not attempt to identify or separate multiple people.


---

## 7. Optional Accessories

Optional accessories can add information that the contactless node cannot reliably obtain.

Possible future integrations:

- existing SpO₂ device;
- existing blood-pressure cuff;
- other validated external medical devices.

These should feed the same cloud resident record through adapters. SpO₂/BP and other medical accessories remain optional.

---

## 8. Monitoring Capabilities

The platform should be **general and extensible**, not hard-coded around one event such as falls.

### Physiological monitoring targets

Depending on sensor quality and validation:

- heart-rate trend;
- respiratory rate/trend;
- HRV research features;
- temperature trend;
- combined physiological deviation from personal baseline.

### Behavioral / physical monitoring targets

- presence;
- movement/activity;
- inactivity;
- restlessness;
- position/state;
- standing/sitting/lying/floor-like state;
- bed-related state if inferable from fusion;
- bed-exit-like movement if inferable;
- fall-like or sudden downward movement;
- collapse/syncope-like patterns;
- repetitive/seizure-like movement patterns;
- other previously unseen abnormal patterns.

### Event/anomaly families the product should support

The system should be broad enough to surface both **known patterns** and **unknown anomalies**. Initial examples include:

- fall-like / rapid downward-movement event;
- collapse/syncope-like event;
- unusual movement or position transition;
- prolonged inactivity after movement;
- unusually high activity/restlessness;
- repetitive/high-frequency movement pattern;
- heart-rate trend significantly different from the resident's baseline;
- respiratory-rate/pattern significantly different from baseline;
- combined physiological deterioration pattern across multiple signals;
- unusual nighttime or bed-exit-like activity when supported by fusion;
- low-confidence/ambiguous multi-person event;
- sensor/device-quality issue;
- `unknown_anomaly` when something is clearly unusual but does not fit a known pattern.

Python should detect and describe the **objective anomaly facts**. It does not need to force the event into one semantic cause. The LLM may attach likely explanations such as `fall_like`, `assisted_movement`, `collapse_like`, or `unknown`, with alternatives and uncertainty.

### Specific medical-event research

The platform may later research whether multi-sensor patterns correlate strongly enough with specific events such as cardiac events, respiratory distress, seizures, or physiological deterioration.

Until validated, the product should describe these as **anomalies, possible event patterns, or research classifications**, not definitive medical diagnoses.

---

## 9. Continuous Data Flow

Data collection is continuous while the device is operating.

The system should:

1. receive compact edge telemetry from radar, thermal, and CSI;
2. store processed history needed for trends, replay, baselines, and event analysis;
3. optionally store bounded raw/debug windows when explicitly captured for development, research, or event investigation;
4. validate/standardize edge telemetry and derive normalized measurements/features;
5. synchronize and fuse sensor evidence for the resident assigned to the monitored room;
6. compare against individual baselines;
7. create anomaly candidates and deterministic warning candidates;
8. immediately create a provisional event when strong urgent deterministic policy requires it;
9. selectively invoke the LLM on rich anomaly evidence for non-urgent interpretation or urgent-event enrichment;
10. apply deterministic product policy to choose no action, continued observation, awareness, or caregiver work;
11. surface approved events in the relevant product;
12. capture human outcome/feedback;
13. update resident memory and eligible baseline data;
14. use accumulated labeled events for future system improvements.

Exact processed-history and optional raw/debug retention durations are intentionally configurable and not locked yet. Continuous raw upload/storage is not a production requirement.

---

## 10. Data Quality and Confidence

The product must never display a measurement as trustworthy merely because a sensor produced a value.

The cloud must track:

- sensor availability;
- signal quality;
- missing data;
- disagreement between modalities;
- likely multi-person interference;
- freshness;
- confidence in derived measurements;
- confidence in events.

A measurement may be shown as **unavailable** or **low confidence** rather than forcing a number.

Example:

- `Heart-rate trend: 74 BPM — High quality`
- `Heart-rate trend: unavailable — resident moving / low signal quality`

---

## 11. Personal Baseline and Calibration

Each resident/person has a baseline state:

- `new`
- `calibrating`
- `partial`
- `established`

The baseline may learn:

- normal physiological ranges/trends;
- time-of-day behavior;
- normal movement/activity;
- usual position patterns;
- recurring routines;
- normal variability.

### Baseline learning rules

- confirmed-normal periods may influence the baseline;
- false positives caused by normal routine may influence the baseline;
- confirmed concerning events should not teach the system that the event is normal;
- unknown/unreviewed events should not automatically redefine normal;
- bad sensor data must be excluded;
- updates should be bounded, versioned, and reversible.

Calibration should depend on sufficient valid data, not a hard-coded number of calendar days.

### Behavior during calibration

- data collection and device-health monitoring begin immediately;
- broad obvious patterns may still create events during `new`/`calibrating`, but personalized conclusions are limited and visibly lower-confidence;
- extreme-value warnings require strong signal quality and a versioned rule; prototype rules are synthetic/test-only until validated;
- `partial` may enable personalized monitoring for some dimensions while others remain provisional or unavailable;
- resident-away, possible-multiple-person, poor-quality, concerning-event, and unresolved-anomaly windows are excluded from baseline learning.

### Presence and setup changes

- resident-away is an awareness/timeline state, not a resident warning;
- resident-specific measurements and baseline learning pause while the resident is away;
- possible caregiver/visitor presence limits resident-specific monitoring and pauses baseline learning;
- an extremely unusual room-level pattern during possible multi-person presence may create a low-confidence verification event without claiming resident-specific attribution;
- moving the resident, materially moving the device, replacing a core sensor, or materially changing the room starts partial or full recalibration;
- resident history and semantic memory remain, while affected physical-sensing baseline dimensions recalibrate;
- the dashboard provides an explicit setup-change/recalibration action and reason.

---

## 12. Anomaly and Event System

Python/numerical processing decides whether something is sufficiently unusual to become an anomaly episode and whether a strong deterministic warning condition requires immediate provisional caregiver work. Non-urgent anomaly episodes are interpreted from structured evidence before deterministic product policy chooses whether to create an event.

### Event evidence may include

- magnitude of deviation from baseline;
- rate of change;
- duration;
- cross-sensor agreement;
- resident state before/after;
- signal quality;
- multiple-person state;
- sensor/device health;
- relevant optional accessory data.

### Event priorities

The implementation should support configurable priority levels such as:

- `watch`
- `high`
- `critical`

Exact medical thresholds and clinical warning rules are **not** invented during software development. They remain configurable until validated.

Priority and confidence are separate. Priority may consider objective severity, confidence/quality, duration, rate of change, sensor agreement, personal-baseline deviation, recurrence, and missing information.

- `watch` is awareness/review and may be grouped, summarized, hidden, or auto-closed by settings;
- `high` needs timely staff attention and always remains visible in the dashboard;
- `critical` needs immediate staff attention and cannot be hidden in the dashboard;
- administrators configure notification delivery channels and low-priority noise controls.

### LLM-independent warning path

Certain deterministic warnings can create/raise events without relying on the LLM. The LLM may explain such an event but cannot suppress it.

This is LLM-independent, not necessarily internet-independent. True on-device/offline safety logic is future scope unless explicitly added later.

---

## 13. LLM Interpretation Layer

The LLM is called only for meaningful anomaly episodes, event enrichment, or scheduled context-maintenance tasks, not continuously for raw sensor streams.

### Inputs

- structured anomaly/event facts and evidence references;
- resident memory/context;
- relevant previous events;
- relevant previous human feedback;
- stable versioned system instructions/skill file;
- confidence and data-quality information.

### Outputs

- likely explanation(s);
- alternative explanation(s);
- uncertainty/confidence;
- concise plain-English event summary;
- caregiver-facing reason for why the event matters;
- optional recommended verification step such as "check resident" when policy allows;
- no fabricated sensor values.

The LLM must be allowed to output `unknown` / `insufficient evidence`.

If the LLM is unavailable, urgent deterministic events still exist and non-urgent deterministic policy can still use objective evidence and fallback wording. No safety path depends on a successful LLM call.

---

## 14. Event Lifecycle

Core lifecycle:

`detected → open → acknowledged → checked → resolved`

`detected` is internal; `open` is the first user-visible state. Related signals within a configurable quiet-time gap update one active event episode. A recurrence after the gap creates a new linked event. Resolved events remain immutable and do not reopen; later occurrences become new linked events.

`watch` items may auto-close when the condition returns to normal and remain in history. Unacknowledged `high` and `critical` events never silently expire; they become overdue and may escalate according to configurable policy. Repeated related events show a recurrence/pattern indicator.

Resolution outcome:

- `confirmed`
- `false_positive`
- `uncertain`

Additional structured fields may capture what actually happened.

The event record must preserve the original evidence and interpretation even after later feedback.

---

## 15. Feedback Loop

Feedback should take seconds.

### Basic flow

1. Human reviews/checks the event.
2. Human chooses `confirmed`, `false positive`, or `unsure`.
3. A feedback AI may ask one or two short follow-up questions.
4. The response is converted into structured feedback.
5. Feedback is stored with provenance and confidence.

Example:

- System: "Possible unusual movement event."
- Caregiver: "False positive."
- AI: "What actually happened?"
- Caregiver: "I was helping them stand up."
- AI: "Is that part of their normal routine?"
- Caregiver: "Yes."

Structured result:

- outcome: false positive
- actual event: assisted movement
- routine: yes
- source: caregiver-confirmed

### Feedback confidence

V1 treats authenticated clinic dashboard operators as authorized, trusted feedback sources. Every feedback change records actor, time, source event, and version. Authorized operators may correct or supersede earlier feedback without deleting history.

---

## 16. Learning Loops

There are three different learning speeds.

### A. Fast: Resident memory

Relevant feedback and routines may update resident context promptly.

Authorized operators can view, add, correct, or retire resident routines/context from resident settings. Memory changes remain versioned and auditable.

### B. Controlled: Personal baseline

Trusted normal data gradually updates numerical baselines within bounded rules.

### C. Offline/versioned: Global system improvements

Accumulated labeled events can later improve:

- filters;
- feature extraction;
- fusion;
- anomaly logic;
- event classifiers;
- global AI instructions.

System-wide changes must be evaluated and versioned before deployment. Feedback does not automatically rewrite safety logic or the global skill file after each event.

### Flexible routines and legitimate new behavior

Authorized operators may record broad routines, habits, temporary changes,
and expected new behavior before an anomaly or through later feedback. These
entries immediately inform relevant LLM context but do not act as rigid
schedules and do not directly suppress urgent physical evidence. A legitimate
new normal enters numerical baselines only after controlled, clean,
single-person, good-quality coverage; the prior baseline remains versioned and
replayable. Every admitted learning window must fall inside the expected-
behavior entry's effective interval. When that context expires, an in-progress
adoption stops without publishing a numerical baseline.

---

## 17. Active Learning

The system may proactively ask a user when it repeatedly sees a pattern it cannot explain.

Example:

> "We often see this unusual activity around 1 PM on Tuesdays. Is something normally happening then?"

Human response can become resident context, such as a therapy session or routine transfer.

Active-learning prompts must be sparse and useful; they should not create notification fatigue.

---

## 18. Device Health and Degraded Operation

The system must distinguish resident events from device problems.

Device-health cases include:

- device offline;
- individual sensor missing;
- frozen/stale stream;
- upload failures;
- low-quality/noisy sensing;
- time/sequence anomalies;
- room assignment missing or possible multi-person presence.

### Degradation rules

- one missing modality should lower confidence, not automatically stop the entire system;
- if CSI is unavailable, radar + thermal may continue;
- if the LLM is unavailable, events still surface with structured evidence;
- if cloud connectivity drops, the device should buffer/retry compact edge telemetry within practical storage limits;
- the dashboard must show device last-seen and sensor-health state.

---

## 19. Simulator-First Development

Software development starts before real hardware integration.

The simulator must generate the same versioned ingestion contract that the real device will eventually use.

Minimum scenario library:

- normal resting;
- normal movement;
- physiological deviation;
- unusual movement;
- prolonged inactivity;
- fall-like sequence;
- collapse-like sequence;
- repetitive movement pattern;
- sensor noise/failure;
- missing sensor;
- multi-person/interference case;
- recurring normal routine;
- recovery/return to normal.

The architecture should remain broad enough to add new scenarios without changing core event infrastructure.

---

## 20. Privacy, Security, and Development Data

Initial development uses synthetic/test residents and synthetic or properly authorized data.

Do not put real PHI in development fixtures, logs, prompts, screenshots, or analytics.

Architecture principles:

- tenant isolation;
- role-based access;
- least privilege;
- encryption in transit;
- secrets outside source control;
- auditability for sensitive actions;
- pseudonymous internal resident IDs;
- configurable retention;
- minimum necessary context sent to an LLM.

Any real clinical deployment requires a separate privacy/security/compliance review.

---

## 21. Success Metrics

The prototype/research system should measure:

### Detection

- event recall;
- precision;
- false alerts per monitored person-day;
- detection latency;
- performance by event type/pattern;
- performance before/after personalization.

### Sensor/system

- sensor uptime;
- percentage of time each derived vital/feature is high quality;
- missing-data rate;
- confidence calibration;
- fusion performance versus individual modalities;
- device/cloud availability.

### AI

- interpretation structured-output validity;
- percentage of interpretations rated useful/correct;
- unknown/uncertain rate;
- LLM latency/cost per event;
- hallucinated-data rate (target: zero).

### Feedback

- feedback completion rate;
- median feedback completion time;
- percentage of events with trustworthy outcome labels;
- false-positive reduction after personalization.

### Product

- staff/family comprehension of events;
- alert fatigue/user satisfaction;
- setup/calibration success;
- willingness to pilot/pay discovered through customer interviews.

No unsupported numeric clinical-performance target is locked before data exists.

---

## 22. V1 Requirements

V1 is a **general monitoring platform**, not a single-event detector.

V1 must demonstrate:

1. contract-valid production UI/UX running first on mock data;
2. continuous simulated edge-telemetry ingestion from radar, thermal, and CSI;
3. processed telemetry storage/replay plus optional bounded raw/debug capture;
4. modular radar/thermal/CSI edge and cloud interfaces;
5. one assigned resident per monitored room, with ambiguous/multi-person sensing handled as degraded or unavailable;
6. multi-sensor fusion;
7. personal baseline/calibration;
8. general anomaly detection, including an `unknown_anomaly` path;
9. deterministic configurable warning path;
10. event lifecycle and confidence;
11. selective LLM interpretation;
12. clinic dashboard workflow;
13. home/family product workflow at least at functional MVP level or behind the shared API, depending on build sequencing;
14. human feedback with AI follow-ups;
15. resident memory update;
16. device-health monitoring;
17. evaluation/replay harness;
18. ability to replace simulator with real hardware/edge adapters without redesigning the stack.

---

## 23. Non-Goals for Initial Build

Do not make the initial codebase depend on:

- a specific final vendor/raw sensor format;
- a specific LLM provider;
- one hard-coded event taxonomy;
- a trained custom event classifier;
- EHR integration;
- nurse-call integration;
- custom SpO₂/BP hardware;
- medical diagnosis claims;
- production HIPAA certification;
- automatic global self-modification;
- RGB cameras or microphones.

---

## 24. Decisions Intentionally Left Adjustable

These remain configuration/research decisions:

- exact radar vendor output and edge-conversion details;
- exact CSI implementation and RuView usage;
- exact sensor sampling and edge-telemetry rates;
- exact filters;
- exact derived-feature equations;
- fusion weights;
- anomaly thresholds;
- calibration duration;
- hard clinical warning thresholds;
- exact processed-history and diagnostic-raw retention durations;
- exact LLM provider/model;
- exact deployment/cloud vendor;
- exact multi-person/interference detection behavior and room placement constraints;
- future trained classifier architecture;
- final pricing and first market wedge.

The architecture must make these replaceable without rewriting the product.
