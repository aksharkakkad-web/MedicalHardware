# Telemetry Intelligence Bridge Design

**Status:** Approved product direction; implementation design for Akshar's backend lane  
**Date:** 2026-09-23  
**Owner:** Akshar — backend and monitoring intelligence  
**Hardware handoff reviewed:** `origin/hardware/device-frame-format` at `ed990bc`

## 1. Outcome

Build the missing backend bridge between compact radar, thermal, and Wi-Fi CSI
telemetry and the existing monitoring-intelligence engine.

When this work is complete, a contract-valid packet shaped like Mahin's current
hardware output can be received, authenticated, stored once, assigned to the
correct room and resident, normalized, fused, replayed, and passed into the
existing baseline/anomaly/AI/event path. Improvements to sensor quality remain
isolated to firmware and source-specific normalizers.

This is backend software completion at the hardware boundary. It does not claim
clinical accuracy, finish Rishit's real frontend client, deploy production
infrastructure, or pass the separate live-model quality gate.

## 2. Product Flow

```text
Mahin's sensor/host pipeline
        |
        | compact versioned telemetry batch
        v
Authenticated ingestion API
        |
        +-- verify device -> room -> resident assignment
        +-- reject malformed, oversized, conflicting, or stale input
        +-- store exact payload once; make exact retries safe
        v
Source normalizers
        |
        +-- radar -> hardware-neutral observations
        +-- thermal -> hardware-neutral observations
        +-- Wi-Fi CSI -> hardware-neutral observations
        v
Assignment-scoped fusion frame
        |
        v
Existing baseline -> anomaly -> AI -> event engine
        |
        v
Existing resident/event APIs and future real frontend client
```

## 3. Compatibility With Mahin's Branch

The current hardware branch already supplies the required foundation:

- one HTTP request contains a list of current radar, thermal, and CSI envelopes;
- each envelope carries schema, device, tenant, room, source, sensor model,
  sequence, optional device time, optional monotonic time, payload format,
  payload, and transport metadata;
- missing measurements are omitted instead of zero-filled;
- source quality limitations are carried as `quality_reasons`;
- heartbeats use a separate endpoint;
- writes use a bearer token;
- live and synthetic hardware pass through the same encoder/parser path.

The backend will accept Mahin's current payloads. The following additions are
backward-compatible improvements, not prerequisites for initial bench use:

1. `stream_id`: a non-identifying device/host boot identifier. It makes sequence
   restart after reboot unambiguous. Missing `stream_id` uses a legacy stream
   and remains safe, but a sequence reset is rejected until the producer adds it.
2. `device_monotonic_ms`: current null values remain valid, but populated values
   improve ordering and replay.
3. Shared capture identity: the backend treats one telemetry-list POST as one
   capture batch, so Mahin's current per-envelope batch IDs do not block fusion.
4. Host-derived `/v1/assessments` is not a production anomaly input. Hardware
   sends measurements and measurement quality; the cloud owns personal
   baselines, anomaly episodes, severity, and recommended action.

## 4. Ingestion Contract

`POST /v1/ingest/telemetry` accepts either one envelope or a bounded list.
Mahin's normal producer sends a list representing one capture cycle.

Rules:

- all envelopes in a list belong to one tenant, device, and declared room;
- each source appears at most once in one capture cycle;
- supported V1 sources are `radar`, `thermal`, and `wifi_csi`;
- source and payload format must agree;
- measurement fields are finite and unit/range validated;
- unavailable measurement fields are omitted, never explicit nulls;
- the server assigns `received_at` and later `processed_at`;
- the server resolves the active device and room assignments and does not trust
  the resident identity from telemetry;
- a declared tenant or room mismatch is rejected;
- exact request retries return the original result and do not reprocess;
- a reused packet identity with different content is a conflict;
- a lower sequence in the same stream is rejected as stale;
- sequence gaps are accepted and recorded as an operational limitation;
- request size and batch count are bounded.

The response reports accepted, duplicate, rejected, and processing state per
capture batch without exposing secret or identifying data.

## 5. Authentication Boundary

The first implementation uses a configured ingest bearer key suitable for the
bench and local integration. It is compared in constant time and never stored
in the repository or response. The endpoint is unavailable when no key is
configured outside explicit test injection.

This does not claim production device identity. Per-device credential rotation
can replace the authenticator later without changing telemetry, normalization,
fusion, or intelligence interfaces.

## 6. Durable Storage and Retry Safety

Persist:

- one capture-batch record with request fingerprint and processing status;
- one immutable edge-telemetry packet per accepted envelope;
- one immutable normalized observation per processed packet;
- one immutable fused frame per processed capture batch;
- heartbeat identities needed for idempotency and device-health history;
- validation/processing errors in bounded, non-secret form.

Packet identity is:

```text
tenant_id + device_id + source + stream_id + sequence + schema_version
```

For current hardware without `stream_id`, the value is `legacy`. Exact
duplicates are successful no-ops. Conflicting duplicates are rejected.

Ingestion is committed before intelligence processing. If later processing
fails, accepted telemetry remains durable and marked pending/failed so replay
can safely try again.

## 7. Source Normalization

Only one module understands each source-specific payload. Downstream code sees
the existing `NormalizedObservation` contract.

Canonical mappings include:

| Source input | Normalized feature | Unit / purpose |
|---|---|---|
| radar `movement_score` | `movement_energy` | normalized / movement |
| radar `respiration_rpm` | `respiratory_rate` | rpm / respiration |
| radar `heart_rate_bpm` | `heart_rate` | bpm / physiology |
| radar `distance_m` | `distance_from_sensor` | m / posture + presence |
| thermal `person_detected` | `person_detected` | boolean / presence |
| thermal `centroid_y` | `vertical_position` | normalized / posture |
| thermal `position_features.near_floor_score` | `near_floor_score` | normalized / posture |
| thermal temperature fields | stable temperature feature names | C / physiology |
| CSI `movement_score` | `movement_energy` | normalized / movement |
| CSI `presence_score` | `presence_score` | normalized / presence |
| CSI `respiration_feature` | `respiration_periodicity` | normalized / respiration |
| any `signal_quality` | `signal_health` | normalized / source quality |

`FeaturePurpose` gains `physiology`; this is a domain vocabulary addition, not
a clinical claim.

Present measurements remain evidence. `quality_reasons` explain omitted or
limited source information and do not automatically invalidate unrelated
present measurements. Empty payloads become unusable observations instead of
fabricated zeros.

Optional future posture fields such as tracked height, vertical velocity, and
position state can be added to a versioned source normalizer without changing
the rest of the system. Mahin's current payload does not yet prove a robust
fall classification, and the backend will not invent one from insufficient
measurements.

## 8. Assignment and Fusion

The server resolves:

```text
authenticated tenant + device -> active room -> active resident
```

If either active assignment is missing or conflicts, telemetry remains stored
for device diagnostics but no resident-specific observation, baseline update,
anomaly, or event is created.

All valid observations from one telemetry-list POST are aligned into one
existing `AlignedFrame`. Missing sources remain explicit. Agreements and
contradictions are preserved by existing fusion behavior; the system does not
average disagreement away.

## 9. Intelligence Connection

The bridge calls the existing persistent monitoring service through an injected
processor boundary. This keeps API tests deterministic and lets evaluation use
scripted AI while runtime configuration can use a live provider later.

The coordinator supplies:

- the resolved tenant, room, resident, and current setup version;
- the fused frame and stable context key;
- the latest resident memory;
- current resident-away/multi-person flags when known;
- a stable anomaly identity for the active episode;
- the latest established numerical baseline.

If no usable baseline exists, the frame is stored as `calibrating` and cannot
create an ordinary anomaly. A bounded calibration/bootstrap path builds the
initial test-only baseline only from good, assignment-valid, resident-present,
single-person frames. Low-quality, away, ambiguous, setup-change, or anomaly
frames never teach the baseline.

The existing AI/event engine is not called for ordinary raw packets. It is
called only after deterministic anomaly evidence exists.

## 10. Heartbeats and Device Health

`POST /v1/ingest/heartbeat` validates the same bearer key and known device,
deduplicates by stream and sequence, records last-seen, and appends an existing
device-health observation.

Mappings:

- `ok` with no backlog -> online;
- buffered packets -> buffering;
- retrying transport -> retrying;
- missing expected sources -> degraded source states;
- invalid assignment -> assignment unavailable.

These are operational awareness states, not resident warnings.

## 11. Replay and Evaluation

The replay harness emits the exact production envelope and keeps scenario
ground truth outside it. It records machine-readable JSON plus a plain-English
Markdown report.

Minimum scenario families:

- stable normal activity and normal human variation;
- resident away and return;
- bathroom-like short absence;
- guest/multi-person ambiguity when explicitly supported by a fixture;
- unusual movement, prolonged inactivity, physiological deviation;
- fall-like optional posture sequence;
- radar, thermal, and CSI missing/noisy independently;
- duplicate request, conflicting duplicate, stale sequence, sequence gap;
- network retry and host restart with a new `stream_id`;
- assignment missing/mismatch;
- recovery and recurring anomaly;
- low-quality packets that must not teach the baseline.

Report metrics include accepted/rejected/duplicate counts, normalization and
fusion coverage, resident-assignment blocks, replay equality, event recall on
supported synthetic cases, false events on normal cases, and processing
latency. No clinical performance claim is produced.

## 12. Failure Semantics

- Invalid envelope: reject that atomic capture request with specific bounded
  field errors; store no partial resident frame.
- Exact retry: return the original accepted result.
- Assignment unavailable: store telemetry; mark blocked; create no resident
  output.
- Normalizer failure: store telemetry; mark failed; create no invented data.
- Intelligence or AI failure: retain processed evidence and expose pending or
  staff-review state according to existing engine behavior.
- Database failure before ingest commit: return failure so the device retries.
- Failure after ingest commit: return accepted/pending and permit replay.

## 13. Non-Goals

- changing Mahin's signal-processing math;
- accepting continuous raw arrays on the production telemetry endpoint;
- trusting host-derived anomaly/severity verdicts;
- production PKI or per-device credential rotation;
- clinical threshold validation or clinical diagnostic claims;
- Rishit's frontend real-client switch;
- production deployment;
- passing or changing the separate Gemini/GPT live-model quality gate.

## 14. Done Conditions

The backend milestone is complete when:

1. Mahin's checked-in telemetry fixtures parse without modification.
2. Exact retries cannot duplicate packets, frames, anomaly revisions, AI runs,
   or events.
3. Invalid assignment cannot create resident-specific output.
4. Missing/noisy sensors degrade explicitly without fabricated values.
5. A realistic device-shaped replay can create an existing product event using
   a scripted AI provider and that event is readable through the existing API.
6. Stored telemetry and fused frames replay deterministically after restart.
7. Focused tests, full pytest, unittest compatibility, migration tests, and
   backend compilation pass.
8. Documentation states what is proven with synthetic data and what still
   requires live hardware and live-model validation.
