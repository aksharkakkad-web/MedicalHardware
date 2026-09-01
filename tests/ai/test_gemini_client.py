import json

import pytest

from backend.app.ai.client import InterpretationRequest
from backend.app.ai.gemini import (
    GeminiLLMClient,
    GeminiProviderError,
    GeminiTransportError,
)


def _request() -> InterpretationRequest:
    return InterpretationRequest(
        anomaly_id="anomaly_1",
        packet_revision=2,
        prompt="Use only supplied evidence.",
        skill_bundle=("core", "movement"),
        prompt_version="prompt_v1",
        skill_bundle_version="skills_v1",
        retrieval_contract_version="retrieval_v1",
        output_schema_version="output_v1",
        model_id="gemini",
        model_version="gemini-3.5-flash",
        invocation_version="invocation_v1",
        relevant_context_version="memory_v1",
        payload_json='{"evidence":"bounded"}',
        available_evidence_refs=("evidence://1",),
        available_measurements=("movement_energy",),
        unavailable_measurements=(),
        contradictions=(),
        required_missing_information=("cause",),
        required_limitations=("non_diagnostic",),
        required_unsupported_conclusions=("causal_explanation", "medical_diagnosis", "person_identity", "unobserved_measurement"),
        retrieved_context_refs=(),
        request_fingerprint="fingerprint_1",
        urgent_deterministic_event=False,
    )


def _model_output() -> dict[str, object]:
    return {
        "likely_explanation": "unusual_movement",
        "confidence": 0.4,
        "alternatives": [],
        "uncertainty": "cause_not_established",
        "supporting_evidence_refs": ["evidence://1"],
        "contradicting_evidence_refs": [],
        "described_measurements": ["movement_energy"],
        "addressed_contradictions": [],
        "missing_information": ["cause"],
        "limitations": ["non_diagnostic"],
        "unsupported_conclusions": ["causal_explanation", "medical_diagnosis", "person_identity", "unobserved_measurement"],
        "needs_more_observation": True,
        "recommended_disposition": "observe",
    }


def _response(payload: dict[str, object] | None = None) -> bytes:
    text = json.dumps(_model_output() if payload is None else payload)
    return json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]}).encode()


class RecordingTransport:
    def __init__(self, responses: list[bytes | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def generate(self, *, model: str, api_key: str, body: bytes, timeout: float) -> bytes:
        self.calls.append({"model": model, "api_key": api_key, "body": body, "timeout": timeout})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_gemini_request_uses_low_thinking_and_strict_json_schema() -> None:
    transport = RecordingTransport([_response()])
    client = GeminiLLMClient(api_key="test-secret", transport=transport, sleep=lambda _: None)

    result = client.interpret(_request())

    body = json.loads(transport.calls[0]["body"])
    config = body["generationConfig"]
    prompt_text = body["contents"][0]["parts"][0]["text"]
    assert transport.calls[0]["model"] == "gemini-3.5-flash"
    assert config["thinkingConfig"] == {"thinkingLevel": "low"}
    assert config["responseMimeType"] == "application/json"
    assert config["responseSchema"]["required"]
    assert "additionalProperties" not in config["responseSchema"]
    assert "additionalProperties" not in config["responseSchema"]["properties"]["alternatives"]["items"]
    assert config["responseSchema"]["properties"]["alternatives"]["maxItems"] == 0
    assert config["maxOutputTokens"] >= 2048
    assert '"allowed_evidence_refs":["evidence://1"]' in prompt_text
    assert '"required_missing_information":["cause"]' in prompt_text
    assert '"required_unsupported_conclusions"' in prompt_text
    assert '"resident_context_refs_are_not_evidence":true' in prompt_text
    assert '"non_unknown_alternatives_require_supporting_evidence":true' in prompt_text
    assert result.anomaly_id == "anomaly_1"
    assert result.request_fingerprint == "fingerprint_1"


def test_gemini_retries_transient_errors_but_not_invalid_output() -> None:
    transient = GeminiTransportError("temporary provider error", status_code=503, retryable=True)
    transport = RecordingTransport([transient, _response()])
    client = GeminiLLMClient(api_key="test-secret", transport=transport, sleep=lambda _: None)

    client.interpret(_request())
    assert len(transport.calls) == 2

    invalid = RecordingTransport([b'{"candidates":[]}'])
    client = GeminiLLMClient(api_key="test-secret", transport=invalid, sleep=lambda _: None)
    with pytest.raises(GeminiProviderError, match="usable candidate"):
        client.interpret(_request())
    assert len(invalid.calls) == 1


def test_gemini_respects_provider_retry_delay_for_rate_limits() -> None:
    sleeps: list[float] = []
    limited = GeminiTransportError(
        "rate limited",
        status_code=429,
        retryable=True,
        retry_after_seconds=2.5,
    )
    transport = RecordingTransport([limited, _response()])
    client = GeminiLLMClient(api_key="test-secret", transport=transport, sleep=sleeps.append)

    client.interpret(_request())

    assert sleeps == [2.5]


def test_provider_errors_never_include_the_api_key() -> None:
    secret = "highly-sensitive-key"
    transport = RecordingTransport([GeminiTransportError(f"failed {secret}", status_code=401, retryable=False)])
    client = GeminiLLMClient(api_key=secret, transport=transport, sleep=lambda _: None)

    with pytest.raises(GeminiProviderError) as caught:
        client.interpret(_request())

    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)


def test_gemini_requires_a_key_at_runtime() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiLLMClient(api_key="")


def test_lean_provider_contract_drops_model_generated_alternatives() -> None:
    payload = _model_output()
    payload["alternatives"] = [
        {
            "rank": 1,
            "label": "routine_movement",
            "confidence": 0.2,
            "supporting_evidence_refs": [],
            "contradicting_evidence_refs": [],
        }
    ]
    client = GeminiLLMClient(
        api_key="test-secret",
        transport=RecordingTransport([_response(payload)]),
        sleep=lambda _: None,
    )

    result = client.interpret(_request())

    assert result.alternatives == ()
