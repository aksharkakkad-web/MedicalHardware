# Hardware ↔ Backend Handoff

**Audience:** Mahin and Akshar  
**Status:** Software socket implemented and tested with Mahin-shaped payloads  
**Purpose:** Replace the test telemetry producer with the bench hardware without
redesigning the backend intelligence.

## The simple version

Mahin's host pipeline already produces the three compact inputs the backend
expects: radar, thermal, and Wi-Fi CSI. The backend now authenticates those
inputs, stores them before processing, proves which resident is assigned to the
device's room, converts each source into shared evidence, and sends that
evidence through the existing baseline → anomaly → AI analysis → caregiver
event flow.

The next checkpoint is integration, not a new architecture phase.

## Exact connection

The backend exposes:

- `POST /v1/ingest/telemetry` for one envelope or one list of envelopes;
- `POST /v1/ingest/heartbeat` for transport and source health.

The backend needs these local environment settings:

```dotenv
APP_ENV=development
DATABASE_URL=sqlite+pysqlite:///./local-product.db
INGEST_BEARER_KEY=replace-with-a-local-bench-key
INGEST_TENANT_ID=tenant_demo
```

The host sends the same secret as an authorization header. `INGEST_TENANT_ID`
binds that credential to one tenant; the tenant in every envelope must match.
Do not commit a real secret.

Before telemetry is resident-specific, the backend must already know:

```text
tenant_demo
  device_room_214 → room_214 → one active resident
```

Those are example bench identifiers. If the team chooses different values,
use the same values in registration and in Mahin's command. The backend never
accepts a resident identity from telemetry and never guesses an assignment.

Run the backend after applying migrations:

```bash
alembic upgrade head
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

On Mahin's branch, run the bridge with fake or real input:

```bash
cd firmware/host
python3 bridge.py --source fake
```

For hardware, use the bridge's real serial-port option instead. Then point the
host pipeline at the backend:

```bash
export INGEST_API_KEY='the-same-local-bench-key'
python3 pipeline.py \
  --ingest http://127.0.0.1:8000 \
  --device-id device_room_214 \
  --tenant-id tenant_demo \
  --room-id room_214 \
  --seconds 60
```

Mahin's current host pipeline also posts a host-derived temperature verdict to
`/v1/assessments`. The product backend intentionally does not expose that route.
That request can return `404` during the first integration and must not control
product anomalies. Disable or ignore that call; the backend derives anomaly
episodes from compact measured telemetry.

## Accepted telemetry formats

| Source | Payload format | Intended evidence |
|---|---|---|
| Radar | `radar_edge_features_v1` | heart/respiration values when supportable, distance, movement, quality, and optional position evidence |
| Thermal | `mlx90640_edge_features_v1` | presence, position/temperature trend, quality, and optional posture evidence |
| Wi-Fi CSI | `esp32_csi_edge_v1` | presence, movement, RF disturbance, respiration feature, and quality |

The cloud endpoint accepts compact edge features, not continuous raw ADC,
thermal-frame, or CSI arrays. Diagnostic raw captures are a separate future
bench/research path.

## Packet rules Mahin needs to follow

1. One telemetry-list request represents one capture moment. It may contain up
   to eight items, but only one item per source.
2. Every item in that request must use the same tenant, device, and room.
3. `sequence` is a positive number that rises within a
   tenant/device/source/stream/schema combination.
4. `stream_id` is an optional boot/session identifier. Missing currently means
   `legacy`, so Mahin's producer works now. Add a fresh, non-identifying
   `stream_id` on each host/device restart next.
5. Omit unavailable measurements. Never send `null`, a guessed value, or zero
   to stand for missing data.
6. Send quality limitations in `quality_reasons` instead of hiding them.
7. The three source envelopes may have different producer `batch_id` values;
   the backend still treats one list request as one capture.

## What happens on retries and gaps

- Exact retry of an accepted packet: safe no-op, reported as a duplicate.
- Same identity with changed content: rejected as a conflict.
- Lower or repeated sequence in the same stream: rejected as stale unless it
  is the exact retry.
- Sequence gap: accepted, with the gap recorded for awareness.
- Device/host restart: use a new `stream_id`; sequence numbers may restart.

This means a network retry cannot create duplicate evidence or events, and a
device reboot does not need to fake ever-increasing sequence numbers.

## Backend response meaning

Telemetry returns one of these processing states:

- `processed`: the capture reached the intelligence path;
- `calibrating`: the capture is valid, but this resident still needs eligible
  numerical history before anomaly comparison is honest;
- `blocked`: assignment or current monitoring conditions prohibit
  resident-specific processing;
- `pending` or `processing`: committed work has not finished yet;
- `failed`: the original packet remains stored and can be replayed.

Heartbeat responses map the device to `online`, `buffering`, `retrying`,
`degraded`, `offline`, or `assignment_unavailable`. A device problem changes
monitoring availability; it is not automatically a resident health event.

## Ownership boundary

Mahin owns:

- sensor acquisition and vendor/raw decoding;
- compact feature quality and timestamps;
- boot/session `stream_id`, sequence numbers, buffering, retries, and heartbeat;
- proving measurements against safe reference instruments or labeled actions.

Akshar/backend owns:

- authentication, validation, durable storage, and replay;
- device → room → resident assignment proof;
- source normalization, time alignment, fusion, personal baseline, anomalies,
  AI analysis, events, feedback, and audit history.

There is no RFID path. V1 assumes one assigned resident per room. Possible
extra-person periods reduce or pause resident-specific conclusions rather than
guessing whose signal is present.

## Hardware integration checkpoint

The checkpoint passes when the team can show all of the following:

1. fake bridge data reaches the registered backend and produces stored frames;
2. exact retries do not duplicate frames, analyses, or events;
3. real radar, thermal, and CSI each arrive with honest quality/missingness;
4. unplugging/degrading a source produces limited or unavailable monitoring;
5. a new `stream_id` permits a clean restart;
6. ordinary room activity and away periods do not create caregiver events;
7. labeled test actions create the expected evidence without claiming medical
   accuracy; and
8. saved captures replay to the same software result after restart.

Only after that checkpoint should the team tune thresholds against real data.

