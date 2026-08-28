# Respiration situation skill

Version: `respiration_v1`

## Objective

Interpret supported respiratory-feature deviations as non-diagnostic sensor patterns.

## Evidence allowed

Use only supplied respiratory measurements, units, quality, personal-baseline deviations, progression, missingness, contradictions, and exact evidence references.

## Uncertainty rules

Missing initiating respiratory evidence makes overall strength unavailable. State that sensor evidence cannot establish physiology or cause; use `unknown` when support is insufficient.

## Unsupported claims

Do not invent respiratory rate, distress, apnea, disease, or clinical thresholds. Do not describe a missing or unusable modality as measured.

## Output fields

Populate the core structured output and explicitly list described measurement names, evidence references, limitations, and contradictions.
