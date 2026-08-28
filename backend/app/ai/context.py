"""Bounded serialization of evidence and relevant resident context."""

import json
from hashlib import sha256
from math import isfinite
from sys import float_info

from backend.app.ai.client import InterpretationRequest
from backend.app.ai.skills import select_skill_bundle
from backend.app.domain._validation import require_nonblank_text, require_strict_bool
from backend.app.domain.feedback import ResidentMemory
from backend.app.intelligence.evidence import EvidencePacket


_MAX_RELEVANT_MEMORY_ENTRIES = 20
_MAX_FINITE_FLOAT_INTEGER = int(float_info.max)
_REQUEST_TEXT_FIELDS = {
    "anomaly_id",
    "invocation_version",
    "model_id",
    "model_version",
    "output_schema_version",
    "payload_json",
    "prompt",
    "prompt_version",
    "relevant_context_version",
    "request_fingerprint",
    "retrieval_contract_version",
    "schema_version",
    "skill_bundle_version",
}
_REQUEST_TUPLE_FIELDS = {
    "available_evidence_refs",
    "available_measurements",
    "contradictions",
    "required_limitations",
    "required_missing_information",
    "required_unsupported_conclusions",
    "retrieved_context_refs",
    "skill_bundle",
    "unavailable_measurements",
}
_PRIMARY_SKILLS = {
    "fall_like",
    "inactivity",
    "monitoring_degraded",
    "movement",
    "respiration",
    "routine_change",
    "unknown_anomaly",
}
_ANOMALY_EVIDENCE_KEYS = {
    "agreements",
    "anomaly_id",
    "baseline_id",
    "baseline_policy_version",
    "changed_features",
    "config_version",
    "contradictions",
    "current_time",
    "evidence_limited",
    "evidence_refs",
    "feature_contract_version",
    "filter_version",
    "frame_id",
    "limitations",
    "lifecycle_state",
    "missing_initiating_features",
    "missing_modalities",
    "monitoring_setup_version",
    "overall_strength",
    "packet_revision",
    "progression",
    "room_id",
    "strength_scale",
    "unknowns",
}
_CHANGED_FEATURE_KEYS = {
    "direction",
    "evidence_ref",
    "feature_name",
    "observation_id",
    "persistence_frames",
    "quality_class",
    "quality_reasons",
    "robust_z",
    "source",
    "trajectory",
    "unit",
    "value",
}
_CONTEXT_ENTRY_KEYS = {
    "context_kind",
    "context_ref",
    "description",
    "entry_id",
    "flexibility_note",
    "local_time_end",
    "local_time_start",
    "recurrence_note",
}


def _text_list(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and bool(item.strip()) for item in value
    )


def _number_or_none(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return abs(value) <= _MAX_FINITE_FLOAT_INTEGER
    return isinstance(value, float) and isfinite(value)


def _number(value: object) -> bool:
    return value is not None and _number_or_none(value)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def validate_interpretation_request_shape(request: InterpretationRequest) -> None:
    """Validate the complete outer request before downstream consumers use it."""

    if not isinstance(request, InterpretationRequest):
        raise ValueError("interpretation request has invalid structure")
    for field in _REQUEST_TEXT_FIELDS:
        value = getattr(request, field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"interpretation request {field} must be text")
    for field in _REQUEST_TUPLE_FIELDS:
        value = getattr(request, field)
        if not isinstance(value, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            raise ValueError(f"interpretation request {field} must be a text tuple")
    if (
        isinstance(request.packet_revision, bool)
        or not isinstance(request.packet_revision, int)
        or request.packet_revision < 1
    ):
        raise ValueError("interpretation request packet_revision must be positive")
    if not isinstance(request.urgent_deterministic_event, bool):
        raise ValueError("interpretation request urgent flag must be boolean")
    if (
        len(request.skill_bundle) not in (2, 3)
        or request.skill_bundle[0] != "core"
        or request.skill_bundle[1] not in _PRIMARY_SKILLS
        or (
            len(request.skill_bundle) == 3
            and request.skill_bundle[2] != "multi_person"
        )
    ):
        raise ValueError("interpretation request skill bundle is malformed")


def validate_interpretation_request_payload(
    request: InterpretationRequest,
) -> tuple[str, int, tuple[str, ...]]:
    """Validate embedded request JSON as a total canonical trust boundary."""

    if not isinstance(request, InterpretationRequest) or not isinstance(
        request.payload_json,
        str,
    ):
        raise ValueError("interpretation request payload must be JSON text")
    try:
        payload = json.loads(request.payload_json)
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        raise ValueError("interpretation request is not canonical JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("interpretation request payload must be an object")
    try:
        canonical_payload = _canonical_json(payload)
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        raise ValueError("interpretation request is not canonical JSON") from exc
    if canonical_payload != request.payload_json:
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
    anomaly = payload["anomaly_evidence"]
    context = payload["resident_context"]
    guardrails = payload["guardrails"]
    versions = payload["versions"]
    if not isinstance(anomaly, dict) or set(anomaly) != _ANOMALY_EVIDENCE_KEYS:
        raise ValueError("interpretation anomaly evidence must use the exact schema")
    for field in (
        "agreements",
        "contradictions",
        "evidence_refs",
        "limitations",
        "missing_initiating_features",
        "missing_modalities",
        "unknowns",
    ):
        if not _text_list(anomaly[field]):
            raise ValueError(f"interpretation anomaly {field} must be text list")
    changed_features = anomaly["changed_features"]
    if not isinstance(changed_features, list) or any(
        not isinstance(item, dict)
        or set(item) != _CHANGED_FEATURE_KEYS
        or not _text_list(item["quality_reasons"])
        or any(
            not isinstance(item[field], str) or not item[field].strip()
            for field in (
                "direction",
                "feature_name",
                "observation_id",
                "quality_class",
                "source",
                "trajectory",
                "unit",
            )
        )
        or (
            item["evidence_ref"] is not None
            and not isinstance(item["evidence_ref"], str)
        )
        or isinstance(item["persistence_frames"], bool)
        or not isinstance(item["persistence_frames"], int)
        or item["persistence_frames"] < 0
        or not _number(item["robust_z"])
        or not _number(item["value"])
        for item in changed_features
    ):
        raise ValueError("interpretation changed features must use the exact schema")
    for field in (
        "anomaly_id",
        "baseline_id",
        "baseline_policy_version",
        "config_version",
        "current_time",
        "feature_contract_version",
        "filter_version",
        "frame_id",
        "lifecycle_state",
        "monitoring_setup_version",
        "progression",
        "room_id",
        "strength_scale",
    ):
        if not isinstance(anomaly[field], str) or not anomaly[field].strip():
            raise ValueError(f"interpretation anomaly {field} must be text")
    if (
        not isinstance(anomaly["evidence_limited"], bool)
        or isinstance(anomaly["packet_revision"], bool)
        or not isinstance(anomaly["packet_revision"], int)
        or anomaly["packet_revision"] < 1
        or not _number_or_none(anomaly["overall_strength"])
    ):
        raise ValueError("interpretation anomaly scalar provenance is malformed")
    if (
        not isinstance(context, dict)
        or set(context) != {"entries", "resident_id", "version"}
        or not isinstance(context["resident_id"], str)
        or not context["resident_id"].strip()
        or isinstance(context["version"], bool)
        or not isinstance(context["version"], int)
        or context["version"] < 0
        or not isinstance(context["entries"], list)
    ):
        raise ValueError("interpretation resident context must use the exact schema")
    entry_ids: list[str] = []
    for item in context["entries"]:
        if (
            not isinstance(item, dict)
            or set(item) != _CONTEXT_ENTRY_KEYS
            or any(
                not isinstance(item[field], str) or not item[field].strip()
                for field in ("context_kind", "context_ref", "description", "entry_id")
            )
            or any(
                item[field] is not None and not isinstance(item[field], str)
                for field in (
                    "flexibility_note",
                    "local_time_end",
                    "local_time_start",
                    "recurrence_note",
                )
            )
        ):
            raise ValueError("interpretation context entry must use the exact schema")
        entry_ids.append(item["entry_id"])
    if len(entry_ids) != len(set(entry_ids)):
        raise ValueError("interpretation context entry IDs must be unique")
    expected_refs = tuple(
        "resident-memory://"
        f"{context['resident_id']}/{context['version']}/entries/{entry_id}"
        for entry_id in entry_ids
    )
    if (
        not isinstance(request.retrieved_context_refs, tuple)
        or not _text_list(list(request.retrieved_context_refs))
        or tuple(request.retrieved_context_refs) != expected_refs
        or tuple(item["context_ref"] for item in context["entries"])
        != expected_refs
        or not isinstance(request.urgent_deterministic_event, bool)
        or guardrails
        != {"urgent_deterministic_event": request.urgent_deterministic_event}
        or not isinstance(payload["schema_version"], str)
        or not payload["schema_version"].strip()
        or payload["schema_version"] != request.schema_version
        or not isinstance(payload["request_fingerprint"], str)
        or not payload["request_fingerprint"].strip()
        or not _text_list(payload["skill_bundle"])
        or not isinstance(versions, dict)
        or set(versions)
        != {
            "invocation",
            "model",
            "output_schema",
            "prompt",
            "relevant_context",
            "retrieval_contract",
            "skill_bundle",
            "skills",
        }
        or not _text_list(versions["skills"])
        or any(
            not isinstance(versions[field], str) or not versions[field].strip()
            for field in set(versions) - {"skills"}
        )
    ):
        raise ValueError("interpretation request payload provenance is malformed")
    return context["resident_id"], context["version"], tuple(entry_ids)


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

    validate_interpretation_request_shape(request)
    validate_interpretation_request_payload(request)
    bundle = select_skill_bundle(packet)
    payload = json.loads(request.payload_json)
    missing, limitations, unsupported = _required_declarations(
        packet,
        bundle.skill_names,
    )
    context = payload.get("resident_context", {})
    context_entries = context.get("entries", ())
    if (
        request.relevant_context_version
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
    canonical = _canonical_json(material)
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
        payload_json=_canonical_json(payload),
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
    "validate_interpretation_request_shape",
    "validate_interpretation_request_payload",
    "validate_interpretation_request_binding",
]
