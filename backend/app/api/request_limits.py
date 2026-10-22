"""Bounded request-body handling for device ingestion."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from backend.app.contracts.common import ErrorDetail, ErrorEnvelope


MAX_INGEST_BODY_BYTES = 512 * 1024
_INGEST_PATHS = frozenset(
    {
        "/v1/ingest/telemetry",
        "/v1/ingest/heartbeat",
    }
)


def install_ingest_body_limit(
    app: FastAPI,
    *,
    max_bytes: int = MAX_INGEST_BODY_BYTES,
) -> None:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")

    @app.middleware("http")
    async def limit_ingest_body(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path not in _INGEST_PATHS:
            return await call_next(request)

        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > max_bytes:
                    return _too_large()
            except ValueError:
                return _too_large()

        chunks: list[bytes] = []
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > max_bytes:
                return _too_large()
            chunks.append(chunk)
        body = b"".join(chunks)
        # BaseHTTPMiddleware's cached request replays `_body` to the endpoint.
        # We set it only after enforcing the streaming ceiling above.
        request._body = body
        return await call_next(request)


def _too_large() -> JSONResponse:
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code="request_too_large",
            message="Request body is too large",
        )
    )
    return JSONResponse(
        status_code=413,
        content=envelope.model_dump(mode="json"),
    )


__all__ = ["MAX_INGEST_BODY_BYTES", "install_ingest_body_limit"]
