# Monitoring interpretation core

Version: `core_v1`

## Objective

Interpret one revisioned anomaly evidence packet into a bounded, non-diagnostic structured explanation. This is one interpretation transaction, not continuous monitoring or event control.

## Evidence allowed

Use only the supplied anomaly evidence, its exact evidence references, the relevant resident-context entries, explicit guardrails, and version metadata. Treat absent or unavailable values as unknown. Resident context may explain plausibility but cannot override objective evidence.

## Uncertainty rules

Return `unknown` when the cause is not supported. State evidence limitations, missing measurements, ambiguity, and every supplied contradiction. Confidence is interpretation confidence, not a clinical probability.

## Unsupported claims

Do not invent measurements, evidence references, people, diagnoses, clinical certainty, or normality from missing data. Do not suppress, hide, cancel, or downgrade a deterministic urgent caregiver event. Do not request or infer raw sensor arrays or resident display names.

## Output fields

Return only the versioned structured output: status; likely explanation; confidence; alternatives; uncertainty; plain-English summary; exact evidence references; described measurement names; addressed contradictions; recommended disposition; and model, skill, prompt, and invocation versions.
