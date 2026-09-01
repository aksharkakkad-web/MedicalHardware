import json
from concurrent.futures import ThreadPoolExecutor
import time

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


class SequenceTransport:
    def __init__(self, responses) -> None:
        self.responses = iter(responses)
        self.started_at = []
        self.clock = None

    def generate(self, **kwargs):
        self.started_at.append(self.clock())
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


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


def test_parallel_stage_calls_share_one_thread_safe_rate_limiter() -> None:
    transport = RecordingTransport(_envelope({"result": "ok"}))
    original_generate = transport.generate
    started = []

    def timestamped_generate(**kwargs):
        started.append(time.monotonic())
        return original_generate(**kwargs)

    transport.generate = timestamped_generate
    client = GeminiStructuredAnalysisClient(
        api_key="test-secret",
        transport=transport,
        minimum_interval_seconds=0.03,
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        tuple(
            executor.map(
                client.analyze,
                (_request(AnalysisStage.SPECIALIST), _request(AnalysisStage.FINAL)),
            )
        )

    assert len(started) == 2
    assert abs(started[1] - started[0]) >= 0.025


def test_retry_attempts_use_the_same_rate_limiter_as_first_attempts() -> None:
    now = [0.0]

    def monotonic() -> float:
        return now[0]

    def sleep(seconds: float) -> None:
        now[0] += seconds

    transport = SequenceTransport(
        (
            GeminiTransportError("retry", status_code=503, retryable=True),
            _envelope({"result": "ok"}),
        )
    )
    transport.clock = monotonic
    client = GeminiStructuredAnalysisClient(
        api_key="test-secret",
        transport=transport,
        minimum_interval_seconds=0.4,
        max_attempts=2,
        monotonic=monotonic,
        sleep=sleep,
    )

    response = client.analyze(_request(AnalysisStage.RECALL))

    assert response.status is StageStatus.COMPLETE
    assert transport.started_at == pytest.approx([0.0, 0.4])
