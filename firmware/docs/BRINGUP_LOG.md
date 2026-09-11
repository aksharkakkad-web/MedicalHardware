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

## 2026-09-08 — M4 CSI receiver

**The C6 link is good.** With the TX node across the room on a power bank, the
S3 receives **~487 ESP-NOW packets/sec** against 499 transmitted — about 97.6%
delivery. The onboard ceramic antenna is not the problem.

**Zero CSI was a receiver bug, not a link or antenna problem.** A staged
diagnostic separated the causes:

| Mode | CSI callbacks / 3 s | ESP-NOW recv / 3 s |
|---|---|---|
| STA, no promiscuous | **0** | 1460 |
| promiscuous on | 56 | 1480 |
| promiscuous + filter | 50–310 | ~1475 |

In plain STA mode the driver discards frames not addressed to this station
before they reach the CSI stage, so the callback never fires. Enabling
promiscuous mode fixes it. This is now set in the stream firmware with a
data-frame filter, so ambient beacons from every AP in range do not dilute the
stream.

**Rate is still far below the packet rate: 1.4 Hz measured.** Two observations
point at the cause rather than the receiver:

- captured CSI reports **RSSI −91 dBm**, while the C6 measures **−54 dBm** in
  the same room. What is being captured is distant ambient traffic, not the
  beacon.
- the diagnostic's CSI counts swung 16–310 per window while ESP-NOW reception
  stayed rock steady at ~1470, so the frames are arriving and being decoded but
  are not producing CSI.

**Prime suspect: the ESP-NOW PHY rate.** Broadcast ESP-NOW defaults to a basic
802.11b rate, which carries no HT-LTF and does not yield a usable channel
estimate. Fixing it means setting an explicit OFDM/HT rate on the TX peer
(`esp_now_set_peer_rate_config()` on the C6's Arduino 3.x core) — which requires
retrieving the C6 to reflash it.

Secondary suspect, not yet ruled out: the bench loop is thermal-bound at ~7.8 Hz
because `mlx.getFrame()` blocks, and drains at most 32 ring entries per
iteration. That caps throughput but cannot explain an RSSI of −91.

**Not yet resolved.** CSI is proven working end to end — frames parse, 64
subcarriers, zero CRC errors — but not yet locked to the TX node.

## 2026-09-08 — CSI vitals, and where the processing lives

**Split: the node streams, the Mac thinks.** Confirmed and kept deliberately.

On the device: vendor UART decode for the radar (has to happen where the UART
is), CRC framing, and a validity bitmask. Nothing else. The CSI callback copies
`info->buf` verbatim and returns; thermal ships all 768 raw float32 pixels; lux
ships raw. No filtering, no feature extraction, no inference.

On the host: thermal blob detection, sensor corroboration, and all vitals DSP.

For the cloud later, note the distinction the data contract already draws
(`docs/DATA_CONTRACT.md` §4): raw streaming is a *local* development path over
USB or LAN. What goes to the cloud is the compact `EdgeTelemetryEnvelope` —
a few hundred bytes/sec — because raw CSI at 25 Hz x 64 subcarriers is not
something to pay for over WAN. Those are two different sinks, not a migration.

**CSI vitals implemented on the host**, following the method ruvnet/ruview
settled on: biquad bandpass into breathing (0.1–0.5 Hz) and cardiac
(0.8–2.0 Hz), then autocorrelation with breathing-harmonic rejection.

Three bugs, all caught by testing against synthetic signals with known answers:

1. A single biquad section leaked breathing into the cardiac band, producing a
   confident **120 bpm** for a true 72. Cascaded the section.
2. Taking the largest autocorrelation value cannot distinguish a real period
   from monotonic decay caused by a slower rhythm. Now requires a true local
   maximum.
3. The harmonic guard at ruview's ±8% rejected *every* real heart rate: at
   0.25 Hz breathing, harmonics k=4,5,6 land on 60, 75 and 90 bpm and the guard
   bands blanket the whole cardiac range. Narrowed to ±3%, which keeps 72 bpm
   while still rejecting a candidate sitting exactly on 75.

Decimation is per band. At 10 Hz a 1.2 Hz pulse is 8.3 samples per cycle, so
adjacent lags land ~8 bpm apart; the cardiac band now runs near the native rate
with parabolic interpolation around the peak.

Regression tests in `firmware/host/tests/test_vitals.py`, 5 passing, including
two that assert the estimator reports **nothing** — for pure noise, and for a
"heart rate" sitting on the 5th breathing harmonic.

**On real hardware it currently declines to report.** With a person at 0.75 m
it returns `breathing: subcarriers disagree` and `heart: no periodicity`. That
is the intended behaviour rather than a fabricated number, but it means the
thresholds need tuning against real recordings with a deliberately still
subject. Synthetic ground truth is satisfied; real-world is not yet.

**No validated accuracy exists for CSI vitals anywhere, including ruview.**
Their ADR-293 states plainly that for vitals "MEASURED is currently
unreachable" — they have no reference-sensor ground truth either. Their
published measured numbers cover presence (82.3% temporal-triplet) and MM-Fi
pose (82.69% torso-PCK), not vitals. Producing a trustworthy number here needs
a chest strap or pulse oximeter recorded alongside a session. Until then these
are unvalidated estimates and the dashboard says so.

## 2026-09-08 — all processing off the node, and full rates

**The node no longer interprets anything.** Radar decoding moved to the host as
`firmware/host/radar_decode.py`; the device forwards raw UART bytes as a new
frame type. What remains on the S3 is copying bytes and framing them:

| Modality | On device |
|---|---|
| CSI | copy `info->buf` out of the callback, forward |
| Thermal | 768 raw float32 pixels, forwarded |
| Radar | raw UART bytes, no parsing |
| Ambient | raw lux |

Nothing is filtered, thresholded, or inferred there. The C6 only transmits.

**Task layout.** Core 0 runs the CSI drain (priority 6) and the radar UART
drain (priority 4). Core 1 runs the Arduino loop, which owns both I2C devices.
The radar UART buffer is 4096 bytes, deep enough to cover a thermal read.

**Two bugs found and fixed on the way:**

*Radar starvation.* Parsing inline in `loop()` used blocking reads, sharing a
thread with a thermal frame read that occupies over 100 ms. Radar ran at
**0.7 Hz**. Forwarding raw bytes from a dedicated task took it to **23.8 Hz**,
a 34x improvement, and the decode quality is unchanged because the same
checksum-validated parser now runs on the host.

*I2C is not thread-safe.* Moving the BH1750 onto its own task let it interleave
with a thermal transaction mid-read. Thermal went to **0 Hz** while the light
sensor kept happily reporting — a failure that looks like a broken thermal
sensor rather than a concurrency bug. Both I2C devices are now driven from one
thread. CSI and radar have no bus to contend for and stay on their own tasks.

**Rates, all four running simultaneously:**

| Modality | Before | Now |
|---|---|---|
| Wi-Fi CSI | 27 Hz | **39 Hz** |
| Radar | 0.7 Hz | **23.8 Hz** |
| Thermal | 7.9 Hz | **8.1 Hz** |
| Ambient | 2.0 Hz | 2.0 Hz |

CRC errors and resyncs occur only during USB enumeration and stop accumulating
once the link settles (6 and 8 across the whole session).

Thermal is capped by the sensor: chess mode reads two subpages per full frame,
so a 16 Hz refresh yields ~8 Hz complete frames. Raising it further needs
1 MHz I2C, which previously failed under Wi-Fi load.

## 2026-09-09 — C6 reflash: OFDM rate, and the half-duplex limit

**OFDM rate forced — the fix the S3's CSI needed.** `esp_now_set_peer_rate_config()`
with `WIFI_PHY_MODE_HT20` / `WIFI_PHY_RATE_MCS0_LGI` returns `ESP_OK`, and the
beacon still holds 498 Hz. Broadcast ESP-NOW otherwise defaults to a basic
802.11b rate that carries no HT-LTF, which is why the bench node had been
capturing CSI at RSSI −91 (distant ambient traffic) while this node sat at −50
in the same room.

**C6 CSI capture: silent until the full Wi-Fi 6 acquire config was set.** The
short config — `enable`, `acquire_csi_legacy/ht20/ht40/su/mu` — returned
`ESP_OK` from all four setup calls and the callback never fired once. Adding
`acquire_csi_force_lltf`, `acquire_csi_vht` and
`acquire_csi_he_stbc_mode` (MAC v3 path) made it fire immediately. Every
success code lied; only the counter told the truth.

**Then it stopped, and the reason is physical.** Capture climbed to 103 frames
during boot and froze the instant the beacon reached 498 Hz:

```
tx   0 Hz  csi_seen=67   relayed=17  rssi=-50
tx 425 Hz  csi_seen=83   relayed=31  rssi=-53
tx 498 Hz  csi_seen=103  relayed=51  rssi=-75
tx 498 Hz  csi_seen=103  relayed=51  rssi=-75   <- frozen
```

The radio is half-duplex. A node transmitting 500 packets/sec has almost no
airtime left to receive, so it cannot also be a useful receiver. This is not a
configuration problem and no amount of tuning fixes it.

**Consequence: the C6 is a transmitter or a receiver, not both.** Since the
bench node's CSI depends on this beacon, the beacon wins. Using the C6 as a
second receiver would need either a much lower beacon rate — which degrades the
measurement it exists to enable — or a third node to take over transmitting.

The relay path (frame type 6, `SENSE_FRAME_CSI_REMOTE`) is implemented and
proven to work end to end; it is simply starved at full beacon rate. It becomes
useful the moment a third node exists.

**Still to measure:** whether the OFDM rate actually raises the bench node's CSI
quality. That needs the C6 back across the room on the power bank with the S3
reconnected over USB.

## 2026-09-10 — M4 CSI done: 500 Hz, and the bandwidth budget

**M4 PASS. 503.7 Hz sustained**, against the brief's ≥450 Hz done-condition.
Captured RSSI −63 dBm, i.e. the TX node rather than distant ambient traffic.
`csi_accepted` and `espnow_rx` are identical (70411 each): **every beacon packet
now yields exactly one CSI frame**, and `csi_dropped` is 0.

Three changes got there, all needed together:

1. Promiscuous mode — without it the driver discards frames before the CSI
   stage. Measured 0 callbacks against 1460 receptions.
2. `channel_filter_en = false` and MGMT+DATA filtering — DATA-only collapsed
   yield to 1.4 Hz.
3. An OFDM/HT20 rate forced on the TX peer. Broadcast ESP-NOW defaults to a
   basic 802.11b rate carrying no HT-LTF, so the beacon produced no usable
   estimate at all; the CSI arriving before this fix was ambient traffic.

Plus a MAC filter accepting only the TX node, which turns a mixture of
transmitters into one coherent time series.

**Streaming is decimated to 100 Hz; capture stays at 500.** At full rate CSI
alone is ~75 KB/s over USB CDC and it starved everything else — thermal fell to
1.0 Hz, radar to 17 Hz, and CRC errors climbed as writes were truncated.
Nothing downstream needs 500 Hz: the vitals estimator decimates to 25 Hz
internally, and 0.1–2.0 Hz signals are nowhere near Nyquist-limited by 100 Hz.
The 500 Hz figure was a gait-Doppler requirement, and gait is out of scope. The
true capture rate is still reported, from the device's own counter.

**Balanced result, all five streams at once:**

| Stream | Rate |
|---|---|
| CSI captured | 503.7 Hz |
| CSI streamed | 102 Hz |
| Thermal | 7.8 Hz |
| Radar | 21.6 Hz |
| Ambient | 2.0 Hz |

A mutex-timeout bug surfaced on the way: at 500 Hz the CSI drain held the TX
mutex almost continuously, and thermal frames hit a 50 ms timeout and were
silently discarded. Raising the timeout and dropping the drain task's priority
below the Arduino loop fixed it.

**CSI vitals produced their first real readings** once the stream was clean and
single-source, and they do not agree with the radar. Recorded here rather than
smoothed over: CSI 71.7 bpm at full confidence while radar reported 83.0 bpm,
and CSI found no breathing while radar reported 15 rpm. Neither instrument is
validated against a reference, so the disagreement identifies no winner. Note
also that CSI reporting a confident heart rate while failing to find breathing
is backwards — breathing is the larger, easier signal — which is reason to
distrust that particular number rather than celebrate it.

## 2026-09-11 — M8: edge telemetry pipeline

Live sensors now flow through feature extraction into contract envelopes and
into a validating ingest endpoint. End to end against real hardware: **48
envelopes sent, 48 accepted, 0 rejected**, plus 16 heartbeats, evenly split
across radar, thermal and wifi_csi.

**Extraction** (`firmware/host/edge/extractors.py`) produces the three declared
payload formats. The governing rule is the contract's: an unavailable value is
never zero-filled, imputed or forward-filled — the field is omitted and a
reason recorded. Concretely, with no target the radar still volunteers a
distance of 0.0, and that is dropped rather than forwarded.

**Envelopes** (`edge/envelope.py`) carry strictly increasing sequence numbers
per `(device, source)`, `device_time` null until the node has wall time, and
transport batch/retry metadata.

**Ingest** (`mock_ingest/server.py`) stands in for `POST /v1/ingest/telemetry`,
which does not exist yet and belongs to the backend lane. It validates
strictly and returns the specific violation, because a bare 422 tells the
firmware lane nothing.

**Tests** (`tests/test_edge_contract.py`, 12 passing) carry their weight in the
negative cases. A validator that accepts everything proves nothing, so these
assert rejection of: a null in a measurement field, a score outside 0–1, a
replayed sequence number, an unknown payload format, and a missing required
field. Three more assert the no-zero-fill rule directly — radar with no target
omits distance and both vitals, absent vitals are omitted rather than zeroed,
and `near_floor_score` is withheld unless the whole body is in frame, since a
person standing close otherwise looks identical to one lying down.

**Handoff artefact:** `tests/fixtures/valid_envelopes.json` and
`heartbeat.json` are contract-valid examples of all three sources, for whoever
implements the real backend route.

Not done here: the real ingest endpoint, and network transport from the device.
Both are deliberate — the endpoint is Akshar's lane, and raw streaming stays on
USB while only compact envelopes are intended for the network.
