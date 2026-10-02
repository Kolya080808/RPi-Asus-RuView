# ASUS CSI sensing lab

An experimental system for collecting Channel State Information from an ASUS GT-AX11000
and storing data on a Raspberry Pi Zero 2 W. This repository documents the starting
point, captures, decoder, motion detector, and project limitations.

## Current results

The stock Broadcom `csimon` on the GT-AX11000 provides records through Netlink. In two
independent captures, the fresh region matched `payload[0x60:0x140]`: 224 bytes,
56 pairs of little-endian signed int16 I/Q values. In a clean test, one person waved
their arms; the change in normalized amplitude was roughly seven times the still
baseline. In a separate test, positions near the router, in the middle, and at the
far end of the room produced different mean CSI profiles.

This demonstrates data acquisition and motion detection in this setup.
Skeletons, individual body parts, heart rate, and breathing have not yet been implemented or validated.
Upstream RuView itself describes its current pose model as a first cut with
low validated accuracy. The full analysis and limitations are in
[docs/RESEARCH.md](docs/RESEARCH.md).

Device versions and capabilities are documented in
[docs/HARDWARE.md](docs/HARDWARE.md). Official upstream RuView project:
[github.com/ruvnet/RuView](https://github.com/ruvnet/RuView).

## Contents

- `maps/home/` — apartment plans, source-linked geometry, and annotated device positions.
- `docs/HOME-MAP.md` — confirmed placement, map limitations, and project decisions.
- `docs/NEXT-STEPS.md` — proposed map annotation, API, recording, and evaluation workflow.
- `src/` — decoder, Pi collector, and conservative motion indicator.
- `scripts/` — device rollback and analysis of saved captures.
- `docs/RESEARCH.md` — the complete original research report, without abridgment.
- `docs/EXPERIMENTS.md` — a log of the three main tests and their numerical results.
- `docs/HARDWARE.md` — addresses, firmware versions, and verified device CSI capabilities.
- `docs/` — requirements, results, history format, and hardware state.
- `evidence/` — text captures, plots, and diagnostic output.

Private keys, the history database, and the deployment manifest are deliberately excluded from Git.
They are needed only on the operational devices; sharing the repository with someone
else must not grant access to the router.

## Collection on Raspberry Pi

For a live graph directly from ASUS, with no Pi required:

```powershell
python .\scripts\live_motion.py
```

Press **Start** in the window. See [docs/LIVE-MOTION.md](docs/LIVE-MOTION.md)
for smoothing, Stop, saved data, and capture limits.

For automatic recording, export, and a local motion PNG from this PC, run:

```powershell
python .\scripts\capture_plot.py --seconds 60 --open
```

See [docs/CAPTURE-PLOT.md](docs/CAPTURE-PLOT.md) for setup and offline replay.
The PNG opens after the bounded capture; this is not a live display.

Files are deployed on the Pi at `/home/pi/ruview-lab`. Example of a bounded session:

```sh
python3 /home/pi/ruview-lab/recorder.py capture --seconds 60 --interval-ms 100
python3 /home/pi/ruview-lab/recorder.py history
python3 /home/pi/ruview-lab/motion.py SESSION_ID
```

The session automatically disables `csimon` and removes the temporary monitored peer.
Autostart is not enabled. History is stored in SQLite on the Pi; automatic deletion is not implemented yet.

## Local panel on the Raspberry Pi

The first local panel is a standard-library HTTP service. It displays the
existing apartment map and device placements, lets the user save experiment
points and routes, and stores metadata in the Pi history database. Capture
control is intentionally disabled for now so the Pi cannot fill its storage
before a retention/export policy is defined. The shared client contract for a
phone web app and PC program is documented in [docs/API.md](docs/API.md) and
[docs/API.openapi.json](docs/API.openapi.json). It does not expose the panel
to the Internet and does not change the ASUS router configuration.

After the Pi is reachable over SSH, deploy it from this repository:

```powershell
python .\scripts\deploy_panel.py
```

The service listens on port 80, so the panel is available at
`http://raspberrypi.local/` when the Pi's hostname and local mDNS service
resolve that name. HTTPS is intentionally not enabled yet; the panel is
designed for the trusted home LAN and does not provide Internet access control.
The deployment script uses the documented Pi address `192.168.50.100` by
default; use `--host raspberrypi.local` if that name already resolves over SSH.

The current implementation status is documented in
[docs/API.md](docs/API.md), [docs/NEXT-STEPS.md](docs/NEXT-STEPS.md), and
[docs/HANDOFF.md](docs/HANDOFF.md). The shared API and panel are implemented;
CSI capture control through them is intentionally disabled while storage
retention and export rules are being designed.
Device markers use the source annotation pixels, and hovering a marker shows
its model, region, height, and placement notes in an unclipped top-level card.

## Rollback

Check without making changes:

```powershell
python .\scripts\rollback.py --check
```

Apply rollback:

```powershell
python .\scripts\rollback.py --apply
```

The script removes only known experimental keys and files with matching
hashes. A complete device snapshot was not taken before the experiment; see
[docs/ROLLBACK.md](docs/ROLLBACK.md) for details.

## License and external components

Original scripts and documentation are distributed under Apache-2.0.
ASUS/Broadcom firmware, the `csimond` utility, RuView, and third-party models have
their own licenses and are not included in this repository.
