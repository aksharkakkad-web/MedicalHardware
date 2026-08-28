from datetime import datetime

import pytest
from sqlalchemy import func, select

from backend.app.db.models import (
    AuditLogRow,
    IdempotencyRecordRow,
    ResidentMemorySnapshotRow,
    ResidentNotificationPreferenceVersionRow,
)
from backend.app.db.preference_repositories import NotificationPreferenceRepository
from backend.app.db.repositories import FeedbackRepository
from backend.app.domain.feedback import ResidentMemory
from backend.app.domain.preferences import ResidentNotificationPreferences


PREFERENCE_PATH = "/v1/residents/resident_demo_a/notification-preferences"
MEMORY_PATH = "/v1/residents/resident_demo_a/memory/entries"


def _headers(key: str) -> dict[str, str]:
    return {
        "X-Tenant-Id": "tenant_demo",
        "X-Actor-Id": "operator_1",
        "Idempotency-Key": key,
    }


def _counts(api_client) -> tuple[int, int, int, int]:
    with api_client.app.state.session_factory() as session:
        return tuple(
            session.scalar(select(func.count()).select_from(row_type))
            for row_type in (
                ResidentNotificationPreferenceVersionRow,
                ResidentMemorySnapshotRow,
                AuditLogRow,
                IdempotencyRecordRow,
            )
        )


class FaultingPreferenceRepository(NotificationPreferenceRepository):
    def save(
        self,
        tenant_id: str,
        preferences: ResidentNotificationPreferences,
        *,
        expected_version: int,
    ) -> ResidentNotificationPreferences:
        super().save(
            tenant_id,
            preferences,
            expected_version=expected_version,
        )
        raise RuntimeError("synthetic preference persistence failure")


class FaultingMemoryRepository(FeedbackRepository):
    def save_memory(
        self,
        tenant_id: str,
        memory: ResidentMemory,
        *,
        expected_version: int,
        changed_at: datetime,
    ) -> ResidentMemory:
        super().save_memory(
            tenant_id,
            memory,
            expected_version=expected_version,
            changed_at=changed_at,
        )
        raise RuntimeError("synthetic memory persistence failure")


def test_preference_failure_rolls_back_version_audit_and_idempotency(
    api_client,
) -> None:
    api_client.app.state.preference_repository_factory = (
        FaultingPreferenceRepository
    )
    try:
        with pytest.raises(RuntimeError):
            api_client.put(
                PREFERENCE_PATH,
                headers=_headers("preference-rollback"),
                json={
                    "schema_version": "1.0",
                    "expected_version": 0,
                    "event_delivery": {
                        "watch": False,
                        "high": True,
                        "critical": True,
                    },
                    "awareness_delivery": {
                        "away": True,
                        "return": True,
                        "limited": False,
                        "unavailable": True,
                    },
                    "changed_at": "2026-08-25T15:00:00Z",
                },
            )
    finally:
        del api_client.app.state.preference_repository_factory

    assert _counts(api_client) == (0, 0, 0, 0)


def test_memory_failure_rolls_back_snapshot_audit_and_idempotency(
    api_client,
) -> None:
    api_client.app.state.memory_repository_factory = FaultingMemoryRepository
    try:
        with pytest.raises(RuntimeError):
            api_client.post(
                MEMORY_PATH,
                headers=_headers("memory-rollback"),
                json={
                    "schema_version": "1.0",
                    "expected_version": 0,
                    "description": "Morning routine",
                    "changed_at": "2026-08-25T15:10:00Z",
                },
            )
    finally:
        del api_client.app.state.memory_repository_factory

    assert _counts(api_client) == (0, 0, 0, 0)
