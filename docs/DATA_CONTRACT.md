# Contactless Adaptive Care Platform — Data & API Contract

**Status:** V1 contract for UI-first and simulator-first development
**Version:** 1.4
**Important:** Final vendor-specific radar/CSI raw shapes are intentionally hardware-dependent. Production software stabilizes around a versioned **EdgeTelemetryEnvelope** emitted after lightweight on-device preprocessing. Optional raw/debug capture is separate and bounded.

---

## 1. Contract Principles

1. Every public/domain object has a `schema_version`.
2. Hardware vendor/raw formats are converted at the edge and must not leak into product/domain code.
3. Simulator and real ESP32 use the same edge-telemetry ingestion envelope.
4. Firmware/edge adapters convert vendor/raw sensor data into compact per-modality telemetry before upload.
5. Cloud normalizers validate edge telemetry and convert it into normalized observations for fusion.
6. V1 supports one assigned resident per monitored room. Device-to-room and room-to-resident assignments are server-side and authorized.
7. Units are explicit.
8. Quality/confidence is explicit.
9. Unknown/unavailable is valid; never invent a value.
10. Events preserve the evidence/version state that created them.
11. IDs are opaque strings/UUIDs, not names or medical information.
12. Contracts support future optional medical accessories without changing core objects.

---

## 2. Core Identifiers

Recommended identifiers:

- `tenant_id` — facility, organization, or home account
- `location_id` — facility/site/home
- `room_id` — physical monitoring area
- `resident_id` — pseudonymous monitored-person ID
- `device_id` — room hardware node
- `sensor_source_id` — logical sensor on device
- `event_id`
- `feedback_id`
- `baseline_id`
- `interpretation_id`

Names and other identifying information live in product/profile tables, not in edge telemetry.

---

## 3. Timestamp Rules

Every edge telemetry packet should support:

- `device_time` — nullable ISO timestamp if device has synchronized wall time;
- `device_monotonic_ms` — nullable monotonic time;
- `sequence` — required increasing integer per device/source stream;
- `received_at` — assigned by backend;
- `processed_at` — assigned during cloud processing.

The system must not assume device clocks are perfect.

---


## Primary Production Ingestion: Edge Telemetry

The default production path uploads **compact per-sensor telemetry**, not continuous raw arrays. Each packet is versioned and source-specific.

Edge preprocessing may include:

- vendor/raw decoding;
- obvious-invalid filtering;
- lightweight feature/measurement extraction;
- downsampling/aggregation/compression;
- per-sensor quality indicators;
- timestamps/sequence numbers;
- batching and retry metadata.

The cloud still performs cross-sensor fusion, room/resident assignment, personal baselines, anomaly/event logic, and all LLM/feedback learning.

### Optional diagnostic raw capture

Raw radar/thermal/CSI data may be uploaded only when explicitly requested for hardware development, research, debugging, calibration, or event-window replay. It uses a separate bounded diagnostic path and is not required for normal product operation.


## 4. Edge Telemetry Ingestion Envelope

Endpoint concept:

`POST /v1/ingest/telemetry`

```json
{
  "schema_version": "1.0",
  "device_id": "dev_room_214",
  "tenant_id": "tenant_demo",
  "room_id": "room_214",
  "source": "radar",
  "sensor_model": "prototype_60ghz_radar",
  "sequence": 184201,
  "device_time": null,
  "device_monotonic_ms": 9184412,
  "payload_format": "radar_edge_features_v1",
  "payload": {
    "heart_rate_bpm": 72.0,
    "respiration_rpm": 15.0,
    "distance_m": 1.15,
    "movement_score": 0.18,
    "signal_quality": 0.91
  },
  "transport": {
    "batch_id": "batch_001",
    "retry_count": 0
  }
}
```

### `source` enum

Initial:

- `radar`
- `thermal`
- `wifi_csi`
- `accessory`

### `payload_format`

Free versioned identifier owned by the firmware/edge adapter, examples:

- `simulated_radar_edge_v1`
- `radar_edge_features_v1`
- `mlx90640_edge_features_v1`
- `esp32_csi_edge_v1`

Only the relevant source normalizer should understand the source-specific payload internals. Product/domain/UI code must consume normalized objects instead.

---

## 5. Thermal Edge Telemetry Example

The edge should normally send compact thermal features rather than the full 32×24 frame continuously. Exact features may evolve as hardware testing shows what is useful.

```json
{
  "schema_version": "1.0",
  "device_id": "dev_room_214",
  "tenant_id": "tenant_demo",
  "room_id": "room_214",
  "source": "thermal",
  "sensor_model": "MLX90640",
  "sequence": 9982,
  "device_time": null,
  "device_monotonic_ms": 9184490,
  "payload_format": "mlx90640_edge_features_v1",
  "payload": {
    "person_detected": true,
    "centroid_x": 0.53,
    "centroid_y": 0.41,
    "temperature_trend_c": 0.2,
    "max_observed_temp_c": 35.7,
    "position_features": {
      "near_floor_score": 0.08
    },
    "signal_quality": 0.88
  }
}
```

Full/compressed thermal frames may be captured through the optional diagnostic path when needed for research, debugging, or algorithm development.

---

## 6. Wi-Fi CSI Edge Telemetry Example

The edge should reduce the high-volume CSI stream into compact features/measurements suitable for cloud fusion. The exact feature extraction depends on the final ESP32/RuView implementation and is intentionally replaceable.

```json
{
  "schema_version": "1.0",
  "device_id": "dev_room_214",
  "tenant_id": "tenant_demo",
  "room_id": "room_214",
  "source": "wifi_csi",
  "sensor_model": "ESP32-S3",
  "sequence": 23001,
  "device_time": null,
  "device_monotonic_ms": 9184511,
  "payload_format": "esp32_csi_edge_v1",
  "payload": {
    "presence_score": 0.96,
    "movement_score": 0.21,
    "rf_disturbance_score": 0.17,
    "respiration_feature": 0.62,
    "signal_quality": 0.82
  }
}
```

Raw CSI may be captured separately for development/evaluation, but is not the default cloud-ingestion payload.

---

## 7. Room and Resident Monitoring Assignment

V1 supports one assigned resident per monitored room. This is configuration data, not sensor telemetry. A monitoring device must resolve to one room, and that room must resolve to one active resident assignment before resident-specific processing begins.

```json
{
  "schema_version": "1.0",
  "assignment_id": "assign_room_214_a",
  "tenant_id": "tenant_demo",
  "device_id": "dev_room_214",
  "room_id": "room_214",
  "resident_id": "resident_demo_a",
  "status": "active",
  "effective_from": "2026-08-24T00:00:00Z",
  "effective_to": null
}
```

Only one active resident assignment is allowed per monitored room in V1. If the assignment is missing or conflicting, the backend must not create resident-specific observations or events. If sensing suggests multiple people may be present, resident-specific output is marked ambiguous, low-confidence, or unavailable; the system does not guess who produced a signal.

### Optional diagnostic raw capture

Endpoint concept:

`POST /v1/ingest/diagnostic-raw`

This path is disabled or tightly controlled in normal production. It may accept bounded radar/thermal/CSI windows for hardware development, calibration, research, debugging, or event replay. Diagnostic payloads should carry device/source/time/version metadata plus a binary/blob reference or bounded payload; they should not share the normal telemetry table.

---

## 8. Device Heartbeat

Endpoint concept:

`POST /v1/ingest/heartbeat`

```json
{
  "schema_version": "1.0",
  "device_id": "dev_room_214",
  "sequence": 881,
  "device_monotonic_ms": 9185000,
  "firmware_version": "sim-0.1.0",
  "buffered_packets": 0,
  "sources_seen": ["radar", "thermal", "wifi_csi"],
  "transport_status": "ok"
}
```

The ESP32 may calculate per-sensor transport/signal quality or validity indicators when available, but cloud fusion owns final resident/event confidence.

---

## 9. Normalized Observation

Created by one cloud normalizer from compact edge telemetry.

```json
{
  "schema_version": "1.0",
  "observation_id": "obs_123",
  "tenant_id": "tenant_demo",
  "room_id": "room_214",
  "resident_id": "resident_demo_a",
  "device_id": "dev_room_214",
  "source": "radar",
  "window_start": "2026-08-24T21:00:00Z",
  "window_end": "2026-08-24T21:00:05Z",
  "features": [
    {
      "name": "respiratory_rate",
      "value": 15.2,
      "unit": "breaths_per_min",
      "quality": 0.92
    },
    {
      "name": "movement_energy",
      "value": 0.18,
      "unit": "normalized",
      "quality": 0.96
    }
  ],
  "source_quality": 0.94,
  "processor_version": "radar_processor_sim_v1"
}
```

### Quality rules

- normalized `0.0–1.0` where `1.0` means highest confidence/quality;
- feature may omit `value` and include `status: "unavailable"` instead;
- processor must include a reason for unavailable/low-quality values when known.

---

## 10. Fused Frame

Represents the system's cross-sensor understanding of a time window.

```json
{
  "schema_version": "1.0",
  "fused_frame_id": "fused_001",
  "tenant_id": "tenant_demo",
  "room_id": "room_214",
  "resident_id": "resident_demo_a",
  "window_start": "2026-08-24T21:00:00Z",
  "window_end": "2026-08-24T21:00:05Z",
  "features": {
    "heart_rate": {"value": 74, "unit": "bpm", "quality": 0.86},
    "respiratory_rate": {"value": 15.2, "unit": "breaths_per_min", "quality": 0.92},
    "movement": {"value": 0.18, "unit": "normalized", "quality": 0.95},
    "thermal_trend": {"value": 0.1, "unit": "celsius_delta", "quality": 0.82},
    "position_state": {"value": "lying_like", "quality": 0.79}
  },
  "modalities_present": ["radar", "thermal", "wifi_csi"],
  "sensor_agreement": 0.88,
  "presence_state": "resident_present",
  "monitoring_state": "active",
  "multi_person_state": "unlikely",
  "limitations": [],
  "overall_quality": 0.87,
  "fusion_version": "fusion_v1"
}
```

Values in examples are synthetic and not clinical thresholds.

Presence states:

- `unknown`
- `resident_present`
- `resident_away`
- `possible_multi_person`

Monitoring states:

- `active` — resident-specific monitoring may run subject to quality;
- `limited` — some outputs are low-confidence or unavailable;
- `paused` — awareness/history continues but resident-specific learning is stopped;
- `unavailable` — assignment, device, or data conditions prevent resident-specific monitoring.

---

## 11. Baseline Snapshot

```json
{
  "schema_version": "1.0",
  "baseline_id": "baseline_a_0042",
  "resident_id": "resident_demo_a",
  "status": "partial",
  "monitoring_setup_version": "setup_room_214_v1",
  "calibration_reason": "initial_setup",
  "valid_from": "2026-08-24T20:00:00Z",
  "dimensions": {
    "heart_rate": {
      "typical": 70,
      "spread": 8,
      "unit": "bpm"
    },
    "respiratory_rate": {
      "typical": 15,
      "spread": 2,
      "unit": "breaths_per_min"
    },
    "movement_night": {
      "typical": 0.12,
      "spread": 0.05,
      "unit": "normalized"
    }
  },
  "data_quality": 0.88,
  "baseline_engine_version": "baseline_v1"
}
```

Exact math is replaceable. Baseline status enum:

- `new`
- `calibrating`
- `partial`
- `established`

---

## 12. Anomaly Candidate

Internal object; not necessarily user-facing.

```json
{
  "schema_version": "1.0",
  "anomaly_id": "anom_001",
  "resident_id": "resident_demo_a",
  "room_id": "room_214",
  "window_start": "2026-08-24T21:02:00Z",
  "window_end": "2026-08-24T21:02:10Z",
  "anomaly_score": 0.89,
  "confidence": 0.84,
  "facts": [
    {
      "feature": "movement",
      "description": "movement increased sharply relative to personal baseline",
      "magnitude": 3.8,
      "unit": "x_baseline"
    },
    {
      "feature": "position_state",
      "description": "position changed from lying-like toward floor-like"
    }
  ],
  "quality": {
    "overall": 0.86,
    "multi_person_state": "unlikely",
    "missing_modalities": []
  },
  "baseline_id": "baseline_a_0042",
  "engine_version": "anomaly_v1"
}
```

No semantic diagnosis is required here.

---

## 13. Monitoring Event

Durable product object.

```json
{
  "schema_version": "1.0",
  "event_id": "evt_001",
  "tenant_id": "tenant_demo",
  "resident_id": "resident_demo_a",
  "room_id": "room_214",
  "created_at": "2026-08-24T21:02:11Z",
  "episode_id": "episode_001",
  "status": "open",
  "priority": "high",
  "event_kind": "resident_anomaly",
  "confidence": 0.84,
  "headline": "Unusual multi-sensor event",
  "objective_family": "unusual_movement",
  "evidence": {
    "anomaly_ids": ["anom_001"],
    "baseline_id": "baseline_a_0042",
    "fused_frame_ids": ["fused_101", "fused_102"],
    "raw_window_refs": []
  },
  "warning_policy": {
    "matched": false,
    "policy_version": "warning_demo_v1"
  },
  "interpretation_status": "pending",
  "related_event_ids": [],
  "recurrence_count": 1,
  "overdue_at": null
}
```

### Event status enum

- `detected`
- `open`
- `acknowledged`
- `checked`
- `resolved`

Episode rules:

- related evidence inside a configurable quiet-time gap updates the same open episode;
- recurrence outside that gap creates a new event with links in `related_event_ids`;
- resolved events do not reopen;
- high/critical events may populate `overdue_at` and never silently expire;
- watch items may auto-close into history when policy allows.

### Resolution outcome enum

- `confirmed`
- `false_positive`
- `uncertain`

### Event kind

Initial open taxonomy:

- `resident_anomaly`
- `deterministic_warning`
- `device_issue`

Optional `objective_family` values may help the UI and evaluation harness without claiming a real-world cause, for example:

- `unusual_movement`
- `rapid_downward_movement`
- `prolonged_inactivity`
- `repetitive_movement`
- `heart_rate_deviation`
- `respiratory_deviation`
- `combined_physiological_deviation`
- `position_transition`
- `multi_person_ambiguity`
- `unknown_anomaly`
- `device_quality_issue`

These are objective/broad signal families, not diagnoses. Semantic labels such as `fall_like`, `assisted_transfer`, `collapse_like`, `respiratory_distress_like`, etc. belong primarily in interpretations/outcomes and must always allow `unknown`.

---

## 14. LLM Interpretation Input

The LLM input is structured context, not raw sensor arrays.

```json
{
  "schema_version": "1.0",
  "event": {
    "event_id": "evt_001",
    "priority": "high",
    "confidence": 0.84,
    "facts": [
      "movement increased 3.8x personal baseline",
      "position changed toward floor-like",
      "movement remained unusually low afterward"
    ],
    "sensor_quality": "high"
  },
  "resident_context": {
    "baseline_status": "established",
    "relevant_routines": [],
    "relevant_notes": []
  },
  "similar_events": [],
  "relevant_feedback": [],
  "interpreter_prompt_version": "event_interpreter_v1"
}
```

No full raw streams or unnecessary identifying details.

---

## 15. LLM Interpretation Output

Strict schema:

```json
{
  "schema_version": "1.0",
  "interpretation_id": "int_001",
  "event_id": "evt_001",
  "status": "complete",
  "likely_explanation": {
    "label": "fall_like_or_collapse_like_movement",
    "confidence": 0.72
  },
  "alternatives": [
    {"label": "assisted_movement", "confidence": 0.31}
  ],
  "uncertainty": "The system cannot confirm the cause from sensor evidence alone.",
  "plain_english_summary": "A sudden large movement was followed by a floor-like position change and unusually little movement afterward.",
  "evidence_refs": ["movement_deviation", "position_change", "post_event_inactivity"],
  "model_id": "provider_model_tbd",
  "prompt_version": "event_interpreter_v1"
}
```

Confidence values are interpretation confidence, not clinical probabilities.

The LLM must be allowed to return:

```json
{
  "likely_explanation": {"label": "unknown", "confidence": 0.0}
}
```

---

## 16. Feedback Record

```json
{
  "schema_version": "1.0",
  "feedback_id": "fb_001",
  "event_id": "evt_001",
  "resident_id": "resident_demo_a",
  "actor_type": "caregiver",
  "outcome": "false_positive",
  "actual_event_label": "assisted_movement",
  "routine": true,
  "actor_confidence": "high",
  "supersedes_feedback_id": null,
  "answers": [
    {
      "question": "What actually happened?",
      "answer": "I helped them stand up."
    },
    {
      "question": "Is this part of their normal routine?",
      "answer": "Yes"
    }
  ],
  "created_at": "2026-08-24T21:06:00Z",
  "feedback_agent_version": "feedback_v1"
}
```

### Actor types

- `caregiver`
- `family`
- `researcher`
- `system_test`

---

## 17. Resident Memory Snapshot

Semantic context used by the LLM, separate from the numerical baseline.

```json
{
  "schema_version": "1.0",
  "resident_id": "resident_demo_a",
  "memory_version": 12,
  "summary": "Resident often has assisted movement in the morning.",
  "routines": [
    {
      "description": "Assisted standing/movement commonly occurs around 8 AM",
      "confidence": 0.86,
      "status": "active",
      "source_feedback_ids": ["fb_001"]
    }
  ],
  "updated_at": "2026-08-24T21:07:00Z",
  "updater_version": "memory_v1"
}
```

Memory is versioned and auditable. It is not the same object as the numerical baseline. Authorized operators may add, correct, or retire entries; corrections create a new version rather than deleting history.

---

## 18. Device Health Record

```json
{
  "schema_version": "1.0",
  "device_id": "dev_room_214",
  "observed_at": "2026-08-24T21:10:00Z",
  "overall_status": "degraded",
  "sources": {
    "radar": "ok",
    "thermal": "ok",
    "wifi_csi": "missing"
  },
  "last_seen": "2026-08-24T21:09:59Z",
  "notes": ["CSI stream missing for 60 seconds"]
}
```

---

## 19. Product API Concepts

### Residents / status

- `GET /v1/residents`
- `GET /v1/residents/{resident_id}`
- `GET /v1/residents/{resident_id}/status`
- `GET /v1/residents/{resident_id}/trends`

### Events

- `GET /v1/events`
- `GET /v1/events/{event_id}`
- `POST /v1/events/{event_id}/acknowledge`
- `POST /v1/events/{event_id}/checked`
- `POST /v1/events/{event_id}/resolve`

### Feedback

- `POST /v1/events/{event_id}/feedback`
- `POST /v1/feedback/{feedback_id}/answer`

### Device health

- `GET /v1/devices`
- `GET /v1/devices/{device_id}/health`

Exact REST paths may change, but domain objects and semantics should remain stable.

---

## 20. Database Entities

Minimum conceptual tables/collections:

- `tenants`
- `locations`
- `rooms`
- `residents`
- `devices`
- `device_assignments`
- `room_resident_assignments`
- `accessories` (optional/future)
- `edge_telemetry`
- `diagnostic_raw_chunks` (optional/bounded)
- `normalized_observations`
- `fused_frames`
- `baseline_snapshots`
- `anomaly_candidates`
- `monitoring_events`
- `event_evidence`
- `llm_interpretations`
- `feedback_records`
- `resident_memory_snapshots`
- `device_health_records`
- `system_versions`
- `audit_log`

Do not denormalize resident names/PHI into sensor tables.

---

## 21. Idempotency and Replay

### Ingestion

An edge telemetry packet is uniquely identified by:

`device_id + source + sequence + schema_version`

Duplicate retries must not duplicate stored data or downstream events.

### Processing

Processing should record edge-preprocessor/fusion/anomaly versions so stored telemetry and any diagnostic raw windows can be replayed through newer algorithms.

### LLM

Interpretation calls should have an idempotency key based on:

`event_id + prompt_version + relevant_context_version`

---

## 22. Version Metadata Required on Events

For evaluation/reproducibility, an event should eventually be able to point to:

- sensor processor versions;
- fusion version;
- baseline version;
- anomaly engine version;
- warning policy version;
- LLM model/provider identifier;
- prompt version;
- resident memory version;
- simulator scenario/version when synthetic.

---

## 23. Simulator Contract

The simulator should emit synthetic **edge telemetry** using the same contract as the real ESP32. Separate diagnostic fixtures may emulate raw sensor data for firmware/processor testing.

Scenario metadata is development-only and must not leak into production reasoning unless explicitly running in test mode.

Example internal scenario config:

```json
{
  "scenario_id": "fall_like_001",
  "duration_seconds": 60,
  "resident_id": "resident_demo_a",
  "phases": [
    "normal_rest",
    "large_movement",
    "downward_position_change",
    "low_movement_after"
  ]
}
```

The backend should not receive the ground-truth scenario label through the production sensor envelope. Evals compare output to ground truth separately.

---

## 23A. Frontend Mock Contract

UI-first development uses **contract-valid fixtures**, not separate ad-hoc mock schemas.

Frontend code should depend on a typed `MonitoringClient`-style interface with two implementations:

- `MockMonitoringClient` — returns local fixture data and performs local/in-memory state transitions for UI development;
- `ApiMonitoringClient` — calls the real product API.

Both must expose the same domain semantics.

Minimum fixture scenarios should include:

- normal/healthy-looking resident state;
- calibrating resident;
- high-confidence unusual movement event;
- physiological deviation event;
- `unknown_anomaly`;
- low-confidence/multi-person event;
- missing/conflicting room-resident assignment;
- device/sensor issue;
- LLM interpretation pending;
- LLM interpretation unavailable;
- acknowledged/checked/resolved event states;
- confirmed, false-positive, and uncertain feedback outcomes.

Mock-only fields must never leak into production API types. Ground-truth labels used by tests/evals remain outside product payloads.

---

## 24. Contract Changes

### V1.3 breaking scope decision

V1.3 removes the wearable/reader identity source from the production ingestion contract. Resident attribution now comes from an authorized one-resident-per-room assignment. Simulators, backend models, frontend fixtures, and future firmware must use only radar, thermal, and Wi-Fi CSI as core sensor sources and must represent suspected multi-person presence as ambiguous or unavailable resident-specific monitoring.

### V1.4 product-logic expansion

V1.4 adds resident presence/monitoring states, setup-versioned calibration, linked event episodes and recurrence, overdue behavior, correctable feedback, and editable/versioned resident memory semantics.

When changing any domain object:

1. update this document first or in the same change;
2. add/migrate schema version;
3. preserve backward compatibility where reasonable;
4. add migration/adapters;
5. update simulator fixtures;
6. update API/backend/frontend tests;
7. update evals;
8. note breaking changes explicitly.
