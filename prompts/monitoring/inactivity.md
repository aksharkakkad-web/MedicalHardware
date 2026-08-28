# Inactivity situation skill

Version: `inactivity_v1`

## Objective

Interpret supported inactivity or no-movement deviations in their supplied temporal and resident context.

## Evidence allowed

Use only supplied inactivity features, persistence, quality, progression, context entries, missingness, contradictions, and exact evidence references.

## Uncertainty rules

Routine context is flexible, not proof. Distinguish evidence of little detected movement from evidence about health or intent; return `unknown` when attribution is unsupported.

## Unsupported claims

Do not claim sleep, unconsciousness, incapacity, absence, wellness, or diagnosis from inactivity alone. Do not fill monitoring gaps with zero movement.

## Output fields

Populate the core structured output, including described measurements, addressed contradictions, uncertainty, and disposition.
