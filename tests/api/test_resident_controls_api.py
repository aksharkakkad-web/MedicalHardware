from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    AuditLogRow,
    IdempotencyRecordRow,
    ResidentMemorySnapshotRow,
    ResidentNotificationPreferenceVersionRow,
    TenantRow,
)


RESIDENT_ID = "resident_demo_a"
PREFERENCE_PATH = f"/v1/residents/{RESIDENT_ID}/notification-preferences"
MEMORY_PATH = f"/v1/residents/{RESIDENT_ID}/memory"
EVENT_DELIVERY = {"watch": False, "high": False, "critical": False}
AWARENESS_DELIVERY = {
    "away": True,
    "return": True,
    "limited": False,
    "unavailable": True,
}


def _headers(key: str | None = None, *, tenant_id: str = "tenant_demo"):
    headers = {
        "X-Tenant-Id": tenant_id,
        "X-Actor-Id": "operator_1",
    }
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _count(api_client, row_type: type, *, action: str | None = None) -> int:
    with api_client.app.state.session_factory() as session:
        statement = select(func.count()).select_from(row_type)
        if action is not None:
            statement = statement.where(AuditLogRow.action == action)
        return session.scalar(statement)


def test_preferences_get_is_honest_then_put_appends_and_replays(api_client) -> None:
    missing = api_client.get(PREFERENCE_PATH, headers=_headers())
    assert missing.status_code == 200
    assert missing.json() == {
        "schema_version": "1.0",
        "resident_id": RESIDENT_ID,
        "data_availability": "not_yet_available",
        "version": None,
        "event_delivery": None,
        "awareness_delivery": None,
        "high_critical_dashboard_visibility": "always_visible",
        "changed_by": None,
        "changed_at": None,
    }

    body = {
        "schema_version": "1.0",
        "expected_version": 0,
        "event_delivery": EVENT_DELIVERY,
        "awareness_delivery": AWARENESS_DELIVERY,
        "changed_at": "2026-08-25T15:00:00Z",
    }
    first = api_client.put(
        PREFERENCE_PATH,
        headers=_headers("preference-create"),
        json=body,
    )
    replay = api_client.put(
        PREFERENCE_PATH,
        headers=_headers("preference-create"),
        json=body,
    )

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert first.json() == {
        "schema_version": "1.0",
        "resident_id": RESIDENT_ID,
        "data_availability": "available",
        "version": 1,
        "event_delivery": EVENT_DELIVERY,
        "awareness_delivery": AWARENESS_DELIVERY,
        "high_critical_dashboard_visibility": "always_visible",
        "changed_by": "operator_1",
        "changed_at": "2026-08-25T15:00:00Z",
    }
    assert api_client.get(PREFERENCE_PATH, headers=_headers()).json() == first.json()
    assert _count(api_client, ResidentNotificationPreferenceVersionRow) == 1
    assert _count(
        api_client,
        AuditLogRow,
        action="resident.notification_preferences.changed",
    ) == 1
    assert _count(api_client, IdempotencyRecordRow) == 1


def test_preference_stale_and_cross_tenant_writes_have_no_effect(api_client) -> None:
    first_body = {
        "schema_version": "1.0",
        "expected_version": 0,
        "event_delivery": EVENT_DELIVERY,
        "awareness_delivery": AWARENESS_DELIVERY,
        "changed_at": "2026-08-25T15:00:00Z",
    }
    assert api_client.put(
        PREFERENCE_PATH,
        headers=_headers("preference-first"),
        json=first_body,
    ).status_code == 200

    stale = api_client.put(
        PREFERENCE_PATH,
        headers=_headers("preference-stale"),
        json={**first_body, "changed_at": "2026-08-25T15:01:00Z"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "concurrent_update"

    with api_client.app.state.session_factory() as session:
        session.add(TenantRow(tenant_id="tenant_other"))
        session.commit()
    cross_tenant = api_client.put(
        PREFERENCE_PATH,
        headers=_headers("preference-cross", tenant_id="tenant_other"),
        json=first_body,
    )
    assert cross_tenant.status_code == 404
    assert _count(api_client, ResidentNotificationPreferenceVersionRow) == 1


def test_memory_add_correct_retire_preserves_history_and_links(api_client) -> None:
    add = api_client.post(
        f"{MEMORY_PATH}/entries",
        headers=_headers("memory-add"),
        json={
            "schema_version": "1.0",
            "expected_version": 0,
            "description": "Assisted standing is common before breakfast.",
            "changed_at": "2026-08-25T15:10:00Z",
        },
    )
    assert add.status_code == 200
    added = add.json()
    assert added["version"] == 1
    original = added["entries"][0]
    assert original["source_kind"] == "operator"
    assert original["source_feedback_id"] is None

    correct = api_client.post(
        f"{MEMORY_PATH}/entries/{original['entry_id']}/correct",
        headers=_headers("memory-correct"),
        json={
            "schema_version": "1.0",
            "expected_version": 1,
            "description": "Assisted standing is common after breakfast.",
            "reason": "The routine time was entered incorrectly.",
            "changed_at": "2026-08-25T15:20:00Z",
        },
    )
    assert correct.status_code == 200
    corrected = correct.json()
    assert corrected["version"] == 2
    assert corrected["entries"][0]["status"] == "retired"
    replacement = corrected["entries"][1]
    assert replacement["status"] == "active"
    assert replacement["supersedes_entry_id"] == original["entry_id"]

    retire = api_client.post(
        f"{MEMORY_PATH}/entries/{replacement['entry_id']}/retire",
        headers=_headers("memory-retire"),
        json={
            "schema_version": "1.0",
            "expected_version": 2,
            "reason": "This routine is no longer current.",
            "changed_at": "2026-08-25T15:30:00Z",
        },
    )
    assert retire.status_code == 200
    retired = retire.json()
    assert retired["version"] == 3
    assert all(entry["status"] == "retired" for entry in retired["entries"])
    assert api_client.get(MEMORY_PATH, headers=_headers()).json() == retired
    assert _count(api_client, ResidentMemorySnapshotRow) == 3
    assert _count(api_client, AuditLogRow, action="resident_memory.entry_added") == 1
    assert _count(api_client, AuditLogRow, action="resident_memory.entry_corrected") == 1
    assert _count(api_client, AuditLogRow, action="resident_memory.entry_retired") == 1


def test_memory_replay_stale_and_cross_tenant_commands_are_safe(api_client) -> None:
    body = {
        "schema_version": "1.0",
        "expected_version": 0,
        "description": "Morning routine",
        "changed_at": "2026-08-25T15:10:00Z",
    }
    first = api_client.post(
        f"{MEMORY_PATH}/entries",
        headers=_headers("memory-replay"),
        json=body,
    )
    replay = api_client.post(
        f"{MEMORY_PATH}/entries",
        headers=_headers("memory-replay"),
        json=body,
    )
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()

    stale = api_client.post(
        f"{MEMORY_PATH}/entries",
        headers=_headers("memory-stale"),
        json={**body, "changed_at": "2026-08-25T15:11:00Z"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "concurrent_update"

    with api_client.app.state.session_factory() as session:
        session.add(TenantRow(tenant_id="tenant_other"))
        session.commit()
    cross_tenant = api_client.post(
        f"{MEMORY_PATH}/entries",
        headers=_headers("memory-cross", tenant_id="tenant_other"),
        json=body,
    )
    assert cross_tenant.status_code == 404
    assert _count(api_client, ResidentMemorySnapshotRow) == 1
