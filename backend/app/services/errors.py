"""Stable product errors independent of HTTP transport concerns."""


class ProductError(Exception):
    code = "product_error"
    default_message = "The request could not be completed"

    def __init__(self, message: str | None = None) -> None:
        self.message = self.default_message if message is None else message
        super().__init__(self.message)


class NotFoundError(ProductError):
    code = "not_found"
    default_message = "Resource not found"


class ConcurrentUpdateError(ProductError):
    code = "concurrent_update"
    default_message = "Resource was updated by another request"
