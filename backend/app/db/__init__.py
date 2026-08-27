"""Durable product storage primitives."""

from backend.app.db.base import Base
from backend.app.db.session import create_engine_for_url, create_session_factory

__all__ = ["Base", "create_engine_for_url", "create_session_factory"]
