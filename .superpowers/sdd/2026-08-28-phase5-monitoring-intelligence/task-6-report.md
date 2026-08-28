# Task 6 report: situation-specific AI interpretation boundary

## Status

Implemented and committed as `3915a2b` (`feat: add monitoring AI skill boundary`).

## Delivered

- Added immutable provider-neutral request/result types, interpretation/disposition enums, `LLMClient`, and an offline deterministic fake provider.
- Added an explicit rooted monitoring-skill registry and deterministic selection of `core` plus exactly one primary skill, with optional `multi_person` qualification.
- Added bounded request assembly from one immutable `EvidencePacket` revision and time-relevant versioned `ResidentMemory` entries.
- Preserved `overall_strength=None`, `missing_initiating_features`, contradictions, unknowns, provenance, and replay versions without raw sensor arrays or resident display names.
- Added structured output validation for invented evidence references, unavailable/unsupported measurement descriptions, diagnostic certainty, omitted contradictions, invalid enum values, confidence bounds, packet identity mismatches, and urgent deterministic-event downgrades.
- Added all nine versioned monitoring prompt skills, each covering objective, allowed evidence, uncertainty, unsupported claims, and output fields.

## TDD evidence

RED:

```text
python3 -m pytest tests/ai/test_monitoring_interpretation.py -q
ModuleNotFoundError: No module named 'backend.app.ai'
1 error, 1 pre-existing warning
```

Focused GREEN:

```text
python3 -m pytest tests/ai/test_monitoring_interpretation.py -q
14 passed, 1 pre-existing warning in 0.03s
```

Full suite:

```text
python3 -m pytest -q
477 passed, 85 subtests passed, 1 pre-existing warning in 15.48s
```

## Self-review

- Staged paths were limited to the 16 Task 6 implementation, prompt, and test files.
- `git diff --cached --check` passed.
- No network provider, stream monitoring, sensor math, event creation, diagnosis, or live policy mutation was added.
- The only warning was the repository's existing Starlette/httpx deprecation warning.

## Fix Round 1

Status: completed and committed as `52317fb` (`fix: harden monitoring AI interpretation boundary`).

### Root cause

The original result schema treated provider declarations and prose as partially trusted, echoed only partial provenance, and serialized every active/effective memory entry. The fix makes claims, alternatives, caregiver wording, provenance, and retrieved context independently inspectable and request-bound.

### Exact regression tests added

- `test_complete_result_exposes_ranked_evidence_bound_analysis`
- `test_context_retrieval_includes_relevant_typed_routine_and_denies_other_notes`
- `test_unknown_anomaly_retrieval_denies_context_without_an_explicit_match_rule`
- `test_validator_rejects_each_forged_provenance_field` (12 cases: anomaly ID, packet revision, model ID, model version, skill names, skill-bundle version, prompt version, invocation version, retrieval-contract version, output-schema version, relevant-context version, and request fingerprint)
- `test_empty_claim_declarations_cannot_hide_invented_numeric_prose`
- `test_medical_conclusions_are_rejected_on_every_text_surface` (8 cases: likely explanation, alternatives, uncertainty, plain-English summary, missing information, limitations, unsupported conclusions, and caregiver wording)
- `test_blank_uncertainty_is_rejected`
- `test_packet_and_attribution_limitations_cannot_be_omitted`
- `test_alternative_confidence_rank_and_references_are_validated`
- `test_caregiver_wording_cannot_describe_an_unavailable_measurement`

Existing request/result fixtures and the invented-reference test were strengthened to use the complete schema, required missingness/limitations, supporting versus contradicting references, full provenance, and deny-by-default degraded-context behavior.

### TDD and verification results

Fix Round 1 RED:

```text
python3 -m pytest tests/ai/test_monitoring_interpretation.py -q
37 failed, 5 passed, 1 pre-existing warning in 0.26s
```

The RED failures directly showed the unrelated degraded-case routine being forwarded and the absence of ranked alternatives, required limitation fields, retrieved-context references, request fingerprinting, and full provenance fields.

Focused GREEN:

```text
python3 -m pytest tests/ai/test_monitoring_interpretation.py -q
42 passed, 1 pre-existing warning in 0.05s
```

Full suite:

```text
python3 -m pytest -q
505 passed, 85 subtests passed, 1 pre-existing warning in 13.03s
```

### Fix summary

- Added immutable ranked alternatives with bounded-confidence validation and per-alternative supporting/contradicting references.
- Added top-level supporting/contradicting references, required missing information and limitations, unsupported conclusions, observation need, and separate caregiver wording.
- Bound results to every request provenance field and a SHA-256 fingerprint covering prompt, bounded payload/context, skill bundle, and model identity/version.
- Replaced active-note forwarding with deterministic typed/content relevance, explicit context references, stable ordering, a 20-entry bound, default exclusion of `general_context`, and no context for unknown/degraded skills without a match rule.
- Validated medical/certainty and numeric-measurement claims across every result text surface, including alternatives and caregiver wording, independent of declaration lists.
- No Task 7 files were modified.

## Fix Round 2

Status: completed and committed as `54ddf47` (`fix: control AI context and interpretation semantics`).

### Root cause

Fix Round 1 still inferred context relevance from resident-note prose and accepted open-ended provider prose after applying incomplete safety regexes. That architecture could leak an unrelated note through an ambiguous keyword and could never exhaustively validate arbitrary summary, caregiver, alternative, or declaration text.

### Exact regression tests added or strengthened

- `test_context_retrieval_includes_relevant_typed_routine_and_denies_other_notes` now explicitly selects `movement_routine`.
- `test_context_retrieval_defaults_to_no_resident_entries`
- `test_retirement_account_balance_note_never_leaks_without_explicit_selection`
- `test_explicit_context_ids_are_deduplicated_stably_ordered_and_fingerprinted`
- `test_explicit_context_rejects_invalid_entry_ids` (5 cases: unknown, retired, expired, future, and `general_context`)
- `test_explicit_context_selection_is_bounded`
- `test_validator_rejects_each_forged_provenance_field` now includes forged `schema_version`.
- `test_provider_cannot_override_deterministic_summary_with_pulse_claim`
- `test_provider_cannot_override_deterministic_caregiver_wording`
- `test_malformed_alternative_is_rejected_without_dereferencing_it`
- `test_pneumonia_is_rejected_as_an_uncontrolled_category` (likely explanation and alternative)
- `test_hidden_text_in_addressed_contradictions_is_rejected_as_undeclared`
- `test_required_controlled_fields_reject_blank_or_free_prose` (blank explanation, summary, caregiver wording, and uncontrolled uncertainty)
- `test_blank_alternative_label_is_rejected`
- `test_declared_identifier_fields_reject_extras` (missing information, limitations, non-allowlisted unsupported conclusion, and allowlisted-but-undeclared unsupported conclusion)
- `test_declared_identifier_fields_reject_omissions` (missing information and unsupported conclusions; existing tests already cover contradiction and limitation omissions)

Existing complete-result, fake-provider, unknown-result, alternative, context, and unavailable-measurement fixtures were updated to the controlled category/uncertainty and deterministic-rendering contract.

### TDD and verification results

Fix Round 2 RED:

```text
python3 -m pytest tests/ai/test_monitoring_interpretation.py -q
53 failed, 4 passed, 1 pre-existing warning in 0.31s
```

The RED failures began at the intentionally missing `relevant_context_entry_ids` API and reproduced the uncontrolled category/template/declaration, malformed-alternative, and schema-provenance gaps.

Focused GREEN:

```text
python3 -m pytest tests/ai/test_monitoring_interpretation.py -q
57 passed, 1 pre-existing warning in 0.05s
```

Full suite:

```text
python3 -m pytest -q
520 passed, 85 subtests passed, 1 pre-existing warning in 15.83s
```

### Fix summary

- Removed free-text context keyword matching. Context now defaults empty and accepts only explicit entry IDs that are deduplicated, sorted, bounded to 20, owned by the resident memory, active/effective at packet time, and non-general; explicitly requested invalid IDs fail visibly.
- The exact retrieved context references and payload remain bound into the SHA-256 request fingerprint.
- Added controlled `ExplanationCategory` and `UncertaintyCategory` values plus per-situation category allowlists.
- Replaced provider-authored summary/caregiver prose with exact backend templates derived from controlled category and disposition; validator rejects any mismatch generically.
- Missing information, limitations, addressed contradictions, and unsupported conclusions are exact request-declared identifiers. Unsupported conclusions also use a closed allowlist.
- Validator checks malformed alternatives before dereferencing, enforces required nonblank/controlled fields, and binds `schema_version` to the supported request/result version.
- No keyword or medical/measurement denylist remains in production validation, and no Task 7 file was modified.

## Fix Round 3

Status: completed in the Fix Round 3 commit.

### Root cause

Fix Round 2 validated semantic values but still coerced arbitrary scalars and used provider-controlled containers in `enumerate`, tuple unpacking, `set`, and `strip` before checking their runtime shapes. Context selection also created an entry-ID dictionary before establishing snapshot uniqueness, allowing a retired duplicate to overwrite an active entry during lookup.

### Exact regression tests added

- `test_context_snapshot_rejects_active_and_retired_duplicate_entry_ids`
- `test_untrusted_result_container_shapes_are_rejected_deterministically` (9 cases: alternatives, top-level supporting/contradicting evidence refs, described measurements, addressed contradictions, missing information, limitations, unsupported conclusions, and skill bundle)
- `test_untrusted_result_scalar_shapes_are_rejected_deterministically` (10 cases: interpretation ID, summary, caregiver wording, likely explanation, uncertainty, status, disposition, confidence, observation need, and model ID)
- `test_nested_alternative_reference_shapes_are_rejected_deterministically` (supporting and contradicting refs)
- `test_blank_interpretation_id_is_rejected`
- `test_declared_tuples_require_nonblank_string_items` (6 representative non-string/blank item cases)
- `test_semantic_declaration_tuples_reject_duplicates` (7 cases: contradictions, missing information, limitations, unsupported conclusions, supporting refs, contradicting refs, and described measurements)
- `test_alternative_reference_tuples_reject_duplicates` (supporting and contradicting refs)

### TDD and verification results

Fix Round 3 RED:

```text
python3 -m pytest tests/ai/test_monitoring_interpretation.py -q
36 failed, 59 passed, 1 pre-existing warning in 0.28s
```

The RED run reproduced raw `TypeError`/`AttributeError` paths for malformed containers and text, silent duplicate normalization, a blank accepted interpretation ID, and the active/retired duplicate memory-ID collision.

Focused GREEN:

```text
python3 -m pytest tests/ai/test_monitoring_interpretation.py -q
95 passed, 1 pre-existing warning in 0.06s
```

Full suite:

```text
python3 -m pytest -q
558 passed, 85 subtests passed, 1 pre-existing warning in 12.65s
```

### Fix summary

- Made `validate_interpretation` a total boundary for untrusted result objects through explicit result, scalar, enum, tuple, tuple-item, and nested-alternative guards before any coercion, iteration, unpacking, set construction, enum conversion, or string operation.
- Preserved deterministic semantic validation after successful shape validation, including exact provenance, controlled rendering, evidence/measurement support, declaration omissions/extras, and urgent-event protection.
- Enforced a nonblank interpretation ID and nonblank string tuple items, with duplicate rejection for all semantic declaration, measurement, and evidence-reference tuples, including nested alternative references.
- Rejected duplicate memory entry IDs across the entire snapshot before lookup, and serialized selected entries only from the exact active/effective non-general authorization map.
- `git diff --check` passed. The only warning was the repository's existing Starlette/httpx deprecation warning. No Task 7 files were modified.
