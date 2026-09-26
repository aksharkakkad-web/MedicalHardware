# Phase 6 Telemetry Backend Review

**Review date:** September 24, 2026

**Owner:** Akshar

**Verdict:** The independent backend software path is complete with toy and
device-shaped data. It is ready for Mahin's hardware producer and Rishit's real
frontend client; it is not yet validated as a real-world monitoring system.

## What was built

The backend can now take the same compact radar, thermal, and Wi-Fi CSI shapes
Mahin's host software produces and carry them through the intelligence already
built in Phase 5:

```text
authenticated device telemetry
→ durable packet storage
→ safe retry/conflict handling
→ device → room → resident assignment proof
→ radar / thermal / CSI normalization
→ one aligned multimodal frame
→ personal calibration and anomaly detection
→ staged AI interpretation when warranted
→ caregiver event workflow
→ durable history and replay after restart
```

This closes the missing software gap between “the device emitted useful
features” and “the product has trustworthy evidence to evaluate.”

## Product-level behavior now implemented

### Input and durability

- One authenticated endpoint receives one source envelope or one bounded
  multimodal capture list.
- A separate authenticated endpoint receives device heartbeat information.
- The original accepted packets are committed before intelligence processing.
- New accepted captures return `202 pending` immediately; one durable
  background lane performs downstream work and drains unfinished work after
  restart.
- Exact retries do not repeat downstream work.
- Changed reuse of a packet identity, stale same-stream packets, sequence gaps,
  and new boot/session streams each have explicit behavior.
- Pending or failed work can be replayed after a process restart.

### Identity and safety boundary

- A registered device must actively belong to the claimed room.
- That room must have exactly one active resident assignment.
- Missing or conflicting assignment stores the evidence but blocks
  resident-specific intelligence.
- RFID is not used, and the backend never trusts a resident ID supplied by a
  sensor producer.

### Evidence conversion

- Radar, thermal, and Wi-Fi CSI each have a source-specific validator and
  normalizer.
- Missing fields remain missing; they are not converted to zero or guessed.
- Source quality limitations remain attached to the evidence.
- Source-limited measurements cannot independently activate an ordinary
  anomaly, and broad engineering/sensor bounds reject impossible values before
  they reach a baseline.
- All valid sources from one request become one aligned frame for the existing
  intelligence engine.

### Intelligence connection

- A new resident with no numerical baseline is reported as `calibrating`.
- Established eligible baselines receive the fused frame and can create anomaly
  episodes, evidence revisions, AI analysis, disposition, and caregiver events.
- Invalid assignment, away/visitor conditions, and bad evidence cannot silently
  teach the personal baseline.
- Historical replay restores incomplete anomaly/event state without pretending
  an old packet is a new live observation.
- Ordinary anomalies remain `analysis_pending` and create no caregiver event
  when no trusted AI provider is configured. The explicit urgent safety path
  remains separate.
- Host-generated `/v1/assessments` are not trusted as product anomalies.

## What the mass test proved

The canonical device-shaped campaign has 48 scenario cases covering ordinary
activity, away periods, source degradation, missing fields, network retries,
identity conflicts, assignment failures, anomaly patterns, recurrence, and
restart/replay behavior.

| Measure | Result |
|---|---:|
| Scenario cases | 48 / 48 passed |
| Accepted packets | 385 |
| Exact retries safely ignored | 3 |
| Expected identity conflicts detected | 2 / 2 |
| Expected assignment blocks detected | 2 / 2 |
| Feature-mapping failures | 0 |
| Supported synthetic anomaly recall | 100% |
| False caregiver events in normal/away cases | 0 |
| Caregiver events without trusted live AI output | 0 |
| Replay-idempotency failures | 0 |

Two saved evaluation runs produced the same functional results. The first run
had a median isolated-case runtime of 202.245 ms and p95 of 370.206 ms on the
development machine. Those timings are a development reference, not a service
level promise.

The mass replay intentionally leaves the live model unconfigured and proves
pending-safe behavior. A separate focused integration test supplies a valid
staged analysis and proves that trusted AI output can create one idempotent
high-priority caregiver event.

Detailed artifacts and the rerun command are in
`docs/TELEMETRY_PIPELINE_TEST_REPORT.md`.

## What this does not prove

The software fixtures prove logic, contracts, failure handling, and replay.
They do not prove:

- that a real sensor measures heart rate, respiration, posture, presence, or
  movement accurately in an occupied room;
- field false-alert or missed-event rates;
- production threshold or priority calibration;
- clinical meaning, diagnosis, or safety;
- long-duration reliability, fleet scale, retention, backups, or deployment;
- production authentication, authorization, privacy, and compliance;
- live Gemini/Terra/Sol quality on representative hardware evidence; or
- the complete browser journey against the real backend.

## Current backend stage

There is no remaining hidden independent “build the telemetry foundation”
phase. Backend work now becomes integration and evidence-driven validation:

1. register Mahin's bench tenant/device/room assignment;
2. run his fake producer through the real endpoint;
3. run each real sensor and compare it with safe reference observations;
4. collect ordinary variation, visitors, away periods, degradation, and labeled
   anomaly-like actions;
5. tune only from those captured results;
6. run the staged live-model release gate on representative evidence; and
7. connect Rishit's selected real frontend paths and complete the visible
   caregiver journey.

The architecture should change only if those measurements expose a real
contract gap. Better sensor quality should improve the payload evidence, not
force a rewrite of the product, event workflow, or intelligence boundary.

## Reviewer decision

**Approved:** hardware/backend bench integration, representative-data
collection, frontend API convergence, and live-model evaluation.

**Not approved:** claims of clinical readiness, reliable real-resident anomaly
detection, production deployment, or field accuracy.

Use `docs/HARDWARE_BACKEND_HANDOFF.md` for the exact integration socket and
`docs/CURRENT_STAGE.md` for the shared team checkpoint.
