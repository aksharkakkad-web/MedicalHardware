"""Live sensors -> edge features -> envelopes -> ingest.

Reads the bridge's own snapshot stream, so it observes exactly what the
dashboard observes, and posts contract envelopes to an ingest endpoint at a
fixed cadence.

    python3 pipeline.py --ingest http://127.0.0.1:8500 --seconds 60
"""

from __future__ import annotations

import argparse
import json
import os
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


def post(url: str, body, retries: int = 2, api_key: str | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers)
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
    ap.add_argument("--api-key", default=os.environ.get("INGEST_API_KEY"),
                    help="bearer token for the ingest endpoint; "
                         "defaults to $INGEST_API_KEY")
    args = ap.parse_args()
    if not args.api_key:
        print("No API key. Set INGEST_API_KEY or pass --api-key.")
        return

    b = envelope.EnvelopeBuilder(args.device_id, args.tenant_id, args.room_id)
    t_end = time.monotonic() + args.seconds
    sent = accepted = rejected = 0
    assessments_sent = [0]
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

        vitals = snap.get("vitals") or {}
        v_conf = vitals.get("confidence")

        pl, why = extractors.radar_features(snap.get("radar"), health.get("radar", {}))
        # Confidence no longer surfaces as a number; it gates instead. A vitals
        # reading the conditions cannot support is withheld with its reason
        # rather than shipped for something downstream to treat as fact.
        pl, why = extractors.gate(pl, why, ["heart_rate_bpm", "respiration_rpm"], v_conf)
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
        pl, why = extractors.gate(pl, why, ["respiration_feature"], v_conf)
        if pl:
            envelopes.append(b.build("wifi_csi", extractors.FORMAT_CSI, pl, None, why, batch))

        if envelopes:
            code, resp = post(f"{args.ingest}/v1/ingest/telemetry", envelopes, api_key=args.api_key)
            sent += len(envelopes)
            accepted += resp.get("accepted", 0)
            rejected += resp.get("rejected", 0)
            if code != 202:
                for r in (resp.get("results") or []):
                    if r.get("errors"):
                        print(f"  REJECTED seq {r['sequence']}: {r['errors']}")

        # Abnormality travels on its own channel. The three payload formats are
        # frozen and have no field for a verdict, and the contract puts
        # baselines and anomaly logic in the cloud - so this is labelled
        # host-derived rather than folded into telemetry.
        est = ((snap.get("body") or {}).get("head_temp") or {}).get("estimate") or {}
        status = est.get("status")
        if status and status.get("state") not in (None, "no reading"):
            rel = status.get("relative") or {}
            t_conf = est.get("confidence") or {}
            assessment = {
                "schema_version": "1.0",
                "source_stage": "host",
                "device_id": args.device_id,
                "room_id": args.room_id,
                "kind": "temperature_deviation",
                "state": status["state"],
                "observed_at_ms": int(time.time() * 1000),
                "value_f": est.get("core_f"),
                "uncertainty_f": est.get("uncertainty_f"),
                "baseline_f": rel.get("baseline_f"),
                "delta_f": rel.get("delta_f"),
                "unusualness_pct": (est.get("unusualness") or {}).get("pct"),
                "measurement_confidence_pct": t_conf.get("pct"),
                "limiting_factor": t_conf.get("limiting"),
                "can_tell": status.get("can_tell"),
                "note": status.get("note"),
            }
            code, _ = post(f"{args.ingest}/v1/assessments", assessment, api_key=args.api_key)
            if code == 202:
                assessments_sent[0] += 1

        dev = snap.get("device") or {}
        post(f"{args.ingest}/v1/ingest/heartbeat",
             b.heartbeat("bench-0.1.0", dev.get("csi_dropped", 0),
                         [s for s in ("radar", "thermal", "wifi_csi")
                          if health.get(s, {}).get("status") == "ok"]),
             api_key=args.api_key)
        time.sleep(1.0 / args.hz)

    print(f"\nsent {sent}  accepted {accepted}  rejected {rejected}"
          f"  assessments {assessments_sent[0]}")


if __name__ == "__main__":
    main()
