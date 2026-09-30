# Project handoff

The project aims to test whether the built-in CSI Monitor on an ASUS
GT-AX11000 can serve as a Wi-Fi sensing source, with a Raspberry Pi Zero 2 W as a local
collector and history server. The user's long-term requirement is to obtain
a human skeleton and RuView features with minimal power consumption.

As of September 29, 2026, the following facts have been confirmed:

1. The GT-AX11000 running 3.0.0.4.388_24548 reports Broadcom chipnum 0xaaa4 and provides
   `wl csimon`; the stock `/usr/sbin/csimond` receives data from Netlink subsystem 23.
2. The Pi Zero 2 W running Debian 13 ARM64 is accessible over SSH and can record the router's
   raw output. The Pi's built-in Wi-Fi is not used as a CSI source.
3. The useful dynamic region in the captures follows a 96-byte header and contains 224 bytes
   of CSI. It is decoded as 56 complex values, each consisting of `int16 I + int16 Q`.
4. The large tail extending to 2048 bytes alternates between two old samples and is not
   treated as fresh CSI.
5. When one person waved their arms, the normalized amplitude change metric rose
   from approximately 0.019 to 0.132. This is an indicator of motion across the entire scene.
6. Mean CSI profiles differed when standing in three areas of the room, but
   the boundaries were annotated manually and included transitions between positions.
7. Read-only diagnostics on the RP-AX58 (`192.168.50.136`) and RP-AX56 (`192.168.50.156`)
   advertise `csimon`, but no standalone `csimond` was found on either device.
   Working userspace capture from the repeaters has not yet been demonstrated; see
   [HARDWARE.md](HARDWARE.md) for details.

Do not claim skeleton reconstruction, joint recognition, medical measurements,
or established compatibility with RuView's pose pipeline based on this report.
These require synchronized CSI and video labels, repeated captures, loss measurements,
and evaluation on a held-out test. A camera is allowed only as a calibration tool;
the final system must operate without one.

The full technical report is in [RESEARCH.md](RESEARCH.md), the original
requirements in [REQUIREMENTS.md](REQUIREMENTS.md), operating instructions in
[RECORDING.md](RECORDING.md), hardware details in [HARDWARE.md](HARDWARE.md),
and rollback instructions in [ROLLBACK.md](ROLLBACK.md). Upstream RuView: [github.com/ruvnet/RuView](https://github.com/ruvnet/RuView).
