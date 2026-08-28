# Contactless Adaptive Care Platform — Data & API Contract

**Status:** V1 contract for UI-first and simulator-first development
**Version:** 1.7
**Important:** Final vendor-specific radar/CSI raw shapes are intentionally hardware-dependent. Production software stabilizes around a versioned **EdgeTelemetryEnvelope** emitted after lightweight on-device preprocessing. Optional raw/debug capture is separate and bounded.

## Phase 2 Checkpoint D — Clinic Event Queue

`GET /v1/events` is the clinic-wide caregiver work queue. It reuses the exact
`EventResponse` object used by event detail and resident history.

Query parameters:

- repeated `status` values are OR filters for `open`, `acknowledged`,
  `checked`, and `resolved`;
- repeated `priority` values are OR filters for `watch`, `high`, and
  `critical`;
- optional `resident_id` and `room_id` narrow the tenant-owned queue;
- `resident_id`, `room_id`, `limit`, and `cursor` are single-valued; repeating
  one is rejected as ambiguous;
- filter categories combine with AND;
- `limit` defaults to `25` and accepts `1` through `100`;
- `cursor` is opaque, stable, and bound to the tenant and normalized filters.

With no `status`, the endpoint returns active caregiver work: `open`,
`acknowledged`, and `checked`. Resolved history remains available by requesting
`status=resolved`, or by explicitly combining resolved with active statuses.
The internal transient `detected` state is not a valid clinic queue filter.
Unknown or cross-tenant resident/room filters return an empty result rather
than revealing whether the identifier exists elsewhere.

The deterministic queue order is:

1. unresolved before resolved;
2. `critical`, then `high`, then `watch`;
3. overdue before not overdue;
4. newest `last_signal_at`;
5. newest `created_at`;
6. `event_id` ascending as the final tie-breaker.

The response is:

```json
{
  "schema_version": "1.0",
  "items": [],
  "total_items": 0,
  "next_cursor": null
}
```

`total_items` counts all tenant-owned events matching the normalized filters,
not only the current page. `next_cursor` is `null` on the final page. Malformed
cursors or reuse under different filters return the versioned `invalid_input`
error with `field: "cursor"`. Lifecycle actions can move an event between
filtered views, so the clinic client refreshes the active queue after a
successful acknowledge, check, or resolve action.

Trend intelligence is not part of this checkpoint and is not fabricated. The
current clinic client does not require a trend read for the selected connection
path; a future trends contract will expose explicit unavailable states when
that later intelligence phase begins.

## Phase 2 Checkpoint A — Resident Status and Calibration

These Product API paths give the dashboard a stable view of whether monitoring
is usable, what awareness states occurred, and how much resident-specific
calibration is available:

- `GET /v1/residents/{resident_id}/status`
- `GET /v1/residents/{resident_id}/awareness`
- `GET /v1/residents/{resident_id}/calibration`
- `POST /v1/residents/{resident_id}/setup-changes`

Resident-away and possible-multi-person are awareness states. They do not
become warning events. The awareness list is chronological and the current
status is the newest item. Unknown or unavailable data stays explicit. An
assigned resident with no monitoring or calibration history still returns a
status response: unavailable parts are `null`, `data_availability` explains
whether the response is complete or partial, and `unavailable_reasons` says
which histories have not started. This is distinct from a missing or
cross-tenant resident, which returns `404`.

Example status response:

```json
{
  "schema_version": "1.0",
  "resident_id": "resident_demo_a",
  "room_id": "room_214",
  "data_availability": "available",
  "unavailable_reasons": [],
  "device_assignment_state": "assigned",
  "device": {
    "schema_version": "1.0",
    "device_id": "device_room_214",
    "display_label": "Room 214 monitor",
    "assignment": {
      "schema_version": "1.0",
      "location_id": "location_demo",
      "location_label": "Demo clinic",
      "room_id": "room_214",
      "room_label": "Room 214",
      "assigned_at": "2026-08-24T00:00:00Z"
    },
    "health": {
      "schema_version": "1.0",
      "device_id": "device_room_214",
      "data_availability": "available",
      "state": "online",
      "observed_at": "2026-08-24T21:02:11Z",
      "last_seen_at": "2026-08-24T21:02:11Z",
      "sources": [],
      "limitations": [],
      "policy_version": "synthetic_device_health_v1",
      "policy_test_only": true
    }
  },
  "monitoring": {
    "schema_version": "1.0",
    "resident_id": "resident_demo_a",
    "room_id": "room_214",
    "observed_at": "2026-08-24T21:02:11Z",
    "monitoring_state": "active",
    "presence_state": "resident_present",
    "baseline_learning_allowed": true,
    "resident_measurements_allowed": true,
    "reasons": [],
    "quality_policy_version": "synthetic_monitoring_quality_v1",
    "quality_policy_test_only": true
  },
  "calibration": {
    "schema_version": "1.0",
    "resident_id": "resident_demo_a",
    "version": 1,
    "recorded_at": "2026-08-24T21:02:11Z",
    "setup_version": "setup_room_214_v1",
    "status": "established",
    "eligible_windows": 12,
    "excluded_windows": 2,
    "reason": "calibration_complete",
    "prior_setup_versions": [],
    "dimensions": [
      {
        "schema_version": "1.0",
        "dimension": "movement",
        "status": "established",
        "eligible_windows": 12,
        "excluded_windows": 2
      }
    ],
    "setup_changes": []
  }
}
```

Example status before monitoring and calibration histories exist:

```json
{
  "schema_version": "1.0",
  "resident_id": "resident_new",
  "room_id": "room_new",
  "data_availability": "not_yet_available",
  "unavailable_reasons": [
    "monitoring_not_yet_available",
    "calibration_not_yet_available",
    "device_assignment_unavailable"
  ],
  "device_assignment_state": "assignment_unavailable",
  "device": null,
  "monitoring": null,
  "calibration": null
}
```

Resident status composes the current active device assignment and latest
device-health observation with the newest resident monitoring snapshot. A
known non-`online` device makes the current monitoring view `unavailable` and
prevents learning/measurements. Missing health uses
`device_health_not_yet_available`; missing assignment uses
`device_assignment_unavailable`. These current-view rules do not rewrite the
awareness timeline and do not create resident warning events. A later
`online` observation restores the latest otherwise-valid monitoring view.

Example setup-change request:

```json
{
  "schema_version": "1.0",
  "reason": "device_moved",
  "affected_dimensions": ["movement"],
  "changed_at": "2026-08-24T22:00:00Z",
  "expected_calibration_version": 1
}
```

Example awareness response (items are oldest to newest):

```json
{
  "schema_version": "1.0",
  "resident_id": "resident_demo_a",
  "items": [
    {
      "schema_version": "1.0",
      "resident_id": "resident_demo_a",
      "room_id": "room_214",
      "observed_at": "2026-08-24T20:55:00Z",
      "monitoring_state": "active",
      "presence_state": "resident_present",
      "baseline_learning_allowed": true,
      "resident_measurements_allowed": true,
      "reasons": [],
      "quality_policy_version": "synthetic_monitoring_quality_v1",
      "quality_policy_test_only": true
    },
    {
      "schema_version": "1.0",
      "resident_id": "resident_demo_a",
      "room_id": "room_214",
      "observed_at": "2026-08-24T20:56:00Z",
      "monitoring_state": "paused",
      "presence_state": "resident_away",
      "baseline_learning_allowed": false,
      "resident_measurements_allowed": false,
      "reasons": ["resident_away"],
      "quality_policy_version": "synthetic_monitoring_quality_v1",
      "quality_policy_test_only": true
    }
  ]
}
```

Example standalone calibration response:

```json
{
  "schema_version": "1.0",
  "resident_id": "resident_demo_a",
  "version": 1,
  "recorded_at": "2026-08-24T21:00:00Z",
  "setup_version": "setup_room_214_v1",
  "status": "established",
  "eligible_windows": 12,
  "excluded_windows": 2,
  "reason": "calibration_complete",
  "prior_setup_versions": [],
  "dimensions": [
    {
      "schema_version": "1.0",
      "dimension": "movement",
      "status": "established",
      "eligible_windows": 12,
      "excluded_windows": 2
    },
    {
      "schema_version": "1.0",
      "dimension": "respiratory_rate",
      "status": "established",
      "eligible_windows": 12,
      "excluded_windows": 2
    }
  ],
  "setup_changes": []
}
```

Example setup-change response:

```json
{
  "schema_version": "1.0",
  "resident_id": "resident_demo_a",
  "version": 2,
  "recorded_at": "2026-08-24T22:00:00Z",
  "setup_version": "setup_room_214_v2",
  "status": "partial",
  "eligible_windows": 12,
  "excluded_windows": 2,
  "reason": "device_moved",
  "prior_setup_versions": ["setup_room_214_v1"],
  "dimensions": [
    {
      "schema_version": "1.0",
      "dimension": "movement",
      "status": "calibrating",
      "eligible_windows": 0,
      "excluded_windows": 0
    },
    {
      "schema_version": "1.0",
      "dimension": "respiratory_rate",
      "status": "established",
      "eligible_windows": 12,
      "excluded_windows": 2
    }
  ],
  "setup_changes": [
    {
      "schema_version": "1.0",
      "previous_setup_version": "setup_room_214_v1",
      "new_setup_version": "setup_room_214_v2",
      "affected_dimensions": ["movement"],
      "reason": "device_moved",
      "actor_id": "operator_1",
      "changed_at": "2026-08-24T22:00:00Z"
    }
  ]
}
```

The server creates the next setup/calibration version. Only the named
dimensions restart calibration; unaffected dimensions, prior setup history,
and resident memory remain intact. Setup changes require an idempotency key so
retries cannot create duplicate history. All timestamps are UTC. Quality and
calibration policies in the toy-data checkpoint are synthetic and test-only,
not clinical thresholds.

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

Device health is operational product state, not resident health. Phase 2
supports `online`, `offline`, `degraded`, `buffering`, `retrying`, and
`assignment_unavailable`. Health observations and assignments are historical
facts; current state is the newest tenant-owned record. All examples in this
checkpoint are synthetic and test-only.

Example current health response:

```json
{
  "schema_version": "1.0",
  "device_id": "device_room_214",
  "data_availability": "available",
  "state": "degraded",
  "observed_at": "2026-08-25T14:00:00Z",
  "last_seen_at": "2026-08-25T13:59:55Z",
  "sources": [
    {
      "schema_version": "1.0",
      "source": "thermal",
      "state": "degraded",
      "limitations": ["reduced_frame_rate"]
    }
  ],
  "limitations": ["thermal_detail_reduced"],
  "policy_version": "synthetic_device_health_v1",
  "policy_test_only": true
}
```

A known device with no health history returns `200` without inventing a state:

```json
{
  "schema_version": "1.0",
  "device_id": "device_new",
  "data_availability": "not_yet_available",
  "state": null,
  "observed_at": null,
  "last_seen_at": null,
  "sources": [],
  "limitations": [],
  "policy_version": null,
  "policy_test_only": null
}
```

Each `GET /v1/devices` item contains `device_id`, `display_label`, the current
nullable `assignment`, and the same `health` object. An assignment contains
`location_id`, `location_label`, `room_id`, `room_label`, and UTC
`assigned_at`. One active room is allowed per device and one active device per
room. Missing assignment is explicit and never guessed from telemetry.

## 18A. Resident Notification Preferences

Preferences store future delivery choices; Phase 2 does not send a real
notification. High and critical events remain visible in the clinic dashboard
even when their separate delivery toggle is off.

Current saved preferences:

```json
{
  "schema_version": "1.0",
  "resident_id": "resident_demo_a",
  "data_availability": "available",
  "version": 2,
  "event_delivery": {
    "watch": false,
    "high": true,
    "critical": true
  },
  "awareness_delivery": {
    "away": true,
    "return": true,
    "limited": false,
    "unavailable": true
  },
  "high_critical_dashboard_visibility": "always_visible",
  "changed_by": "operator_1",
  "changed_at": "2026-08-25T15:00:00Z"
}
```

A known resident without saved preferences returns `200` honestly:

```json
{
  "schema_version": "1.0",
  "resident_id": "resident_new",
  "data_availability": "not_yet_available",
  "version": null,
  "event_delivery": null,
  "awareness_delivery": null,
  "high_critical_dashboard_visibility": "always_visible",
  "changed_by": null,
  "changed_at": null
}
```

The update body is:

```json
{
  "schema_version": "1.0",
  "expected_version": 1,
  "event_delivery": {
    "watch": false,
    "high": true,
    "critical": true
  },
  "awareness_delivery": {
    "away": true,
    "return": true,
    "limited": false,
    "unavailable": true
  },
  "changed_at": "2026-08-25T15:00:00Z"
}
```

The first update uses `expected_version: 0`. Every later update names the
current version. A stale version returns a conflict rather than overwriting a
newer choice. Each successful update appends one preference version, one audit
record, and one idempotency result in the same transaction.

## 18B. Resident-Memory Administration

`GET /v1/residents/{resident_id}/memory` returns the complete current memory
snapshot. Each entry includes provenance and an optional correction link:

- `source_kind` is `feedback` or `operator`;
- `source_feedback_id` is present only for feedback-created memory;
- `supersedes_entry_id` links a corrected replacement to the retired entry;
- retirement metadata preserves who retired an entry, when, and why.

Direct add body:

```json
{
  "schema_version": "1.0",
  "expected_version": 2,
  "description": "Assisted standing is common before breakfast.",
  "changed_at": "2026-08-25T15:10:00Z"
}
```

Correction body:

```json
{
  "schema_version": "1.0",
  "expected_version": 3,
  "description": "Assisted standing is common after breakfast.",
  "reason": "The routine time was entered incorrectly.",
  "changed_at": "2026-08-25T15:20:00Z"
}
```

Retirement body:

```json
{
  "schema_version": "1.0",
  "expected_version": 4,
  "reason": "This routine is no longer current.",
  "changed_at": "2026-08-25T15:30:00Z"
}
```

Add creates one active operator-sourced entry. Correct retires the selected
active entry and creates one linked active replacement in the same new memory
version. Retire creates a new version with the selected entry retired. Old
snapshots and entries are never deleted. These commands cannot change event
history, numerical calibration, warning thresholds, or global behavior.

Memory versions form one resident-wide ordered timeline. A command may target
any active entry, including an older entry, but its `changed_at` cannot precede
the latest existing memory change. This allows later correction of older
context while preventing a new memory version from being inserted backward in
the audit history.

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

### Preferences and resident memory

- `GET /v1/residents/{resident_id}/notification-preferences`
- `PUT /v1/residents/{resident_id}/notification-preferences`
- `GET /v1/residents/{resident_id}/memory`
- `POST /v1/residents/{resident_id}/memory/entries`
- `POST /v1/residents/{resident_id}/memory/entries/{entry_id}/correct`
- `POST /v1/residents/{resident_id}/memory/entries/{entry_id}/retire`

Exact REST paths may change, but domain objects and semantics should remain stable.

### Phase 2 first durable slice

This subsection freezes the Product API surface implemented by the first
durable Phase 2 backend slice. All values shown are synthetic. Public
timestamps are UTC-only and use the `Z` form in JSON.

Implemented read paths:

- `GET /health`
- `GET /v1/residents`
- `GET /v1/residents/{resident_id}`
- `GET /v1/residents/{resident_id}/events`
- `GET /v1/residents/{resident_id}/memory`
- `GET /v1/residents/{resident_id}/status`
- `GET /v1/residents/{resident_id}/awareness`
- `GET /v1/residents/{resident_id}/calibration`
- `GET /v1/residents/{resident_id}/notification-preferences`
- `GET /v1/events`
- `GET /v1/events/{event_id}`
- `GET /v1/devices`
- `GET /v1/devices/{device_id}/health`

Implemented caregiver action paths:

- `POST /v1/events/{event_id}/acknowledge`
- `POST /v1/events/{event_id}/checked`
- `POST /v1/events/{event_id}/resolve`
- `POST /v1/events/{event_id}/feedback`
- `POST /v1/residents/{resident_id}/setup-changes`
- `PUT /v1/residents/{resident_id}/notification-preferences`
- `POST /v1/residents/{resident_id}/memory/entries`
- `POST /v1/residents/{resident_id}/memory/entries/{entry_id}/correct`
- `POST /v1/residents/{resident_id}/memory/entries/{entry_id}/retire`

Every `/v1` request requires the development-only `X-Tenant-Id` and
`X-Actor-Id` headers. Every caregiver action also requires
`Idempotency-Key`. Every caregiver action body requires
`"schema_version": "1.0"`, and its timestamp must be explicitly UTC (`Z` or
`+00:00`), not merely convertible to UTC. Repeating the same key with the same
method, path, actor, tenant, and logical request returns the originally stored
response without repeating event, feedback, memory, or audit effects. Reusing
the key for a different logical request returns `idempotency_conflict`. Cross-tenant reads
and actions return the same not-found response as a missing identifier.
Production authentication is not implemented by these headers.

`ResidentSummary` has exactly these fields:

```json
{
  "schema_version": "1.0",
  "resident_id": "resident_demo_a",
  "display_label": "Resident A",
  "room_id": "room_214",
  "room_label": "Room 214",
  "assignment_status": "active"
}
```

`EventResponse` has exactly these fields, including the shown nested action
and priority-history fields:

```json
{
  "schema_version": "1.0",
  "event_id": "evt_phase2_demo",
  "episode_id": "episode_phase2_demo",
  "resident_id": "resident_demo_a",
  "room_id": "room_214",
  "objective_family": "unusual_movement",
  "headline": "Unusual movement detected",
  "priority": "high",
  "status": "resolved",
  "created_at": "2026-08-24T21:02:11Z",
  "last_signal_at": "2026-08-24T21:02:11Z",
  "signal_count": 1,
  "related_event_ids": [],
  "recurrence_count": 1,
  "overdue_at": null,
  "overdue": false,
  "resolution_outcome": "false_positive",
  "action_history": [
    {
      "schema_version": "1.0",
      "action": "opened",
      "actor_id": "system:monitoring_event",
      "occurred_at": "2026-08-24T21:02:11Z",
      "previous_status": "detected",
      "status": "open",
      "resolution_outcome": null
    },
    {
      "schema_version": "1.0",
      "action": "acknowledged",
      "actor_id": "operator_1",
      "occurred_at": "2026-08-24T21:03:00Z",
      "previous_status": "open",
      "status": "acknowledged",
      "resolution_outcome": null
    },
    {
      "schema_version": "1.0",
      "action": "checked",
      "actor_id": "operator_1",
      "occurred_at": "2026-08-24T21:04:00Z",
      "previous_status": "acknowledged",
      "status": "checked",
      "resolution_outcome": null
    },
    {
      "schema_version": "1.0",
      "action": "resolved",
      "actor_id": "operator_1",
      "occurred_at": "2026-08-24T21:05:00Z",
      "previous_status": "checked",
      "status": "resolved",
      "resolution_outcome": "false_positive"
    }
  ],
  "priority_history": [
    {
      "schema_version": "1.0",
      "previous_priority": null,
      "priority": "high",
      "actor_id": "system:monitoring_event",
      "changed_at": "2026-08-24T21:02:11Z"
    }
  ],
  "resident_memory_version": null,
  "resident_memory_entry_ids": [],
  "version": 4
}
```

`LearningDecisionResponse` has exactly these fields, including the shown
nested feedback, memory, and memory-entry fields:

```json
{
  "schema_version": "1.0",
  "feedback": {
    "schema_version": "1.0",
    "feedback_id": "fb_synthetic_example",
    "event_id": "evt_phase2_demo",
    "resident_id": "resident_demo_a",
    "actor_id": "operator_1",
    "outcome": "false_positive",
    "actual_event_label": "assisted_movement",
    "routine": true,
    "created_at": "2026-08-24T21:06:00Z"
  },
  "memory": {
    "schema_version": "1.0",
    "resident_id": "resident_demo_a",
    "version": 1,
    "entries": [
      {
        "schema_version": "1.0",
        "entry_id": "memory_synthetic_example",
        "description": "assisted_movement",
        "source_kind": "feedback",
        "source_feedback_id": "fb_synthetic_example",
        "supersedes_entry_id": null,
        "status": "active",
        "created_by": "operator_1",
        "created_at": "2026-08-24T21:06:00Z",
        "retired_by": null,
        "retired_at": null,
        "retirement_reason": null
      }
    ]
  },
  "memory_updated": true,
  "baseline_window_eligible": true,
  "global_label_recorded": true
}
```

All Product API failures use this strict error envelope. The outer envelope
is versioned with `schema_version: "1.0"`; the nested detail is strict and
intentionally unversioned:

```json
{
  "schema_version": "1.0",
  "error": {
    "code": "invalid_transition",
    "message": "The requested transition is not allowed",
    "field": null
  }
}
```

The Product API does not yet return event evidence, resident trends, AI
interpretation, production authentication, notification delivery, or home
real-data views. Those capabilities remain deferred inside Phase 2 or to their
later roadmap phases; existing telemetry, anomaly, AI, and hardware contracts
remain the future implementation boundary.

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

### V1.5 device-health composition

V1.5 adds durable locations, device-to-room assignment history, append-only
operational health states, and explicit resident-status composition. Device
health remains separate from resident health, and missing/unhealthy device
conditions never produce fake resident measurements.

### V1.6 resident controls and memory provenance

V1.6 adds append-only resident notification/awareness preference versions and
authorized resident-memory add, correction, and retirement actions. Preference
delivery choices never hide high or critical clinic events. Memory entries now
carry explicit feedback/operator provenance and correction links; history is
never deleted and memory remains separate from calibration and safety policy.

### V1.7 clinic event queue and API handoff

V1.7 adds the tenant-scoped clinic event queue with active-work defaults,
combined status/priority/resident/room filters, caregiver-attention ordering,
tenant-and-filter-bound keyset cursors, strict single-value parameters, and
resolved-history access. It also publishes one generated OpenAPI artifact and
the exact frontend composition map. No trend, evidence, AI, notification, or
clinical intelligence is fabricated by this handoff.

When changing any domain object:

1. update this document first or in the same change;
2. add/migrate schema version;
3. preserve backward compatibility where reasonable;
4. add migration/adapters;
5. update simulator fixtures;
6. update API/backend/frontend tests;
7. update evals;
8. note breaking changes explicitly.
