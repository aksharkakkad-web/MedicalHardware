# Host tooling

Reads the bench node's binary frame stream and serves a live dashboard.

## Run

PlatformIO's bundled Python already has `pyserial`, so nothing needs installing:

```bash
cd firmware/host

# with the bench node plugged in (auto-detects the port)
~/.platformio/penv/bin/python bridge.py

# without any hardware, for demos
~/.platformio/penv/bin/python bridge.py --source fake
```

Then open <http://127.0.0.1:8420>.

Synthetic output is labelled **DEMO DATA** in the dashboard and travels through
the same encoder and parser as real hardware, so the view cannot accidentally
work only for simulated input. Measured and simulated data must never be
mistakable for one another.

## Telemetry pipeline

The ingest endpoints require a bearer token. Set one and keep it out of the
repository:

```bash
export INGEST_API_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')"

~/.platformio/penv/bin/python -m mock_ingest.server --port 8500   # receiver
~/.platformio/penv/bin/python pipeline.py --seconds 60            # sender
curl -s http://127.0.0.1:8500/stats                              # counters
```

Started without a key the receiver generates one and prints it, so it is never
accidentally unauthenticated. Reads (`/stats`) are open because it is a local
bench aid; writes are not.

`/v1/ingest/telemetry` and `/v1/ingest/heartbeat` mirror
`docs/DATA_CONTRACT.md`. The bench host does not send temperature anomaly
assessments or posture notifications.

Measurement confidence is not displayed anywhere. It gates instead - a reading
the conditions cannot support is withheld from the payload with its reason
rather than sent for something downstream to treat as fact.

## Layout

| Path | Purpose |
|---|---|
| `stream/frames.py` | Parser for `firmware/shared/frame.h`. Resyncs on the magic word, verifies CRC16-CCITT, never raises on a corrupt frame |
| `bridge.py` | Serial (or synthetic) source, rate/liveness tracking, SSE server |
| `dashboard/index.html` | The live view. Follows `docs/design-system.md` |

## The one rule that matters

An absent reading is `None` from the wire all the way to the browser, where it
renders as "not available". It is never 0, never imputed, never carried forward
from the last good value. `docs/DATA_CONTRACT.md` requires this, and the radar
makes it concrete: with nobody in the room the module still volunteers a
distance of `0.0`, and it will report a confident heart rate off a desk.

## Vital-sign freshness and evidence (29 September 2026)

The bench host uses the node's `t_us / 1e6` for CSI sampling. Host monotonic
arrival times are used separately for transport liveness and estimate age.
Thermal/radar corroboration checks device timestamps, using the decoded
point-cloud timestamp for radar presence rather than a later UART status log.
The existing `device_monotonic_ms` field now receives node time in outgoing
telemetry. This is coarse temporal compatibility, not calibrated sensor-latency
alignment or synchronization between multiple devices.

The current engineering policies are:

- Readings expire after 3 seconds without their source update. Raw radar heart,
  breathing, distance and presence messages expire independently; status logs
  cannot keep them alive.
- The displayed heart and breathing estimates require 3 distinct observations
  from one instrument and publish at most once every 4 seconds. The smoother
  uses an 8-second history, weights observations with heuristic sensor quality,
  and requires repeated evidence before accepting a large jump. A same-source,
  time-aligned breathing observation is required for a heart estimate; breathing
  does not itself determine heart rate. An unavailable or changed instrument
  clears the estimate. Polling the dashboard adds no new observations.
- Both displayed rates prefer radar through 1.5 m when it has a usable value;
  Wi-Fi CSI is a secondary fallback. CSI disagreement does not reduce the
  in-range radar display weight. This is a bench source-selection policy,
  not a claim that radar is always accurate.
- The CSI estimator starts a new window after a device-clock rollback or a
  gap over 0.5 seconds and requires the configured observation duration.
  Device reset also invalidates cached derived results; an in-flight snapshot
  from an older acquisition epoch is retried.
- A thermal veto requires a finite, live frame with device time within 1 second
  of radar presence. No blob means no resolved warm region in that view. It
  does not prove that the room is empty or that the radar target is furniture.
  Missing, invalid, stale or time-incompatible thermal data is unavailable
  corroboration. `unknown` presence is distinct from no detection.
- Cross-instrument rate comparison also requires contemporaneous observations.
  A missing comparator is `agree: null`, not agreement.
- Vital confidence is an **uncalibrated engineering quality score**. Its 0.6
  validation factor is retained; it is not a 60% probability of correctness.
  An unavailable cross-check has an explicit conservative 0.6 factor. These
  constants have not been fitted against reference physiology.
- After 4 seconds without dashboard events, numeric readings and live stream
  indicators become unavailable. Synthetic input remains labelled DEMO DATA.
- The dashboard shows head skin-surface temperature with an explicit note that
  it is not body temperature. Its main vital readout and thermal scene HUD show
  only the published heart and breathing estimates, never raw rate fallbacks.
- Automatic posture notifications and temperature anomaly assessments are
  disabled. Body position remains visible on the thermal scene when available.

No firmware, mesh, multi-person attribution or new sensing algorithm is added
by these fixes. The current 2.4 GHz hardware and configured radar selection
limits remain unvalidated against reference instruments. The raw-data bench
host is a development tool; the production edge/cloud responsibilities in
`docs/ARCHITECTURE.md` are unchanged.

Verification (synthetic and contract tests, not physiological validation):

```sh
python3 firmware/host/tests/run_all.py
node firmware/host/tests/test_dashboard_freshness.js
node firmware/host/tests/test_dashboard_focus.js
```
