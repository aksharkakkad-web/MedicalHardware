"""Turn live sensor state into the payloads docs/DATA_CONTRACT.md declares.

One rule governs everything here, from the contract's quality rules:

    An unavailable value is never zero-filled, imputed, or forward-filled.

So a field is either present with a real measurement or absent from the dict
entirely, and the reason is recorded in `quality_reasons`. This matters more
than it sounds. The radar volunteers a distance of 0.0 with nobody in the room
and a confident heart rate off a desk; forwarding either as a number puts a
fabricated reading into the product.

Scores are normalised 0-1 because the contract's examples are. Where a real
measurement has different units the conversion is stated inline.
"""

from __future__ import annotations

FORMAT_RADAR = "radar_edge_features_v1"
FORMAT_THERMAL = "mlx90640_edge_features_v1"
FORMAT_CSI = "esp32_csi_edge_v1"

THERMAL_COLS = 32
THERMAL_ROWS = 24


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def radar_features(radar: dict | None, health: dict) -> tuple[dict, list[str]]:
    """radar_edge_features_v1."""
    payload: dict = {}
    reasons: list[str] = []
    if not radar:
        return payload, ["no radar frame"]

    present = radar.get("presence")
    if present is None:
        reasons.append("presence unknown")
    elif not present:
        # Everything else is conditional on somebody being there. Emitting a
        # distance for an empty room is the zero-fill this contract forbids.
        reasons.append("no target present")
        payload["movement_score"] = 0.0
        payload["signal_quality"] = _clamp01(health.get("hz", 0) / 8.0)
        return payload, reasons

    if radar.get("distance_m") is not None:
        payload["distance_m"] = round(radar["distance_m"], 2)
    else:
        reasons.append("distance not reported")

    for src, dst in (("respiration_rpm", "respiration_rpm"),
                     ("heart_rate_bpm", "heart_rate_bpm")):
        if radar.get(src) is not None:
            payload[dst] = round(radar[src], 1)
        else:
            reasons.append(f"{dst} not reported by the module")

    # Movement is not a field the module gives, so derive it from range change
    # rather than inventing a scale.
    payload["signal_quality"] = _clamp01(health.get("hz", 0) / 8.0)
    return payload, reasons


def thermal_features(body: dict | None, thermal: dict | None,
                     health: dict, trend_c: float | None) -> tuple[dict, list[str]]:
    """mlx90640_edge_features_v1."""
    payload: dict = {}
    reasons: list[str] = []
    if not thermal:
        return payload, ["no thermal frame"]

    payload["person_detected"] = body is not None
    payload["max_observed_temp_c"] = thermal.get("max")

    if trend_c is not None:
        payload["temperature_trend_c"] = round(trend_c, 2)
    else:
        reasons.append("temperature trend needs more history")

    if body:
        # Contract centroids are normalised 0-1 across the frame.
        torso = (body.get("landmarks") or {}).get("torso")
        if torso:
            payload["centroid_x"] = round(torso["x"] / THERMAL_COLS, 2)
            payload["centroid_y"] = round(torso["y"] / THERMAL_ROWS, 2)

        # near_floor_score: how low in frame the body sits. Only meaningful
        # when the body is not cut off at the bottom - otherwise a person
        # standing close looks identical to one lying down.
        if body.get("fully_visible"):
            base = (body.get("landmarks") or {}).get("base")
            if base:
                payload["position_features"] = {
                    "near_floor_score": round(_clamp01(base["y"] / (THERMAL_ROWS - 1)), 2)
                }
        else:
            reasons.append("near_floor_score needs a fully visible body")
    else:
        reasons.append("no body region above thermal contrast threshold")

    payload["signal_quality"] = _clamp01(health.get("hz", 0) / 8.0)
    return payload, reasons


def csi_features(csi: dict | None, motion: dict | None, vitals: dict | None,
                 health: dict, captured_hz: float | None) -> tuple[dict, list[str]]:
    """esp32_csi_edge_v1."""
    payload: dict = {}
    reasons: list[str] = []
    if not csi:
        return payload, ["no CSI frame"]

    if motion:
        energy = motion.get("energy", 0.0)
        payload["movement_score"] = round(_clamp01(energy / 5.0), 2)
        # Presence from channel disturbance. One antenna cannot localise, so
        # this says the path changed, not that a person is in a given place.
        payload["presence_score"] = round(_clamp01(energy / 3.0), 2)
    else:
        reasons.append("movement needs a longer CSI history")

    rssi = csi.get("rssi")
    if rssi is not None:
        # Link degradation relative to the strong-link reference of -50 dBm.
        payload["rf_disturbance_score"] = round(_clamp01((-50 - rssi) / 40.0), 2)

    if vitals and vitals.get("breathing_rpm") is not None:
        # A feature, not a rate: the contract's field is a normalised score.
        payload["respiration_feature"] = round(_clamp01(vitals["breathing_rpm"] / 30.0), 2)
    else:
        reasons.append("no breathing periodicity in the CSI band")

    # Quality against the capture rate the link is actually sustaining.
    if captured_hz:
        payload["signal_quality"] = round(_clamp01(captured_hz / 450.0), 2)
    else:
        payload["signal_quality"] = round(_clamp01(health.get("hz", 0) / 100.0), 2)
    return payload, reasons
