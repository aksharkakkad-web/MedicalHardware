"""Strict stand-in for POST /v1/ingest/telemetry.

The real route does not exist yet and lives in the backend lane, so this
validates against docs/DATA_CONTRACT.md and rejects anything off-contract. It
is deliberately unforgiving: the point is to catch a malformed envelope here,
on the bench, rather than after the backend route is written.

Rejections carry the specific violation, because "422" alone tells the firmware
lane nothing.

    python3 -m mock_ingest.server [--port 8500]
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VALID_SOURCES = {"radar", "thermal", "wifi_csi", "accessory"}
VALID_FORMATS = {
    "radar_edge_features_v1", "mlx90640_edge_features_v1",
    "esp32_csi_edge_v1", "simulated_radar_edge_v1",
}
REQUIRED = [
    "schema_version", "device_id", "tenant_id", "room_id", "source",
    "sensor_model", "sequence", "device_time", "device_monotonic_ms",
    "payload_format", "payload",
]

# Fields whose absence is meaningful. A zero here would be a fabricated
# reading, so an explicit null is rejected just as hard as a wrong type: the
# contract says omit the field, not null it.
NEVER_NULL = {
    "distance_m", "heart_rate_bpm", "respiration_rpm",
    "presence_score", "movement_score", "respiration_feature",
    "centroid_x", "centroid_y", "max_observed_temp_c",
}


class Auth:
    """Bearer-token check for the ingest endpoints.

    The key is read from the environment or generated at startup - never a
    literal in the source, and never written to the repository. Comparison is
    constant-time so a wrong key cannot be recovered by timing the response.

    Reads are left open because /stats is a local bench aid. Writes are not.
    """

    def __init__(self, key: str | None) -> None:
        self.key = key
        self.generated = False
        if not self.key:
            self.key = secrets.token_urlsafe(24)
            self.generated = True

    def check(self, header: str | None) -> str | None:
        if not header:
            return "missing Authorization header; expected 'Bearer <key>'"
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer":
            return f"unsupported authorization scheme {scheme!r}; expected Bearer"
        if not hmac.compare_digest(token.strip(), self.key):
            return "invalid API key"
        return None


class Store:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.accepted: list[dict] = []
        self.rejected: list[dict] = []
        self.heartbeats: list[dict] = []
        self.assessments: list[dict] = []
        self.last_seq: dict[tuple[str, str], int] = {}


def validate(env: dict, store: Store) -> list[str]:
    errs = []
    for f in REQUIRED:
        if f not in env:
            errs.append(f"missing required field '{f}'")
    if errs:
        return errs

    if env["schema_version"] != "1.0":
        errs.append(f"unsupported schema_version {env['schema_version']!r}")
    if env["source"] not in VALID_SOURCES:
        errs.append(f"source {env['source']!r} not in {sorted(VALID_SOURCES)}")
    if env["payload_format"] not in VALID_FORMATS:
        errs.append(f"unknown payload_format {env['payload_format']!r}")
    if not isinstance(env["sequence"], int):
        errs.append("sequence must be an integer")
    if not isinstance(env.get("payload"), dict):
        errs.append("payload must be an object")

    # Strictly increasing per (device, source), per the contract.
    key = (env.get("device_id"), env.get("source"))
    seq = env.get("sequence")
    if isinstance(seq, int):
        prev = store.last_seq.get(key)
        if prev is not None and seq <= prev:
            errs.append(f"sequence {seq} not greater than previous {prev} for {key}")

    for k, v in (env.get("payload") or {}).items():
        if v is None and k in NEVER_NULL:
            errs.append(f"payload.{k} is null; omit the field instead of nulling it")
        if k.endswith("_score") or k == "signal_quality":
            if isinstance(v, (int, float)) and not (0.0 <= v <= 1.0):
                errs.append(f"payload.{k}={v} outside 0-1")

    t = env.get("transport")
    if t is not None:
        if not isinstance(t, dict):
            errs.append("transport must be an object")
        elif "retry_count" in t and not isinstance(t["retry_count"], int):
            errs.append("transport.retry_count must be an integer")
    return errs


def make_handler(store: Store, auth: Auth):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _json(self, code: int, body: dict):
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path != "/stats":
                self.send_error(404)
                return
            with store.lock:
                self._json(200, {
                    "accepted": len(store.accepted),
                    "rejected": len(store.rejected),
                    "heartbeats": len(store.heartbeats),
                    "assessments": len(store.assessments),
                    "recent_assessments": store.assessments[-3:],
                    "by_source": {
                        s: sum(1 for e in store.accepted if e["source"] == s)
                        for s in sorted({e["source"] for e in store.accepted})
                    },
                    "recent_rejections": store.rejected[-5:],
                })

        def do_POST(self):
            err = auth.check(self.headers.get("Authorization"))
            if err:
                # 401 with the reason, so a misconfigured sender can be fixed
                # without guessing. The reason never reveals the key.
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Bearer realm="ingest"')
                raw = json.dumps({"error": err}).encode()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            n = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError as e:
                self._json(400, {"error": f"invalid JSON: {e}"})
                return

            if self.path == "/v1/assessments":
                # Deliberately NOT part of the frozen telemetry payloads.
                # docs/DATA_CONTRACT.md puts personal baselines and anomaly
                # logic in the cloud, and the three payload formats have no
                # field for a verdict. Folding one in would silently fork the
                # contract, so host-derived assessments travel on their own
                # channel and are labelled as host-derived.
                errs = []
                for f in ("device_id", "room_id", "kind", "state", "observed_at_ms"):
                    if f not in body:
                        errs.append(f"missing required field '{f}'")
                if body.get("source_stage") != "host":
                    errs.append("source_stage must be 'host' for a host-derived assessment")
                if errs:
                    self._json(422, {"errors": errs})
                    return
                with store.lock:
                    store.assessments.append(body)
                self._json(202, {"ok": True})
                return

            if self.path == "/v1/ingest/heartbeat":
                with store.lock:
                    store.heartbeats.append(body)
                self._json(202, {"ok": True})
                return

            if self.path != "/v1/ingest/telemetry":
                self.send_error(404)
                return

            envelopes = body if isinstance(body, list) else [body]
            results = []
            for env in envelopes:
                with store.lock:
                    errs = validate(env, store)
                    if errs:
                        store.rejected.append({"sequence": env.get("sequence"),
                                               "source": env.get("source"),
                                               "errors": errs})
                    else:
                        store.accepted.append(env)
                        store.last_seq[(env["device_id"], env["source"])] = env["sequence"]
                results.append({"sequence": env.get("sequence"), "errors": errs})

            bad = [r for r in results if r["errors"]]
            self._json(422 if bad else 202,
                       {"accepted": len(results) - len(bad), "rejected": len(bad),
                        "results": results if bad else None})

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8500)
    ap.add_argument("--api-key", default=os.environ.get("INGEST_API_KEY"),
                    help="bearer token required on POST; defaults to $INGEST_API_KEY")
    args = ap.parse_args()
    store = Store()
    auth = Auth(args.api_key)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(store, auth))
    print(f"mock ingest on http://127.0.0.1:{args.port}")
    print("  POST /v1/ingest/telemetry   POST /v1/ingest/heartbeat")
    print("  POST /v1/assessments        GET  /stats")
    if auth.generated:
        print(f"\n  generated API key: {auth.key}")
        print("  export INGEST_API_KEY to set your own and keep it stable")
    else:
        print("\n  API key loaded from configuration")
    srv.serve_forever()


if __name__ == "__main__":
    main()
