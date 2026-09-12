"""Contract conformance for the edge telemetry path.

The negative cases carry the weight. An ingest validator that accepts
everything proves nothing, and the failure this whole path is built to prevent
is a fabricated zero reaching the product.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from edge import envelope, extractors  # noqa: E402
from mock_ingest.server import Store, validate  # noqa: E402

FIXTURES = HERE / "fixtures"


def builder():
    return envelope.EnvelopeBuilder("dev_bench_01", "tenant_bench", "room_bench")


def test_valid_envelope_accepted():
    b, store = builder(), Store()
    env = b.build("radar", extractors.FORMAT_RADAR,
                  {"distance_m": 1.02, "signal_quality": 0.9}, 123456)
    assert validate(env, store) == []


def test_sequence_strictly_increases_per_source():
    b = builder()
    radar = [b.build("radar", extractors.FORMAT_RADAR, {}, None)["sequence"] for _ in range(3)]
    thermal = [b.build("thermal", extractors.FORMAT_THERMAL, {}, None)["sequence"] for _ in range(3)]
    assert radar == [1, 2, 3]
    # Streams are independent, as the contract specifies per (device, source).
    assert thermal == [1, 2, 3]


def test_replayed_sequence_rejected():
    b, store = builder(), Store()
    env = b.build("radar", extractors.FORMAT_RADAR, {"signal_quality": 0.8}, None)
    assert validate(env, store) == []
    store.last_seq[("dev_bench_01", "radar")] = env["sequence"]
    again = dict(env)
    errs = validate(again, store)
    assert any("not greater than previous" in e for e in errs), errs


def test_null_in_a_measurement_field_is_rejected():
    """The contract says omit an unavailable field, not null it."""
    b, store = builder(), Store()
    env = b.build("radar", extractors.FORMAT_RADAR,
                  {"distance_m": None, "signal_quality": 0.8}, None)
    errs = validate(env, store)
    assert any("omit the field" in e for e in errs), errs


def test_score_out_of_range_rejected():
    b, store = builder(), Store()
    env = b.build("wifi_csi", extractors.FORMAT_CSI,
                  {"presence_score": 1.7, "signal_quality": 0.5}, None)
    errs = validate(env, store)
    assert any("outside 0-1" in e for e in errs), errs


def test_unknown_payload_format_rejected():
    b, store = builder(), Store()
    env = b.build("radar", "radar_edge_features_v99", {"signal_quality": 0.5}, None)
    errs = validate(env, store)
    assert any("unknown payload_format" in e for e in errs), errs


def test_missing_required_field_rejected():
    b, store = builder(), Store()
    env = b.build("radar", extractors.FORMAT_RADAR, {"signal_quality": 0.5}, None)
    del env["room_id"]
    errs = validate(env, store)
    assert any("room_id" in e for e in errs), errs


# --- the rule this whole path exists to enforce --------------------------

def test_radar_with_no_target_omits_distance_and_vitals():
    """With nobody present the module still volunteers distance 0.0.

    Forwarding it would put a confident "0.00 m" into an empty room.
    """
    payload, reasons = extractors.radar_features(
        {"presence": False, "distance_m": 0.0,
         "respiration_rpm": None, "heart_rate_bpm": None},
        {"hz": 8.0},
    )
    assert "distance_m" not in payload
    assert "heart_rate_bpm" not in payload
    assert "respiration_rpm" not in payload
    assert any("no target" in r for r in reasons)


def test_radar_absent_vitals_are_omitted_not_zeroed():
    payload, reasons = extractors.radar_features(
        {"presence": True, "distance_m": 1.2,
         "respiration_rpm": None, "heart_rate_bpm": None},
        {"hz": 8.0},
    )
    assert payload["distance_m"] == 1.2
    assert "heart_rate_bpm" not in payload
    assert len([r for r in reasons if "not reported" in r]) == 2


def test_thermal_near_floor_needs_a_whole_body():
    """A person standing close looks like one lying down when cut off."""
    body = {"fully_visible": False,
            "landmarks": {"torso": {"x": 16.0, "y": 12.0},
                          "base": {"x": 16.0, "y": 23.0}}}
    payload, reasons = extractors.thermal_features(
        body, {"max": 34.0, "min": 21.0}, {"hz": 8.0}, 0.1)
    assert "position_features" not in payload
    assert any("fully visible" in r for r in reasons)

    body["fully_visible"] = True
    payload, _ = extractors.thermal_features(
        body, {"max": 34.0, "min": 21.0}, {"hz": 8.0}, 0.1)
    assert "near_floor_score" in payload["position_features"]


def test_temperature_trend_absent_without_history():
    payload, reasons = extractors.thermal_features(
        None, {"max": 34.0, "min": 21.0}, {"hz": 8.0}, None)
    assert "temperature_trend_c" not in payload
    assert any("trend" in r for r in reasons)


def test_every_generated_envelope_validates():
    """Generate one of each and check them against the receiver."""
    b, store = builder(), Store()
    cases = [
        ("radar", extractors.FORMAT_RADAR,
         extractors.radar_features({"presence": True, "distance_m": 1.02,
                                    "respiration_rpm": 15.0, "heart_rate_bpm": 72.0},
                                   {"hz": 8.0})),
        ("thermal", extractors.FORMAT_THERMAL,
         extractors.thermal_features(
             {"fully_visible": True,
              "landmarks": {"torso": {"x": 16.0, "y": 12.0},
                            "base": {"x": 16.0, "y": 22.0}}},
             {"max": 34.2, "min": 21.0}, {"hz": 8.0}, 0.2)),
        ("wifi_csi", extractors.FORMAT_CSI,
         extractors.csi_features({"rssi": -55}, {"energy": 1.4},
                                 {"breathing_rpm": 14.0}, {"hz": 100.0}, 480.0)),
    ]
    out = []
    for source, fmt, (payload, reasons) in cases:
        env = b.build(source, fmt, payload, 9184490, reasons)
        errs = validate(env, store)
        assert errs == [], (source, errs)
        store.last_seq[(env["device_id"], env["source"])] = env["sequence"]
        out.append(env)

    # Handoff artefact for whoever implements the real backend route.
    FIXTURES.mkdir(exist_ok=True)
    (FIXTURES / "valid_envelopes.json").write_text(json.dumps(out, indent=2))
    (FIXTURES / "heartbeat.json").write_text(
        json.dumps(b.heartbeat("bench-0.1.0", 0, ["radar", "thermal", "wifi_csi"]), indent=2))


# --- auth ----------------------------------------------------------------

def test_auth_rejects_missing_wrong_and_bad_scheme():
    from mock_ingest.server import Auth
    a = Auth("correct-horse")
    assert a.check(None) is not None
    assert "missing Authorization" in a.check(None)
    assert "invalid API key" in a.check("Bearer wrong")
    assert "unsupported authorization scheme" in a.check("Basic correct-horse")
    assert a.check("Bearer correct-horse") is None


def test_auth_generates_a_key_when_none_supplied():
    """A server with no configured key must not end up unauthenticated."""
    from mock_ingest.server import Auth
    a = Auth(None)
    assert a.generated
    assert len(a.key) >= 20
    assert a.check(f"Bearer {a.key}") is None


def test_auth_error_never_echoes_the_key():
    from mock_ingest.server import Auth
    a = Auth("super-secret-value")
    for header in (None, "Bearer nope", "Basic super-secret-value"):
        msg = a.check(header) or ""
        assert "super-secret-value" not in msg, msg


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_"):
            continue
        try:
            fn()
            print(f"PASS {name}")
            passed += 1
        except AssertionError as exc:
            print(f"FAIL {name}: {exc}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
