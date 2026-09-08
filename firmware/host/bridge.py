"""Serial -> browser bridge for the bench node.

Reads the binary frame stream (or a synthetic stand-in), keeps the latest state
per modality, and pushes snapshots to the dashboard over server-sent events.

SSE rather than WebSockets on purpose: it is one-way, which is all a live view
needs, and it works on the standard library alone.

Run with hardware:      python3 -m bridge --port /dev/cu.usbmodemXXXX
Run without hardware:   python3 -m bridge --source fake

Synthetic output is labelled as such the whole way to the browser, which shows a
DEMO badge. Measured and simulated data must never be mistakable for one another.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import random
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import stream.frames as F

DASHBOARD = Path(__file__).parent / "dashboard" / "index.html"


class RateMeter:
    """Frames/sec over a sliding window."""

    def __init__(self, window: float = 3.0) -> None:
        self.window = window
        self.stamps: list[float] = []

    def tick(self) -> None:
        now = time.monotonic()
        self.stamps.append(now)
        cutoff = now - self.window
        while self.stamps and self.stamps[0] < cutoff:
            self.stamps.pop(0)

    @property
    def hz(self) -> float:
        if len(self.stamps) < 2:
            return 0.0
        span = self.stamps[-1] - self.stamps[0]
        return (len(self.stamps) - 1) / span if span > 0 else 0.0

    @property
    def age(self) -> float:
        return time.monotonic() - self.stamps[-1] if self.stamps else 1e9


# MLX90640 optical field of view, from the datasheet. Used to turn a thermal
# column index into a real bearing, which is what lets a thermal centroid and a
# radar distance describe the same point in the room.
THERMAL_FOV_H_DEG = 55.0
THERMAL_FOV_V_DEG = 35.0


def thermal_blob(px: list[float]) -> dict | None:
    """Locate the warmest connected region and describe it.

    Returns None when the scene has no meaningful thermal contrast. A flat room
    must read as empty rather than as a person-shaped patch of sensor noise.
    """
    ordered = sorted(px)
    ambient = ordered[len(ordered) // 2]
    peak = ordered[-1]
    contrast = peak - ambient

    # Below this the frame is a uniform room. The threshold is deliberately
    # generous: a false "nobody here" is safer than a phantom person.
    if contrast < 1.8:
        return None

    cut = ambient + contrast * 0.55
    sx = sy = n = 0
    lo_x, hi_x, lo_y, hi_y = 999, -1, 999, -1
    for i, v in enumerate(px):
        if v < cut:
            continue
        col = i % F.THERMAL_COLS
        row = i // F.THERMAL_COLS
        sx += col
        sy += row
        n += 1
        lo_x = min(lo_x, col); hi_x = max(hi_x, col)
        lo_y = min(lo_y, row); hi_y = max(hi_y, row)

    if n < 4:
        return None

    cx = sx / n
    bearing = ((cx / F.THERMAL_COLS) - 0.5) * THERMAL_FOV_H_DEG
    return {
        "cx": round(cx, 2),
        "cy": round(sy / n, 2),
        "pixels": n,
        "box": [lo_x, lo_y, hi_x, hi_y],
        "bearing_deg": round(bearing, 1),
        "peak_c": round(peak, 1),
        "ambient_c": round(ambient, 1),
        "contrast_c": round(contrast, 1),
    }


class State:
    """Latest value per modality, plus liveness."""

    def __init__(self, simulated: bool) -> None:
        self.lock = threading.Lock()
        self.simulated = simulated
        self.thermal: list[float] | None = None
        self.radar: F.RadarFrame | None = None
        self.csi_amps: list[float] | None = None
        self.csi_rssi: int | None = None
        self.lux: float | None = None
        self.rate = {
            "thermal": RateMeter(), "radar": RateMeter(),
            "csi": RateMeter(), "ambient": RateMeter(),
        }
        self.parser_stats = F.Stats()
        self.connected = False
        self.source_label = "simulated" if simulated else "waiting"

    def apply(self, frame) -> None:
        with self.lock:
            if isinstance(frame, F.ThermalFrame):
                self.thermal = frame.pixels
                self.rate["thermal"].tick()
            elif isinstance(frame, F.RadarFrame):
                self.radar = frame
                self.rate["radar"].tick()
            elif isinstance(frame, F.CsiFrame):
                self.csi_amps = frame.amplitudes
                self.csi_rssi = frame.rssi
                self.rate["csi"].tick()
            elif isinstance(frame, F.AmbientFrame):
                self.lux = frame.lux
                self.rate["ambient"].tick()

    def snapshot(self) -> dict:
        with self.lock:
            thermal = self.thermal
            radar = self.radar
            amps = self.csi_amps
            rssi = self.csi_rssi
            lux = self.lux
            rates = {k: (m.hz, m.age) for k, m in self.rate.items()}
            stats = self.parser_stats

        def health(key: str, expect: float) -> dict:
            hz, age = rates[key]
            if age > 3.0:
                status = "offline"
            elif hz < expect * 0.5:
                status = "degraded"
            else:
                status = "ok"
            return {"hz": round(hz, 1), "status": status}

        out = {
            "simulated": self.simulated,
            "source": self.source_label,
            "health": {
                "thermal": health("thermal", 7.0),
                "radar": health("radar", 4.0),
                "csi": health("csi", 8.0),
                "ambient": health("ambient", 1.5),
            },
            "stats": {
                "frames_ok": stats.frames_ok,
                "crc_errors": stats.crc_errors,
                "resyncs": stats.resyncs,
            },
        }

        blob = None
        if thermal:
            blob = thermal_blob(thermal)
            out["thermal"] = {
                "pixels": [round(v, 1) for v in thermal],
                "min": round(min(thermal), 1),
                "max": round(max(thermal), 1),
                "blob": blob,
            }
        if radar:
            # None stays None all the way to the browser. Never coerce an
            # absent reading into a number.
            out["radar"] = {
                "presence": radar.presence,
                "distance_m": None if radar.distance_m is None else round(radar.distance_m, 2),
                "respiration_rpm": None if radar.respiration_rpm is None else round(radar.respiration_rpm, 1),
                "heart_rate_bpm": None if radar.heart_rate_bpm is None else round(radar.heart_rate_bpm, 1),
            }
        if amps:
            out["csi"] = {"amps": [round(a, 1) for a in amps[:64]], "rssi": rssi}

        # Dark/lit only. The BH1750 is broadband with no spectral channels, so
        # anything circadian would need melanopic weighting this part cannot
        # provide - see firmware/docs/LIGHT_SENSING_NOTES.md.
        if lux is not None and rates["ambient"][1] < 3.0:
            if lux < 5:
                band = "dark"
            elif lux < 50:
                band = "dim"
            elif lux < 300:
                band = "lit"
            else:
                band = "bright"
            out["ambient"] = {"lux": round(lux, 1), "band": band}

        # Cross-check the two independent sensors. This is the part that earns
        # its keep: the radar alone will report a confident target, and even a
        # heart rate, off a desk. Thermal cannot see a desk as warm, so
        # disagreement is the signal that something is wrong.
        radar_target = bool(radar and radar.presence)
        thermal_body = blob is not None
        if radar_target and thermal_body:
            agree, verdict = True, "person"
        elif radar_target and not thermal_body:
            agree, verdict = False, "radar_only"
        elif thermal_body and not radar_target:
            agree, verdict = False, "thermal_only"
        else:
            agree, verdict = True, "empty"

        out["fusion"] = {
            "verdict": verdict,
            "agree": agree,
            "distance_m": None if not radar or radar.distance_m is None else round(radar.distance_m, 2),
            "bearing_deg": blob["bearing_deg"] if blob else None,
        }
        return out


# ------------------------------------------------------------------ sources ---

def serial_reader(state: State, port: str) -> None:
    import serial  # imported lazily so the fake source needs no dependency

    parser = F.FrameParser()
    state.parser_stats = parser.stats
    while True:
        try:
            with serial.Serial(port, 115200, timeout=0.1) as ser:
                state.connected = True
                state.source_label = port
                while True:
                    chunk = ser.read(8192)
                    if chunk:
                        for frame in parser.feed(chunk):
                            state.apply(frame)
        except Exception as exc:  # port vanished on reset, or not plugged in
            state.connected = False
            state.source_label = f"reconnecting ({exc.__class__.__name__})"
            time.sleep(1.0)


def fake_reader(state: State) -> None:
    """Synthetic frames through the real encoder and the real parser.

    Deliberately routed through the same code path as hardware so the dashboard
    cannot accidentally work only for simulated input.
    """
    parser = F.FrameParser()
    state.parser_stats = parser.stats
    t0 = time.monotonic()
    next_thermal = next_radar = next_csi = 0.0

    while True:
        now = time.monotonic()
        t = now - t0
        t_us = int(now * 1e6)
        blob = b""

        # A warm body drifting across the field of view.
        if now >= next_thermal:
            next_thermal = now + 1 / 8
            cx = 16 + 9 * math.sin(t * 0.4)
            cy = 12 + 4 * math.cos(t * 0.3)
            px = []
            for row in range(F.THERMAL_ROWS):
                for col in range(F.THERMAL_COLS):
                    d2 = (col - cx) ** 2 + ((row - cy) * 1.4) ** 2
                    px.append(21.5 + 12.0 * math.exp(-d2 / 26.0) + random.gauss(0, 0.12))
            blob += F.encode(F.TYPE_THERMAL, t_us, F._THERMAL.pack(*px))

        if now >= next_radar:
            next_radar = now + 1 / 8
            dist = 1.05 + 0.35 * math.sin(t * 0.25)
            breathing = 14.0 + 1.5 * math.sin(t * 0.11)
            valid = F.RADAR_VALID_PRESENCE | F.RADAR_VALID_DISTANCE | F.RADAR_VALID_RESPIRATION
            hr = float("nan")
            # Heart rate only inside its usable range, and even then only
            # sometimes - matching how the real part behaves.
            if dist < 1.5 and math.sin(t * 0.2) > -0.3:
                valid |= F.RADAR_VALID_HEART_RATE
                hr = 68.0 + 6.0 * math.sin(t * 0.5)
            blob += F.encode(
                F.TYPE_RADAR, t_us,
                F._RADAR.pack(valid, 1, 0xFF, dist, breathing, hr),
            )

        if now >= next_csi:
            next_csi = now + 1 / 120
            n = 64
            iq = []
            for k in range(n):
                base = 22 + 9 * math.sin(k * 0.28)
                breath = 2.6 * math.sin(t * 1.4 + k * 0.05)
                amp = base + breath + random.gauss(0, 1.4)
                ph = k * 0.35 + t
                iq += [
                    max(-127, min(127, int(amp * math.cos(ph)))),
                    max(-127, min(127, int(amp * math.sin(ph)))),
                ]
            blob += F.encode(
                F.TYPE_CSI, t_us,
                F._CSI_HEAD.pack(-47 + int(3 * math.sin(t)), n) + struct.pack(f"<{n*2}b", *iq),
            )

        if blob:
            for frame in parser.feed(blob):
                state.apply(frame)
        time.sleep(0.004)


# ------------------------------------------------------------------- server ---

def make_handler(state: State):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # keep the console clean
            pass

        def do_GET(self):
            if self.path.startswith("/stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                try:
                    while True:
                        payload = json.dumps(state.snapshot())
                        self.wfile.write(f"data: {payload}\n\n".encode())
                        self.wfile.flush()
                        time.sleep(1 / 15)
                except (BrokenPipeError, ConnectionResetError):
                    return
            elif self.path in ("/", "/index.html"):
                body = DASHBOARD.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

    return Handler


def autodetect_port() -> str | None:
    # The Anker hub enumerates as a usbmodem too; it is not a board.
    cands = [p for p in glob.glob("/dev/cu.usbmodem*") if "SN234567892" not in p]
    return cands[0] if cands else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["serial", "fake"], default="serial")
    ap.add_argument("--port", default=None)
    ap.add_argument("--http-port", type=int, default=8420)
    args = ap.parse_args()

    if args.source == "serial":
        port = args.port or autodetect_port()
        if not port:
            print("No board found. Plug one in, or run with --source fake.")
            return
        state = State(simulated=False)
        threading.Thread(target=serial_reader, args=(state, port), daemon=True).start()
        print(f"Reading {port}")
    else:
        state = State(simulated=True)
        threading.Thread(target=fake_reader, args=(state,), daemon=True).start()
        print("Synthetic source - output is labelled DEMO in the dashboard")

    srv = ThreadingHTTPServer(("127.0.0.1", args.http_port), make_handler(state))
    print(f"\n  Dashboard:  http://127.0.0.1:{args.http_port}\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
