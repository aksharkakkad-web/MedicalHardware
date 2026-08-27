# Contactless Adaptive Care Platform — Technical Architecture

**Status:** Pre-build architecture source of truth
**Version:** 1.4
**Companion docs:** `PRD.md`, `DATA_CONTRACT.md`, `BUILD_PLAN.md`, root `AGENTS.md`

---

## 1. Architecture Goal

Build a modular monitoring platform whose real product UI can be developed first against contract-valid mock data, whose cloud intelligence can then be developed against simulated **edge telemetry**, and which can finally accept real ESP32-preprocessed radar/thermal/CSI data without rewriting the product.

The architecture must support:

- continuous multimodal sensor ingestion;
- lightweight edge preprocessing + cloud intelligence;
- replaceable hardware/edge adapters;
- personal baselines;
- general anomaly/event detection;
- LLM interpretation only after event creation;
- separate clinic and home product surfaces;
- fast human feedback;
- controlled personalization/learning;
- strong observability and graceful degradation.

---

## 2. Locked Architectural Decisions

- Core inputs: 60 GHz radar + MLX90640 thermal + ESP32-S3 Wi-Fi CSI.
- Embedded device performs lightweight per-modality raw-to-usable conversion, downsampling/compression, packaging, and buffering/retry.
- V1 supports one assigned resident per monitored room. Device-to-room and room-to-resident assignments provide product attribution.
- Suspected multi-person presence makes resident-specific monitoring ambiguous or unavailable; V1 does not identify or separate multiple people.
- Embedded device does not perform cross-sensor fusion, personal baselines, anomaly/event decisions, LLM reasoning, or feedback learning.
- Cloud is the intelligence layer.
- Python handles filtering, feature extraction, fusion, baseline, anomaly detection, confidence, device health, and deterministic warnings.
- LLM interprets already-created events; it does not monitor continuous telemetry or suppress deterministic events.
- Data collection is continuous.
- Vendor/raw hardware formats are hidden behind edge adapters; the cloud primarily receives compact edge telemetry.
- A versioned normalized internal contract is the stable software boundary.
- Simulator and real hardware use the same ingestion boundary.
- Postgres/Supabase is the default V1 database.
- FastAPI is the default backend API framework.
- Next.js is the default web stack.
- Clinic and home are separate product surfaces sharing core services.
- LLM provider is abstracted behind an interface.
- Global learning is versioned/evaluated, not automatic live self-modification.
- Product frontends are built UI-first against contract-valid mock providers, then switched to real APIs behind the same frontend client interface.

---

## 3. End-to-End Flow

```text
RADAR ───────┐
THERMAL ─────┼──> ESP32-S3 edge node
WIFI CSI ────┘      • per-sensor raw→usable conversion
                     • downsample/compress
                      • timestamp/package/buffer/retry
                         |
                         v
                 HTTPS ingestion API
                         |
                         v
                Edge telemetry store
                         |
                         v
                 Cloud normalizers
                radar thermal csi
                   \    |    /
                    v   v   v
              Time alignment + fusion
                + room assignment
                         |
                         v
                Fused resident state
                         |
              +----------+-----------+
              |                      |
              v                      v
       Baseline engine         Device health
              |                      |
              +----------+-----------+
                         v
                  Anomaly engine
                         |
                         v
                    Event engine
              +----------+----------+
              |                     |
              v                     v
      deterministic policy     context builder
              |                     |
              |                     v
              |              LLM interpreter
              |                     |
              +----------+----------+
                         v
                  Product event API
                 /                 \n                v                   v
        Clinic dashboard        Home app
                \                   /
                 v                 v
                  Human feedback
                         |
                         v
               Structured outcome data
                 /                 \n                v                   v
       Resident memory       Baseline eligibility
                \                   /
                 v                 v
                 Controlled learning
                         |
                         +----> future evaluated model/system updates
```

---

## 3A. UI-First / Mock-to-Real Architecture

The clinic dashboard and home app should be built as **real production frontends before the full backend/sensor pipeline is complete**.

They must depend on a small frontend data-client interface rather than importing fixture files directly throughout components.

```text
UI COMPONENTS
      ↓
MonitoringClient interface
   ↙              ↘
MockClient       ApiClient
   ↓              ↓
contract-valid   FastAPI
fixtures         backend
```

Rules:

- `MockClient` and `ApiClient` return the same domain shapes.
- UI components should not know whether data is mocked or real.
- Mock values may be synthetic, but schemas and lifecycle semantics must match `DATA_CONTRACT.md`.
- Product interactions such as acknowledge, checked, resolve, and feedback should work locally in mock mode before the backend exists.
- Once the backend implements the contract, switching providers should not require redesigning pages/components.
- UI-first work is also a product-discovery tool: if a workflow is confusing in the mock product, fix the requirement before hardening backend behavior.

---

## 4. Layer 1 — Embedded Sensor Node

### Responsibilities

The embedded node should make sensor data compact and transportable without becoming the decision-making brain:

- acquire radar, thermal, and CSI data;
- decode vendor/raw outputs;
- perform lightweight per-sensor filtering and raw-to-usable conversion;
- calculate compact per-sensor values/features where practical (for example radar vital/motion outputs, thermal summary/location features, CSI movement/presence features);
- downsample/aggregate/compress high-volume streams;
- attach source metadata, sequence numbers, and timestamps;
- construct/batch EdgeTelemetryEnvelope packets;
- optionally retain/upload bounded diagnostic raw windows;
- buffer during network interruption and retry idempotently;
- heartbeat/transport health;
- secure device authentication.

### Explicitly not on device

- cross-sensor radar+thermal+CSI fusion;
- final monitoring-confidence decisions;
- personal baseline modeling;
- anomaly/event decisions;
- deterministic alert policy evaluation;
- LLM calls;
- resident memory or feedback learning;
- global system/model updates.

The exact vendor/raw formats remain TBD until hardware testing. Firmware/edge adapters therefore convert vendor-specific data into a stable versioned edge-telemetry schema before normal production upload. Optional diagnostic raw capture uses a separate bounded path.

---


## Edge vs Cloud Split

### Edge / ESP32

The edge exists to make sensor data **small, usable, and reliable to transport**. It may do per-modality conversion, obvious-invalid filtering, downsampling/aggregation/compression, timestamping, packetization, local buffering/retry, and bounded diagnostic raw capture.

### Cloud

The cloud owns the intelligence that depends on history or multiple inputs: modality validation, radar+thermal+CSI fusion, room/resident assignment, personal baselines, anomaly/confidence/event logic, deterministic warning policies, resident memory, LLM interpretation, feedback, and learning/evaluation.

This boundary is deliberate: **edge makes data manageable; cloud makes it intelligent.**


## 5. Layer 2 — Ingestion Gateway

### Responsibilities

- authenticate device;
- validate envelope schema/version;
- reject impossible/oversized payloads;
- assign server receive time;
- deduplicate by device/source/sequence;
- persist compact edge telemetry;
- optionally persist bounded diagnostic raw chunks;
- emit work for processing;
- maintain device last-seen state.

### V1 transport

Use versioned HTTPS/HTTP POST endpoints.

MQTT or another streaming transport may be introduced later behind the same domain contracts if needed.

---

## 6. Layer 3 — Telemetry & Diagnostic Storage

Store enough **edge telemetry** to support:

- trends and personal baselines;
- event replay;
- algorithm research;
- debugging;
- sensor validation;
- baseline backfills;
- labeled datasets later.

Diagnostic raw sensor windows are optional and bounded; they are not the normal continuous storage format.

Recommended V1 model:

- metadata/index in Postgres;
- large binary/chunk payloads may use object storage when volume requires it;
- retention is configurable;
- event-adjacent diagnostic raw windows may be kept when useful; continuous routine raw storage is not assumed.

Do not hard-code permanent processed or diagnostic-raw retention durations yet.

---

## 7. Layer 4 — Sensor Adapters / Processors

Each sensor has a separate **edge preprocessor** that converts vendor/raw output into compact per-modality telemetry. The cloud then has a lightweight normalizer/validator per modality before fusion.

### Radar processor

Potential outputs:

- derived heart-rate estimate/trend + quality;
- respiratory estimate/trend + quality;
- distance;
- motion features;
- position/displacement features;
- raw waveform-derived features if available.

### Thermal processor

Potential outputs:

- thermal frame statistics;
- warm-body localization;
- thermal trend;
- position/floor/bed evidence;
- quality/occlusion indicators.

### Wi-Fi CSI processor

Potential outputs:

- presence/movement features;
- RF disturbance features;
- respiration-related features;
- localization/body-motion features;
- quality/confidence indicators.

RuView may be used as an implementation/reference for CSI processing, but the rest of the stack depends only on our normalized contract.

### Room/resident assignment adapter

V1 maps each monitoring device to a room and each monitored room to one assigned resident. This assignment provides product attribution without a wearable identity layer. The adapter must reject missing or conflicting assignments and expose suspected multi-person presence as degraded or unavailable resident-specific monitoring.

### Optional medical accessory adapter

SpO₂ devices, BP cuffs, or future validated sensors plug in through independent adapters and become additional normalized evidence.

---

## 8. Layer 5 — Time Alignment and Sensor Fusion

Sensor fusion consumes normalized compact features + room/resident assignment context, not vendor-specific raw formats.

Responsibilities:

- align observations into common time windows;
- track which modalities are present;
- determine monitoring suitability: resident present, resident away, possible multi-person, or unavailable;
- compare independent evidence;
- represent disagreement;
- calculate per-feature quality;
- detect likely multi-person/interference conditions;
- produce a fused observation/frame.

Fusion should not require all sensors. Missing modalities reduce confidence rather than automatically stopping monitoring.

---

## 9. Layer 6 — Personal Baseline Engine

Stores versioned resident-specific normal behavior.

Baseline dimensions may include:

- physiological levels/trends;
- movement/activity statistics;
- time-of-day behavior;
- position/state distributions;
- recurring routines;
- variability/seasonality.

### Update policy

Baseline updates only use eligible data:

- high-enough sensor quality;
- confirmed normal or otherwise trusted;
- not inside known concerning event windows;
- not unreviewed ambiguous anomalies;
- bounded against runaway adaptation.

Every baseline update creates a new version or auditable revision.

Calibration behavior:

- device health and broad/test-only warning paths may run before a personal baseline is established;
- personalized conclusions remain limited and visibly lower-confidence during `new` and `calibrating`;
- `partial` enables only the dimensions with sufficient eligible coverage;
- away, possible-multi-person, poor-quality, concerning-event, and unresolved-anomaly windows are ineligible for learning;
- room moves, material device moves, core-sensor replacement, or material layout changes create a new monitoring-setup version and return affected dimensions to `calibrating` or `partial`;
- resident history and semantic memory survive recalibration.

---

## 10. Layer 7 — Device Health / Monitoring Quality

Device health is a first-class domain, separate from resident health.

Detect:

- device offline;
- sensor missing;
- stale/frozen stream;
- packet loss/sequence gaps;
- clock anomalies;
- persistently low signal quality;
- sensor disagreement;
- possible multi-person interference;
- accessory disconnected;
- ingestion backlog.

This produces `device_health` records and, when appropriate, operational events distinct from resident events.

---

## 11. Layer 8 — Anomaly Engine

The anomaly engine is intentionally general.

Inputs:

- fused observation;
- baseline snapshot;
- device/sensor quality;
- recent normalized history;
- optional accessory evidence.

Outputs:

- anomaly score(s);
- which dimensions are unusual;
- magnitude/direction of deviations;
- duration/rate-of-change facts;
- confidence;
- evidence list;
- possible deterministic warning matches.

The engine should start with simple configurable statistical/rule-based methods and remain replaceable by better models when labeled data exists.

The anomaly layer may recognize broad **objective event families** such as sudden movement, prolonged inactivity, vital deviation, repetitive motion, or device-quality failure, but it should not be required to decide the real-world cause. Semantic interpretation belongs to the LLM/context layer.

An explicit `unknown_anomaly` path must exist for events that are clearly unusual but do not map cleanly to a known pattern.

Do not hard-code the codebase around one event type.

---

## 12. Layer 9 — Event and Policy Engine

An anomaly candidate is not automatically a user-facing alert.

The event engine decides when evidence becomes a durable domain `MonitoringEvent`.

Responsibilities:

- event creation/deduplication;
- priority assignment;
- event lifecycle state;
- merge/update related anomaly windows;
- attach evidence and baseline version;
- trigger deterministic/LLM-independent warning policy;
- trigger optional LLM interpretation;
- route event to product surfaces.

Episode and recurrence rules:

- `detected` is internal and `open` is the first user-visible state;
- related evidence inside a configurable quiet-time gap updates one active episode;
- recurrence after that gap creates a new event linked to prior events;
- resolved events remain immutable and never reopen;
- repeated linked events expose recurrence/pattern information;
- watch items may auto-close into history, while high/critical events become overdue and never silently expire.

### Deterministic warning policy

Hard-warning rules are configurable and versioned. They may raise priority/create an event without the LLM.

The initial repo must not invent unvalidated medical thresholds. Use simulator/demo rules labeled as synthetic/test-only until validated.

---

## 13. Layer 10 — Context Builder

The LLM should receive only relevant structured context.

Context builder retrieves:

- event facts/evidence;
- confidence/quality;
- resident memory;
- relevant recent/previous events;
- relevant human feedback;
- current baseline summary;
- stable versioned interpreter instructions.

Do not dump full raw sensor history or entire resident records into the LLM.

---

## 14. Layer 11 — LLM Interpreter

The interpreter is behind a provider-neutral interface.

### Runtime prompt components

Implementation should eventually create versioned prompt/skill files such as:

- `prompts/event_interpreter.md`
- `prompts/feedback_agent.md`
- `prompts/resident_memory_updater.md`

### Event interpreter outputs

Strict structured response:

- likely explanation;
- alternatives;
- confidence/uncertainty;
- plain-English summary;
- evidence references;
- no invented measurements;
- `unknown` supported.

### Failure behavior

If LLM invocation fails:

- event remains valid;
- product shows objective evidence;
- interpretation status is `unavailable`;
- retry policy may run asynchronously.

---

## 15. Layer 12 — Product APIs and Frontend Client Boundary

Expose shared domain APIs while keeping product behavior separate. Frontends consume these through a typed client interface that can be backed by either contract-valid mock fixtures or the real API.

### Shared

- authentication/session;
- resident profile and room assignment;
- latest status;
- event list/detail;
- trends;
- feedback submission;
- device status.
- resident monitoring/presence status;
- recurrence and overdue state;
- notification preferences;
- editable, versioned resident memory settings.

### Clinic-specific

- multi-resident overview;
- prioritization queue;
- acknowledgment/check/resolve workflows;
- staff audit trail;
- operational device view.

### Home-specific

- simplified loved-one status;
- meaningful trend summaries;
- family-friendly event detail;
- routine/context feedback;
- lower-noise notification policy.

No automatic clinic→family data exposure.

---

## 16. Layer 13 — Feedback Engine

Feedback is stored as structured ground truth with provenance.

Flow:

1. user selects outcome;
2. optional AI follow-up asks at most a small number of useful questions;
3. structured fields are saved;
4. original event remains immutable;
5. resident memory updater may run;
6. baseline eligibility is recalculated;
7. labeled outcome becomes evaluation/training data.

Authenticated clinic operators are treated as trusted V1 feedback sources. Corrections supersede prior feedback/memory versions without deleting audit history.

The AI feedback agent asks questions; it does not directly mutate safety configuration.

---

## 17. Layer 14 — Learning System

### Resident memory

Fast, semantic context update from trusted feedback/routines.

### Personal baseline

Controlled numerical update from eligible data.

### Global improvement

Offline/evaluated workflow:

`dataset snapshot → experiment → metrics → review → version → deploy`

Potential future classifier sits here. It becomes evidence for interpretation, not an unquestioned final truth.

---

## 18. Tech Stack

### Frontend

- Next.js + TypeScript
- shared UI/domain client code where useful
- separate clinic and home applications or clearly isolated routes/packages

### Backend

- Python 3.12+
- FastAPI
- Pydantic for contracts
- SQLAlchemy/Alembic (or equivalent) for DB access/migrations
- pytest for backend tests

### Data

- Postgres (Supabase-hosted is the default V1 choice)
- object storage if raw binary volumes justify it

### AI

- provider-neutral `LLMClient` interface
- structured-output validation
- versioned prompt files
- event-level caching/idempotency

### Quality

- Ruff/formatting/linting
- type checking where practical
- frontend lint/typecheck/build
- Playwright or equivalent for critical user flows

Exact cloud hosting provider remains flexible.

---

## 19. Suggested Repository Layout

```text
/
├── AGENTS.md
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DATA_CONTRACT.md
│   └── BUILD_PLAN.md
├── apps/
│   ├── clinic-dashboard/
│   └── home-app/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── domain/
│   │   ├── db/
│   │   ├── ingestion/
│   │   ├── sensors/
│   │   │   ├── radar/
│   │   │   ├── thermal/
│   │   │   └── csi/
│   │   ├── fusion/
│   │   ├── baseline/
│   │   ├── anomaly/
│   │   ├── events/
│   │   ├── ai/
│   │   ├── feedback/
│   │   └── device_health/
│   └── tests/
├── firmware/
│   ├── sensors/
│   ├── edge_processing/
│   └── transport/
├── simulator/
│   ├── scenarios/
│   └── tests/
├── prompts/
└── evals/
```

The logical module boundaries matter more than the exact folder names.

---

## 20. Single-Resident Room and Ambiguity Architecture

V1 supports one assigned resident per monitored room.

Possible states:

- room and resident assignment valid, with single-person sensing suitable for monitoring;
- room or resident assignment missing/conflicting;
- possible caregiver/visitor presence;
- multi-person or otherwise ambiguous sensing;
- room temporarily unsuitable for resident-specific measurements.

The system does not attempt to identify or separate multiple people. When single-resident attribution is not supported by the sensing context, resident-specific measurements and events must be lowered in confidence or marked unavailable.

---

## 21. Time Model

Because exact ESP32 synchronization is not yet known, contracts support multiple timestamps:

- device capture time if available;
- device monotonic/sequence metadata;
- server receive time;
- processed/fused window time.

Fusion must tolerate small clock uncertainties and expose synchronization quality.

A future hardware-specific time-sync strategy can be added without changing domain contracts.

---

## 22. Failure / Degradation Matrix

| Failure | Required behavior |
|---|---|
| LLM unavailable | Keep event; show evidence; interpretation unavailable/retry |
| CSI unavailable | Continue radar + thermal with lower confidence |
| Thermal unavailable | Continue remaining modalities with lower confidence |
| Radar unavailable | Mark vital/motion features unavailable; continue other evidence |
| Room/resident assignment missing | Do not create resident-specific monitoring output until the assignment is repaired |
| Device offline | Operational/device alert + last-seen |
| Temporary internet loss | Device buffers/retries; backend deduplicates |
| Duplicate upload | Idempotent ingest |
| Multi-person ambiguity | Lower confidence or mark resident-specific measurements unavailable; do not guess attribution |
| Low signal quality | Show unavailable/low confidence rather than fake precision |
| DB processing backlog | Ingestion remains durable; expose health metrics |

---

## 23. Observability

Track at minimum:

- ingestion rate/error rate;
- per-device last seen;
- sequence gaps;
- processing latency;
- sensor quality distributions;
- anomaly/event rate;
- false-positive outcomes;
- LLM latency/failure/cost;
- feedback completion;
- baseline update history;
- model/prompt/version IDs attached to events;
- queue/backlog depth if asynchronous workers are introduced.

Every important event must be reproducible from stored evidence/version metadata where practical.

---

## 24. Architecture Rules Codex Must Preserve

1. Never couple core domain logic to vendor-specific raw payloads.
2. Edge processing may reduce/convert each sensor stream, but keep cross-sensor fusion, baselines, anomaly/event decisions, and learning in the cloud unless this document is intentionally changed.
3. Attribute V1 monitoring through one-resident room assignment; never guess resident-specific values during possible multi-person presence.
4. Never make continuous raw upload the default production path.
5. Never call the LLM for every sample/telemetry packet.
6. Never let the LLM delete/suppress deterministic events.
7. Never invent medical thresholds in production code.
8. Never hide low-quality data behind confident-looking numbers.
9. Keep clinic and home workflows separate.
10. Keep event evidence immutable/auditable.
11. Keep learning versioned and reversible.
12. Keep all contracts backward/version compatible or migrate them deliberately.
