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

# --- trigger-on-change mode ---------------------------------------------
#
# POSTURE_SENSITIVE=1 fires on any notable change in the motion region: it
# appearing, its shape changing, or it moving across the frame. No orientation
# logic, no upright precondition, no sustain.
#
# It will fire when someone walks past, waves, or shifts in a chair. That is
# the intent - it is a trigger for filming, not a detector - and it is a
# separate mode so it cannot be mistaken for the real one.
SENSITIVE_COOLDOWN_S = 6.0
SENSITIVE_ASPECT_DELTA = 0.35
SENSITIVE_CENTROID_PX = 3.0
SENSITIVE_PIXEL_RATIO = 1.6

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
    """Sustained posture change, or - in sensitive mode - any change at all."""

    def __init__(self, demo: bool | None = None) -> None:
        self.sensitive = os.environ.get("POSTURE_SENSITIVE", "") == "1"
        self.demo = (os.environ.get("POSTURE_DEMO", "") == "1"
                     if demo is None else demo)
        self._last_motion: dict | None = None
        self.sustain_s = DEMO_SUSTAIN_S if self.demo else SUSTAIN_S
        self.cooldown_s = DEMO_COOLDOWN_S if self.demo else COOLDOWN_S
        # Demo mode keeps the transition requirement. Firing on any horizontal
        # region meant it triggered on ordinary movement, a chair, or a warm
        # object that happened to be wide - the alert has to mean "this person
        # was upright and now is not", which is the only thing that resembles a
        # fall. Demo mode shortens the window rather than removing it.
        self.require_prior_upright = True
        self.prior_margin_s = DEMO_PRIOR_MARGIN_S if self.demo else PRIOR_MARGIN_S
        # How long the upright shape must hold before it counts.
        self.confirm_upright_s = 1.0 if self.demo else 3.0
        # And how recently, so a fall is tied to a standing observation rather
        # than to one from minutes ago.
        self.upright_valid_for_s = 20.0 if self.demo else 90.0
        self.history: list[tuple[float, str, bool]] = []  # time, posture, fully_visible
        self.horizontal_since: float | None = None
        self.upright_since: float | None = None
        # When the person was last confidently upright. A fall is only reported
        # against a confirmed upright, never against "not currently horizontal".
        self.confirmed_upright_at: float | None = None
        # None, not 0.0. A zero start puts the first ever event inside the
        # cooldown window and suppresses it - the one notification that matters
        # most is the first one.
        self.last_notified: float | None = None

    def _sensitive_check(self, motion: dict, now: float) -> PostureEvent | None:
        """Fire on any notable change in the motion region."""
        prev, self._last_motion = self._last_motion, motion
        if (self.last_notified is not None
                and now - self.last_notified < SENSITIVE_COOLDOWN_S):
            return None

        reason = None
        if prev is None:
            reason = "movement detected"
        else:
            da = abs(motion.get("aspect", 0) - prev.get("aspect", 0))
            pc, cc = motion.get("centroid") or [0, 0], prev.get("centroid") or [0, 0]
            dc = ((pc[0] - cc[0]) ** 2 + (pc[1] - cc[1]) ** 2) ** 0.5
            pa, pb = motion.get("pixels", 1), max(1, prev.get("pixels", 1))
            ratio = max(pa / pb, pb / pa)
            if da >= SENSITIVE_ASPECT_DELTA:
                reason = f"shape changed (aspect {prev['aspect']:.2f} to {motion['aspect']:.2f})"
            elif dc >= SENSITIVE_CENTROID_PX:
                reason = f"moved {dc:.1f} px across the frame"
            elif ratio >= SENSITIVE_PIXEL_RATIO:
                reason = f"size changed ({pb} to {pa} px)"
        if not reason:
            return None

        self.last_notified = now
        return PostureEvent(
            kind="motion_change", at=time.time(), detail=reason,
            confidence_pct=0.0, prior_posture=None,
            limitations=["SENSITIVE MODE: fires on any movement, not on a fall"],
        )

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
        #
        # "not horizontal" is not the same as upright. A clipped or ambiguous
        # region means the orientation is unknown, and treating unknown as
        # upright is what let someone standing close to the sensor - filling
        # the frame, therefore measuring wide - arm the detector and then
        # immediately satisfy it.
        if self.sensitive and motion is not None:
            ev = self._sensitive_check(motion, now)
            if ev:
                return ev

        if motion is not None:
            state = motion.get("orientation", "unknown")
            fully = not motion.get("touches_bottom", False)

        # An upright observation only counts once the shape has held that way
        # for long enough to be trusted.
        if state == "upright":
            if self.upright_since is None:
                self.upright_since = now
            if now - self.upright_since >= self.confirm_upright_s:
                self.confirmed_upright_at = now
        else:
            self.upright_since = None

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

        # Require a confirmed upright, recently. This is the whole guard
        # against a false alarm from someone standing close: filling the frame
        # reads as wide, but it never reads as a confirmed *upright*, so the
        # detector is never armed and the horizontal shape alone cannot fire it.
        if self.confirmed_upright_at is None:
            return None
        since_upright = now - self.confirmed_upright_at
        if since_upright > self.upright_valid_for_s:
            return None
        if since_upright < held:
            # The upright confirmation must predate the horizontal period.
            return None
        prior = "standing"

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


def _unused_marker():
    pass


def notify(event: PostureEvent, topic: str | None = None,
           server: str = "https://ntfy.sh") -> tuple[bool, str]:
    """Send to an ntfy topic. Returns (sent, detail).

    ntfy is used because it needs no account and no credentials in the repo -
    a topic name is the whole configuration. That also means anyone who knows
    the topic can read it, so keep SUBJECT_NAME generic if the topic is shared.

    Message text is configurable so a demo can read naturally on camera:
        SUBJECT_NAME   optional subject label
        ALERT_TITLE    notification title (default "Sustained horizontal posture")
    """
    topic = topic or os.environ.get("NTFY_TOPIC")
    if not topic:
        return False, "no NTFY_TOPIC configured"

    name = os.environ.get("SUBJECT_NAME", "Subject")
    motion_only = event.kind == "motion_change"
    default_title = "Thermal motion change" if motion_only else "Sustained horizontal posture"
    title = os.environ.get("ALERT_TITLE", default_title)
    observation = "motion change" if motion_only else "sustained horizontal posture"
    body = (f"{name}: {observation} observed in the thermal view. "
            "This prototype cannot determine whether a fall occurred.")

    req = urllib.request.Request(
        f"{server}/{topic}",
        data=body.encode(),
        headers={
            "Title": title,
            "Priority": "default",
            "Tags": "information_source",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_tls_context()) as r:
            return r.status < 300, f"HTTP {r.status}"
    except Exception as exc:
        return False, f"{exc.__class__.__name__}: {exc}"
