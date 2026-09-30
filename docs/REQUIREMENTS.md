# Requirements and current limitations

User requirements: a human skeleton reflecting actual movement, RuView features,
and a script to roll back all device changes. The Pi may serve only as a web server.
The Pi is currently in the bedroom with two repeaters; it can be relocated.

Do not treat an animated template, simulation, or camera output as evidence of
Wi-Fi pose reconstruction. Validation requires matched CSI measurements and reference
movements; also evaluate an empty room and a disconnected source.
A camera is allowed for calibration/training: a webcam and a phone camera are available.
Preference: run everything on the Pi Zero 2 W; an always-on PC is undesirable.
Recording and history playback are required. Retention duration and video recording are undecided.

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
