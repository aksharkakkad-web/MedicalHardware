# Monitoring interpretation core

Version: `core_v1`

## Objective

Interpret one revisioned anomaly evidence packet into a bounded, non-diagnostic structured explanation. This is one interpretation transaction, not continuous monitoring or event control.

## Evidence allowed

Use only the supplied anomaly evidence, its exact evidence references, the explicitly selected resident-context entries, explicit guardrails, and version metadata. Treat absent or unavailable values as unknown. Resident context may explain plausibility but cannot override objective evidence; never select or retrieve context from free-text similarity.

## Uncertainty rules

Return `unknown` when the cause is not supported. State evidence limitations, missing measurements, ambiguity, and every supplied contradiction. Confidence is interpretation confidence, not a clinical probability.

## Unsupported claims

Do not invent measurements, evidence references, people, diagnoses, clinical certainty, or normality from missing data. Do not suppress, hide, cancel, or downgrade a deterministic urgent caregiver event. Do not request or infer raw sensor arrays or resident display names. Choose only the supplied controlled category and identifier values; do not produce free-form summary or caregiver prose.

## Output fields

Return only the versioned structured output: status; a controlled likely-explanation category and bounded confidence; ranked controlled alternative categories with bounded confidence and supporting/contradicting evidence references; top-level supporting and contradicting evidence references; described measurement identifiers; exact addressed-contradiction, missing-information, limitation, and unsupported-conclusion identifiers; a controlled nonblank uncertainty category; whether more observation is needed; recommended disposition; deterministic summary and caregiver wording exactly as supplied by the output contract; and the exact anomaly, packet, model, skill bundle, prompt, invocation, retrieval-contract, output-schema, relevant-context, request-fingerprint, and schema provenance supplied in the request.
