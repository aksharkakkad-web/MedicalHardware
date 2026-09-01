import json

import pytest

from backend.app.ai.analysis_contracts import AnalysisStage, StageRequest, StageStatus
from backend.app.ai.gemini import (
    GeminiProviderError,
    GeminiStructuredAnalysisClient,
    GeminiTransportError,
)


def _request(stage: AnalysisStage) -> StageRequest:
    return StageRequest(
        stage=stage,
        anomaly_id="anomaly_1",
        packet_revision=2,
        skill_names=(
            "recall_router" if stage is AnalysisStage.RECALL else "movement_fall",
        ),
        prompt="Use bounded evidence and return structured output.",
        payload_json='{"case":{"evidence":"bounded"}}',
        response_schema={
            "type": "object",
            "required": ["result"],
            "properties": {"result": {"type": "string"}},
        },
        request_fingerprint=f"fingerprint_{stage.value}",
        model_tier=(
            "recall_tier" if stage is AnalysisStage.RECALL else "precision_tier"
        ),
    )


def _envelope(payload: dict[str, object]) -> bytes:
    return json.dumps(
        {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(payload)}]}}
            ],
            "modelVersion": "gemini-3.5-flash-001",
            "usageMetadata": {
                "promptTokenCount": 31,
                "candidatesTokenCount": 9,
            },
        }
    ).encode()


class RecordingTransport:
    def __init__(self, response: bytes | Exception) -> None:
        self.response = response
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.mark.parametrize(
    ("stage", "thinking_level"),
    (
        (AnalysisStage.RECALL, "low"),
        (AnalysisStage.SPECIALIST, "high"),
        (AnalysisStage.FINAL, "high"),
        (AnalysisStage.REPAIR, "high"),
    ),
)
def test_structured_client_uses_stage_schema_and_reasoning_level(
    stage: AnalysisStage,
    thinking_level: str,
) -> None:
    request = _request(stage)
    transport = RecordingTransport(_envelope({"result": "ok"}))
    clock = iter((10.0, 10.025))
    client = GeminiStructuredAnalysisClient(
        api_key="test-secret",
        transport=transport,
        minimum_interval_seconds=0,
        monotonic=lambda: next(clock),
        sleep=lambda _: None,
    )

    response = client.analyze(request)

    body = json.loads(transport.calls[0]["body"])
    config = body["generationConfig"]
    prompt = body["contents"][0]["parts"][0]["text"]
    assert transport.calls[0]["model"] == "gemini-3.5-flash"
    assert transport.calls[0]["timeout"] == 180.0
    assert config["thinkingConfig"] == {"thinkingLevel": thinking_level}
    assert config["responseSchema"] == request.response_schema
    assert config["responseMimeType"] == "application/json"
    assert request.prompt in prompt
    assert request.payload_json in prompt
    assert "test-secret" not in prompt
    assert response.status is StageStatus.COMPLETE
    assert response.payload_json == '{"result":"ok"}'
    assert response.model_version == "gemini-3.5-flash-001"
    assert response.input_tokens == 31
    assert response.output_tokens == 9
    assert response.latency_ms == pytest.approx(25.0)


def test_structured_provider_failure_is_sanitized() -> None:
    transport = RecordingTransport(
        GeminiTransportError(
            "secret-bearing transport text",
            status_code=503,
            retryable=False,
        )
    )
    client = GeminiStructuredAnalysisClient(
        api_key="test-secret",
        transport=transport,
        max_attempts=1,
        minimum_interval_seconds=0,
    )

    with pytest.raises(GeminiProviderError) as exc:
        client.analyze(_request(AnalysisStage.RECALL))

    assert "test-secret" not in str(exc.value)
    assert "secret-bearing" not in str(exc.value)
    assert "503" in str(exc.value)


def test_structured_client_requires_pinned_supported_model_and_bounded_timeout() -> None:
    with pytest.raises(ValueError, match="pinned"):
        GeminiStructuredAnalysisClient(api_key="test", model="gemini-flash-latest")
    with pytest.raises(ValueError, match="180"):
        GeminiStructuredAnalysisClient(api_key="test", timeout_seconds=181)
