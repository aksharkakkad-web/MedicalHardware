"""Application service boundaries shared by product adapters."""

from backend.app.services.errors import ConcurrentUpdateError, NotFoundError, ProductError

__all__ = ["ConcurrentUpdateError", "NotFoundError", "ProductError"]
