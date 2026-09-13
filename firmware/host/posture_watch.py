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

# How far before the horizontal period an upright observation must sit to count
# as a transition. Normal mode wants clear separation; demo mode only needs
# enough to prove the person was actually standing first.
PRIOR_MARGIN_S = 2.0
DEMO_PRIOR_MARGIN_S = 0.4


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
        # Demo mode keeps the transition requirement. Firing on any horizontal
        # region meant it triggered on ordinary movement, a chair, or a warm
        # object that happened to be wide - the alert has to mean "this person
        # was upright and now is not", which is the only thing that resembles a
        # fall. Demo mode shortens the window rather than removing it.
        self.require_prior_upright = True
        self.prior_margin_s = DEMO_PRIOR_MARGIN_S if self.demo else PRIOR_MARGIN_S
        self.history: list[tuple[float, str, bool]] = []  # time, posture, fully_visible
        self.horizontal_since: float | None = None
        # None, not 0.0. A zero start puts the first ever event inside the
        # cooldown window and suppresses it - the one notification that matters
        # most is the first one.
        self.last_notified: float | None = None

    def update(self, body: dict | None, confidence_pct: float | None,
               now: float | None = None,
               motion: dict | None = None) -> PostureEvent | None:
        now = now if now is not None else time.monotonic()
        posture = (body or {}).get("posture")
        position = ((body or {}).get("position") or {}).get("position")
        # Prefer the keypoint-derived position; fall back to the extent ratio.
        state = position or posture or "unknown"
        fully = bool((body or {}).get("fully_visible"))

        # Motion wins when it disagrees. The absolute-temperature path can lock
        # onto a static hot object and report a confident, frozen posture; the
        # motion region cannot, because a static object is the background.
        if motion is not None:
            state = "horizontal" if motion.get("horizontal") else "upright"
            fully = not motion.get("touches_bottom", False)

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
            if now - t > held + self.prior_margin_s and st not in ("lying down", "horizontal", "unknown"):
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
            limitations.insert(0, "DEMO MODE: 1.2 s trigger with a 0.4 s "
                                  "upright precondition")
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
    the topic can read it, so keep SUBJECT_NAME generic if the topic is shared.

    Message text is configurable so a demo can read naturally on camera:
        SUBJECT_NAME   name used in the alert  (default "Mahin")
        ALERT_TITLE    notification title      (default "Fall detected")
    """
    topic = topic or os.environ.get("NTFY_TOPIC")
    if not topic:
        return False, "no NTFY_TOPIC configured"

    name = os.environ.get("SUBJECT_NAME", "Mahin")
    title = os.environ.get("ALERT_TITLE", "Fall detected")
    body = f"Patient {name} has fallen. Please check immediately."

    req = urllib.request.Request(
        f"{server}/{topic}",
        data=body.encode(),
        headers={
            "Title": title,
            "Priority": "urgent",
            "Tags": "rotating_light",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_tls_context()) as r:
            return r.status < 300, f"HTTP {r.status}"
    except Exception as exc:
        return False, f"{exc.__class__.__name__}: {exc}"
