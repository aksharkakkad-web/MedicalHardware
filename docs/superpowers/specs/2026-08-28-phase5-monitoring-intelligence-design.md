# Phase 5 Monitoring Intelligence Design

**Status:** Approved for implementation
**Date:** 2026-08-28
**Owner:** Akshar — backend and monitoring intelligence
**Research inputs:** `docs/research/2026-08-28-contactless-monitoring-v1-research.md`, `docs/research/2026-08-28-anomaly-filter-llm-replication-research.md`

## Purpose

Build the lean V1 cloud-intelligence path on normalized simulated observations
without waiting for edge telemetry, real hardware, or frontend integration.
The phase must prove that ordinary human variation stays mostly quiet,
meaningful simulated changes create reproducible anomaly evidence, uncertain
information remains uncertain, and approved policy outcomes enter the durable
caregiver event system that already exists.

This design supersedes the earlier assumption that the LLM always interprets
an already-created event. The locked behavior is:

```text
Non-urgent path:
normalized evidence
→ anomaly episode
→ rich evidence packet
→ situation-specific LLM interpretation
→ deterministic policy
→ optional caregiver event

Urgent path:
strong deterministic safety evidence
→ provisional caregiver event immediately
→ LLM interpretation/enrichment afterward
```

The LLM never monitors continuous telemetry, performs sensor math, diagnoses a
condition, or suppresses a deterministic urgent event.

## Scope

Phase 5 builds:

- a hardware-neutral normalized feature contract;
- per-feature and per-purpose quality;
- deterministic normalized-fixture replay;
- time-window fusion that preserves missing and contradictory evidence;
- versioned resident numerical baselines;
- strict learning eligibility, freezing, selective recalibration, and
  controlled adoption of a legitimate new normal;
- a lean anomaly filter with persistence and hysteresis;
- a separate anomaly-episode lifecycle;
- a deterministic fall-like fast path using synthetic/test-only policy;
- rich versioned anomaly evidence packets;
- flexible resident routines, habits, temporary changes, and expected-new-
  behavior context;
- situation-specific versioned LLM skills, read-only context retrieval, one
  structured interpretation transaction, and deterministic validation;
- deterministic disposition policy;
- idempotent bridging into the existing caregiver event lifecycle;
- scenario replay and operational metrics.

Phase 5 does not build:

- vendor/raw radar, thermal, or CSI parsing;
- edge telemetry ingestion, transport retry, or normal telemetry persistence;
- the frontend resident-profile experience;
- real notification delivery;
- production authentication;
- real hardware thresholds or clinical claims;
- heart-rate caregiver decisions;
- multi-person identity or signal separation;
- an end-to-end multimodal neural model;
- online global self-modification.

## Product success rule

The system favors recall when capturing internal anomaly candidates and favors
precision before interrupting a caregiver.

```text
possible numerical change
→ capture candidate generously
→ remove bad attribution and ordinary variation
→ require persistence/corroboration
→ interpret with relevant context
→ interrupt selectively
```

Internal anomaly packets, observations, and shadow scores are not caregiver
alerts. Operational success is measured at both layers:

- meaningful simulated changes captured and false packets per resident-day;
- useful caregiver events, missed events, false events per resident-day, and
  detection latency.

## End-to-end flow

```text
NORMALIZED RADAR ───┐
NORMALIZED THERMAL ─┼→ quality/context gate
NORMALIZED CSI ─────┘          ↓
                       aligned feature frame
                               ↓
                    flexible personal baseline
                               ↓
                 unusual enough + long enough?
                       ↙                  ↘
                     no                    yes
                     ↓                      ↓
              learn if eligible      anomaly episode
                                             ↓
                                  rich evidence packet
                                             ↓
                                  select skill bundle
                                             ↓
                             one structured LLM call
                                             ↓
                              deterministic validator
                                             ↓
                      no action / observe / awareness /
                              caregiver event
                                             ↓
                              existing event backend
                                             ↓
                        acknowledgment/check/resolution
                                             ↓
                         feedback + resident memory
                                             ↓
                     controlled future baseline eligibility
```

## Normalized feature boundary

The cloud intelligence consumes normalized feature observations, never vendor
payloads. A normalized observation identifies tenant, room, assigned resident,
device, source, feature window, processor version, and one or more features.

Each feature contains:

- stable feature name and explicit unit;
- numeric, boolean, categorical, or unavailable value;
- `GOOD`, `LIMITED`, or `UNUSABLE` quality;
- quality reasons;
- observation time and freshness;
- purpose eligibility, such as movement, posture, respiration, or presence.

An observation may be useful for movement and unusable for respiration. There
is no universal sensor-quality number that hides that distinction.

Initial hardware-neutral feature names may include:

- presence evidence and person-count hint;
- approximate position/zone;
- tracked height and vertical velocity;
- horizontal speed;
- radar, thermal, and CSI movement energy;
- thermal floor proximity, uprightness, and foreground area;
- CSI periodicity and environment-shift evidence;
- time since meaningful movement;
- movement-burst count and repetition score;
- respiration rate and respiration quality;
- experimental heart-rate observation with no policy authority.

All numerical values used by simulation are synthetic and test-only.

## Quality and context gate

Quality classes mean:

- `GOOD`: may participate in detection and baseline learning when all other
  eligibility rules pass;
- `LIMITED`: may support evidence but cannot train normality;
- `UNUSABLE`: value is absent, never zero-filled, forward-filled, or imputed.

Room context is evaluated before resident anomaly logic:

- `resident_present`: resident-specific processing may run;
- `resident_away`: awareness only, inactivity detection pauses, learning
  pauses;
- `possible_multi_person`: attribution is ambiguous, resident learning pauses,
  and ordinary resident-specific anomaly conclusions are unavailable;
- assignment/device unavailable: operational monitoring state, not resident
  behavior.

A monitoring-degradation detector runs in parallel and has priority over
behavioral interpretation. Frozen values, stale timestamps, sensor movement,
configuration changes, and environment shifts must not become resident
anomalies.

## Time lanes

V1 uses separate timescales rather than one universal window:

### Fast safety lane

Consumes source-rate or short-window kinematic/posture evidence for rapid
transitions. It does not wait for the general anomaly or LLM path before
opening a provisional urgent event when the configured synthetic rule matches.

### Behavior lane

Consumes one-second normalized simulated frames as a starting hypothesis for
movement, inactivity, repetition, and unknown anomalies. Window sizes and
persistence are policy configuration, not hard-coded medical truth.

### Slow routine lane

Consumes minute/hour/day summaries for changes in routine. Slow changes create
observation, awareness, or active-learning opportunities before urgent work.

## Fusion

Fusion is late, event-specific, and logical. It does not average all sensors
into one global score.

It records:

- available modalities;
- independent supporting sensors;
- supporting features;
- contradictions;
- missing/stale sources;
- monitoring limitations;
- time-alignment quality.

Absence of corroboration and contradictory evidence are different states.
Missing CSI must not reduce a strong radar measurement mathematically; it
reduces evidence completeness. CSI remains supporting rather than required for
safety.

## Personal numerical baseline

The production V1 baseline uses transparent resident-specific statistics:

- median;
- median absolute deviation;
- interquartile range;
- lower and upper empirical quantiles;
- a feature-resolution scale floor;
- eligible coverage;
- setup, feature, and baseline versions.

Robust deviation is calculated against the best mature applicable context,
falling back from a mature time context to the resident-global baseline. The
exact context bins, coverage requirements, horizon, and thresholds are
versioned synthetic configuration hypotheses until evaluated.

The initial routine-history horizon may begin at 14 days because the research
found relevant recent-history precedent, but it is not applied blindly to
fast kinematic features and is not a clinical constant.

### Learning eligibility

A feature window may teach normality only when:

- resident/room assignment is valid;
- the resident is present;
- single-person attribution is suitable;
- monitoring is active;
- the feature quality is `GOOD`;
- no anomaly candidate affecting that feature is active;
- no unresolved relevant anomaly guard exists;
- no setup/configuration change invalidates the feature;
- the window is not inside an active freeze or recovery guard.

Baseline freezing begins at the anomaly candidate timestamp, not later event
creation. Affected dimensions remain frozen through the episode and a
configurable post-episode guard.

### Calibration and recalibration

Existing `new`, `calibrating`, `partial`, and `established` product states are
preserved. The intelligence layer additionally records per-feature eligible
coverage and authority. Setup changes create a new baseline lineage and reset
only affected dimensions. Resident semantic memory and old baseline versions
remain intact.

### Adopting a legitimate new normal

A nurse can declare an expected new behavior before an anomaly or classify an
event afterward. This immediately updates semantic resident context; it does
not immediately overwrite numerical normality.

An expected-new-behavior entry starts a controlled adoption candidate:

1. record the operator, source, effective window, and intended duration;
2. make matching context available to the LLM immediately;
3. continue recording objective behavior;
4. admit later matching windows only when quality, attribution, safety, and
   anomaly guards pass;
5. require configured clean coverage before publishing a new baseline version;
6. retain the old version and adoption provenance for rollback/replay.

Temporary expected behavior expires and does not automatically become a
permanent baseline. Sensor/setup problems trigger recalibration, not resident
learning.

## Flexible resident profile context

The existing versioned resident-memory system is extended rather than
replaced. Entries can represent:

- routine;
- habit;
- temporary change;
- expected new behavior;
- general context.

Entries may carry an effective start/end, optional broad local-time range,
optional recurrence description, and operator-entered flexibility note.
These fields express tendencies, not exact schedules.

Examples include variable bathroom/away trips, naps, quiet reading, assisted
movement, visitors, and temporary schedule changes.

Routine context never directly suppresses strong urgent safety evidence. It
helps the LLM and policy distinguish ordinary human variation from a
meaningful change. The system may propose a repeated pattern for nurse review,
but it cannot silently add a human-level conclusion to the profile.

## Lean anomaly filter

The production filter performs numerical gating only:

- calculate per-feature robust deviation;
- record magnitude, direction, rate, and trajectory;
- require event-specific persistence;
- recognize sensor agreement and contradiction;
- start/end with hysteresis;
- preserve unknown anomalies;
- package evidence for interpretation.

It does not broadly decide what the behavior means.

V1 production authority is a transparent personal baseline filter. A small
EWMA value may describe sustained progression but does not independently
create events at first. Isolation Forest may run later in shadow mode with a
fixed feature mask and deterministic seed. PELT is offline/replay-only. Neural
autoencoders and multimodal classifiers are postponed.

All thresholds and window sizes live in a versioned `SyntheticAnomalyPolicy`
or equivalent configuration with an explicit `test_only` marker.

## Anomaly lifecycle

Numerical anomaly episodes are separate from caregiver events:

```text
CANDIDATE → ACTIVE → RECOVERING → CLOSED
```

- `CANDIDATE`: threshold crossed; persistence not yet satisfied;
- `ACTIVE`: persistence/corroboration satisfied; evidence packet revisions
  may be interpreted;
- `RECOVERING`: initiating evidence has weakened but end conditions are not
  satisfied;
- `CLOSED`: evidence returned inside configured end bounds for the required
  duration.

Missing samples stop recovery timers; they never mean recovery.

Continuous related evidence updates one anomaly ID. A new period after clear
recovery creates a new anomaly with `recurrence_of`. Closed anomalies remain
immutable except for append-only references/audit metadata.

## Urgent fall-like fast path

The initial synthetic fall-like state machine is:

```text
STABLE
→ RAPID_DESCENT
→ LOW_POSITION
→ POST_TRANSITION
→ CONFIRMED_FALL_LIKE or RECOVERED
```

It may consider downward velocity, height collapse, thermal low/floor-like
geometry, and post-transition movement. Exact values are configurable,
synthetic, and test-only. Simulated confounders must include quick sitting,
kneeling, controlled descent, picking something up, and intentional lying.

Strong radar plus thermal corroboration may create a provisional event
immediately. Strong radar with thermal unavailable may create a lower-
confidence provisional event according to policy. Contradiction is preserved
and never averaged away. Possible multiple-person context must state that
resident attribution is uncertain.

## Rich anomaly evidence packet

An active anomaly produces an immutable, revisioned structured packet with:

- schema/anomaly/revision IDs;
- resident, room, and timing references;
- filter, configuration, feature, setup, and baseline versions;
- calibration maturity and freeze reasons;
- monitoring/presence/multiple-person context;
- overall strength definition and progression;
- initiating and changed features;
- current values, units, quality, baseline statistics, deviations, rates,
  trajectories, and persistence;
- bounded multi-resolution timelines;
- per-sensor availability, diagnostics, and evidence;
- agreement, contradictions, and missing information;
- relevant resident-memory/event/feedback references;
- deterministic-trigger reasons;
- explicit unknowns;
- bounded evidence references for replay/drill-down.

The packet is much richer than a paragraph summary but excludes continuous raw
radar, thermal, and CSI streams.

## LLM skills and context

V1 uses one primary structured interpretation transaction with read-only
retrieval. Separate versioned skill files are selected by situation and
assembled into the call; separate skill files do not require ten sequential
LLM calls.

Shared skills:

- evidence inspection;
- relevant-context retrieval;
- contradiction and uncertainty checking;
- recommendation;
- caregiver wording;
- structured-output rules.

Situation skills:

- fall-like/rapid transition;
- inactivity while present;
- elevated/repetitive movement;
- respiration deviation;
- routine/new-behavior change;
- monitoring degradation;
- possible multiple-person context;
- unknown anomaly.

Read-only retrieval may access bounded anomaly/feature timelines, baseline
history, similar anomalies, related events, caregiver feedback, resident
context, sensor quality, and setup/device changes. It cannot issue arbitrary
database queries or mutate state.

The structured result contains:

- objective category or unknown;
- ranked non-diagnostic alternatives;
- ordinal interpretation confidence;
- supporting and contradicting evidence references;
- missing information;
- whether more observation is needed;
- recommended product disposition;
- objective caregiver wording;
- explicitly unsupported conclusions.

Every invocation records model/provider identifier, model version when
available, skill-bundle version, prompt version, retrieval contract version,
output-schema version, invocation ID, and retrieved references.

Phase 5 implements a provider-neutral client plus deterministic fake/test
provider. Selection and live integration of a production LLM provider remain
configurable and do not block the intelligence contract or evals.

## Deterministic validation and policy

Every LLM result is validated before policy uses it:

- every claimed measurement/evidence reference exists;
- unavailable values are not described as measured;
- no diagnostic or causal certainty is introduced;
- contradictions, calibration limitations, and attribution limitations are
  preserved;
- recommended action is an allowed enum;
- the LLM cannot downgrade or suppress an urgent deterministic trigger.

Invalid or unavailable interpretation uses objective templates generated from
the evidence packet.

Policy evaluates in this order:

```text
system/data integrity
→ presence/away/multiple-person restrictions
→ urgent deterministic safety triggers
→ anomaly strength/persistence/calibration
→ validated LLM interpretation
→ NO_ACTION / OBSERVE / AWARENESS / CAREGIVER_EVENT
```

Confidence describes evidence/interpretation trust. Priority describes
response urgency. They remain separate.

## Caregiver acknowledgment, cooldown, and resolution

Acknowledging a caregiver event quiets duplicate attention; it does not claim
that the numerical anomaly ended.

While an event is acknowledged:

- continuing related signals update the same event;
- duplicate external notifications are suppressed according to configurable
  event-family/priority policy;
- the event remains visible;
- material escalation may override cooldown;
- critical evidence cannot be hidden;
- an unrelated anomaly may create separate work.

The anomaly closes from evidence recovery. The caregiver event resolves from a
caregiver action or allowed watch policy. Resolved events remain immutable. A
later recurrence after recovery creates a new linked event.

Actual external notification delivery and reminder schedules are not Phase 5;
the intelligence produces auditable suppression/cooldown recommendations for
later delivery infrastructure.

## Feedback behavior

Authenticated clinic feedback is trusted and auditable. The backend supports
product dispositions including:

- expected new behavior;
- temporary expected behavior;
- checked/no concern;
- confirmed concern;
- sensor or room problem;
- uncertain/continue monitoring.

These dispositions map onto existing confirmed/false-positive/uncertain event
outcomes plus typed resident-context and learning decisions. They do not alter
original event evidence or silently modify global logic.

## Persistence and replay

Phase 5 persists or represents through repository interfaces:

- baseline snapshots and feature statistics;
- anomaly episodes and packet revisions;
- interpretation inputs/results and version metadata;
- policy dispositions and event bridges;
- typed resident context and baseline-adoption provenance.

Phase 5 normalized-fixture replay must reproduce deterministic decisions from:

- normalized observations;
- quality/context decisions;
- baseline version;
- filter/config/feature versions;
- anomaly packet revisions;
- fake LLM response and retrieved references;
- policy version.

Full edge-telemetry ingestion persistence and replay arrive in Phase 6.

## Module boundaries

The implementation should use focused backend modules rather than one large
monitoring file:

```text
backend/app/intelligence/
├── observations.py
├── quality.py
├── fusion.py
├── baseline.py
├── anomaly.py
├── evidence.py
├── fall_detection.py
├── interpretation.py
├── policy.py
└── orchestration.py

backend/app/ai/
├── client.py
├── skills.py
├── context.py
└── validation.py

prompts/monitoring/
├── core.md
├── fall_like.md
├── inactivity.md
├── movement.md
├── respiration.md
├── routine_change.md
├── monitoring_degraded.md
├── multi_person.md
└── unknown_anomaly.md

evals/monitoring/
├── scenarios.py
├── replay.py
└── metrics.py
```

Existing monitoring, calibration, feedback/memory, device-health, events,
repositories, service, API, and audit modules are extended at explicit seams;
they are not duplicated.

## Scenario and invariant coverage

Required scenarios include:

- variable normal daily movement;
- random bathroom/away trips and normal return;
- sleep, quiet reading, and ordinary stillness;
- expected habits and temporary changes;
- visitor/possible-multiple-person periods;
- meaningful elevated or repetitive movement;
- prolonged inactivity while present;
- fall-like transitions and confounders;
- respiration deviation with good and bad quality;
- unknown anomaly;
- missing, stale, frozen, and contradictory sensors;
- room/device/setup change;
- new behavior entered before an anomaly;
- new behavior confirmed after an event;
- continuing anomaly after event acknowledgment;
- recurrence after recovery;
- LLM unavailable, invalid, contradictory, and unsupported output.

Required invariants:

- missing input never becomes a numeric value;
- `UNUSABLE` never updates a baseline;
- away and possible-multiple-person periods never update resident normality;
- active candidate/anomaly periods freeze affected baseline dimensions;
- acknowledgment never closes a numerical anomaly;
- an anomaly never ends solely because data disappeared;
- room/sensor changes create a new affected baseline lineage;
- one continuous condition never spams separate events;
- deterministic urgent events survive LLM failure/disagreement;
- identical evidence and versions replay identically;
- no LLM factual claim without evidence provenance.

## Evaluation outputs

The replay harness reports:

- meaningful anomaly recall;
- false anomaly packets per simulated resident-day;
- false caregiver events per simulated resident-day;
- missed meaningful events;
- candidate, packet, and event latency;
- duplicate-event rate;
- event-duration error;
- baseline contamination, with a software-integrity target of zero;
- time in active, limited, paused, and unavailable monitoring;
- interpretation schema validity;
- supported-claim and unsupported-claim counts;
- replay reproducibility.

No unsupported numerical clinical-performance target is locked. The simulator
produces an operating curve across versioned threshold/persistence
configurations.

## Failure behavior

| Failure | Behavior |
| --- | --- |
| Missing/stale sensor | Preserve missingness, reduce evidence completeness, never impute |
| Possible multiple people | Freeze personalization and avoid resident attribution |
| Device/setup change | Monitoring limitation plus selective recalibration |
| Incomplete baseline | Deterministic safety still runs; personalized authority is limited |
| LLM unavailable/invalid | Deterministic policy and objective templates continue |
| LLM contradicts urgent trigger | Urgent event remains; contradiction is stored |
| Persistence not met | Candidate closes silently; no caregiver event |
| Evidence disappears during recovery | Recovery timer pauses; no false closure |
| Existing active related event | Update it idempotently; do not spam |

## Implementation checkpoints

### A. Contract and deterministic replay foundation

Normalized observations, purpose-specific quality, aligned frames, synthetic
policy configuration, and canonical replay identity.

### B. Personal baseline and human-variation engine

Robust statistics, calibration authority, eligibility/freezing, routine
context, selective recalibration, and controlled new-normal adoption.

### C. Anomaly episodes and urgent fast path

Deviation, persistence, hysteresis, episode revisions, recurrence, monitoring
degradation, fall-like synthetic policy, and rich evidence packets.

### D. LLM skills, retrieval, and validation

Versioned situation skills, provider-neutral structured interpreter,
read-only context, fake provider, provenance validation, and fallback.

### E. Deterministic disposition and event bridge

No-action/observe/awareness/event decisions, confidence/priority separation,
idempotent connection to existing durable events, acknowledgment/cooldown
semantics, and feedback/new-normal loop.

### F. Complete replay and evaluation gate

Full normal/abnormal/degraded/human-variation scenario matrix, operational
metrics, restart/replay checks where persistence exists, and founder-facing
walkthrough.

## Phase 5 completion gate

Phase 5 is complete when normalized simulated scenarios prove that:

1. ordinary human variation and normal away trips stay mostly quiet;
2. meaningful changes create rich, reproducible anomaly packets;
3. weak, stale, conflicting, away, visitor, and setup-change data remain
   honest and do not contaminate the baseline;
4. legitimate new behavior updates semantic context immediately and numerical
   normality only through controlled clean learning;
5. urgent deterministic evidence creates a provisional event without the LLM;
6. non-urgent anomalies use relevant situation skills and context before
   deterministic disposition;
7. invalid/unavailable LLM output cannot break safety or invent evidence;
8. continuous signals update one event and acknowledgment does not falsify
   anomaly recovery;
9. the existing durable caregiver workflow receives approved events without a
   competing event system;
10. one command replays the Phase 5 scenario suite and reports operational
    metrics.

Real-world detection accuracy, notification delivery, frontend convergence,
edge ingestion, and hardware validation remain explicit later gates.
