"""Strict Gemini REST adapter for bounded monitoring interpretations."""

from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
import re
import time
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
            "alternatives": {"type": "array", "items": alternative},
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
    instruction = (
        f"{request.prompt}\n\n"
        "Return only the JSON object required by the response schema. Copy only exact "
        "controlled identifiers and evidence references supplied below.\n\n"
        f"INPUT:\n{request.payload_json}"
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
        alternatives = tuple(
            InterpretationAlternative(
                rank=item["rank"],
                label=item["label"],
                confidence=item["confidence"],
                supporting_evidence_refs=tuple(item["supporting_evidence_refs"]),
                contradicting_evidence_refs=tuple(item["contradicting_evidence_refs"]),
            )
            for item in alternatives_value
            if isinstance(item, dict)
        )
        if len(alternatives) != len(alternatives_value):
            raise TypeError
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
    model: str = "gemini-3.7-flash"
    timeout_seconds: float = 180.0
    max_attempts: int = 3
    minimum_interval_seconds: float = 12.5
    transport: GeminiTransport | None = None
    sleep: Callable[[float], None] = time.sleep
    monotonic: Callable[[], float] = time.monotonic
    _last_request_started_at: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.api_key = self.api_key if self.api_key is not None else os.getenv("GEMINI_API_KEY")
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise ValueError("GEMINI_API_KEY is required at runtime")
        if self.model != "gemini-3.7-flash":
            raise ValueError("Gemini model must be pinned to gemini-3.7-flash")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 180:
            raise ValueError("timeout_seconds must be between 0 and 180")
        if not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")
        if not 0 <= self.minimum_interval_seconds <= 60:
            raise ValueError("minimum_interval_seconds must be between 0 and 60")
        if self.transport is None:
            self.transport = UrllibGeminiTransport()

    def interpret(self, request: InterpretationRequest) -> InterpretationResult:
        body = _request_body(request)
        if self._last_request_started_at is not None:
            remaining = self.minimum_interval_seconds - (
                self.monotonic() - self._last_request_started_at
            )
            if remaining > 0:
                self.sleep(remaining)
        self._last_request_started_at = self.monotonic()
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.transport.generate(
                    model=self.model,
                    api_key=self.api_key,
                    body=body,
                    timeout=self.timeout_seconds,
                )
                return _result_from_payload(request, _parse_model_payload(response))
            except GeminiTransportError as exc:
                if not exc.retryable or attempt == self.max_attempts:
                    status = f" status={exc.status_code}" if exc.status_code is not None else ""
                    raise GeminiProviderError(f"Gemini request failed.{status}") from None
                self.sleep(
                    max(
                        0.25 * (2 ** (attempt - 1)),
                        exc.retry_after_seconds or 0.0,
                    )
                )
        raise GeminiProviderError("Gemini request failed")


__all__ = [
    "GeminiLLMClient",
    "GeminiProviderError",
    "GeminiTransport",
    "GeminiTransportError",
    "UrllibGeminiTransport",
]
