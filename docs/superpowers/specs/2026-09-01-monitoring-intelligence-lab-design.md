# Monitoring Intelligence Lab Design

**Date:** 2026-09-01  
**Status:** Proposed implementation specification  
**Owner:** Akshar — backend intelligence and evaluation  
**Related foundation:** `2026-08-28-phase5-monitoring-intelligence-design.md`

## Product decision

Build one repeatable evaluation lab around the monitoring-intelligence system
that already exists. Do not create a second anomaly engine or a second event
system.

The lab uses:

- the deterministic fake provider for very large, exact software testing;
- Gemini 3.7 Flash for broad, free development-time interpretation testing;
- Terra as the intended production primary model;
- Sol as the intended production fallback model;
- the same evidence packet, skill files, output contract, validator, policy,
  event lifecycle, feedback, and memory path for every provider.

Gemini is a development model, not the production authority. A large Gemini
run can improve the skills and expose weaknesses, but it cannot certify Terra
or Sol. Before production readiness is claimed, Terra and Sol must pass a
smaller release-gate campaign using the exact production configuration.

## What this can and cannot prove

This lab can provide strong engineering evidence that:

- the backend behaves correctly over a wide range of synthetic timelines;
- normal human variation usually stays quiet;
- meaningful changes reach the correct evidence and event paths;
- urgent deterministic safety rules do not depend on an LLM;
- LLM outputs are grounded, structured, contained, and safely rejected when
  invalid;
- acknowledgments, cooldowns, recurrence, feedback, resident memory, and
  controlled baseline learning behave consistently;
- changes can be compared against prior versions with saved evidence.

It cannot prove clinical performance, hardware detection accuracy, real-world
false-alert rates, or medical safety. Those require simulated edge telemetry,
controlled hardware recordings, real operating time, and later field
validation. Reports must state this limitation prominently.

## Approaches considered

### Selected: one broad development model plus production-model release gates

Gemini performs the large live-model development campaign. Terra and Sol run
only the smaller, high-value production rehearsal. This gives broad feedback
without spending production-model money on cases already caught by exact
software tests.

### Rejected: run Terra and Sol for every generated case

This would test the final models directly, but it would make early prompt and
scenario iteration unnecessarily expensive. Most generated cases are better
used to test deterministic logic without an external model call.

### Rejected: combine Gemini, Gemma, GLM, DeepSeek, and xAI in the product

Multiple simultaneous models add latency, disagreement handling, provider
failure modes, and evaluation ambiguity. They do not automatically improve
caregiver decisions. Alternative models may be compared later, but V1 ships
one primary and one explicit fallback rather than a voting ensemble.

## Complete product flow under test

```text
synthetic room timeline
→ normalized observations
→ quality and presence decisions
→ personal baseline and routine context
→ anomaly candidate and persistence filter
→ rich evidence packet
→ urgent deterministic bypass, when applicable
→ situation skill + bounded resident context
→ structured LLM interpretation
→ schema, evidence, and safety validation
→ deterministic disposition policy
→ event creation/update/suppression/recovery
→ caregiver acknowledgment and feedback
→ resident memory proposal and controlled baseline learning
→ replay, metrics, failures, and version comparison
```

The expected answer remains outside this flow. The system never receives the
scenario label, expected event, or later feedback while making the original
decision.

## Test truth model

Each case belongs to one of three expectation classes:

1. **Must detect** — missing the meaningful change or safety path is a failure.
2. **Must stay quiet** — creating unnecessary caregiver work is a failure.
3. **Gray zone** — several conservative outcomes are acceptable, but factual,
   grounding, attribution, and lifecycle rules still have exact expectations.

Truth comes from versioned scenario definitions and founder-reviewed expected
product behavior. An LLM never grades another LLM as the sole source of truth.
Automatic grading may use deterministic checks only; human review resolves
new or ambiguous product questions.

## Scenario library

The existing 24 stable Phase 5 scenarios remain the canonical seed set. The
lab expands them into at least 120 founder-reviewable canonical timelines,
distributed across these 12 clusters:

1. ordinary movement and day-to-day variation;
2. sleep, reading, resting, and inactivity;
3. bathroom trips, away periods, returns, and uncertain presence;
4. flexible routines, planned changes, and temporary context;
5. visitors, possible multiple people, and attribution ambiguity;
6. elevated, unusual, and repetitive movement;
7. prolonged inactivity and slow changes;
8. fall-like transitions and common confounders;
9. respiration deviation with good, weak, and contradictory quality;
10. missing, stale, frozen, delayed, duplicated, and conflicting input;
11. event acknowledgment, cooldown, escalation, recovery, and recurrence;
12. feedback, resident memory, baseline adoption, provider failure, and
    adversarial or invalid AI output.

Canonical cases include complete timelines, not isolated labels. Each defines:

- starting baseline, routine context, resident memory, and event history;
- observations and quality changes over time;
- information intentionally missing or contradictory;
- expected internal path and allowed product outcomes;
- forbidden outcomes;
- expected caregiver work or expected quiet behavior;
- expected learning behavior after feedback;
- the reason the case exists.

## Large synthetic generation

The lab creates deterministic variations from canonical timelines using saved
random seeds. Variations include:

- time-of-day and duration shifts;
- natural day-to-day baseline variance;
- different degrees of signal strength and confidence;
- boundary values immediately above and below persistence thresholds;
- delayed, duplicated, reordered, missing, and conflicting observations;
- visitor and away intervals inserted at different points;
- prior routine and memory entries that are relevant, irrelevant, temporary,
  expired, or conflicting;
- active, acknowledged, resolved, cooled-down, and recurring event histories;
- provider timeout, rate limit, malformed JSON, unsupported claims, and
  contradictory recommendations;
- sequential feedback that should or should not become resident memory or a
  numerical baseline update.

The generator must be reproducible. Every case has a stable case ID, parent
scenario ID, seed, generator version, configuration versions, and expected
behavior. The ground-truth label is stored beside the evaluation case and is
never included in the production request.

## Campaign scale

### Exact software campaign

- At least 100,000 distinct generated timelines.
- Ten declared seeds or perturbation passes.
- Target: at least 1,000,000 complete pipeline executions.
- Uses the deterministic fake provider and injected provider failures.
- Runs without network access or API cost.

This campaign proves software invariants, state transitions, replay behavior,
boundary handling, and large-scale metric accounting.

### Gemini development campaign

- Target: 100,000 saved live interpretations over time, limited by the free
  project quota.
- First meaningful checkpoint: 25,000 balanced interpretations.
- At least 10,000 cases form a fixed comparison set that future prompt and
  model versions must replay.
- At least 2,000 critical or ambiguous cases are repeated five times to
  measure classification consistency.
- The run is resumable. Rate-limit exhaustion pauses safely and continues from
  the last saved case rather than restarting or silently dropping work.

The campaign never automatically enables billing, changes provider, or sends
real patient information. The runner accepts a maximum-call budget and records
all quota pauses. Google billing status remains an account setting that the
software cannot guarantee; it must be checked in AI Studio before a large run.

### Terra/Sol production release gate

This gate is not part of the free Gemini campaign and requires a separate cost
confirmation immediately before execution.

- Terra: 5,000 balanced and difficult cases using the final production setup.
- Sol: 1,000 highest-risk, Gemini/Terra disagreement, and fallback cases.
- Explicit fallback drills simulate Terra timeout, invalid output, and
  unavailability, then prove that Sol receives the same bounded request.
- Both models replay the fixed comparison set needed for release decisions.

Passing Gemini is not a substitute for this gate.

## Gemini provider behavior

Add a real Gemini client behind the existing provider-neutral `LLMClient`
boundary. The monitoring engine must not contain Gemini-specific logic.

The client must:

- pin `gemini-3.7-flash`, never use a drifting `latest` alias;
- request strict structured JSON matching the existing interpretation schema;
- use low or disabled thinking for bulk classification unless a named
  experiment explicitly changes it;
- use deterministic generation settings where supported;
- allow up to 180 seconds for a response;
- retry only bounded transport and rate-limit failures;
- preserve the original first response for validity and latency measurement;
- checkpoint before and after every external call;
- redact credentials from commands, logs, artifacts, errors, and reports;
- record provider, requested model, returned model version, token usage,
  latency, finish reason, skill bundle, prompt version, schema version,
  retrieval version, and request fingerprint;
- return `UNAVAILABLE` on exhausted retries so deterministic fallback policy
  continues safely.

The API key remains only in ignored local configuration or a future secrets
manager. It is never committed or copied into an evaluation artifact.

## Skill and context evaluation

Every situation skill is tested independently and in the full pipeline:

- core safety and grounding rules;
- fall-like;
- inactivity;
- movement;
- respiration;
- routine change;
- monitoring degradation;
- possible multiple people;
- unknown anomaly;
- caregiver feedback interpretation;
- resident-memory update proposals.

Tests prove that the selected skill matches the evidence family, relevant
context is included, unrelated history is excluded, and prompt or note text
cannot introduce unsupported measurements or override safety policy.

The request may include bounded evidence, relevant routine or memory entries,
selected prior events, and relevant feedback. It must not include raw sensor
arrays, unlimited history, other residents' data, or the hidden expected
answer.

## What is measured

Metrics are calculated overall and separately for every scenario cluster,
expectation class, confidence band, quality state, skill, provider, prompt
version, and policy version.

### Detection and quietness

- must-detect recall;
- must-stay-quiet success rate;
- meaningful anomaly recall;
- false anomaly packets;
- false awareness items and caregiver events;
- urgent, packet, and event latency;
- priority and disposition confusion matrices.

### AI quality

- first-response JSON validity;
- validated-result rate;
- correct objective category and acceptable alternatives;
- supported and unsupported factual claims;
- invented measurements or references;
- missing uncertainty or limitations;
- attribution guesses during away or multiple-person states;
- wording safety and non-diagnostic language;
- repeated-run classification consistency;
- timeout, retry, and fallback rates;
- input, output, and thinking-token usage.

### Lifecycle and learning

- duplicate event rate;
- acknowledgment/cooldown correctness;
- escalation and recurrence lineage;
- recovery timing and false closure;
- memory changes with and without explicit feedback;
- temporary-context expiry;
- clean-window requirements for baseline adoption;
- baseline contamination;
- rollback and replay reproducibility.

### System integrity

- cross-tenant or cross-resident leakage;
- idempotency under duplicate and reordered input;
- restart and resume correctness;
- deterministic replay equality;
- artifact completeness and checksums;
- wall-clock latency and throughput.

## Zero-tolerance hard gates

Any occurrence fails the campaign regardless of aggregate scores:

- an urgent deterministic trigger is suppressed or downgraded by an LLM;
- invented measurements, unavailable values, or nonexistent evidence reach
  caregiver-facing product state;
- the system guesses resident attribution while presence is ambiguous;
- away, visitor, poor-quality, active-anomaly, setup-change, or recovery data
  contaminates the personal baseline;
- one continuous condition creates duplicate caregiver events;
- a replay creates different deterministic state from identical versions and
  inputs;
- one tenant or resident receives another tenant or resident's information;
- invalid structured output is accepted as valid;
- AI failure prevents deterministic safety policy from continuing;
- feedback directly changes global safety policy or silently rewrites original
  evidence;
- numerical baseline learning occurs without eligible clean observations;
- acknowledgment falsely closes the underlying anomaly.

## Initial engineering release targets

The following are engineering targets for synthetic evaluation, not clinical
claims:

- 100% pass on all zero-tolerance hard gates;
- 100% recall on founder-reviewed urgent and must-detect canonical cases;
- at least 98% recall across generated meaningful cases;
- at least 99% quiet behavior across generated must-stay-quiet cases;
- at least 99.5% first-response schema validity for the chosen live-model
  configuration, while containment of invalid output remains 100%;
- at least 98% classification consistency across repeated critical cases;
- zero baseline contamination, duplicate replay events, and data leakage;
- 100% checkpoint recovery after an intentionally interrupted campaign.

Targets that fail are not averaged away. The report shows the failing cluster,
case IDs, severity, evidence, and whether the problem belongs to scenario
truth, deterministic logic, skill/context, provider behavior, validation,
policy, lifecycle, or learning.

## Failure-review loop

Every campaign follows the same loop:

1. freeze versions, seeds, scenario catalog, and run budget;
2. run the exact deterministic suite;
3. run generated deterministic cases;
4. run the selected live-model campaign from saved evidence packets;
5. validate and grade every result;
6. stop immediately on a zero-tolerance hard-gate violation;
7. cluster ordinary failures by root cause;
8. review representative failures and correct scenario truth when necessary;
9. change one bounded component: filter, context, skill, validator, or policy;
10. replay the fixed regression set and full relevant campaign;
11. compare against the last accepted run;
12. accept only changes that fix the target problem without introducing a
    worse safety or quietness regression.

Every confirmed failure becomes a permanent regression case.

## Run artifacts

Large local artifacts live under an ignored
`eval-results/monitoring/<run-id>/` directory. Every run saves:

- `manifest.json` — purpose, versions, seeds, provider, budget, timestamps;
- `cases-*.jsonl.gz` — generated inputs, hidden expectations, and IDs;
- `responses-*.jsonl.gz` — redacted requests, raw model results, validation;
- `failures.jsonl` — all failed cases with root-cause status;
- `metrics.json` — complete aggregate and sliced measurements;
- `hard-gates.json` — each invariant and supporting case IDs;
- `comparison.json` — differences from the prior accepted run;
- `report.md` — founder-readable outcome and limitations;
- `checksums.json` — artifact integrity;
- `checkpoint.json` — resumable progress and quota state.

Reports never contain API keys, raw secrets, or real patient information.
Selected accepted summaries may be copied into versioned documentation; large
raw artifacts remain local or move to an approved private artifact store.

## Module boundaries

Extend the existing evaluation system rather than rebuilding it:

```text
backend/app/ai/
├── client.py                 existing provider-neutral contract
└── gemini.py                 Gemini provider only

prompts/monitoring/
├── existing situation skills
├── feedback_agent.md
└── resident_memory_updater.md

evals/monitoring/
├── scenarios.py             existing 24 stable cases
├── metrics.py               existing Phase 5 metrics and gates
├── replay.py                existing canonical replay
├── taxonomy.py              expectation classes and scenario clusters
├── generation.py            deterministic timeline variations
├── grading.py               exact and allowed-outcome grading
├── campaign.py              batching, checkpointing, resume, quota handling
├── artifacts.py             manifests, chunks, checksums, reports
└── cli.py                   one operator entrypoint
```

The generator, expected answers, and graders stay outside production modules.
The provider client is the only network-aware component used by the monitoring
engine.

## Commands and operating modes

One evaluation entrypoint exposes clear modes:

- `smoke` — canonical cases and configuration validation;
- `pr` — deterministic regression and a bounded generated sample;
- `mass` — one-million-execution offline campaign;
- `gemini` — resumable free-quota live campaign;
- `compare` — compare two saved runs;
- `release` — Terra/Sol production gate, disabled until separately configured
  and cost-confirmed.

The default mode never makes a paid call. Live modes require an explicit
provider, call limit, and artifact directory.

## Implementation checkpoints

### Checkpoint 1 — Evaluation contracts and artifact safety

Scenario taxonomy, truth classes, manifests, redaction, checkpoints, and
artifact formats. Existing 24-case replay remains unchanged and passing.

### Checkpoint 2 — Gemini provider and strict validation

Pinned model, structured output, bounded thinking, timeout/retry behavior,
usage accounting, credential redaction, fake transport tests, and a tiny live
smoke test.

### Checkpoint 3 — Canonical expansion and deterministic generation

At least 120 reviewable timelines, seeded variations across all 12 clusters,
boundary and failure injection, and proof that hidden truth never enters the
production request.

### Checkpoint 4 — Campaign runner and reporting

Chunked execution, interruption/resume, rate-limit pause, metrics, hard gates,
failure clustering, comparisons, checksums, and founder-readable reports.

### Checkpoint 5 — Full deterministic campaign

At least 1,000,000 complete executions, saved evidence, independent code
review, full regression tests, and documented failures or passes.

### Checkpoint 6 — Gemini development campaign

Quota-aware live execution, first 25,000-result checkpoint, critical repeats,
skill/context improvements through the review loop, and a final accepted
Gemini development report.

### Checkpoint 7 — Product convergence and later production gate

Rishit's frontend scenario flow consumes ordinary backend contracts, Phase 6
simulated telemetry drives the same intelligence boundary, and Terra/Sol run
the separately approved production release campaign before launch.

## Completion definition

The current intelligence-lab phase is complete when:

1. the existing 24-case replay still passes exactly;
2. one command can run and resume every declared campaign mode;
3. at least 120 canonical timelines and all 12 clusters are represented;
4. the one-million-execution deterministic campaign completes with artifacts;
5. Gemini 3.7 Flash produces strictly validated interpretations through the
   existing engine without controlling urgent safety policy;
6. the first 25,000 balanced Gemini checkpoint completes, or the free quota is
   transparently documented with a resumable campaign still in progress;
7. every zero-tolerance hard gate passes for the accepted run;
8. all failures, metrics, versions, limitations, and costs are preserved;
9. the result clearly separates synthetic engineering evidence from later
   telemetry, hardware, field, and production-model validation;
10. Terra/Sol release-gate requirements are ready but cannot be marked passed
    until those models themselves are run.

