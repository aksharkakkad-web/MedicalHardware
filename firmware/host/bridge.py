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
import copy
import glob
import json
import math
import os
import random
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import stream.frames as F
from vitals import VitalsEstimator
from radar_decode import RadarDecoder, ID_HEART, ID_BREATH, ID_CLOUD
import body_model
import motion_body
import vitals_select
import confidence

DASHBOARD = Path(__file__).parent / "dashboard" / "index.html"
BODY_VIEW = Path(__file__).parent / "dashboard" / "body.html"


def json_safe(obj):
    """Replace non-finite floats with None, recursively.

    json.dumps writes NaN and Infinity as bare tokens, which are not JSON. The
    browser's JSON.parse rejects the whole message, so a single NaN anywhere in
    a snapshot froze every panel on the dashboard while the sensors were fine.
    An absent reading is None the whole way to the browser.
    """
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    return obj


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
        if self.age > self.window or len(self.stamps) < 2:
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

# The sensor is mounted rotated 180 degrees on the carrier, so the frame is
# rotated rather than merely flipped: correcting only the vertical axis would
# mirror left and right, which would silently invert the bearing that the room
# plan depends on. Applied once here so blob detection, bearing and the
# rendered image all share one orientation.
THERMAL_ROTATE_180 = True


def orient(px: list[float]) -> list[float]:
    return list(reversed(px)) if THERMAL_ROTATE_180 else px


def thermal_blob(px: list[float]) -> dict | None:
    """Locate the warmest connected region and describe it.

    Returns None when the scene has no meaningful thermal contrast. A flat room
    must read as empty rather than as a person-shaped patch of sensor noise.
    """
    if len(px) != F.THERMAL_PIXELS or not all(math.isfinite(v) for v in px):
        return None
    ordered = sorted(px)
    ambient = ordered[len(ordered) // 2]
    peak = ordered[-1]
    contrast = peak - ambient

    # Low contrast means no resolved warm region, not proof of an empty room.
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


def body_geometry(px: list[float], blob: dict | None, distance_m: float | None) -> dict | None:
    """Anatomical landmarks measured from the thermal silhouette.

    These are *measured* from real pixels, not inferred by a model. That is the
    whole reason they exist: a person at 1 m covers roughly 20 thermal pixels,
    which supports a head, a shoulder line, a torso centroid and a base - and
    does not support 17 COCO keypoints. Anything finer would be invention.
    """
    if blob is None:
        return None

    ordered = sorted(px)
    ambient = ordered[len(ordered) // 2]
    cut = ambient + (ordered[-1] - ambient) * 0.55

    # Width profile: for each row, the horizontal span of warm pixels.
    rows: dict[int, list[int]] = {}
    for i, v in enumerate(px):
        if v >= cut:
            rows.setdefault(i // F.THERMAL_COLS, []).append(i % F.THERMAL_COLS)
    if not rows:
        return None

    ys = sorted(rows)
    top, base = ys[0], ys[-1]
    height_px = max(1, base - top + 1)

    def span(r):
        cols = rows[r]
        return min(cols), max(cols)

    # Head: centroid of the top ~20% of the silhouette.
    head_rows = [r for r in ys if r <= top + max(1, height_px * 0.2)]
    head_cols = [c for r in head_rows for c in rows[r]]
    head = (sum(head_cols) / len(head_cols), sum(head_rows) / len(head_rows))

    # Shoulders: the widest row in the upper half.
    upper = [r for r in ys if r <= top + height_px * 0.5]
    sh_row = max(upper, key=lambda r: span(r)[1] - span(r)[0]) if upper else top
    sh_lo, sh_hi = span(sh_row)

    all_cols = [c for r in ys for c in rows[r]]
    centroid = (sum(all_cols) / len(all_cols), sum(r for r in ys for _ in rows[r]) / len(all_cols))
    base_cols = rows[base]
    base_pt = (sum(base_cols) / len(base_cols), float(base))

    width_px = max(1, max(span(r)[1] - span(r)[0] + 1 for r in ys))
    aspect = height_px / width_px

    # Real scale, when the radar has a distance. The MLX90640's 35 degree
    # vertical field of view spans 2*d*tan(17.5) metres across 24 pixels.
    height_m = None
    if distance_m:
        m_per_px = (2.0 * distance_m * math.tan(math.radians(THERMAL_FOV_V_DEG / 2))) / F.THERMAL_ROWS
        height_m = round(height_px * m_per_px, 2)

    # Posture from the extent ratio. Coarse on purpose - this is a shape
    # measurement, not a classifier, and it is reported with its evidence.
    if aspect >= 1.6:
        posture = "upright"
    elif aspect >= 0.9:
        posture = "seated or partly turned"
    else:
        posture = "horizontal"

    return {
        "head": [round(head[0], 2), round(head[1], 2)],
        "shoulder_l": [float(sh_lo), float(sh_row)],
        "shoulder_r": [float(sh_hi), float(sh_row)],
        "torso": [round(centroid[0], 2), round(centroid[1], 2)],
        "base": [round(base_pt[0], 2), round(base_pt[1], 2)],
        "height_px": height_px,
        "width_px": width_px,
        "aspect": round(aspect, 2),
        "height_m": height_m,
        "posture": posture,
        "source": "thermal",
    }


class State:
    """Latest value per modality, plus liveness."""

    def __init__(self, simulated: bool) -> None:
        self.lock = threading.Lock()
        self.snapshot_lock = threading.Lock()
        self.device_times = {}
        self.received_at = {}
        self.radar_raw = False
        self.vitals_out_at = None
        self._epoch = 0
        self._derived_epoch = 0
        self.simulated = simulated
        self.thermal: list[float] | None = None
        self.radar: F.RadarFrame | None = None
        self.radar_decoder = RadarDecoder()
        self.csi_amps: list[float] | None = None
        self.csi_rssi: int | None = None
        self.lux: float | None = None
        # All vitals DSP runs here on the host, not on the node. The device
        # streams raw CSI and does no analysis.
        self.vitals = VitalsEstimator()
        self.vitals_out: dict | None = None
        # Short history of CSI amplitude for a motion-energy readout. CSI
        # cannot give body landmarks from a single antenna, but it does
        # genuinely report whether the channel is being disturbed.
        self.csi_hist: list[list[float]] = []
        self.device: F.DeviceStats | None = None
        self._prev_dev: tuple[float, int] | None = None
        self._captured_hz: float | None = None
        # Rolling window of skin readings. The detected head region shifts by a
        # pixel or two between frames and the peak moves with it, giving about
        # +/-1.7 F of frame-to-frame jitter that is measurement noise rather
        # than any change in the person. A median over a few seconds removes it
        # without lagging a real change meaningfully - skin temperature does
        # not move quickly.
        self.skin_hist: list[tuple[float, float]] = []
        self.vitals_smoother = vitals_select.Smoother()
        self.motion = motion_body.MotionBody()
        self.rate = {
            "thermal": RateMeter(), "radar": RateMeter(),
            "csi": RateMeter(), "ambient": RateMeter(),
        }
        self.parser_stats = F.Stats()
        self.connected = False
        self.source_label = "simulated" if simulated else "waiting"

    def apply(self, frame) -> None:
        with self.lock:
            modality = ("thermal" if isinstance(frame, F.ThermalFrame) else
                        "radar" if isinstance(frame, (F.RadarFrame, F.RadarRawFrame)) else
                        "csi" if isinstance(frame, F.CsiFrame) else
                        "ambient" if isinstance(frame, F.AmbientFrame) else
                        "stats" if isinstance(frame, F.DeviceStats) else None)
            if modality:
                previous = self.device_times.get(modality)
                if previous is not None and frame.t_us < previous:
                    self._reset_measurements()
                self.device_times[modality] = frame.t_us
                self.received_at[modality] = time.monotonic()
            if isinstance(frame, F.ThermalFrame):
                self.thermal = orient(frame.pixels)
                self.rate["thermal"].tick()
            elif isinstance(frame, F.RadarFrame):
                self.radar_raw = False
                self.radar = frame          # legacy on-device decode
                self.rate["radar"].tick()
            elif isinstance(frame, F.RadarRawFrame):
                self.radar_raw = True
                # Vendor protocol decoded here, not on the node.
                self.radar_decoder.feed(frame.data, t_us=frame.t_us)
                st = self.radar_decoder.state
                self.radar = F.RadarFrame(
                    t_us=self.radar_decoder.device_times.get(ID_CLOUD, frame.t_us),
                    presence=st.presence,
                    distance_m=st.distance_m,
                    respiration_rpm=st.respiration_rpm,
                    heart_rate_bpm=st.heart_rate_bpm,
                )
                self.rate["radar"].tick()
            elif isinstance(frame, F.CsiFrame):
                # Normalise out the receiver's automatic gain control. When the
                # AGC steps, every subcarrier amplitude jumps at once - which
                # reads as a whole-body movement that never happened. RSSI
                # tracks the gain state, so referencing amplitudes to it keeps
                # the series comparable across gain changes.
                amps = frame.amplitudes
                if frame.rssi:
                    scale = 10 ** ((frame.rssi + 50) / 40.0)
                    if 0.05 < scale < 20:
                        amps = [a / scale for a in amps]
                self.csi_amps = amps
                self.csi_rssi = frame.rssi
                self.rate["csi"].tick()
                sample_t = frame.t_us / 1_000_000.0
                if self.vitals.samples and (sample_t <= self.vitals.samples[-1][0] or
                                           sample_t-self.vitals.samples[-1][0] > 0.5):
                    self.vitals = VitalsEstimator()
                    self.vitals_out = None
                    self.vitals_out_at = None
                    self._epoch += 1
                self.vitals.add(sample_t, amps)
                self.csi_hist.append(amps)
                if len(self.csi_hist) > 40:
                    self.csi_hist.pop(0)
            elif isinstance(frame, F.DeviceStats):
                self.device = frame
            elif isinstance(frame, F.AmbientFrame):
                self.lux = frame.lux
                self.rate["ambient"].tick()

    def _reset_measurements(self):
        """Called with the acquisition lock held after a reconnect/device reset."""
        self._epoch += 1
        self.device_times.clear()
        self.received_at.clear()
        self.thermal = self.radar = self.csi_amps = self.lux = None
        self.radar_decoder = RadarDecoder()
        self.vitals = VitalsEstimator()
        self.vitals_out = self.vitals_out_at = None
        self.csi_hist = []
        self.device = None
        # Snapshot-derived state is reset at the next snapshot boundary. An
        # in-flight snapshot may finish its old state but cannot publish it.
        for meter in self.rate.values():
            meter.stamps.clear()

    def snapshot(self) -> dict:
        with self.snapshot_lock:
            while True:
                with self.lock:
                    epoch = self._epoch
                    if self._derived_epoch != epoch:
                        self.vitals_smoother = vitals_select.Smoother()
                        self.skin_hist = []
                        self._prev_dev = self._captured_hz = None
                        self.motion = motion_body.MotionBody()
                        self._derived_epoch = epoch
                result = self._snapshot()
                with self.lock:
                    if epoch != self._epoch:
                        continue
                return result

    def _snapshot(self) -> dict:
        now = time.monotonic()
        with self.lock:
            device_times = dict(self.device_times)
            received_at = dict(self.received_at)
            vout_at = self.vitals_out_at
            radar_times = {}
            if self.radar_raw and self.radar is not None:
                self.radar_decoder._recompute()
                rs = self.radar_decoder.state
                self.radar = F.RadarFrame(self.radar.t_us, rs.presence, rs.distance_m,
                                         rs.respiration_rpm, rs.heart_rate_bpm)
                radar_times = dict(self.radar_decoder.updated_at)
            thermal = self.thermal
            radar = self.radar
            amps = self.csi_amps
            rssi = self.csi_rssi
            lux = self.lux
            vout = self.vitals_out
            hist = list(self.csi_hist)
            dev = self.device
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
            return {"hz": 0.0 if status == "offline" else round(hz, 1), "status": status,
                    "age_s": round(age, 3), "device_t_us": device_times.get(key)}

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

        # Freshness is checked before presence, selection and downstream features.
        if out["health"]["radar"]["status"] == "offline":
            radar = None
        thermal_usable = (thermal is not None and out["health"]["thermal"]["status"] != "offline"
                          and len(thermal) == F.THERMAL_PIXELS
                          and all(math.isfinite(v) for v in thermal))
        if not thermal_usable:
            thermal = None
        if out["health"]["csi"]["status"] == "offline":
            amps, hist, vout = None, [], None
        elif vout_at is None or now-vout_at > vitals_select.MAX_READING_AGE_S:
            vout = None
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

        radar_known = radar is not None and radar.presence is not None
        radar_target = radar_known and radar.presence
        thermal_body = blob is not None
        skew_s = (abs(radar.t_us-device_times["thermal"])/1e6
                  if radar_known and thermal_usable else None)
        aligned = skew_s is not None and skew_s <= 1.0
        # These are evidence states, not room-wide identity/emptiness proofs.
        if radar_target and thermal_body and aligned:
            agree, verdict = True, "person"
        elif radar_target:
            agree, verdict = (False if thermal_usable and aligned else None), "radar_only"
        elif thermal_body:
            agree, verdict = (False if radar_known and aligned else None), "thermal_only"
        elif radar_known and thermal_usable and aligned:
            agree, verdict = True, "empty"
        else:
            agree, verdict = None, "unknown"

        # A fresh, finite, time-compatible thermal view without a blob withholds
        # unsupported vitals. It cannot prove that a reflector is furniture:
        # field of view, occlusion and low contrast remain unresolved.
        vetoed = radar_target and thermal_usable and aligned and not thermal_body
        if vetoed:
            out["radar"]["heart_rate_bpm"] = None
            out["radar"]["respiration_rpm"] = None
            out["radar"]["vitals_withheld"] = (
                "person unconfirmed: thermal view has no resolved warm body; "
                "coverage, contrast or occlusion may limit corroboration"
            )
        present = (radar_target or thermal_body) and not vetoed
        out["csi_vitals"] = vout if present and vout is not None else {
            "breathing_rpm": None, "heart_rate_bpm": None,
            "reason": ("person unconfirmed by thermal view" if vetoed else
                       "no fresh presence evidence" if not present else
                       "CSI estimate unavailable or stale"),
        }

        # CSI motion energy: mean per-subcarrier standard deviation over the
        # recent window. This is a real, directly measured quantity. It is not
        # a skeleton and is not labelled as one.
        if len(hist) >= 8:
            n_sub = min(len(hist[0]), 64)
            tot = 0.0
            for k in range(n_sub):
                col = [h[k] for h in hist if k < len(h)]
                m = sum(col) / len(col)
                tot += (sum((c - m) ** 2 for c in col) / len(col)) ** 0.5
            energy = tot / n_sub
            if energy < 0.8:
                motion = "still"
            elif energy < 2.5:
                motion = "slight movement"
            else:
                motion = "active"
            out["csi_motion"] = {"energy": round(energy, 2), "state": motion}

        if thermal:
            body = body_model.analyse(thermal, radar.distance_m if radar else None)
            if body and body.get("head_temp"):
                now = time.monotonic()
                self.skin_hist.append((now, body["head_temp"]["estimate"]["skin_f"]))
                self.skin_hist = [(t, v) for t, v in self.skin_hist if now - t <= 4.0]
                vals = sorted(v for _, v in self.skin_hist)
                if len(vals) >= 5:
                    med = vals[len(vals) // 2]
                    est = body["head_temp"]["estimate"]
                    delta = med - est["skin_f"]
                    est["skin_f"] = round(med, 1)
                    if est.get("core_f") is not None:
                        est["core_f"] = round(est["core_f"] + delta, 1)
                    est["smoothed_over"] = len(vals)
                    est["jitter_f"] = round(vals[-1] - vals[0], 1)

            # Motion-derived body region. Independent of absolute temperature,
            # so the carrier's own self-heating cannot masquerade as a person.
            mb = self.motion.update(thermal)
            if mb:
                out["motion_body"] = mb
            elif self.motion.last_diag:
                out["motion_diag"] = self.motion.last_diag
            if mb and body is not None:
                body["motion"] = mb

            out["body"] = body

        if dev:
            # The streamed CSI rate is deliberately below the captured rate, so
            # report both. Health should judge the radio by what it captured.
            # The node sends stats once a second while snapshots run at 15 Hz,
            # so most snapshots see an unchanged counter. Recompute only when
            # it actually moves, otherwise a zero delta reads as 0 Hz.
            if self._prev_dev is None or dev.csi_accepted < self._prev_dev[1]:
                self._prev_dev = (time.monotonic(), dev.csi_accepted)
                self._captured_hz = None
            elif dev.csi_accepted > self._prev_dev[1]:
                dt = time.monotonic() - self._prev_dev[0]
                if dt > 0.4:
                    self._captured_hz = round(
                        (dev.csi_accepted - self._prev_dev[1]) / dt, 1
                    )
                    self._prev_dev = (time.monotonic(), dev.csi_accepted)
            out["csi_captured_hz"] = (self._captured_hz
                if out["health"]["csi"]["status"] != "offline"
                and now-received_at.get("stats", -math.inf) <= 3.0 else None)
            out["device"] = {
                "csi_accepted": dev.csi_accepted,
                "csi_rejected": dev.csi_rejected,
                "csi_dropped": dev.csi_dropped,
                "espnow_rx": dev.espnow_rx,
                "thermal_recoveries": dev.thermal_recoveries,
            }

        out["vitals"] = vitals_select.select(
            out.get("radar"),
            out.get("csi_vitals"),
            radar.distance_m if radar else None,
            self.vitals_smoother,
            sample_times={
                ("radar", "heart"): radar_times.get(ID_HEART, received_at.get("radar", now)),
                ("radar", "resp"): radar_times.get(ID_BREATH, received_at.get("radar", now)),
                ("wifi_csi", "heart"): vout_at if vout_at is not None else now,
                ("wifi_csi", "resp"): vout_at if vout_at is not None else now,
            }, now=now, health=out["health"],
        )

        if out.get("vitals"):
            out["vitals"]["confidence"] = confidence.vitals_confidence(
                out["vitals"], out.get("health", {}),
                radar.distance_m if radar else None,
            )

        out["fusion"] = {
            "verdict": verdict,
            "agree": agree,
            "presence_status": "corroborated" if verdict == "person" else "unconfirmed" if radar_target or thermal_body else "not_detected" if verdict == "empty" else "unknown",
            "thermal_evidence": "body" if thermal_body else "no_resolved_body" if thermal_usable else "unavailable",
            "time_aligned": aligned,
            "device_skew_s": skew_s,
            "limitations": "finite field of view; no person identity or precise sensor latency calibration",
            "distance_m": None if not radar or radar.distance_m is None else round(radar.distance_m, 2),
            "bearing_deg": blob["bearing_deg"] if blob else None,
        }
        return out


# ------------------------------------------------------------------ sources ---

def vitals_worker(state: State) -> None:
    """Run the estimator off the request path.

    A pass is O(lags x samples) in pure Python and takes a fair fraction of a
    second, which would stall the event stream if it ran inside snapshot().
    """
    while True:
        try:
            with state.lock:
                estimator = copy.copy(state.vitals)
                estimator.samples = list(state.vitals.samples)
                epoch = state._epoch
                observed_at = state.received_at.get("csi")
                input_t_us = state.device_times.get("csi")
            breath, heart = estimator.estimate()
            with state.lock:
                if epoch != state._epoch:
                    continue
                state.vitals_out_at = observed_at
                state.vitals_out = {
                    "device_t_us": input_t_us,
                    "breathing_rpm": None if breath.rate is None else round(breath.rate, 1),
                    "breathing_confidence": round(breath.confidence, 2),
                    "heart_rate_bpm": None if heart.rate is None else round(heart.rate, 1),
                    "heart_confidence": round(heart.confidence, 2),
                    "reason": heart.reason if heart.rate is None else "ok",
                    "breathing_reason": breath.reason,
                }
        except Exception:
            with state.lock:
                state.vitals_out = None
                state.vitals_out_at = None
        time.sleep(1.0)


def serial_reader(state: State, port: str | None) -> None:
    """Read frames, and survive the board re-enumerating.

    Native USB CDC comes back under a different device name after a reset -
    usbmodem101 became usbmodem1101 in practice. Holding the name captured at
    startup meant every reconnect retried a port that no longer existed, and the
    dashboard sat on stale values marked offline while a perfectly healthy board
    sat on the next name along. The port is therefore re-detected on every
    reconnect, and an explicitly requested port is still preferred when it is
    present.
    """
    import serial  # imported lazily so the fake source needs no dependency

    requested = port
    parser = F.FrameParser()
    state.parser_stats = parser.stats

    while True:
        target = requested if (requested and os.path.exists(requested)) else autodetect_port()
        if not target:
            state.connected = False
            state.source_label = "waiting for a board"
            time.sleep(1.0)
            continue
        try:
            with serial.Serial(target, 115200, timeout=0.1) as ser:
                state.connected = True
                state.source_label = target
                while True:
                    chunk = ser.read(8192)
                    if chunk:
                        for frame in parser.feed(chunk):
                            state.apply(frame)
        except Exception as exc:
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
                        payload = json.dumps(json_safe(state.snapshot()), allow_nan=False)
                        self.wfile.write(f"data: {payload}\n\n".encode())
                        self.wfile.flush()
                        time.sleep(1 / 15)
                except (BrokenPipeError, ConnectionResetError):
                    return
            elif self.path.startswith("/calibrate"):
                import urllib.parse
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                try:
                    ref_f = float(q.get("f", [""])[0])
                except ValueError:
                    self.send_error(400, "pass ?f=<reference temperature in F>")
                    return
                # Average several seconds. A single frame is not a measurement:
                # consecutive head readings have been seen to differ by more
                # than 10 F as the detected head region shifts.
                skins, ambs = [], []
                for _ in range(40):
                    snap = state.snapshot()
                    ht = (snap.get("body") or {}).get("head_temp")
                    if ht:
                        skins.append(ht["estimate"]["skin_f"])
                        ambs.append(ht.get("background_c"))
                    time.sleep(0.15)
                if len(skins) < 10:
                    payload = {"ok": False,
                               "error": f"only {len(skins)} of 40 samples saw a head; "
                                        "sit still, facing the sensor, within 1.5 m"}
                else:
                    skins.sort()
                    # Median, then the spread, so an unstable subject is
                    # reported rather than averaged into false precision.
                    med = skins[len(skins) // 2]
                    spread = skins[-1] - skins[0]
                    amb_c = sorted(a for a in ambs if a is not None)
                    amb_c = amb_c[len(amb_c) // 2] if amb_c else None
                    cal = body_model.calibrate((med - 32) * 5 / 9,
                                               (ref_f - 32) * 5 / 9, amb_c)
                    payload = {"ok": True, "reference_f": ref_f,
                               "samples": len(skins),
                               "measured_skin_f": round(med, 1),
                               "sample_spread_f": round(spread, 1),
                               "calibration": cal}
                    if spread > 4.0:
                        payload["warning"] = (
                            f"readings varied by {spread:.1f} F during calibration; "
                            "the offset is only as good as that stability")
                body = json.dumps(json_safe(payload), indent=2, allow_nan=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path in ("/", "/index.html", "/body"):
                body = (BODY_VIEW if self.path == "/body" else DASHBOARD).read_bytes()
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
        # No longer fatal when absent: the reader waits and picks the board up
        # whenever it appears, which is also what happens after every reflash.
        port = args.port
        state = State(simulated=False)
        threading.Thread(target=serial_reader, args=(state, port), daemon=True).start()
        threading.Thread(target=vitals_worker, args=(state,), daemon=True).start()
        print(f"Reading {port or '(auto-detect)'}")
    else:
        state = State(simulated=True)
        threading.Thread(target=fake_reader, args=(state,), daemon=True).start()
        threading.Thread(target=vitals_worker, args=(state,), daemon=True).start()
        print("Synthetic source - output is labelled DEMO in the dashboard")

    srv = ThreadingHTTPServer(("127.0.0.1", args.http_port), make_handler(state))
    print(f"\n  Dashboard:  http://127.0.0.1:{args.http_port}\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
