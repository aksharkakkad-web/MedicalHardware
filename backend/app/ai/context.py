"""Bounded serialization of evidence and relevant resident context."""

import json
from hashlib import sha256

from backend.app.ai.client import InterpretationRequest
from backend.app.ai.skills import select_skill_bundle
from backend.app.domain._validation import require_nonblank_text, require_strict_bool
from backend.app.domain.feedback import ResidentMemory
from backend.app.intelligence.evidence import EvidencePacket


_MAX_RELEVANT_MEMORY_ENTRIES = 20


def _anomaly_evidence_payload(packet: EvidencePacket) -> dict[str, object]:
    return {
        "agreements": list(packet.agreements),
        "anomaly_id": packet.anomaly_id,
        "baseline_id": packet.baseline_id,
        "baseline_policy_version": packet.baseline_policy_version,
        "changed_features": _feature_payload(packet),
        "config_version": packet.config_version,
        "contradictions": list(packet.contradictions),
        "current_time": packet.current_time.isoformat(),
        "evidence_limited": packet.evidence_limited,
        "evidence_refs": list(packet.evidence_refs),
        "feature_contract_version": packet.feature_contract_version,
        "filter_version": packet.filter_version,
        "frame_id": packet.frame_id,
        "limitations": list(packet.limitations),
        "lifecycle_state": packet.lifecycle_state.value,
        "missing_initiating_features": list(packet.missing_initiating_features),
        "missing_modalities": list(packet.missing_modalities),
        "monitoring_setup_version": packet.monitoring_setup_version,
        "overall_strength": packet.overall_strength,
        "packet_revision": packet.packet_revision,
        "progression": packet.progression,
        "room_id": packet.room_id,
        "strength_scale": packet.strength_scale,
        "unknowns": list(packet.unknowns),
    }


def _required_declarations(
    packet: EvidencePacket,
    skill_names: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    missing = tuple(
        sorted(
            {
                *packet.unknowns,
                *packet.missing_initiating_features,
                *packet.missing_modalities,
            }
        )
    )
    limitations = tuple(
        dict.fromkeys(
            (
                *packet.limitations,
                *(
                    ("resident_attribution_ambiguous",)
                    if "multi_person" in skill_names
                    else ()
                ),
            )
        )
    )
    unsupported = {"causal_explanation", "medical_diagnosis"}
    if "multi_person" in skill_names:
        unsupported.add("person_identity")
    if missing:
        unsupported.add("unobserved_measurement")
    return missing, limitations, tuple(sorted(unsupported))


def validate_interpretation_request_binding(
    packet: EvidencePacket,
    request: InterpretationRequest,
) -> None:
    """Bind a request to one exact stored packet and deterministic prompt bundle."""

    bundle = select_skill_bundle(packet)
    try:
        payload = json.loads(request.payload_json)
    except (TypeError, ValueError) as exc:
        raise ValueError("interpretation request is not canonical JSON") from exc
    if (
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
        != request.payload_json
    ):
        raise ValueError("interpretation request is not canonical JSON")
    if set(payload) != {
        "anomaly_evidence",
        "guardrails",
        "request_fingerprint",
        "resident_context",
        "schema_version",
        "skill_bundle",
        "versions",
    }:
        raise ValueError("interpretation request does not use the exact payload schema")
    missing, limitations, unsupported = _required_declarations(
        packet,
        bundle.skill_names,
    )
    context = payload.get("resident_context", {})
    context_entries = context.get("entries", ())
    context_entry_keys = {
        "context_kind",
        "context_ref",
        "description",
        "entry_id",
        "flexibility_note",
        "local_time_end",
        "local_time_start",
        "recurrence_note",
    }
    if (
        not isinstance(context, dict)
        or set(context) != {"entries", "resident_id", "version"}
        or not isinstance(context_entries, list)
        or any(
            not isinstance(item, dict) or set(item) != context_entry_keys
            for item in context_entries
        )
        or payload.get("guardrails")
        != {"urgent_deterministic_event": request.urgent_deterministic_event}
        or payload.get("schema_version") != request.schema_version
        or request.relevant_context_version
        != f"resident_memory_v{context.get('version')}"
    ):
        raise ValueError("interpretation request does not use the exact payload schema")
    expected = (
        (request.anomaly_id, packet.anomaly_id),
        (request.packet_revision, packet.packet_revision),
        (request.prompt, bundle.prompt),
        (request.skill_bundle, bundle.skill_names),
        (request.skill_bundle_version, bundle.bundle_version),
        (request.available_evidence_refs, packet.evidence_refs),
        (
            request.available_measurements,
            tuple(sorted({item.feature_name for item in packet.changed_features})),
        ),
        (
            request.unavailable_measurements,
            tuple(
                sorted(
                    {
                        *packet.missing_initiating_features,
                        *packet.missing_modalities,
                    }
                )
            ),
        ),
        (request.contradictions, packet.contradictions),
        (request.required_missing_information, missing),
        (request.required_limitations, limitations),
        (request.required_unsupported_conclusions, unsupported),
        (
            request.retrieved_context_refs,
            tuple(item.get("context_ref") for item in context_entries),
        ),
        (payload.get("anomaly_evidence"), _anomaly_evidence_payload(packet)),
        (payload.get("skill_bundle"), list(bundle.skill_names)),
        (context.get("resident_id"), packet.resident_id),
    )
    if any(actual != wanted for actual, wanted in expected):
        raise ValueError("interpretation request does not match stored evidence packet")
    versions = payload.get("versions", {})
    if versions != {
        "invocation": request.invocation_version,
        "model": request.model_version,
        "output_schema": request.output_schema_version,
        "prompt": request.prompt_version,
        "relevant_context": request.relevant_context_version,
        "retrieval_contract": request.retrieval_contract_version,
        "skill_bundle": request.skill_bundle_version,
        "skills": list(bundle.skill_versions),
    }:
        raise ValueError(
            "interpretation request versions do not match stored evidence packet"
        )
    fingerprint_payload = dict(payload)
    fingerprint_payload.pop("request_fingerprint", None)
    expected_fingerprint = _request_fingerprint(
        payload=fingerprint_payload,
        prompt=request.prompt,
        skill_bundle=request.skill_bundle,
        model_id=request.model_id,
        model_version=request.model_version,
    )
    if (
        payload.get("request_fingerprint") != expected_fingerprint
        or request.request_fingerprint != expected_fingerprint
    ):
        raise ValueError(
            "interpretation request fingerprint does not match stored evidence packet"
        )


def _feature_payload(packet: EvidencePacket) -> list[dict[str, object]]:
    ref_by_name = {
        reference.rsplit("/", 1)[-1]: reference
        for reference in packet.evidence_refs
    }
    return [
        {
            "direction": item.direction,
            "evidence_ref": ref_by_name.get(item.feature_name),
            "feature_name": item.feature_name,
            "observation_id": item.observation_id,
            "persistence_frames": item.persistence_frames,
            "quality_class": item.quality_class.value,
            "quality_reasons": list(item.quality_reasons),
            "robust_z": item.robust_z,
            "source": item.source,
            "trajectory": item.trajectory,
            "unit": item.unit,
            "value": item.value,
        }
        for item in packet.changed_features
    ]


def _context_ref(resident_memory: ResidentMemory, entry_id: str) -> str:
    return (
        f"resident-memory://{resident_memory.resident_id}/"
        f"{resident_memory.version}/entries/{entry_id}"
    )


def _request_fingerprint(
    *,
    payload: dict[str, object],
    prompt: str,
    skill_bundle: tuple[str, ...],
    model_id: str,
    model_version: str,
) -> str:
    material = {
        "model_id": model_id,
        "model_version": model_version,
        "payload": payload,
        "prompt": prompt,
        "skill_bundle": list(skill_bundle),
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def _select_context_entries(
    resident_memory: ResidentMemory,
    packet: EvidencePacket,
    requested_ids: tuple[str, ...],
) -> tuple[object, ...]:
    if not isinstance(requested_ids, tuple):
        raise ValueError("relevant_context_entry_ids must be a tuple")
    normalized_ids = tuple(
        sorted(
            {
                require_nonblank_text(entry_id, "relevant_context_entry_ids")
                for entry_id in requested_ids
            }
        )
    )
    if len(normalized_ids) > _MAX_RELEVANT_MEMORY_ENTRIES:
        raise ValueError("relevant_context_entry_ids exceeds 20 entries")
    all_entries_by_id = {}
    for entry in resident_memory.entries:
        if entry.entry_id in all_entries_by_id:
            raise ValueError(
                f"resident memory contains duplicate entry_id: {entry.entry_id}"
            )
        all_entries_by_id[entry.entry_id] = entry
    authorized_entries_by_id = {
        entry.entry_id: entry
        for entry in resident_memory.relevant_entries(packet.current_time)
        if entry.context_kind != "general_context"
    }
    selected = []
    for entry_id in normalized_ids:
        entry = all_entries_by_id.get(entry_id)
        if entry is None:
            raise ValueError(f"requested context entry is unknown: {entry_id}")
        if entry.context_kind == "general_context":
            raise ValueError(
                f"requested context entry uses disallowed context kind: {entry_id}"
            )
        if entry_id not in authorized_entries_by_id:
            raise ValueError(
                f"requested context entry is not active/effective: {entry_id}"
            )
        selected.append(authorized_entries_by_id[entry_id])
    return tuple(selected)


def build_interpretation_request(
    packet: EvidencePacket,
    resident_memory: ResidentMemory,
    *,
    model_id: str,
    model_version: str,
    urgent_deterministic_event: bool = False,
    relevant_context_entry_ids: tuple[str, ...] = (),
) -> InterpretationRequest:
    """Build one replayable request without raw arrays or profile identifiers."""

    if not isinstance(packet, EvidencePacket):
        raise ValueError("packet must be an EvidencePacket")
    if not isinstance(resident_memory, ResidentMemory):
        raise ValueError("resident_memory must be a ResidentMemory")
    if resident_memory.resident_id != packet.resident_id:
        raise ValueError("resident memory must belong to packet resident")
    model_id = require_nonblank_text(model_id, "model_id")
    model_version = require_nonblank_text(model_version, "model_version")
    urgent = require_strict_bool(
        urgent_deterministic_event,
        "urgent_deterministic_event",
    )
    bundle = select_skill_bundle(packet)
    relevant_entries = _select_context_entries(
        resident_memory,
        packet,
        relevant_context_entry_ids,
    )
    retrieved_context_refs = tuple(
        _context_ref(resident_memory, entry.entry_id) for entry in relevant_entries
    )
    retrieval_version = "relevant_resident_context_v1"
    output_version = "monitoring_interpretation_output_v1"
    prompt_version = "monitoring_interpreter_v1"
    invocation_version = "monitoring_invocation_v1"
    relevant_context_version = f"resident_memory_v{resident_memory.version}"
    payload = {
        "anomaly_evidence": _anomaly_evidence_payload(packet),
        "guardrails": {"urgent_deterministic_event": urgent},
        "resident_context": {
            "entries": [
                {
                    "context_kind": entry.context_kind,
                    "context_ref": _context_ref(resident_memory, entry.entry_id),
                    "description": entry.description,
                    "entry_id": entry.entry_id,
                    "flexibility_note": entry.flexibility_note,
                    "local_time_end": entry.local_time_end,
                    "local_time_start": entry.local_time_start,
                    "recurrence_note": entry.recurrence_note,
                }
                for entry in relevant_entries
            ],
            "resident_id": packet.resident_id,
            "version": resident_memory.version,
        },
        "schema_version": "1.0",
        "skill_bundle": list(bundle.skill_names),
        "versions": {
            "invocation": invocation_version,
            "model": model_version,
            "output_schema": output_version,
            "prompt": prompt_version,
            "relevant_context": relevant_context_version,
            "retrieval_contract": retrieval_version,
            "skill_bundle": bundle.bundle_version,
            "skills": list(bundle.skill_versions),
        },
    }
    request_fingerprint = _request_fingerprint(
        payload=payload,
        prompt=bundle.prompt,
        skill_bundle=bundle.skill_names,
        model_id=model_id,
        model_version=model_version,
    )
    payload["request_fingerprint"] = request_fingerprint
    (
        required_missing_information,
        required_limitations,
        required_unsupported_conclusions,
    ) = _required_declarations(packet, bundle.skill_names)
    return InterpretationRequest(
        anomaly_id=packet.anomaly_id,
        packet_revision=packet.packet_revision,
        prompt=bundle.prompt,
        skill_bundle=bundle.skill_names,
        prompt_version=prompt_version,
        skill_bundle_version=bundle.bundle_version,
        retrieval_contract_version=retrieval_version,
        output_schema_version=output_version,
        model_id=model_id,
        model_version=model_version,
        invocation_version=invocation_version,
        relevant_context_version=relevant_context_version,
        payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        available_evidence_refs=packet.evidence_refs,
        available_measurements=tuple(
            sorted({item.feature_name for item in packet.changed_features})
        ),
        unavailable_measurements=tuple(
            sorted(
                {
                    *packet.missing_initiating_features,
                    *packet.missing_modalities,
                }
            )
        ),
        contradictions=packet.contradictions,
        required_missing_information=required_missing_information,
        required_limitations=required_limitations,
        required_unsupported_conclusions=required_unsupported_conclusions,
        retrieved_context_refs=retrieved_context_refs,
        request_fingerprint=request_fingerprint,
        urgent_deterministic_event=urgent,
    )


__all__ = [
    "InterpretationRequest",
    "build_interpretation_request",
    "validate_interpretation_request_binding",
]
