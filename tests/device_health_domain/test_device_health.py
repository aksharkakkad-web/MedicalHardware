from datetime import datetime, timedelta, timezone

import pytest

from backend.app.domain.device_health import (
    DeviceHealthObservation,
    DeviceHealthState,
    DeviceSourceHealth,
    DeviceSourceHealthState,
)


OBSERVED_AT = datetime(2026, 8, 25, 14, 0, tzinfo=timezone.utc)


def _observation(**overrides: object) -> DeviceHealthObservation:
    values: dict[str, object] = {
        "device_id": "device_room_214",
        "state": DeviceHealthState.ONLINE,
        "observed_at": OBSERVED_AT,
        "last_seen_at": OBSERVED_AT - timedelta(seconds=5),
        "sources": (
            DeviceSourceHealth(
                source="radar",
                state=DeviceSourceHealthState.ONLINE,
            ),
            DeviceSourceHealth(
                source="thermal",
                state=DeviceSourceHealthState.DEGRADED,
                limitations=("reduced_frame_rate",),
            ),
        ),
        "limitations": ("thermal_detail_reduced",),
    }
    values.update(overrides)
    return DeviceHealthObservation(**values)


@pytest.mark.parametrize("state", tuple(DeviceHealthState))
def test_all_approved_product_health_states_are_supported(
    state: DeviceHealthState,
) -> None:
    observation = _observation(state=state)

    assert observation.state is state
    assert observation.schema_version == "1.0"
    assert observation.policy_test_only is True


def test_source_health_is_strict_and_preserves_limitations() -> None:
    source = DeviceSourceHealth(
        source=" wifi_csi ",
        state="degraded",
        limitations=(" packet_loss ",),
    )

    assert source.source == "wifi_csi"
    assert source.state is DeviceSourceHealthState.DEGRADED
    assert source.limitations == ("packet_loss",)
    assert source.schema_version == "1.0"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("device_id", " "),
        ("state", "healthy"),
        ("observed_at", datetime(2026, 8, 25, 14, 0)),
        (
            "observed_at",
            datetime(
                2026,
                8,
                25,
                10,
                0,
                tzinfo=timezone(-timedelta(hours=4)),
            ),
        ),
        ("sources", [DeviceSourceHealth("radar", "online")]),
        ("limitations", ["late_packets"]),
        ("policy_test_only", 1),
        ("policy_version", " "),
    ),
)
def test_observation_rejects_ambiguous_or_non_utc_values(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        _observation(**{field: value})


def test_observation_rejects_future_last_seen_and_duplicate_sources() -> None:
    with pytest.raises(ValueError, match="last_seen_at"):
        _observation(last_seen_at=OBSERVED_AT + timedelta(seconds=1))

    radar = DeviceSourceHealth("radar", "online")
    with pytest.raises(ValueError, match="sources"):
        _observation(sources=(radar, radar))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("source", " "),
        ("state", "healthy"),
        ("limitations", ["late_packets"]),
        ("limitations", (" ",)),
        ("limitations", ("late_packets", "late_packets")),
    ),
)
def test_source_health_rejects_invalid_values(field: str, value: object) -> None:
    values: dict[str, object] = {
        "source": "radar",
        "state": "online",
        "limitations": (),
    }
    values[field] = value

    with pytest.raises(ValueError):
        DeviceSourceHealth(**values)
