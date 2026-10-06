# Requirements and current limitations

Core objective: replace a conventional surveillance system with a system that
observes the environment through Wi-Fi radio signals, using ASUS routers and
repeaters. The ultimate priority is a three-dimensional human skeleton. The first
practical version must at least estimate the position of a moving object. CSI
collection, decoding, experiments, and the current motion indicator are steps toward
that system, not the project's end goal.

Desired capabilities include a human skeleton reflecting actual movement and relevant
RuView features; these remain targets to validate, not demonstrated capabilities.
A script to roll back device changes is required. The Pi may serve only as a web
server. The Pi is currently in the bedroom with two repeaters; it can be relocated.

Do not treat an animated template, simulation, or camera output as evidence of
Wi-Fi pose reconstruction. Validation requires matched CSI measurements and reference
movements; also evaluate an empty room and a disconnected source.
A camera is allowed for calibration/training: a webcam and a phone camera are available.
Preference: run everything on the Pi Zero 2 W; an always-on PC is undesirable.
Recording and history playback are required. Keep all diagnostic logs for several
weeks and then delete them; the exact retention period and cleanup implementation
remain to be specified. This log policy does not authorize deleting raw CSI history.
Video recording is undecided.

Confirmed: the stock GT-AX11000 csimon provides records, 16 in 8 seconds,
with no ACK failures/overflows. Working hypothesis: a 96-byte header + 224 bytes of I/Q.
Transfer of an ESP32/MM-Fi model to Broadcom is unverified.
Second capture from the Pi: 98 complete records with a 100 ms timer. The 96:320 region
was confirmed again through variability; the tail has two alternating hashes.
Driver: 99 transfers, 1 ACK failure, 0 overflows; 98 saved — collection is not lossless.

RuView README, checked 2026-09-29: pose_v1 first-cut PCK@20 3.0%;
live cog runtime confidence=0 stub; the MM-Fi benchmark uses a separate model/dataset.
The beta note separately reports ~2.5% on proxy labels, with P7–P9 unfinished.
These are upstream claims, not our measurements. A reliable skeleton and full
support for the advertised features on ASUS cannot be promised before validation.

Before any new remote changes: save the initial state,
record exact paths/processes/keys, extend rollback.py, and verify rollback.
Do not install systems or models merely for a demonstration without a real
data stream. Do not reflash the main router as part of diagnostics.

## Delivery and access decisions

Consolidated from NEXT-STEPS on 2026-10-06. The execution order remains in that file.

**Rewrite the full system in C++ and prepare its installers** after reviewing
    the Python implementation, fixing the bugs found, and making any useful
    small improvements. Then migrate the whole implementation when the user
    considers it ready. This includes low-level collection and decoding,
    processing, Pi/server services and API, and the native PC application that
    consumes the API. Target Windows, macOS and Linux for the PC client. Make
    installation packages for the Pi, server and PC; do not create a native
    phone application or phone installer. Phone access stays in the browser and
    the panel must be responsive and usable on a phone. Preserve formats and
    behavior through parity/regression checks and provide upgrade, recovery,
    uninstall and rollback procedures. The user's
    [DJI-Link repository](https://github.com/Kolya080808/DJI-Link) is a reference
    for the PC packaging approach only, not a requirement to
    copy its implementation or architecture wholesale as it is another project.


### Panel authentication

Start with a local username-and-password login. Store only a suitably slow,
salted password hash; use protected sessions, CSRF defenses for writes, account
recovery and revocation, and controls that limit repeated failed attempts.
Passkeys/security keys can be considered as a later additional login method.
Keep the panel's `X-Panel-Token` separate: it is not user authentication. Do not
send project data, device credentials, captures, or source records to an identity
provider.

Done when explicitly enrolled household users can authenticate, a lost
credential can be revoked and recovered safely, and unauthenticated requests
cannot read panel data or perform API actions. Verify locally and on the
authorized Pi before proceeding to the public server tunnel; record the access
toggle and a tested rollback.


### Tunnel acceptance

After validated moving-point tracking and before skeleton work, design the
Pi-server tunnel and cryptography, implement it, add panel controls, then launch
Internet access behind the Pi panel login. Refusing Internet access must leave
the tunnel connected. Direct home-LAN access must remain available both with
and without Internet access. Verify access toggling and rollback.
