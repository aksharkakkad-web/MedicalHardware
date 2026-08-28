# Phase 5 Backend Monitoring Intelligence Review

**Review date:** August 28, 2026
**Owner:** Akshar — backend and monitoring intelligence
**Decision:** The Phase 5 backend lane is complete on deterministic synthetic
normalized fixtures. This does not complete the shared frontend/hardware phase
gate and does not establish clinical, real-device, or production-provider
performance.

## Founder summary

One command now replays 24 stable scenarios through the implemented Phase 5
components and fails if a safety invariant regresses:

```bash
python3 -m backend.app.checkpoints.monitoring_intelligence
```

The machine-readable record is:

```bash
python3 -m evals.monitoring.replay --format json
```

The replay begins with compact, visibly synthetic normalized observations. It
does not use continuous raw sensor arrays, a network API, or a live LLM. IDs,
UTC timestamps, ordering, policy versions, resident context, and fake-provider
behavior are injected. Two fresh command runs emit byte-identical canonical
JSON. The replay also persists one complete intelligence-to-event chain in a
file-backed repository, closes the first database engine, reopens it, hydrates
the chain, and proves exact bridge-signal replay remains idempotent.

## Exact implemented flow

```text
synthetic normalized radar / thermal / CSI features
→ per-feature quality and explicit missingness
→ deterministic aligned frame (agreement and contradiction preserved)
→ versioned robust resident baseline and learning guard
→ numerical anomaly candidate / active / recovering / closed episode
→ immutable revisioned evidence packet
→ one situation-specific deterministic fake-AI interpretation
→ provenance and structured-output evidence validation
→ deterministic disposition and priority
→ idempotent caregiver event bridge
→ acknowledgment, recovery, recurrence, and controlled new-normal adoption
```

The urgent flow is separate:

```text
corroborated synthetic fall-like transition
→ provisional critical caregiver event
→ no wait for AI and no AI suppression authority
```

## What is implemented

- Hardware-neutral normalized feature records and deterministic late fusion.
- Purpose-specific `GOOD`, `LIMITED`, and `UNUSABLE` quality behavior.
- Versioned robust baseline construction, explicit learning eligibility,
  contamination guards, setup lineage, and controlled expected-new-behavior
  adoption.
- Numerical anomaly persistence, hysteresis, recovery, recurrence, and rich
  evidence revisions.
- Operational degradation and a synthetic/test-only fall-like fast path.
- Versioned situation skills, bounded context, provider-neutral requests,
  deterministic fake provider, total validation, and objective fallback.
- Explicit selection of one eligible resident-context entry in a real
  nonurgent request, with request/result provenance checked by the replay.
- Deterministic no-action/observe/awareness/caregiver-event policy and the
  existing durable event lifecycle bridge.
- Repository-backed restart hydration for anomaly revision, interpretation,
  disposition, event bridge, and caregiver-event lineage.
- A canonical replay, computed metrics, and a founder checkpoint that exits
  nonzero on an invariant failure.

## Stable scenario matrix

`AI` is attempted/valid/rejected/unavailable. Counts are measured from the
canonical replay, not expected labels copied into the report.

| Scenario | Class | Monitoring | Candidates | Packets | Events | AI | Result |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| `normal_variation` | ordinary | active | 0 | 0 | 0 | 0/0/0/0 | quiet |
| `random_bathroom_away` | routine | paused | 0 | 0 | 0 | 0/0/0/0 | no resident warning |
| `sleep_reading_stillness` | ordinary | active | 0 | 0 | 0 | 0/0/0/0 | quiet |
| `flexible_routine` | routine | active | 0 | 0 | 0 | 0/0/0/0 | semantic context only |
| `temporary_change` | routine | active | 0 | 0 | 0 | 0/0/0/0 | semantic context only |
| `visitor_multi_person` | operational | limited | 0 | 0 | 0 | 0/0/0/0 | room awareness; no attribution |
| `sustained_movement_change` | meaningful | active | 1 | 1 | 1 | 1/1/0/0 | active event |
| `repetitive_movement` | meaningful | active | 1 | 1 | 1 | 1/1/0/0 | active event |
| `inactivity` | meaningful | active | 1 | 1 | 1 | 1/1/0/0 | active event |
| `fall_like` | urgent | active | 0 | 0 | 1 | 0/0/0/0 | provisional urgent event |
| `fall_like_confounder` | ordinary | active | 0 | 0 | 0 | 0/0/0/0 | quiet |
| `respiration_quality_limited` | operational | limited | 1 | 0 | 0 | 0/0/0/0 | candidate only; no claim |
| `unknown_anomaly` | meaningful | active | 1 | 1 | 1 | 1/1/0/0 | unknown retained; active event |
| `missing_signal` | operational | limited | 0 | 0 | 0 | 0/0/0/0 | missing stays missing |
| `stale_signal` | operational | unavailable | 0 | 0 | 0 | 0/0/0/0 | operational awareness |
| `frozen_signal` | operational | unavailable | 0 | 0 | 0 | 0/0/0/0 | operational awareness |
| `contradictory_sensors` | operational | limited | 0 | 0 | 0 | 0/0/0/0 | contradiction preserved |
| `setup_change` | operational | unavailable | 0 | 0 | 0 | 0/0/0/0 | selective recalibration lineage |
| `preentered_new_behavior` | learning | active | 0 | 0 | 0 | 0/0/0/0 | context immediate; baseline unchanged |
| `post_event_new_behavior` | learning | active | 0 | 0 | 0 | 0/0/0/0 | new baseline after five clean windows |
| `continuing_acknowledged_anomaly` | lifecycle | active | 1 | 2 | 1 | 2/2/0/0 | acknowledged; anomaly still active |
| `recurrence_after_recovery` | lifecycle | active | 2 | 5 | 2 | 4/4/0/0 | new linked history |
| `llm_unavailable` | meaningful | active | 1 | 1 | 1 | 1/0/0/1 | objective fallback |
| `llm_invalid_output` | meaningful | active | 1 | 1 | 1 | 1/0/1/0 | rejected; objective fallback |

The two learning scenarios intentionally start at the lowest approved Task 3
boundary: an already-authorized expected-new-behavior adoption candidate. They
still run the real learning guards and new-normal publisher. This isolates the
later subsystem without pretending the operator UI or Phase 6 ingestion is in
scope.

## Measured synthetic results

The canonical report measured:

- 24 scenarios and 24 declared scenario exposure units;
- meaningful downstream-event recall: 7/7 (`1.0`), meaning every declared
  meaningful scenario produced its expected caregiver work, with no missed
  declared meaningful scenario;
- false packets: 0 (`0.0` per declared exposure unit);
- false caregiver events: 0 (`0.0` per declared exposure unit);
- duplicate caregiver events: 0 across 10 event signal groups (`0.0`);
- baseline contamination: 0 across 57 evaluated learning windows (`0.0`), of
  which 14 were eligible;
- candidate latency available in 9 scenarios: mean `0.0 s`, maximum `0.0 s`;
- packet latency available in 8 scenarios: mean `3.0 s`, maximum `3.0 s`;
- event latency available in 9 scenarios: mean `3.222222 s`, maximum `5.0 s`;
- event-duration error available for one declared signal interval: mean and
  maximum `0.0 s`; unavailable in 23 scenarios without an expected interval;
- monitoring-state counts: 16 active, 4 limited, 1 paused, 3 unavailable;
- compact frame durations by state: 50 active seconds, 4 limited seconds,
  1 paused second, and 3 unavailable seconds;
- interpretations: 12 attempted, 10 valid, 1 rejected, 1 unavailable;
- AI diagnostics: 3 validation reasons, 10 validated evidence references, 1
  evidence reference on the rejected provider result, and 30 explicitly
  unsupported-conclusion declarations; these are not interpretation or claim
  counts; and
- repository restart/hydration gates: 7/7 true;
- exact two-run replay reproducibility: true; canonical JSON size: 40,481
  bytes.

These are engineering-fixture measurements. The exposure units are declared
scenario weights, not elapsed resident-days or operating time; compact frame
duration is not extrapolated into clinical performance. The values are not
clinical targets, production thresholds, real-device accuracy, or a provider
benchmark.

## What frontend can rely on

At the product boundary, frontend work may rely on these concepts and versioned
fields remaining separate:

- monitoring state and degradation/limitation reasons;
- anomaly ID, lifecycle state, evidence revision, and evidence references;
- confidence, contradictions, missing information, and limitations;
- controlled explanation category and deterministic caregiver wording;
- disposition and priority as separate values;
- explicit room-level-only attribution for ambiguous urgent work;
- caregiver event lifecycle, attention suppression, signal count, and
  recurrence links; and
- feature, setup, baseline, filter, prompt/skill, interpretation schema, and
  disposition-policy versions.

Frontend convergence still owns the user-facing presentation, accessibility,
loading/failure behavior, and clinic/home separation. This review does not
claim Rishit's frontend lane is complete.

## Verification

The Task 9 gate is:

```bash
python3 -m pytest -q
python3 -m backend.app.checkpoints.monitoring_intelligence
python3 -m evals.monitoring.replay --format json
git diff --check
```

The replay command must also be run twice with stdout captured and compared as
exact bytes. The focused evaluation suite has executable negative-path tests
for missing scenarios, unexpected caregiver work, acknowledgment/anomaly
collapse, broken recovery/recurrence, premature new-normal adoption, missing
AI fallback, false packets/events, monitoring-state drift, and restart-lineage
loss. Every plain-language founder walkthrough assertion is backed by one of
these record-derived gates.

## Explicit limitations and later work

Still open:

- Phase 6 edge-telemetry ingestion, transport behavior, normal telemetry
  persistence, deduplication, and raw-to-normalized replay;
- any continuous raw radar, thermal, or Wi-Fi CSI stream processing;
- real LLM provider selection, credentials, latency, cost, availability, and
  provider-specific evaluation;
- real hardware thresholds, device performance, environment diversity, and
  sensor validation;
- real-world detection accuracy, alert burden, missed-event rates, and event
  duration accuracy;
- clinical interpretation, clinical validation, medical claims, regulatory
  review, security/privacy review, and pilot readiness;
- external notification delivery; and
- the shared Phase 5 frontend and hardware exit checkpoint.

Phase 6 must consume the same normalized boundary and must not move raw stream
or transport responsibilities into this Phase 5 replay.
