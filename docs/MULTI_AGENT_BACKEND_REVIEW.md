# Multi-Agent Backend Review

**Updated:** September 1, 2026
**Owner:** Akshar
**Status:** Backend software slice complete on toy evidence; frontend, hardware, privacy approval, and real-world validation remain open.

## What now works

The backend now follows the locked product flow:

```text
sensor measurements → numerical anomaly → bounded evidence JSON →
broad recall pass → selected specialists in parallel → final review →
validated action → saved dashboard history → optional staff feedback/memory
```

Deterministic software finds and measures unusual patterns. It does not guess what they mean. The first AI pass keeps plausible explanations broad, specialists review the relevant possibilities, and the final pass combines them into one operational severity and action. Invalid or unavailable AI stays visible as pending or staff-review-needed.

One narrow safety path remains deterministic: once the fall-like state machine
has reached its test-only urgent trigger, critical caregiver work is provisional
and cannot be suppressed by pending, unavailable, or lower-action AI output.
The AI result remains the saved interpretation and can explain uncertainty, but
it does not erase already-qualified urgent work.

The final AI result is bound to the exact resident, room, evidence revision, memory version, and tenant that produced it. Persistent processing requires an explicit current memory snapshot—even when it is intentionally empty—so missing context cannot silently become a different model input. Retries are append-only, so a failed attempt and a later successful attempt both remain reviewable. Fall-like evidence has the same durable path without inventing a normal anomaly record.

Staff-facing summaries and next steps are rendered from controlled, non-diagnostic labels and actions. Model text cannot directly become an alert headline. Unknown output fields, invented evidence references, changed IDs, changed labels, unsupported resident attribution, and prompt-like resident-memory text are rejected or contained.

## What the frontend can use

- Event detail and the clinic queue return the analysis for the exact evidence revision that created the event.
- `GET /v1/residents/{resident_id}/analyses` exposes analyzed, observe, pending, and staff-review history even when no caregiver event was created.
- The committed OpenAPI file is the frontend contract: `docs/openapi/product-api-v1.json`.
- Multi-person periods can still be numerically measured and reviewed by the AI path, but any result remains room-level unless resident attribution is supported.

## Verification completed

- Full local software suite: 859 tests plus 100 subtests.
- New staged mass campaign: 120 cases, 120 recall calls, 240 specialist calls, and 120 final reviews.
- Mass result: zero invented evidence references; 100% expected possibility routing, specialist support, final action, and final severity agreement for the deterministic staged provider.
- Live Gemini 3.5 Flash proof: one complete recall → two specialists → final-review run, ending in a valid `observe/watch` result with no validation errors and no invented evidence references.
- Process → persist → restart → dashboard-read integration proof, including exact event analysis and the resident analysis feed.
- Separate fall-like evidence → analysis → disposition persistence proof.
- Provider-retry → process restart → successful append-only attempt-two proof.
- Multi-revision restart/replay proof, fall-with-AI-pending proof, and durable
  unexpected-orchestration-failure proof.
- Migration downgrade refuses to discard or orphan existing multi-agent history.
- Final staged artifact: `multi_agent_mass_20260901_release`, with every quality
  gate passing and every saved checksum verified.

Generated evidence is stored locally under ignored `eval-results/monitoring/` folders and is not committed.

## What this does not prove

This is software validation, not clinical validation. It does not yet prove real sensor accuracy, real resident alert quality, acceptable false-alert burden in a facility, medical usefulness, or production privacy compliance.

Before production use, the team must approve the Gemini data-processing posture for pseudonymous resident, room, frame, and evidence identifiers. Real names or direct identifiers must not be sent to the model. The hardware track must supply representative telemetry, and the combined frontend/backend/hardware journey must be tested with staff reviewers.

## Next convergence gate

Rishit can connect the dashboard to the published event and analysis contracts now. Akshar's next independent backend work is simulated/real telemetry ingestion and representative-data evaluation. The tracks reconnect when the frontend consumes saved analysis history and the simulator or hardware supplies the same normalized evidence boundary.
