# Multi-Agent Monitoring Interpretation Design

**Date:** 2026-09-01

**Status:** Founder-approved architecture; awaiting written-spec review

**Owner:** Akshar — backend intelligence and evaluation

**Related foundation:** `2026-09-01-monitoring-intelligence-lab-design.md`

## Product decision

The deterministic monitoring pipeline detects and measures meaningful changes
from a resident's personal baseline. It does not decide what happened, how
severe the situation is, or what a caregiver should do.

A three-stage AI pipeline owns interpretation:

1. a recall-focused router creates a broad possibility map and selects the
   relevant specialist skills;
2. precision-focused specialists investigate those possibilities in parallel;
3. one final integrator/reviewer combines the complete case, determines the
   likely situation, expresses uncertainty, sets severity, and recommends the
   caregiver response.

The final review is not an adversarial critic trying to negate the analysis.
It is a truthfulness, completeness, grounding, and usefulness review performed
inside the final integration call. A fast deterministic validator runs after
that call and may request one targeted AI repair only when the output is
invalid.

## Why this replaces the current interpretation design

The existing backend treats one bounded LLM interpretation as advice around a
deterministic disposition policy. That division is no longer the intended
product.

The new division is:

- deterministic software owns anomaly detection, evidence measurement,
  lifecycle mechanics, provenance, duplicate control, and output validation;
- AI owns plausible explanations, contextual interpretation, confidence,
  severity, and recommended action;
- caregivers own the real-world decision, acknowledgment, resolution, and
  feedback;
- controlled feedback and memory services own later learning.

An anomaly's numerical strength is not automatically its danger level. A large
change can still be a normal bathroom visit, a visitor, a planned routine
change, sensor interference, or another harmless explanation. Conversely, a
subtle change may be important in the right context. The AI therefore receives
the measured change but determines its meaning.

## Goals

- Maximize recall early so plausible and important explanations are not skipped.
- Use focused specialist analysis to improve precision before a final action is
  chosen.
- Preserve multiple credible explanations rather than forcing a false single
  answer.
- Make every conclusion traceable to supplied evidence and resident context.
- Express uncertainty and missing information honestly.
- Produce one concise, useful caregiver-facing result.
- Keep skills, model choices, and providers replaceable and independently
  testable.
- Keep normal latency to three sequential AI stages, with all specialist calls
  parallel inside the middle stage.
- Preserve every anomaly and analysis attempt for replay, evaluation, and
  learning.

## Non-goals and safety boundaries

- The system does not make a medical diagnosis.
- It does not claim clinical validation from synthetic tests.
- It does not identify a person from contactless room signals.
- It does not expose or store private model chain-of-thought. It stores concise
  structured conclusions, evidence references, uncertainty, and rationale.
- It does not allow an AI model to invent measurements, resident history, or
  sensor observations.
- It does not allow feedback to rewrite resident memory or numerical baselines
  without the existing controlled learning rules.

## End-to-end flow

```text
sensor features
→ alignment, quality, presence, and personal baseline comparison
→ deterministic anomaly episode
→ bounded evidence and resident-context package
→ Stage 1: recall router
→ Stage 2: selected precision specialists in parallel
→ Stage 3: final integration and quality review
→ deterministic schema and evidence-reference validation
→ optional one-time targeted repair only if validation fails
→ AI disposition applied through deterministic event lifecycle mechanics
→ dashboard result
→ caregiver acknowledgment, resolution, and feedback
→ guarded resident-memory proposal and controlled baseline learning
→ saved replay and evaluation evidence
```

The hidden scenario label, expected answer, later caregiver feedback, and data
from other residents are never included in the analysis request.

## The anomaly episode

The deterministic detector creates an anomaly episode, not a final caregiver
alert. The episode contains measured facts only:

- anomaly family and stable episode/revision identifiers;
- current values and relevant personal-baseline values;
- direction and size of change;
- start time, duration, persistence, recurrence, and recent trajectory;
- sensor quality, agreement, contradiction, missingness, and source status;
- presence, away, return, and possible multi-person context;
- relevant recent activity and event history;
- relevant, bounded routine and resident-memory entries;
- exact evidence identifiers for every included fact;
- prompt, skill, schema, detector, baseline, and context versions.

It does not contain a deterministic severity, recommended action, diagnosis, or
hidden expected outcome.

## Stage 1: recall router

The recall router uses a lower-cost but capable model. Its objective is to avoid
prematurely narrowing the case.

It must:

- list all reasonably plausible explanations supported or left open by the
  evidence;
- include uncommon but important possibilities when the evidence warrants them;
- consider ordinary human variation, flexible routines, visitors, bathroom
  trips, sleep, temporary absence, and sensor problems;
- identify missing or contradictory information;
- select the relevant specialist skills for each possibility;
- mark possibilities that deserve rapid specialist attention;
- cite the evidence that caused each possibility to be routed.

It must not select the final explanation, final severity, or final caregiver
action. Its output is a structured possibility and routing plan.

If the router is invalid or unavailable, a narrow deterministic mapping from
the anomaly's measured signal families selects the primary specialists. This
fallback performs routing only; it does not interpret the situation.

## Stage 2: precision specialists

Selected specialists run concurrently. Each receives the original bounded case
package, the possibilities assigned to it, shared grounding rules, and one
focused specialist skill.

Every specialist returns a structured assessment containing:

- possibilities supported, weakened, or unresolved;
- evidence for and against each conclusion;
- a calibrated confidence band;
- possible severity and response implications;
- missing information and contradictions;
- a concise, non-diagnostic rationale;
- exact evidence references.

The initial specialist catalog is:

1. signal integrity and sensor degradation;
2. movement, gait change, and fall-like activity;
3. respiration and other available physiological changes;
4. inactivity, rest, and sleep;
5. presence, bathroom trips, room exit, and return;
6. routine, visitors, environmental context, and normal human variation;
7. repeated behavior, recurrence, and escalation;
8. unknown or cross-domain anomaly.

Specialists do not see one another's conclusions. This preserves independent
analysis and prevents early group agreement from replacing evidence. Failed or
missing specialist calls are explicitly recorded and passed to the final stage.

Caregiver-feedback interpretation and resident-memory updating remain separate
post-event skills. They are not specialists for the original anomaly decision.

## Stage 3: final integrator and quality reviewer

The final stage uses the strongest configured model tier. It receives the
original case package, recall routing plan, every specialist result, and explicit
records of any unavailable specialist.

It combines rather than votes. Specialist confidence is not blindly averaged.
The final result weighs:

- direct evidence quality and relevance;
- specialist domain fit;
- evidence for and against each possibility;
- agreement, disagreement, and unresolved contradictions;
- resident-specific baseline, routine, and recent context;
- missing information and failed specialist coverage;
- the consequences of uncertainty.

The final stage must review its result before returning it. Its structured
output includes:

- the most likely explanation when the evidence supports one;
- other credible explanations;
- serious possibilities that cannot yet be excluded;
- a confidence band for each retained possibility;
- overall operational severity;
- recommended action: observe, review, check soon, or urgent response;
- caregiver-facing summary and practical next step;
- what staff should look for next;
- what new evidence would change the conclusion;
- explicit uncertainty, missing information, and specialist disagreement;
- evidence references supporting every factual statement;
- a coverage declaration confirming that routed possibilities and specialist
  results were considered.

`Observe` is a valid final action even when the numerical anomaly is strong.
The anomaly remains in history, but AI disposition determines whether it stays
as an observation, becomes an awareness item, or creates active caregiver work.

## Deterministic validation after AI

The validator checks the final result without reinterpreting the case:

- schema and allowed values;
- required fields and coverage declarations;
- evidence-reference existence and scope;
- absence of unsupported measurements or resident facts;
- absence of cross-resident data;
- internal consistency among severity, action, and lifecycle request;
- version and provenance completeness.

It does not impose a minimum severity or override `observe` because of anomaly
strength. When validation fails, the final model receives one targeted repair
request containing the validation errors and its prior structured result. A
second invalid result is not published as trusted analysis.

## Latency, retries, and unavailable AI

Normal analysis uses:

1. one recall-router call;
2. one parallel wave of selected specialist calls;
3. one final integration/review call.

The specialist wave's latency is the slowest selected specialist, not the sum of
all specialist latencies. A fourth call happens only for targeted repair.

Calls use the existing bounded retry policy and may wait up to 180 seconds when
the provider is still making progress. The system checkpoints each stage so a
retry or restart does not repeat completed work unnecessarily.

If final trusted analysis is unavailable:

- the anomaly episode remains saved and visible;
- its state becomes `analysis_pending` or `needs_staff_review`;
- the dashboard says that AI analysis is incomplete rather than guessing a
  severity or hiding the anomaly;
- background retries may continue according to configured provider policy;
- staff can inspect the measured evidence and act independently.

## Model and skill strategy

The orchestration is provider-neutral and uses named capability tiers rather
than embedding provider logic in monitoring code:

- `recall_tier`: lower-cost, low-latency, capable structured reasoning;
- `precision_tier`: stronger model for parallel specialist analysis;
- `final_tier`: strongest configured model for integration and review;
- explicit fallback mappings for unavailable production providers.

Gemini is the development and mass-evaluation provider. Production model choices
remain separately gated. A single provider may temporarily serve multiple tiers
in development without changing the architecture.

Skill files are versioned packages, not one large prompt. The initial registry
contains:

- shared grounding, privacy, uncertainty, and non-diagnostic rules;
- recall-router skill;
- one skill per precision specialist;
- final integration and review skill;
- output schemas and severity/action rubric;
- difficult calibration examples;
- caregiver-feedback skill;
- resident-memory proposal skill.

Each saved analysis records every model, provider, skill version, prompt version,
schema version, context version, latency, retry, token count, and result status.

## Backend service changes

The current single `LLMClient.interpret` path becomes a provider-neutral
orchestration service with these responsibilities:

- build and fingerprint bounded case packages;
- run and validate the recall router;
- select, dispatch, and checkpoint specialists concurrently;
- run final integration/review;
- perform deterministic output validation and optional targeted repair;
- persist every stage and its provenance;
- resume incomplete cases safely;
- apply trusted AI disposition through the existing event lifecycle;
- expose one stable final-analysis contract to the frontend;
- send resolved cases into feedback and guarded learning flows.

Existing anomaly detection, alignment, baselines, evidence revisions,
acknowledgment, cooldown, recurrence, feedback, and guarded learning are reused.
They are changed only where they currently assume deterministic disposition or
one-shot interpretation ownership.

## Event and analysis lifecycle

The backend adds explicit analysis states:

```text
anomaly_detected
→ recall_in_progress
→ specialists_in_progress
→ final_analysis_in_progress
→ analyzed
```

Failure states are `analysis_pending`, `needs_staff_review`, and
`analysis_rejected`. A repaired result keeps lineage to the rejected attempt.

The event manager remains deterministic about mechanics: idempotency, duplicate
control, acknowledgment, cooldown, reopening, resolution, recurrence lineage,
and notification settings. It applies, but does not invent, the AI's severity
and recommended action.

## Frontend contract

Rishit's frontend receives one consolidated analysis containing:

- current analysis state;
- final severity and recommended action when available;
- primary and other credible explanations;
- confidence bands and uncertainty;
- caregiver summary and next step;
- supporting evidence references;
- missing information and specialist disagreement when relevant;
- timestamps and whether the result is final, repaired, or pending.

The frontend does not need to understand provider-specific responses or raw
agent transcripts. It may offer an expandable "why" view using concise stored
rationales and evidence, never private chain-of-thought.

## Evaluation changes

The existing 12-cluster scenario library and one-million-case deterministic
evidence remain useful for anomaly detection and lifecycle invariants. AI
evaluation expands to measure each stage separately and end to end.

### Recall-router measures

- important possibility recall;
- serious possibility recall;
- normal-variation coverage;
- correct specialist routing;
- unnecessary specialist routing;
- missing-information identification.

### Specialist measures

- supported conclusion precision;
- unsupported claim and invented-evidence rate;
- evidence-for/evidence-against completeness;
- confidence calibration;
- appropriate uncertainty and abstention;
- domain-specific scenario accuracy.

### Final-stage measures

- correct combination of specialist evidence;
- preservation of credible alternatives;
- handling of disagreement and missing specialists;
- severity and action agreement with founder-reviewed outcomes;
- caregiver usefulness;
- factual grounding and evidence coverage;
- confidence calibration and repeated-run consistency.

### System measures

- end-to-end accuracy by scenario cluster;
- stage and total latency;
- number of specialist calls and token cost;
- provider failure and recovery;
- invalid-output repair rate;
- pending-analysis duration;
- duplicate, replay, restart, feedback, and learning correctness.

Hard failures include invented evidence reaching the dashboard, hidden or lost
anomalies, cross-resident leakage, invalid output accepted as trusted analysis,
memory mutation without authorized feedback, and claims of clinical validation
from synthetic evidence.

## Migration and implementation sequence

1. Replace the old product-ownership language in the PRD, current-stage,
   intelligence-lab, phase-review, and integration documents.
2. Define the anomaly episode, routing plan, specialist assessment, final
   analysis, and stage-status contracts.
3. Build the skill registry and initial specialist skills.
4. Generalize the provider interface from one interpretation call to typed AI
   stage calls.
5. Build checkpointed orchestration and concurrent specialist dispatch.
6. Build final integration/review, validation, and targeted repair.
7. Move severity and recommended-action ownership from deterministic policy to
   trusted final AI disposition.
8. Add persistence, replay, diagnostics, and frontend APIs for the new states.
9. Update scenario truth and evaluation metrics for recall, precision,
   synthesis, grounding, latency, and failure behavior.
10. Run focused tests, canonical review, offline regression, live Gemini
    development campaigns, and later production-model release gates.

## Completion criteria

The architecture is implemented when:

- every meaningful anomaly produces a versioned evidence package;
- recall routing, selected parallel specialists, and final integration/review
  run through provider-neutral contracts;
- the final result can retain multiple explanations and cite every fact;
- AI owns severity and recommended action without a deterministic severity
  floor;
- invalid or unavailable AI never causes an anomaly to disappear;
- event mechanics, feedback, and memory learning remain deterministic and
  replayable;
- the frontend receives one stable consolidated result and pending states;
- evaluation artifacts quantify every AI stage and the whole pipeline;
- documentation clearly distinguishes synthetic software evidence from later
  hardware, operational, human, and clinical validation.
