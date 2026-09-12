"""Sustained posture-change detection, and notification when it happens.

WHAT THIS IS NOT. It is not a fall detector and must not be relied on as one.
Section 3 of HARDWARE_BRINGUP_BRIEF.md rules out alerting that someone might
act on for a health decision, and the reason is concrete: an unreliable fall
alarm fails in two directions, and the false-negative direction means a person
is on the floor and help does not come because the system was trusted.

What the sensor can actually support, and what this therefore reports:

  - a body whose silhouette has been horizontal for a sustained period, and
  - a transition into that state from an upright one.

What it cannot distinguish:

  - falling from lying down deliberately, stretching, or doing floor exercises
  - a person from a warm object of similar extent
  - anything at all once the body leaves the 35 degree vertical field of view,
    which is exactly what happens when someone goes to the floor close to a
    wall-mounted sensor

It also cannot see the fall itself. A fall lasts a few hundred milliseconds; at
8 Hz that is one or two frames, and the thermal stream has been observed as low
as 1 Hz under Wi-Fi load. So this detects the *aftermath* - a posture that
persists - not the event.

Notification goes out labelled as a posture change with its confidence and its
limitations attached, so a person reading the alert knows what was and was not
observed.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.request
from dataclasses import dataclass, field

# A posture must hold this long before it is reported. Shorter and every
# bend-to-tie-a-shoelace fires; much longer and the report is stale.
SUSTAIN_S = 8.0

# Never re-notify inside this window. Alarm fatigue is itself a failure mode -
# a channel someone has learned to ignore is worse than no channel.
COOLDOWN_S = 180.0

# History kept for deciding whether the person was upright beforehand.
HISTORY_S = 60.0

# --- demo mode -----------------------------------------------------------
#
# Set POSTURE_DEMO=1 for a trigger fast enough to film: it fires in about a
# second, re-arms in ten, and does not require having seen the person upright
# first.
#
# This is a separate mode rather than looser defaults on purpose. These settings
# make the detector fire on a stretch, a lean, or a warm object of the right
# shape, and a demo preset that quietly became the deployed one is exactly how
# an unreliable alarm ends up being trusted. The notification says DEMO so a
# recording can never be mistaken for the real behaviour.
DEMO_SUSTAIN_S = 1.2
DEMO_COOLDOWN_S = 10.0


@dataclass
class PostureEvent:
    kind: str
    at: float
    detail: str
    confidence_pct: float
    prior_posture: str | None
    limitations: list[str] = field(default_factory=list)


class PostureWatcher:
    def __init__(self, demo: bool | None = None) -> None:
        self.demo = (os.environ.get("POSTURE_DEMO", "") == "1"
                     if demo is None else demo)
        self.sustain_s = DEMO_SUSTAIN_S if self.demo else SUSTAIN_S
        self.cooldown_s = DEMO_COOLDOWN_S if self.demo else COOLDOWN_S
        # Demo mode drops the prior-upright requirement, which is what makes it
        # fire quickly and also what makes it unreliable.
        self.require_prior_upright = not self.demo
        self.history: list[tuple[float, str, bool]] = []  # time, posture, fully_visible
        self.horizontal_since: float | None = None
        # None, not 0.0. A zero start puts the first ever event inside the
        # cooldown window and suppresses it - the one notification that matters
        # most is the first one.
        self.last_notified: float | None = None

    def update(self, body: dict | None, confidence_pct: float | None,
               now: float | None = None) -> PostureEvent | None:
        now = now if now is not None else time.monotonic()
        posture = (body or {}).get("posture")
        position = ((body or {}).get("position") or {}).get("position")
        # Prefer the keypoint-derived position; fall back to the extent ratio.
        state = position or posture or "unknown"
        fully = bool((body or {}).get("fully_visible"))

        self.history.append((now, state, fully))
        self.history = [h for h in self.history if now - h[0] <= HISTORY_S]

        horizontal = state in ("lying down", "horizontal")

        if not horizontal:
            self.horizontal_since = None
            return None

        if self.horizontal_since is None:
            self.horizontal_since = now
            return None

        held = now - self.horizontal_since
        if held < self.sustain_s:
            return None
        if self.last_notified is not None and now - self.last_notified < self.cooldown_s:
            return None

        # Was the person upright earlier in the window? A transition is far more
        # informative than a steady state - someone asleep in bed is horizontal
        # all night and is not an event.
        prior = None
        for t, st, _ in reversed(self.history):
            if now - t > held + 2.0 and st not in ("lying down", "horizontal", "unknown"):
                prior = st
                break
        if prior is None and self.require_prior_upright:
            # No upright observation to transition from. Report nothing rather
            # than treating a persistently horizontal scene as a new event.
            return None

        limitations = [
            "thermal silhouette only; cannot distinguish a fall from lying down",
            "cannot see the fall itself, only a posture that persisted",
        ]
        if self.demo:
            limitations.insert(0, "DEMO MODE: 1.2 s trigger, no upright "
                                  "precondition - fires on a stretch or a lean")
        if not fully:
            limitations.append("body is partly outside the sensor's field of view")
        if confidence_pct is not None and confidence_pct < 40:
            limitations.append(f"weak measurement conditions ({confidence_pct:.0f}%)")

        self.last_notified = now
        return PostureEvent(
            kind="posture_change_to_horizontal",
            at=time.time(),
            detail=(f"horizontal for {held:.1f}s"
                    + (f", previously {prior}" if prior else "")),
            confidence_pct=confidence_pct if confidence_pct is not None else 0.0,
            prior_posture=prior,
            limitations=limitations,
        )


def _tls_context() -> ssl.SSLContext:
    """A verifying TLS context that works on this interpreter.

    PlatformIO's bundled Python has no default CA bundle, so the obvious
    urlopen fails with CERTIFICATE_VERIFY_FAILED. The fix is to point at a real
    bundle, not to disable verification - an unverified push channel can be
    redirected by anyone on the path.
    """
    for loader in (
        lambda: __import__("certifi").where(),
        lambda: "/etc/ssl/cert.pem",
        lambda: "/opt/homebrew/etc/openssl@3/cert.pem",
    ):
        try:
            path = loader()
            if path and os.path.exists(path):
                return ssl.create_default_context(cafile=path)
        except Exception:
            continue
    # Still verifying, just with whatever the platform offers.
    return ssl.create_default_context()


def notify(event: PostureEvent, topic: str | None = None,
           server: str = "https://ntfy.sh") -> tuple[bool, str]:
    """Send to an ntfy topic. Returns (sent, detail).

    ntfy is used because it needs no account and no credentials in the repo -
    a topic name is the whole configuration. That also means anyone who knows
    the topic can read it, so the message carries no identifying information.
    """
    topic = topic or os.environ.get("NTFY_TOPIC")
    if not topic:
        return False, "no NTFY_TOPIC configured"

    demo = any("DEMO MODE" in l for l in event.limitations)
    body = (
        f"{event.detail}\n\n"
        "This is a posture observation from a thermal sensor, not a fall alarm "
        "and not a medical assessment. Limitations:\n"
        + "\n".join(f"- {l}" for l in event.limitations)
    )
    req = urllib.request.Request(
        f"{server}/{topic}",
        data=body.encode(),
        headers={
            "Title": ("DEMO - posture change: horizontal" if demo
                      else "Posture change: horizontal"),
            "Priority": "default",
            "Tags": "eyes",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_tls_context()) as r:
            return r.status < 300, f"HTTP {r.status}"
    except Exception as exc:
        return False, f"{exc.__class__.__name__}: {exc}"
