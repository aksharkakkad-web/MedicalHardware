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
