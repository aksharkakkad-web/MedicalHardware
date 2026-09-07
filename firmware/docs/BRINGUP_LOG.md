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
