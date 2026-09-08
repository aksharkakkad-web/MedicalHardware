# Bring-Up Log

Measured results only. The log is the evidence; do not rely on memory.

## 2026-09-07 — M0 toolchain, M1 I2C scan

**Bench node identified.** ESP32-S3 (QFN56) rev v0.2, 8 MB embedded PSRAM,
40 MHz crystal, USB mode USB-Serial/JTAG, MAC `ac:27:6e:a6:9b:c8`. Enumerates on
macOS as `/dev/cu.usbmodem1101` via native USB CDC. Confirmed with
`esptool.py chip_id`; the board self-reported rather than being assumed.

Note the C6 TX node is not yet on the bench — M4 is blocked until it is.

**Toolchain.** PlatformIO Core 6.1.19 with espressif32 @ 7.0.1 was already
installed at `~/.platformio`; nothing new had to be installed. Build 24.8 s,
flash 5.3 s, hash verified. RAM 5.7% (18,740 / 327,680), flash 8.1%
(271,669 / 3,342,336).

**M0 PASS** — board enumerates, accepts firmware, and blinks.

**M1 PASS** — bus scan at 400 kHz on SDA=GPIO5 (D4) / SCL=GPIO6 (D5):

| Address | Device |
|---|---|
| `0x23` | BH1750 ambient light, onboard the carrier |
| `0x33` | MLX90640 thermal 32×24 |

Both required addresses present, so the bus works and the thermal sensor is
correctly wired. No SDA/SCL swap was needed. No pull-ups added — the carrier
already has them.

**Anomaly investigated and closed.** In the first capture, one scan out of eight
listed `0x23` but not `0x33` while still printing the PASS verdict. Since the
verdict is computed from the same flag that prints the address line, the device
*was* found and only the printed line was lost — a dropped USB CDC line during
the post-reset enumeration window, not an I2C dropout. A follow-up 35 s capture
taken after enumeration settled gave 17/17 scans listing `0x33` with zero
line/verdict mismatches.

Carry-forward for M5: USB CDC can drop bytes around enumeration. The magic-word
resync and CRC16 in `firmware/shared/frame.h` exist for exactly this; the host
parser must count corrupt frames rather than trusting the link.

**Not yet measured:** thermal frame rate (M2), radar UART (M3), CSI rate (M4).

## 2026-09-07 — M2 thermal, M3 radar

### M2 PASS (pending your hand-wave confirmation)

MLX90640 at 1 MHz I2C, chess mode, 18-bit, 16 Hz refresh setting.

- **Measured 7.8 Hz full frames, 0 errors over 164 frames.** This is correct,
  not a shortfall: chess mode reads two subpages per full frame, so a 16 Hz
  refresh setting yields ~8 Hz complete frames. Squarely inside the brief's
  8–16 Hz.
- Scene range 25.0–32.2 °C in a room at roughly 25 °C.
- Rendered at ~4 Hz on purpose; terminal redraw, not the sensor, is the limit
  above that. The measured read rate is printed alongside so the display rate
  is never mistaken for the sample rate.

Open observation: the upper-left corner reads persistently warm across frames
with no one in view. That is very likely the XIAO or carrier self-heating
inside the field of view. It matters later — `near_floor_score` and centroid
features would both be biased by a fixed hot corner — so it needs a mounting
check before M8 thermal features are trusted.

### M3 PASS

**UART established empirically, not guessed.** GPIO44 (pad D7) carries traffic;
GPIO43 (pad D6) is silent. 115200 8N1. These are the classic UART0 pins, safe
only because the host link is native USB CDC.

**The wire format is not the documented Seeed "SY…TC" 60 GHz framing.** No
`0x53 0x59` header appears anywhere in the stream. The actual format, derived
from the bytes and then confirmed against an XOR checksum over 1480 consecutive
frames with **zero checksum failures and zero resyncs**:

```
uint8  sof   = 0x01
uint16 seq          big-endian, increments once per message
uint16 len          big-endian, length of data[] only
uint16 id           big-endian message id
uint8  token
uint8  data[len]    little-endian words
uint8  checksum     XOR of every byte from sof through the last data byte
```

**Message map.** Semantics were established by cross-validation, not assumption.
Message `0x0100` turned out to carry the module's own plain-text status log,
which labels the numeric ids directly:

| id | rate | contents | how it was confirmed |
|---|---|---|---|
| `0x0100` | ~9 Hz | ASCII log, e.g. `"breath rate = 15.000000"` | reads as text |
| `0x0A14` | ~8 Hz | breathing rate, rpm | value matches the `0x0100` text log exactly |
| `0x0A15` | ~2 Hz | heart rate, bpm (observed 97–99) | rate and range |
| `0x0A16` | ~8 Hz | target distance, **cm** | tracked 103.32 → 40.18 as the subject approached, matching `0x0A17` y of 1.013 → 0.401 m |
| `0x0A17` | ~8 Hz | target position (x, y) in metres | cross-checks against `0x0A16` |
| `0x0A04` | ~8 Hz | point cloud: target count + per-target (x, y) | count word tracks presence |
| `0x0A29` | ~8 Hz | target/presence state, observed flipping 1↔2 | flips with occupancy |
| `0x0A13` | ~16 Hz | three small signed floats, ~±0.2 — motion/velocity | magnitude rises with movement |

**Update rate is ~8 Hz, not the ~1 Hz the brief predicted.** Better than
budgeted for presence and distance. It does not change the gait conclusion:
still no raw IF and no dense point cloud, so micro-Doppler remains impossible
from this part.

**Vitals are visibly unstable, exactly as the brief warned.** Breathing rate
swung across 0, 4, 7, 12, 13, 15 rpm within seconds, and the module itself
emitted `"invalid = 235"`. These are consumer-grade estimates from an
uncalibrated sensor that need a near-stationary subject within ~1.5 m (heart)
or ~2 m (respiration). The `0x0100` log gives us an explicit invalidity signal
to gate on — use it in M8 rather than forwarding a number, per the
DATA_CONTRACT rule against zero-filling or inventing a value.

**Not yet measured:** CSI rate (M4) — blocked on the C6 TX node, which is not
on the bench.

## 2026-09-07 — aiming aid: thermal + lux corroboration (unverified on wire)

The M3 aiming sketch now also samples the BH1750 (0x23) and a compact MLX90640
feature set on the same 4 Hz report. This is **bench corroboration**, not
product fusion and not a clinical reading:

- Radar still owns presence and distance. Frozen range still gates vitals.
- Thermal reports scene min/median/max, a count of pixels ≥ median + 2 °C, a
  centroid, and a 16×6 relative-contrast map. That 2 °C cut is a relative
  contrast heuristic, not a body-temperature threshold.
- Lux only flags a covered node (hand / face-down carrier). Ambient light
  cannot detect a person.
- Heart and breath print as `n/a` on a frozen, covered, or thermally flat
  scene so a desk cannot keep showing ~118 bpm.

Not yet captured on the bench after this change. Re-flash, RESET after
re-aiming, and log whether STATIC REFLECTOR still fires on the desk while
THERMAL WARM / THERMAL FLAT track a hand-wave.

## 2026-09-08 — M4 TX node

**Toolchain blocker resolved.** The official `espressif32` platform reports
"This board doesn't support arduino framework" for `seeed_xiao_esp32c6` at both
7.0.1 and 7.1.2 — its board manifest predates C6 Arduino support, so no version
bump fixes it. Switched the TX env to the pioarduino platform fork
(`55.03.311`, Arduino 3.3.11 / ESP-IDF 5.5.5), which does support it. The bench
node stays on the official platform; only the TX env moved.

**ESP32-C6 identified:** ESP32-C6FH4 (QFN32) rev v0.2, Wi-Fi 6, 4 MB embedded
flash, MAC `10:bd:a3:96:47:d8`.

**TX rate PASS: 499 Hz sustained**, against a 500 Hz target (2000 µs interval).
Zero queue failures and zero NACKs across 7,697 packets. ESP-NOW broadcast,
channel 6 locked, power save disabled.

Flash usage is 73.7% — the Arduino 3.x core is much larger than the 2.x core
used on the bench node. Fine here, but worth knowing before adding much to this
sketch.

Pacing is done on `micros()` rather than `delay()`, which cannot resolve 2 ms
reliably once the radio competes for time. The first report reads 0 Hz because
the window opens before the radio finishes bringing up; it settles within two
seconds.

**Still to measure:** CSI callback rate at the RX end. A 499 Hz transmit rate is
the ceiling for it, not a guarantee.
