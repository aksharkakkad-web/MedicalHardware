"""Application service boundaries shared by product adapters."""

from backend.app.services.errors import (
    ConcurrentUpdateError,
    IdempotencyConflictError,
    InvalidInputError,
    InvalidTransitionError,
    NotFoundError,
    ProductError,
)

__all__ = [
    "ConcurrentUpdateError",
    "IdempotencyConflictError",
    "InvalidInputError",
    "InvalidTransitionError",
    "NotFoundError",
    "ProductError",
]
