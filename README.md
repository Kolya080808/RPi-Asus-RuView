# ASUS Wi-Fi radio sensing

The goal is to replace a conventional surveillance system with one that observes the
environment through Wi-Fi radio signals, using ASUS routers and repeaters. This
repository contains the current prototype and research: collecting Channel State
Information (CSI) from an ASUS GT-AX11000, storing it on a Raspberry Pi Zero 2 W,
decoding captures, and testing motion and position-related signal changes. These are
development steps toward the replacement system, not the project's end goal.
The ultimate capability priority is a three-dimensional human skeleton; the first
usable version should at least estimate the position of a moving object.

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

- `src/web_panel.py` and `web/` — local Pi map, manual bounded CSI capture,
  live/replay session controls and annotation workspace; see
  [docs/PANEL.md](docs/PANEL.md).

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
Capture autostart is not enabled. The separate panel already runs as an enabled
service on port 80; collection starts only on an explicit recording request. History is stored in SQLite on the
Pi; automatic deletion is not implemented yet. The requirement is to retain
diagnostic logs for several weeks and then delete them, while preserving raw CSI history.

## Local panel on the Raspberry Pi

The first local panel is a standard-library HTTP service. It displays the
existing apartment map and device placements, lets the user save experiment
points and routes, and stores metadata in the Pi history database. Manual capture
is bounded to 5–1,800 seconds with a storage guard. The live chart requests new
samples every 100 ms after each response and displays the latest 60 seconds.
Separate delete controls target the current recording and a library selection.
Automatic retention and always-on capture remain unimplemented. The contract for a
phone web app and PC program is documented in [docs/API.md](docs/API.md) and
[docs/API.openapi.json](docs/API.openapi.json). It does not expose the panel
to the Internet. Recording temporarily enables the documented ASUS CSI monitor;
segment cleanup disables it and removes the temporary peer. Persistent router
settings are unchanged.

After the Pi is reachable over SSH, deploy it from this repository:

```powershell
python .\scripts\deploy_panel.py --prepare
python .\scripts\rollback.py --panel-only --check
python .\scripts\deploy_panel.py --apply
```

The service listens on port 80, so the panel is available at
`http://raspberrypi.local/` when the Pi's hostname and local mDNS service
resolve that name. HTTPS is intentionally not enabled yet; the panel is
designed for the trusted home LAN and does not provide Internet access control.
The deployment script uses the documented Pi address `192.168.50.100` by
default with the existing pinned host key.

The current implementation status is documented in
[docs/API.md](docs/API.md), [docs/NEXT-STEPS.md](docs/NEXT-STEPS.md), and
[docs/HANDOFF.md](docs/HANDOFF.md). The shared API and panel are implemented;
manual capture and separate current/library session deletion are available;
automatic retention is still being designed.
Device markers use documented map coordinates; selecting one shows its model,
region, height, and placement notes in the inspector.

## Rollback

For the latest panel update, inspect the exact restore plan without changes:

```powershell
python .\scripts\rollback.py --panel-only --check
```

Apply rollback:

```powershell
python .\scripts\rollback.py --panel-only --apply
```

Panel rollback restores only manifest-listed files and the existing service state;
it preserves recordings and device access. Stop any active or paused recording
first. The separate full-lab rollback has a broader scope, including access keys; see
[docs/ROLLBACK.md](docs/ROLLBACK.md) for details.

## License and external components

Original scripts and documentation are distributed under Apache-2.0.
ASUS/Broadcom firmware, the `csimond` utility, RuView, and third-party models have
their own licenses and are not included in this repository.
