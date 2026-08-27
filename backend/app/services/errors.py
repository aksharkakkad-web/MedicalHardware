"""Stable product errors independent of HTTP transport concerns."""


class ProductError(Exception):
    code = "product_error"
    default_message = "The request could not be completed"

    def __init__(
        self,
        message: str | None = None,
        *,
        field: str | None = None,
    ) -> None:
        self.message = self.default_message if message is None else message
        self.field = field
        super().__init__(self.message)


class NotFoundError(ProductError):
    code = "not_found"
    default_message = "Resource not found"


class InvalidInputError(ProductError):
    code = "invalid_input"
    default_message = "Invalid request"


class InvalidTransitionError(ProductError):
    code = "invalid_transition"
    default_message = "The requested transition is not allowed"


class IdempotencyConflictError(ProductError):
    code = "idempotency_conflict"
    default_message = "Idempotency key was already used for a different request"


class ConcurrentUpdateError(ProductError):
    code = "concurrent_update"
    default_message = "Resource was updated by another request"
