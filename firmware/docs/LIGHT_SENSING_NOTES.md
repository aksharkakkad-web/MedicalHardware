# Ambient light — what it is for

The BH1750 on the carrier is now read at 2 Hz and reported as a `dark` /
`dim` / `lit` / `bright` band. **That banding is the only thing implemented.**

Everything below is recorded intent, not built. It is here so the reasoning is
not lost, and so nobody implements the circadian items without reading the
sensor caveat first.

## Candidate uses, in rough order of value

**1. Nocturnal ambulation in darkness.** Radar says someone is up and moving;
lux says the room is dark. A well-established fall-risk condition, and the only
place light becomes near-real-time actionable. The response — turn on a low
night light — is beneficial and harmless if the inference is wrong, which is
what makes it safe to act on without clinical validation. Needs no new parts.

**2. Sleep-environment light hygiene.** Logging overnight lux shows whether
light is leaking in from a hallway, a streetlight, or a device, and when.
Low-stakes, immediately legible, no medical claim required.

**3. Circadian light exposure — with a hard caveat.** Cumulative daytime lux
and nighttime intrusion are legitimately informative, and institutional
settings routinely have too little daytime light and too much at night.

> **The BH1750 cannot support a circadian metric.** It is a broadband lux
> sensor with no spectral channels. Circadian effect depends on the blue-cyan
> content of light, and the field uses melanopic equivalent daylight
> illuminance, which requires spectral weighting. Two sources at identical lux
> can have very different circadian impact.
>
> Honest with this part: "this room got 300 lux at 2pm."
> Not honest: "this person received adequate circadian stimulus."
>
> If circadian work matters, an **AS7341** 11-channel spectral sensor is I2C,
> drops onto the same bus, and costs roughly $15.

**4. Day/night context for everything else.** The quiet workhorse. Activity
level, time out of bed and room transitions all mean something different at 3am
in the dark than at 3pm, and a clock alone cannot tell you whether the lights
are on. It also helps explain thermal background drift, since solar loading
warms floors and furniture.

**5. Routine regularity.** When lights come on and go off, and how consistent
that is day to day, is a cheap proxy for daily routine. Treat it strictly as a
trend surfaced to a caregiver, **never as a flag** — it is noisy and confounded
by visitors, seasons, and shift patterns.

## Boundary

None of these may become alerting, triage, or diagnosis. Section 3 of
`HARDWARE_BRINGUP_BRIEF.md` applies: this is not a medical device. Item 1 is
acceptable precisely because its output is a night light, not a warning.
