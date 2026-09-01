"""Strict Gemini REST adapter for bounded monitoring interpretations."""

from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
import re
import time
from threading import Lock
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.app.ai.analysis_contracts import (
    AnalysisStage,
    StageRequest,
    StageResponse,
    StageStatus,
)
from backend.app.ai.client import (
    ExplanationCategory,
    InterpretationAlternative,
    InterpretationRequest,
    InterpretationResult,
    InterpretationStatus,
    RecommendedDisposition,
    UncertaintyCategory,
    render_caregiver_wording,
    render_plain_english_summary,
)
from backend.app.ai.validation import validate_interpretation


class GeminiTransport(Protocol):
    def generate(
        self,
        *,
        model: str,
        api_key: str,
        body: bytes,
        timeout: float,
    ) -> bytes: ...


class GeminiTransportError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None,
        retryable: bool,
        retry_after_seconds: float | None = None,
    ) -> None:
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)


class GeminiProviderError(RuntimeError):
    """Sanitized provider failure safe for logs and evaluation artifacts."""


def _validate_provider_settings(
    *,
    api_key: str | None,
    model: str,
    timeout_seconds: float,
    max_attempts: int,
    minimum_interval_seconds: float,
) -> str:
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("GEMINI_API_KEY is required at runtime")
    if model != "gemini-3.5-flash":
        raise ValueError("Gemini model must be pinned to gemini-3.5-flash")
    if timeout_seconds <= 0 or timeout_seconds > 180:
        raise ValueError("timeout_seconds must be between 0 and 180")
    if not 1 <= max_attempts <= 5:
        raise ValueError("max_attempts must be between 1 and 5")
    if not 0 <= minimum_interval_seconds <= 60:
        raise ValueError("minimum_interval_seconds must be between 0 and 60")
    return api_key.strip()


@dataclass
class _GeminiExecutor:
    api_key: str
    model: str
    timeout_seconds: float
    max_attempts: int
    minimum_interval_seconds: float
    transport: GeminiTransport
    sleep: Callable[[float], None]
    monotonic: Callable[[], float]
    _last_request_started_at: float | None = field(default=None, init=False)
    _pacing_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def _reserve_request_slot(self) -> float:
        with self._pacing_lock:
            if self._last_request_started_at is not None:
                remaining = self.minimum_interval_seconds - (
                    self.monotonic() - self._last_request_started_at
                )
                if remaining > 0:
                    self.sleep(remaining)
            started_at = self.monotonic()
            self._last_request_started_at = started_at
            return started_at

    def generate(self, body: bytes) -> tuple[bytes, float]:
        started_at: float | None = None
        for attempt in range(1, self.max_attempts + 1):
            attempt_started_at = self._reserve_request_slot()
            if started_at is None:
                started_at = attempt_started_at
            try:
                return (
                    self.transport.generate(
                        model=self.model,
                        api_key=self.api_key,
                        body=body,
                        timeout=self.timeout_seconds,
                    ),
                    started_at,
                )
            except GeminiTransportError as exc:
                if not exc.retryable or attempt == self.max_attempts:
                    status = (
                        f" status={exc.status_code}"
                        if exc.status_code is not None
                        else ""
                    )
                    raise GeminiProviderError(
                        f"Gemini request failed.{status}"
                    ) from None
                self.sleep(
                    max(
                        0.25 * (2 ** (attempt - 1)),
                        exc.retry_after_seconds or 0.0,
                    )
                )
        raise GeminiProviderError("Gemini request failed")


class UrllibGeminiTransport:
    def generate(
        self,
        *,
        model: str,
        api_key: str,
        body: bytes,
        timeout: float,
    ) -> bytes:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        request = Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-goog-api-key": api_key,
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS host
                return response.read()
        except HTTPError as exc:
            retryable = exc.code in {408, 429, 500, 502, 503, 504}
            retry_after_seconds = None
            header = exc.headers.get("Retry-After") if exc.headers else None
            if header:
                try:
                    retry_after_seconds = float(header)
                except ValueError:
                    retry_after_seconds = None
            try:
                payload = json.loads(exc.read())
                details = payload.get("error", {}).get("details", [])
                for detail in details:
                    delay = detail.get("retryDelay") if isinstance(detail, dict) else None
                    if isinstance(delay, str) and re.fullmatch(r"[0-9.]+s", delay):
                        retry_after_seconds = max(
                            retry_after_seconds or 0.0,
                            float(delay[:-1]),
                        )
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
                pass
            raise GeminiTransportError(
                "Gemini HTTP request failed",
                status_code=exc.code,
                retryable=retryable,
                retry_after_seconds=retry_after_seconds,
            ) from None
        except (URLError, TimeoutError, OSError):
            raise GeminiTransportError(
                "Gemini network request failed",
                status_code=None,
                retryable=True,
            ) from None


_CATEGORIES = [item.value for item in ExplanationCategory]
_UNCERTAINTIES = [item.value for item in UncertaintyCategory]
_DISPOSITIONS = [item.value for item in RecommendedDisposition]
_CATEGORIES_BY_SKILL = {
    "fall_like": ("unknown", "fall_like", "unusual_movement"),
    "inactivity": ("unknown", "inactivity"),
    "movement": ("unknown", "unusual_movement", "routine_movement"),
    "respiration": ("unknown", "respiratory_change"),
    "routine_change": ("unknown", "routine_change", "routine_movement"),
    "monitoring_degraded": ("unknown", "monitoring_degraded"),
    "unknown_anomaly": ("unknown",),
}
_REQUIRED_OUTPUT_FIELDS = (
    "likely_explanation",
    "confidence",
    "alternatives",
    "uncertainty",
    "supporting_evidence_refs",
    "contradicting_evidence_refs",
    "described_measurements",
    "addressed_contradictions",
    "missing_information",
    "limitations",
    "unsupported_conclusions",
    "needs_more_observation",
    "recommended_disposition",
)


def _string_array() -> dict[str, object]:
    return {"type": "array", "items": {"type": "string"}}


def _response_schema() -> dict[str, object]:
    alternative = {
        "type": "object",
        "required": [
            "rank",
            "label",
            "confidence",
            "supporting_evidence_refs",
            "contradicting_evidence_refs",
        ],
        "properties": {
            "rank": {"type": "integer", "minimum": 1},
            "label": {"type": "string", "enum": _CATEGORIES},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "supporting_evidence_refs": _string_array(),
            "contradicting_evidence_refs": _string_array(),
        },
    }
    return {
        "type": "object",
        "required": list(_REQUIRED_OUTPUT_FIELDS),
        "properties": {
            "likely_explanation": {"type": "string", "enum": _CATEGORIES},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "alternatives": {"type": "array", "items": alternative, "maxItems": 0},
            "uncertainty": {"type": "string", "enum": _UNCERTAINTIES},
            "supporting_evidence_refs": _string_array(),
            "contradicting_evidence_refs": _string_array(),
            "described_measurements": _string_array(),
            "addressed_contradictions": _string_array(),
            "missing_information": _string_array(),
            "limitations": _string_array(),
            "unsupported_conclusions": _string_array(),
            "needs_more_observation": {"type": "boolean"},
            "recommended_disposition": {"type": "string", "enum": _DISPOSITIONS},
        },
    }


def _request_body(request: InterpretationRequest) -> bytes:
    allowed_categories = list(_CATEGORIES_BY_SKILL[request.skill_bundle[1]])
    if "multi_person" in request.skill_bundle:
        allowed_categories.append("multi_person_ambiguity")
    output_contract = {
        "allowed_evidence_refs": list(request.available_evidence_refs),
        "allowed_explanation_categories": allowed_categories,
        "allowed_measurements": list(request.available_measurements),
        "allowed_recommended_dispositions": (
            ["caregiver_event"]
            if request.urgent_deterministic_event
            else _DISPOSITIONS
        ),
        "non_unknown_alternatives_require_supporting_evidence": True,
        "resident_context_refs": list(request.retrieved_context_refs),
        "resident_context_refs_are_not_evidence": True,
        "required_addressed_contradictions": list(request.contradictions),
        "required_limitations": list(request.required_limitations),
        "required_missing_information": list(request.required_missing_information),
        "required_unsupported_conclusions": list(
            request.required_unsupported_conclusions
        ),
        "unavailable_measurements_must_not_be_described": list(
            request.unavailable_measurements
        ),
    }
    contract_json = json.dumps(
        output_contract,
        separators=(",", ":"),
        sort_keys=True,
    )
    instruction = (
        f"{request.prompt}\n\n"
        "Return only the JSON object required by the response schema. The OUTPUT_CONTRACT "
        "is authoritative: copy every required array exactly, choose only allowed controlled "
        "values, use only allowed_evidence_refs as evidence, and never cite resident_context_refs "
        "as sensor evidence.\n\n"
        f"OUTPUT_CONTRACT:\n{contract_json}\n\nINPUT:\n{request.payload_json}"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": instruction}]}],
        "generationConfig": {
            "thinkingConfig": {"thinkingLevel": "low"},
            "temperature": 0.1,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
            "responseSchema": _response_schema(),
        },
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _list_of_strings(payload: dict[str, object], field: str) -> tuple[str, ...]:
    value = payload.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise GeminiProviderError(f"Gemini returned invalid {field}")
    return tuple(value)


def _parse_model_payload(response: bytes) -> dict[str, object]:
    try:
        envelope = json.loads(response)
        candidates = envelope["candidates"]
        text = candidates[0]["content"]["parts"][0]["text"]
        payload = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError):
        raise GeminiProviderError("Gemini returned no usable candidate") from None
    if not isinstance(payload, dict):
        raise GeminiProviderError("Gemini returned a non-object interpretation")
    unknown = set(payload) - set(_REQUIRED_OUTPUT_FIELDS)
    missing = set(_REQUIRED_OUTPUT_FIELDS) - set(payload)
    if unknown or missing:
        raise GeminiProviderError("Gemini returned an invalid interpretation shape")
    return payload


def _result_from_payload(
    request: InterpretationRequest,
    payload: dict[str, object],
) -> InterpretationResult:
    try:
        category = ExplanationCategory(payload["likely_explanation"])
        uncertainty = UncertaintyCategory(payload["uncertainty"])
        disposition = RecommendedDisposition(payload["recommended_disposition"])
        confidence = float(payload["confidence"])
        alternatives_value = payload["alternatives"]
        if not isinstance(alternatives_value, list):
            raise TypeError
        alternatives: tuple[InterpretationAlternative, ...] = ()
        needs_more_observation = payload["needs_more_observation"]
        if not isinstance(needs_more_observation, bool):
            raise TypeError
    except (KeyError, TypeError, ValueError, OverflowError):
        raise GeminiProviderError("Gemini returned invalid controlled values") from None
    digest = sha256(
        (request.request_fingerprint + json.dumps(payload, sort_keys=True)).encode("utf-8")
    ).hexdigest()[:20]
    result = InterpretationResult(
        interpretation_id=f"gemini_{digest}",
        anomaly_id=request.anomaly_id,
        packet_revision=request.packet_revision,
        status=InterpretationStatus.COMPLETE,
        likely_explanation=category,
        confidence=confidence,
        alternatives=alternatives,
        uncertainty=uncertainty,
        plain_english_summary=render_plain_english_summary(category),
        supporting_evidence_refs=_list_of_strings(payload, "supporting_evidence_refs"),
        contradicting_evidence_refs=_list_of_strings(payload, "contradicting_evidence_refs"),
        described_measurements=_list_of_strings(payload, "described_measurements"),
        addressed_contradictions=_list_of_strings(payload, "addressed_contradictions"),
        missing_information=_list_of_strings(payload, "missing_information"),
        limitations=_list_of_strings(payload, "limitations"),
        unsupported_conclusions=_list_of_strings(payload, "unsupported_conclusions"),
        needs_more_observation=needs_more_observation,
        caregiver_wording=render_caregiver_wording(category, disposition),
        recommended_disposition=disposition,
        model_id=request.model_id,
        model_version=request.model_version,
        skill_bundle=request.skill_bundle,
        skill_bundle_version=request.skill_bundle_version,
        prompt_version=request.prompt_version,
        invocation_version=request.invocation_version,
        retrieval_contract_version=request.retrieval_contract_version,
        output_schema_version=request.output_schema_version,
        relevant_context_version=request.relevant_context_version,
        request_fingerprint=request.request_fingerprint,
        schema_version=request.schema_version,
    )
    return validate_interpretation(request, result)


@dataclass
class GeminiLLMClient:
    api_key: str | None = None
    model: str = "gemini-3.5-flash"
    timeout_seconds: float = 180.0
    max_attempts: int = 3
    minimum_interval_seconds: float = 12.5
    transport: GeminiTransport | None = None
    sleep: Callable[[float], None] = time.sleep
    monotonic: Callable[[], float] = time.monotonic
    _last_request_started_at: float | None = field(default=None, init=False, repr=False)
    _executor: _GeminiExecutor = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.api_key = _validate_provider_settings(
            api_key=(
                self.api_key
                if self.api_key is not None
                else os.getenv("GEMINI_API_KEY")
            ),
            model=self.model,
            timeout_seconds=self.timeout_seconds,
            max_attempts=self.max_attempts,
            minimum_interval_seconds=self.minimum_interval_seconds,
        )
        if self.transport is None:
            self.transport = UrllibGeminiTransport()
        self._executor = _GeminiExecutor(
            api_key=self.api_key,
            model=self.model,
            timeout_seconds=self.timeout_seconds,
            max_attempts=self.max_attempts,
            minimum_interval_seconds=self.minimum_interval_seconds,
            transport=self.transport,
            sleep=self.sleep,
            monotonic=self.monotonic,
        )

    def interpret(self, request: InterpretationRequest) -> InterpretationResult:
        body = _request_body(request)
        response, _started_at = self._executor.generate(body)
        return _result_from_payload(request, _parse_model_payload(response))


def _structured_body(request: StageRequest) -> bytes:
    thinking_level = (
        "low" if request.stage is AnalysisStage.RECALL else "high"
    )
    instruction = (
        f"{request.prompt}\n\n"
        "Return only the JSON object required by the response schema. Use only "
        "the bounded INPUT and exact evidence identifiers supplied there.\n\n"
        f"INPUT:\n{request.payload_json}"
    )
    return json.dumps(
        {
            "contents": [{"role": "user", "parts": [{"text": instruction}]}],
            "generationConfig": {
                "thinkingConfig": {"thinkingLevel": thinking_level},
                "temperature": 0.1,
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json",
                # Gemini accepts a subset of JSON Schema. Strict unknown-key
                # rejection is still enforced locally after the response.
                "responseSchema": _gemini_schema(request.response_schema),
            },
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _gemini_schema(value):
    if isinstance(value, dict):
        return {
            key: _gemini_schema(item)
            for key, item in value.items()
            if key != "additionalProperties"
        }
    if isinstance(value, list):
        return [_gemini_schema(item) for item in value]
    return value


def _structured_payload(response: bytes) -> tuple[str, str, int | None, int | None]:
    try:
        envelope = json.loads(response)
        text = envelope["candidates"][0]["content"]["parts"][0]["text"]
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise TypeError
        model_version = envelope.get("modelVersion", "gemini-3.5-flash")
        usage = envelope.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount")
        output_tokens = usage.get("candidatesTokenCount")
        if not isinstance(model_version, str) or not model_version.strip():
            raise TypeError
        if input_tokens is not None and not isinstance(input_tokens, int):
            raise TypeError
        if output_tokens is not None and not isinstance(output_tokens, int):
            raise TypeError
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError):
        raise GeminiProviderError("Gemini returned no usable structured candidate") from None
    return (
        json.dumps(payload, separators=(",", ":"), sort_keys=True),
        model_version,
        input_tokens,
        output_tokens,
    )


@dataclass
class GeminiStructuredAnalysisClient:
    api_key: str | None = None
    model: str = "gemini-3.5-flash"
    timeout_seconds: float = 180.0
    max_attempts: int = 3
    minimum_interval_seconds: float = 12.5
    transport: GeminiTransport | None = None
    sleep: Callable[[float], None] = time.sleep
    monotonic: Callable[[], float] = time.monotonic
    _executor: _GeminiExecutor = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.api_key = _validate_provider_settings(
            api_key=(
                self.api_key
                if self.api_key is not None
                else os.getenv("GEMINI_API_KEY")
            ),
            model=self.model,
            timeout_seconds=self.timeout_seconds,
            max_attempts=self.max_attempts,
            minimum_interval_seconds=self.minimum_interval_seconds,
        )
        if self.transport is None:
            self.transport = UrllibGeminiTransport()
        self._executor = _GeminiExecutor(
            api_key=self.api_key,
            model=self.model,
            timeout_seconds=self.timeout_seconds,
            max_attempts=self.max_attempts,
            minimum_interval_seconds=self.minimum_interval_seconds,
            transport=self.transport,
            sleep=self.sleep,
            monotonic=self.monotonic,
        )

    def analyze(self, request: StageRequest) -> StageResponse:
        if not isinstance(request, StageRequest):
            raise ValueError("request must be a StageRequest")
        response, started_at = self._executor.generate(_structured_body(request))
        payload_json, model_version, input_tokens, output_tokens = _structured_payload(
            response
        )
        latency_ms = max(0.0, (self.monotonic() - started_at) * 1000.0)
        return StageResponse(
            stage=request.stage,
            status=StageStatus.COMPLETE,
            request_fingerprint=request.request_fingerprint,
            payload_json=payload_json,
            model_id="gemini",
            model_version=model_version,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


__all__ = [
    "GeminiLLMClient",
    "GeminiProviderError",
    "GeminiStructuredAnalysisClient",
    "GeminiTransport",
    "GeminiTransportError",
    "UrllibGeminiTransport",
]
