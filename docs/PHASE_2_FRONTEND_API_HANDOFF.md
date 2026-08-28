# Phase 2 Clinic Frontend API Handoff

**Status:** Backend ready for frontend connection
**Backend owner:** Akshar
**Frontend connection owner:** Rishit
**Purpose:** Replace selected clinic mock-client reads with the Product API
without exposing database details or redesigning the current screens.

## The first real connection path

The resident overview is composed from three public reads:

1. `GET /v1/residents` supplies assigned resident and room identity.
2. `GET /v1/events?limit=100` supplies the tenant's active attention queue;
   the client follows `next_cursor` until it is `null`, then groups the complete
   result by `resident_id`.
3. `GET /v1/residents/{resident_id}/status` supplies current monitoring,
   calibration, assignment, and device-health state for each resident.

This composition belongs inside Rishit's `ApiMonitoringClient`. Page and card
components continue to consume the frontend's own overview model and never
learn API or database shapes.

## Overview field map

| Frontend meaning | Product API source | Rule |
| --- | --- | --- |
| Resident and room labels | `GET /v1/residents` | Use `display_label`, `room_id`, `room_label`, and `assignment_status` directly. |
| Monitoring state | Resident `status.monitoring.monitoring_state` | If `monitoring` is `null`, show unavailable rather than normal. |
| Monitoring explanation | `status.monitoring.reasons` plus `status.unavailable_reasons` | Translate known reason codes to plain language in the frontend. Never invent a safe value. |
| Last monitoring update | `status.monitoring.observed_at` | This must be nullable in the frontend because history may not have started. |
| Device state | `status.device.health.state` and `data_availability` | Support online, offline, degraded, buffering, retrying, assignment unavailable, and not-yet-available. |
| Active event count | Count all fetched active queue items grouped by `resident_id` | Follow every queue page before treating the count as complete; `total_items` is clinic-wide, not per resident. |
| Highest attention priority/headline | First grouped event in API queue order | If no active event exists, use the frontend's neutral no-attention presentation. |

High and critical event visibility does not depend on the resident's delivery
preferences. Preferences affect future notification delivery only.

## Complete clinic operation map

Every `/v1` operation requires development-only `X-Tenant-Id` and
`X-Actor-Id`. Every state-changing operation also requires `Idempotency-Key`
and a body with `schema_version: "1.0"` plus an explicit UTC timestamp.

| Frontend operation | Method and path | Public result |
| --- | --- | --- |
| List residents | `GET /v1/residents` | `ResidentListResponse` |
| Read resident identity | `GET /v1/residents/{resident_id}` | `ResidentSummary` |
| Read resident status | `GET /v1/residents/{resident_id}/status` | `ResidentStatusResponse` |
| Read awareness history | `GET /v1/residents/{resident_id}/awareness` | `AwarenessTimelineResponse` |
| Read calibration/setup | `GET /v1/residents/{resident_id}/calibration` | `CalibrationResponse` |
| Record setup change | `POST /v1/residents/{resident_id}/setup-changes` | Updated `CalibrationResponse` |
| List active clinic events | `GET /v1/events` | `ClinicEventQueueResponse` |
| Filter event history | `GET /v1/events?status=resolved` | `ClinicEventQueueResponse` |
| Read event detail | `GET /v1/events/{event_id}` | `EventResponse` |
| Acknowledge event | `POST /v1/events/{event_id}/acknowledge` | Updated `EventResponse` |
| Mark event checked | `POST /v1/events/{event_id}/checked` | Updated `EventResponse` |
| Resolve event | `POST /v1/events/{event_id}/resolve` | Updated `EventResponse` |
| Submit event feedback | `POST /v1/events/{event_id}/feedback` | `LearningDecisionResponse` |
| List devices | `GET /v1/devices` | `DeviceListResponse` |
| Read device health | `GET /v1/devices/{device_id}/health` | `DeviceHealthResponse` |
| Read preferences | `GET /v1/residents/{resident_id}/notification-preferences` | `ResidentNotificationPreferencesResponse` |
| Update preferences | `PUT /v1/residents/{resident_id}/notification-preferences` | Updated preferences response |
| Read resident memory | `GET /v1/residents/{resident_id}/memory` | `ResidentMemoryResponse` |
| Add resident context | `POST /v1/residents/{resident_id}/memory/entries` | Updated `ResidentMemoryResponse` |
| Correct resident context | `POST /v1/residents/{resident_id}/memory/entries/{entry_id}/correct` | Updated `ResidentMemoryResponse` |
| Retire resident context | `POST /v1/residents/{resident_id}/memory/entries/{entry_id}/retire` | Updated `ResidentMemoryResponse` |

Exact schemas, parameters, and error envelopes are generated in
`docs/openapi/product-api-v1.json`. The narrative source of truth remains
`docs/DATA_CONTRACT.md`.

## Refresh and failure behavior

- Refresh the active event queue after acknowledge, check, or resolve because
  the action may change filter membership or ordering.
- Treat a `404` as missing or inaccessible; do not reveal cross-tenant
  distinctions.
- Treat `409` as a stale/invalid action and refresh the affected resource.
- Treat `422` as a request construction problem; the response identifies the
  invalid field when available.
- Keep the last successful UI visible with a clear stale/error state when a
  refresh fails. Never replace missing data with a normal state.
- Idempotent retries use the same key and logical request. A changed request
  must use a new key.

## Browser connection boundary

Rishit owns the frontend network adapter and should use a same-origin Next.js
route/proxy for the first connection. That proxy can keep the development
tenant/actor headers out of browser components and avoids committing a
production CORS or authentication design during this phase. Production
identity and permissions remain a later security checkpoint.

The backend does not add a surprise aggregate overview endpoint in Checkpoint
D. If later performance evidence justifies one, it will be an explicit shared
contract change rather than hidden coupling.

## Honest deferrals

The API does not yet return resident trends, event evidence, AI interpretation,
notification-delivery results, production authentication, or home/family
real-data views. Rishit's mock experiences may represent later planned states,
but the real client must keep those paths on mocks or show not-yet-available
until their documented backend phase is complete.
