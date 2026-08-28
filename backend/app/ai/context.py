"""Bounded serialization of evidence and relevant resident context."""

import json

from backend.app.ai.client import InterpretationRequest
from backend.app.ai.skills import select_skill_bundle
from backend.app.domain._validation import require_nonblank_text, require_strict_bool
from backend.app.domain.feedback import ResidentMemory
from backend.app.intelligence.evidence import EvidencePacket


_MAX_RELEVANT_MEMORY_ENTRIES = 20


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


def build_interpretation_request(
    packet: EvidencePacket,
    resident_memory: ResidentMemory,
    *,
    model_id: str,
    model_version: str,
    urgent_deterministic_event: bool = False,
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
    relevant_entries = resident_memory.relevant_entries(packet.current_time)[
        :_MAX_RELEVANT_MEMORY_ENTRIES
    ]
    retrieval_version = "relevant_resident_context_v1"
    output_version = "monitoring_interpretation_output_v1"
    prompt_version = "monitoring_interpreter_v1"
    invocation_version = "monitoring_invocation_v1"
    relevant_context_version = f"resident_memory_v{resident_memory.version}"
    payload = {
        "anomaly_evidence": {
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
            "missing_initiating_features": list(
                packet.missing_initiating_features
            ),
            "missing_modalities": list(packet.missing_modalities),
            "monitoring_setup_version": packet.monitoring_setup_version,
            "overall_strength": packet.overall_strength,
            "packet_revision": packet.packet_revision,
            "progression": packet.progression,
            "room_id": packet.room_id,
            "strength_scale": packet.strength_scale,
            "unknowns": list(packet.unknowns),
        },
        "guardrails": {"urgent_deterministic_event": urgent},
        "resident_context": {
            "entries": [
                {
                    "context_kind": entry.context_kind,
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
        urgent_deterministic_event=urgent,
    )


__all__ = ["InterpretationRequest", "build_interpretation_request"]
