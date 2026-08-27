from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.contracts.common import ErrorDetail, ErrorEnvelope
from backend.app.services.errors import (
    ConcurrentUpdateError,
    IdempotencyConflictError,
    InvalidInputError,
    InvalidTransitionError,
    NotFoundError,
    ProductError,
)


ERROR_RESPONSE = {"model": ErrorEnvelope}
READ_ERROR_RESPONSES = {
    404: ERROR_RESPONSE,
    422: ERROR_RESPONSE,
    500: ERROR_RESPONSE,
}
MUTATION_ERROR_RESPONSES = {
    404: ERROR_RESPONSE,
    409: ERROR_RESPONSE,
    422: ERROR_RESPONSE,
    500: ERROR_RESPONSE,
}


def _status_code(error: ProductError) -> int:
    if isinstance(error, NotFoundError):
        return 404
    if isinstance(error, InvalidInputError):
        return 422
    if isinstance(
        error,
        (InvalidTransitionError, IdempotencyConflictError, ConcurrentUpdateError),
    ):
        return 409
    return 400


def register_error_handlers(app: FastAPI) -> None:
    def error_response(
        status_code: int,
        *,
        code: str,
        message: str,
        field: str | None = None,
    ) -> JSONResponse:
        envelope = ErrorEnvelope(
            error=ErrorDetail(code=code, message=message, field=field)
        )
        return JSONResponse(
            status_code=status_code,
            content=envelope.model_dump(mode="json"),
        )

    @app.exception_handler(ProductError)
    async def product_error_handler(
        _: Request,
        error: ProductError,
    ) -> JSONResponse:
        return error_response(
            _status_code(error),
            code=error.code,
            message=error.message,
            field=error.field,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        _: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        first_error = error.errors()[0] if error.errors() else {}
        location = first_error.get("loc", ())
        field = str(location[-1]) if location else None
        return error_response(
            422,
            code="invalid_input",
            message="Invalid request",
            field=field,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        _: Request,
        error: StarletteHTTPException,
    ) -> JSONResponse:
        error_contracts = {
            404: ("not_found", "Resource not found"),
            405: ("method_not_allowed", "Method not allowed"),
        }
        code, message = error_contracts.get(
            error.status_code,
            ("http_error", "The request could not be completed"),
        )
        return error_response(
            error.status_code,
            code=code,
            message=message,
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, __: Exception) -> JSONResponse:
        return error_response(
            500,
            code="internal_error",
            message="Internal server error",
        )
