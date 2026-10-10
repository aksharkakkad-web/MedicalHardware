"""Vendor protocol decoder for the MR60BHA2, running on the host.

The node forwards raw UART bytes; all interpretation happens here. That means
the message map can change without reflashing, and a blocking sensor read on
the device can never starve the radar.

Wire format, established empirically - the module does not use the documented
Seeed "SY...TC" framing. Confirmed against an XOR checksum over 1480
consecutive frames with zero failures:

    uint8  sof = 0x01
    uint16 seq          big-endian
    uint16 len          big-endian, length of data[] only
    uint16 id           big-endian
    uint8  token
    uint8  data[len]    little-endian words
    uint8  checksum     XOR of sof through the last data byte

Message ids were confirmed by cross-checking id 0x0100, which carries the
module's own plain-text status log, against the numeric ids.
"""

from __future__ import annotations

import math
import struct
import time
from dataclasses import dataclass

SOF = 0x01
MAX_DATA = 64

ID_LOG = 0x0100        # ASCII status log, e.g. "breath rate = 15.000000"
ID_BREATH = 0x0A14     # breathing rate, rpm
ID_HEART = 0x0A15      # heart rate, bpm
ID_DISTANCE = 0x0A16   # target distance, cm
ID_POSITION = 0x0A17   # target (x, y), metres
ID_CLOUD = 0x0A04      # point cloud: target count then per-target (x, y)
ID_PRESENCE = 0x0A29   # presence / target state


@dataclass
class RadarState:
    """Absent fields stay None. Never 0.

    With nobody present the module still volunteers a distance of 0.0, and it
    will report a confident heart rate off a desk. Presence gates the rest.
    """

    presence: bool | None = None
    distance_m: float | None = None
    respiration_rpm: float | None = None
    heart_rate_bpm: float | None = None
    x: float | None = None
    y: float | None = None
    log: str = ""
    frames_ok: int = 0
    checksum_errors: int = 0


class RadarDecoder:
    def __init__(self) -> None:
        self.buf = bytearray()
        self.state = RadarState()
        self._count = 0
        self._breath = None
        self._heart = None
        self._distance_cm = None
        self.updated_at = {}
        self.device_times = {}

    def feed(self, data: bytes, t_us: int | None = None) -> None:
        self.buf.extend(data)
        if len(self.buf) > 8192:
            del self.buf[: len(self.buf) - 8192]

        while True:
            start = self.buf.find(bytes([SOF]))
            if start < 0:
                self.buf.clear()
                return
            if start:
                del self.buf[:start]
            if len(self.buf) < 8:
                return

            length = (self.buf[3] << 8) | self.buf[4]
            msg_id = (self.buf[5] << 8) | self.buf[6]
            if length > MAX_DATA:
                del self.buf[:1]  # this 0x01 was data, not a header
                continue

            total = 8 + length + 1
            if len(self.buf) < total:
                return

            frame = bytes(self.buf[:total])
            crc = 0
            for b in frame[:-1]:
                crc ^= b
            del self.buf[:total]

            if crc != frame[-1]:
                self.state.checksum_errors += 1
                continue

            self.state.frames_ok += 1
            self._apply(msg_id, frame[8 : 8 + length], t_us)

    def _apply(self, msg_id: int, data: bytes, t_us: int | None = None) -> None:
        now = time.monotonic()
        if msg_id == ID_LOG:
            self.state.log = "".join(
                chr(c) if 32 <= c < 127 else " " for c in data
            ).strip()
        elif msg_id == ID_BREATH and len(data) >= 4:
            v = struct.unpack_from("<f", data)[0]
            # 0 is the module's "no valid estimate" marker, not a measurement.
            self._breath = v if math.isfinite(v) and v > 0.5 else None
            self.updated_at[msg_id] = now
            self.device_times[msg_id] = t_us
        elif msg_id == ID_HEART and len(data) >= 4:
            v = struct.unpack_from("<f", data)[0]
            self._heart = v if math.isfinite(v) and v > 0.5 else None
            self.updated_at[msg_id] = now
            self.device_times[msg_id] = t_us
        elif msg_id == ID_DISTANCE and len(data) >= 8:
            self._distance_cm = struct.unpack_from("<f", data, 4)[0]
            self.updated_at[msg_id] = now
            self.device_times[msg_id] = t_us
        elif msg_id == ID_POSITION and len(data) >= 8:
            self.state.x, self.state.y = struct.unpack_from("<ff", data)
        elif msg_id == ID_CLOUD and len(data) >= 4:
            self._count = struct.unpack_from("<I", data)[0]
            self.updated_at[msg_id] = now
            self.device_times[msg_id] = t_us
            if self._count == 0:
                self._heart = self._breath = self._distance_cm = None
                for key in (ID_HEART, ID_BREATH, ID_DISTANCE):
                    self.updated_at.pop(key, None)
        elif msg_id == ID_PRESENCE and len(data) >= 2:
            pass  # state word; presence is taken from the point-cloud count

        self._recompute()

    def _recompute(self) -> None:
        s = self.state
        now = time.monotonic()
        fresh = lambda key: key in self.updated_at and now-self.updated_at[key] <= 3.0
        target = self._count > 0 if fresh(ID_CLOUD) else None
        s.presence = target
        if not target:
            s.distance_m = None
            s.respiration_rpm = None
            s.heart_rate_bpm = None
            return
        s.distance_m = (
            self._distance_cm / 100.0
            if fresh(ID_DISTANCE) and self._distance_cm is not None and math.isfinite(self._distance_cm) and self._distance_cm > 1.0
            else None
        )
        s.respiration_rpm = self._breath if fresh(ID_BREATH) else None
        s.heart_rate_bpm = self._heart if fresh(ID_HEART) else None
