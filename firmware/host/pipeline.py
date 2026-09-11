"""Live sensors -> edge features -> envelopes -> ingest.

Reads the bridge's own snapshot stream, so it observes exactly what the
dashboard observes, and posts contract envelopes to an ingest endpoint at a
fixed cadence.

    python3 pipeline.py --ingest http://127.0.0.1:8500 --seconds 60
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request

from edge import envelope, extractors


def read_snapshot(bridge_url: str, timeout: float = 10.0) -> dict | None:
    with urllib.request.urlopen(f"{bridge_url}/stream", timeout=timeout) as r:
        buf = b""
        while buf.count(b"\n\n") < 2:
            buf += r.read(1)
    chunks = [c for c in buf.decode().split("data: ") if c.strip().startswith("{")]
    return json.loads(chunks[-2]) if len(chunks) >= 2 else None


def post(url: str, body, retries: int = 2) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")
        except OSError:
            if attempt == retries:
                raise
            time.sleep(0.5 * (attempt + 1))
    return 0, {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bridge", default="http://127.0.0.1:8420")
    ap.add_argument("--ingest", default="http://127.0.0.1:8500")
    ap.add_argument("--device-id", default="dev_bench_01")
    ap.add_argument("--tenant-id", default="tenant_bench")
    ap.add_argument("--room-id", default="room_bench")
    ap.add_argument("--hz", type=float, default=1.0)
    ap.add_argument("--seconds", type=float, default=30.0)
    args = ap.parse_args()

    b = envelope.EnvelopeBuilder(args.device_id, args.tenant_id, args.room_id)
    t_end = time.monotonic() + args.seconds
    sent = accepted = rejected = 0
    prev_max_temp = None

    print(f"bridge {args.bridge} -> ingest {args.ingest} at {args.hz} Hz\n")
    while time.monotonic() < t_end:
        snap = read_snapshot(args.bridge)
        if not snap:
            time.sleep(1.0 / args.hz)
            continue

        health = snap.get("health", {})
        thermal = snap.get("thermal")
        batch = None
        envelopes = []

        # Temperature trend needs two frames; before that the field is absent
        # rather than 0.
        trend = None
        if thermal and prev_max_temp is not None:
            trend = thermal["max"] - prev_max_temp
        if thermal:
            prev_max_temp = thermal["max"]

        pl, why = extractors.radar_features(snap.get("radar"), health.get("radar", {}))
        if pl:
            envelopes.append(b.build("radar", extractors.FORMAT_RADAR, pl, None, why, batch))

        pl, why = extractors.thermal_features(snap.get("body"), thermal,
                                              health.get("thermal", {}), trend)
        if pl:
            envelopes.append(b.build("thermal", extractors.FORMAT_THERMAL, pl, None, why, batch))

        pl, why = extractors.csi_features(snap.get("csi"), snap.get("csi_motion"),
                                          snap.get("csi_vitals"),
                                          health.get("csi", {}),
                                          snap.get("csi_captured_hz"))
        if pl:
            envelopes.append(b.build("wifi_csi", extractors.FORMAT_CSI, pl, None, why, batch))

        if envelopes:
            code, resp = post(f"{args.ingest}/v1/ingest/telemetry", envelopes)
            sent += len(envelopes)
            accepted += resp.get("accepted", 0)
            rejected += resp.get("rejected", 0)
            if code != 202:
                for r in (resp.get("results") or []):
                    if r.get("errors"):
                        print(f"  REJECTED seq {r['sequence']}: {r['errors']}")

        dev = snap.get("device") or {}
        post(f"{args.ingest}/v1/ingest/heartbeat",
             b.heartbeat("bench-0.1.0", dev.get("csi_dropped", 0),
                         [s for s in ("radar", "thermal", "wifi_csi")
                          if health.get(s, {}).get("status") == "ok"]))
        time.sleep(1.0 / args.hz)

    print(f"\nsent {sent}  accepted {accepted}  rejected {rejected}")


if __name__ == "__main__":
    main()
