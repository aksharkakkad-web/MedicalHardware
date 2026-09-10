"""Parser for the bench node's binary wire format.

The layout is defined once in ``firmware/shared/frame.h``; this module mirrors
it. If the two ever disagree the header wins - change it there first.

The parser never raises on a corrupt frame. USB CDC drops bytes around
enumeration (observed during M1), so resynchronising and counting the damage is
normal operation rather than an error path.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from typing import Iterator

MAGIC = 0xA5A5A5A5
MAGIC_BYTES = struct.pack("<I", MAGIC)

HEADER = struct.Struct("<IBQH")  # magic, type, t_us, payload_len
HEADER_BYTES = 15
CRC_BYTES = 2

TYPE_CSI = 1
TYPE_THERMAL = 2
TYPE_RADAR = 3
TYPE_AMBIENT = 4
TYPE_RADAR_RAW = 5
TYPE_CSI_REMOTE = 6
TYPE_STATS = 7

THERMAL_COLS = 32
THERMAL_ROWS = 24
THERMAL_PIXELS = THERMAL_COLS * THERMAL_ROWS

_CSI_HEAD = struct.Struct("<hH")           # rssi, subcarriers
_THERMAL = struct.Struct(f"<{THERMAL_PIXELS}f")
_RADAR = struct.Struct("<BBBfff")          # valid, presence, quality, dist, resp, hr
_AMBIENT = struct.Struct("<Bf")            # valid, lux
_STATS = struct.Struct("<5I")

RADAR_VALID_PRESENCE = 1 << 0
RADAR_VALID_DISTANCE = 1 << 1
RADAR_VALID_RESPIRATION = 1 << 2
RADAR_VALID_HEART_RATE = 1 << 3
RADAR_VALID_QUALITY = 1 << 4

PRESENCE_ABSENT = 0xFF
QUALITY_ABSENT = 0xFF


def crc16(data: bytes) -> int:
    """CRC16-CCITT: poly 0x1021, init 0xFFFF, no reflection, no final XOR."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


@dataclass
class CsiFrame:
    t_us: int
    rssi: int
    iq: list[int]

    @property
    def amplitudes(self) -> list[float]:
        """Per-subcarrier magnitude from the interleaved I/Q pairs."""
        return [
            math.hypot(self.iq[i], self.iq[i + 1])
            for i in range(0, len(self.iq) - 1, 2)
        ]


@dataclass
class ThermalFrame:
    t_us: int
    pixels: list[float]


@dataclass
class RadarFrame:
    """Absent fields are ``None``.

    They are never 0. A zero distance or a zero heart rate is a plausible
    reading, so it can never double as "missing" - docs/DATA_CONTRACT.md forbids
    zero-filling an unavailable value, and the validity bitmask on the wire
    exists to enforce that here.
    """

    t_us: int
    presence: bool | None = None
    distance_m: float | None = None
    respiration_rpm: float | None = None
    heart_rate_bpm: float | None = None
    quality: int | None = None


@dataclass
class AmbientFrame:
    """Illuminance. ``lux`` is None when the sensor did not answer.

    A dark room is a legitimate 0 lux, so zero can never also mean "no
    reading" - the same rule the radar fields follow.
    """

    t_us: int
    lux: float | None = None


@dataclass
class RadarRawFrame:
    """Undecoded bytes from the radar UART. See host/radar_decode.py."""

    t_us: int
    data: bytes


@dataclass
class DeviceStats:
    """Counters from the node itself."""

    t_us: int
    csi_accepted: int = 0
    csi_rejected: int = 0
    csi_dropped: int = 0
    espnow_rx: int = 0
    thermal_recoveries: int = 0


@dataclass
class Stats:
    frames_ok: int = 0
    crc_errors: int = 0
    resyncs: int = 0
    bytes_read: int = 0
    per_type: dict[int, int] = field(default_factory=dict)


class FrameParser:
    """Incremental parser. Feed it bytes, get frames out."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self.stats = Stats()

    def feed(self, data: bytes) -> Iterator[object]:
        self._buf.extend(data)
        self.stats.bytes_read += len(data)

        while True:
            start = self._buf.find(MAGIC_BYTES)
            if start < 0:
                # Keep the last 3 bytes; a magic word may straddle the boundary.
                if len(self._buf) > 3:
                    del self._buf[: len(self._buf) - 3]
                return
            if start > 0:
                self.stats.resyncs += 1
                del self._buf[:start]

            if len(self._buf) < HEADER_BYTES:
                return
            _magic, ftype, t_us, plen = HEADER.unpack_from(self._buf, 0)

            total = HEADER_BYTES + plen + CRC_BYTES
            if plen > 4096:
                # Implausible length: this magic was data, not a real header.
                self.stats.resyncs += 1
                del self._buf[:4]
                continue
            if len(self._buf) < total:
                return

            payload = bytes(self._buf[HEADER_BYTES : HEADER_BYTES + plen])
            (crc_rx,) = struct.unpack_from("<H", self._buf, HEADER_BYTES + plen)
            crc_calc = crc16(bytes(self._buf[4 : HEADER_BYTES]) + payload)

            del self._buf[:total]

            if crc_rx != crc_calc:
                self.stats.crc_errors += 1
                continue

            frame = self._decode(ftype, t_us, payload)
            if frame is None:
                continue
            self.stats.frames_ok += 1
            self.stats.per_type[ftype] = self.stats.per_type.get(ftype, 0) + 1
            yield frame

    @staticmethod
    def _decode(ftype: int, t_us: int, payload: bytes):
        if ftype == TYPE_CSI:
            if len(payload) < _CSI_HEAD.size:
                return None
            rssi, n_pairs = _CSI_HEAD.unpack_from(payload, 0)
            iq = list(struct.unpack_from(f"<{n_pairs * 2}b", payload, _CSI_HEAD.size))
            return CsiFrame(t_us=t_us, rssi=rssi, iq=iq)

        if ftype == TYPE_THERMAL:
            if len(payload) != _THERMAL.size:
                return None
            return ThermalFrame(t_us=t_us, pixels=list(_THERMAL.unpack(payload)))

        if ftype == TYPE_STATS:
            if len(payload) != _STATS.size:
                return None
            a, rj, d, e, tr = _STATS.unpack(payload)
            return DeviceStats(t_us=t_us, csi_accepted=a, csi_rejected=rj,
                               csi_dropped=d, espnow_rx=e, thermal_recoveries=tr)

        if ftype == TYPE_RADAR_RAW:
            return RadarRawFrame(t_us=t_us, data=payload)

        if ftype == TYPE_AMBIENT:
            if len(payload) != _AMBIENT.size:
                return None
            valid, lux = _AMBIENT.unpack(payload)
            return AmbientFrame(t_us=t_us, lux=lux if valid else None)

        if ftype == TYPE_RADAR:
            if len(payload) != _RADAR.size:
                return None
            valid, presence, quality, dist, resp, hr = _RADAR.unpack(payload)
            return RadarFrame(
                t_us=t_us,
                presence=bool(presence) if valid & RADAR_VALID_PRESENCE else None,
                distance_m=dist if valid & RADAR_VALID_DISTANCE else None,
                respiration_rpm=resp if valid & RADAR_VALID_RESPIRATION else None,
                heart_rate_bpm=hr if valid & RADAR_VALID_HEART_RATE else None,
                quality=quality if valid & RADAR_VALID_QUALITY else None,
            )
        return None


def encode(ftype: int, t_us: int, payload: bytes) -> bytes:
    """Build one frame. Used by the synthetic source and by round-trip tests."""
    head = HEADER.pack(MAGIC, ftype, t_us, len(payload))
    return head + payload + struct.pack("<H", crc16(head[4:] + payload))
