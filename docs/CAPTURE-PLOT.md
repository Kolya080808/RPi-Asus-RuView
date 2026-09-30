# One-command recording and motion PNG

For an actual live window directly from ASUS without the Pi, see
[LIVE-MOTION.md](LIVE-MOTION.md). This document describes the separate Pi-to-PNG workflow.

Run from PowerShell in the repository root:

```powershell
python .\scripts\capture_plot.py --seconds 60 --open
```

Or use the convenience launcher:

```powershell
.\scripts\record-motion.ps1
```

The script checks Pi access, waits 15 seconds for preparation, requests one
bounded recording at a 100 ms interval, exports that exact session, and opens
a local PNG. Stay still for the first 10 seconds of capture, then alternate
movement and pauses. SSH startup adds a small delay after the countdown;
these cues are not synchronized ground-truth labels. Keep the terminal open.

This is automatic plotting after capture, not a real-time graph. Allow about
a minute for the recording, plus countdown, SSH startup, export, and rendering.
No new server, remote packages, or persistent service is installed.

## Requirements

- The Pi must be reachable at `192.168.50.100` with its existing collector in
  `/home/pi/ruview-lab` and working access to the ASUS.
- Local Python, Matplotlib, and an OpenSSH client on PATH.
- Existing `~/.ssh/ruview_pi_lab` and `~/.ssh/ruview_known_hosts` files.
  Unknown/changed SSH host keys are rejected; passwords are not stored.

If Matplotlib is missing: `python -m pip install matplotlib`.
Use `--host`, `--key`, or `--known-hosts` for an explicitly different setup.
The preparation countdown is configurable with `--delay 30`.

## Outputs and interpretation

Each run creates a separate UTC-stamped directory under `recordings/`:

- `motion.png`: amplitude RMS above; normalized amplitude changes and a trailing
  one-second mean below, in the style of `evidence/clean-motion-analysis.png`.
- `records.jsonl`: exported raw CSI for reprocessing.
- `analysis.json`: counts, cadence, timing gaps, and interpretation.
- `samples.json`: computed values with relative timestamps.
- `session.json`: exact Pi session ID and host for remote runs.
- `capture.log`: collector output for new remote captures, including failures.

Larger changes indicate a changing radio scene. They are not a body-part,
position, or presence estimate. No colored activity windows are invented.
Timing uses the provisional microsecond-like device timer. Gaps exceeding
1.8 times the median interval interrupt the motion line; invalid records are
counted, and motion differences do not bridge them. An unexpected timer reset
stops plotting with an error rather than constructing a misleading timeline.
The existing Pi detector remains unchanged; this plot computes its own time-based
smoothing and does not depend on successful Pi motion-event analysis.

Raw data remain on the Pi and local exports are excluded from Git. The Pi's
existing 256 MiB recording limit remains in effect. Sessions are still limited
to 5–60 seconds; do not start overlapping captures.

## Replot without a new capture

Download an existing Pi session:

```powershell
python .\scripts\capture_plot.py --session SESSION_UUID --open
```

Plot an exported file entirely offline:

```powershell
python .\scripts\capture_plot.py --input .\recordings\RUN\records.jsonl --open
```

If export fails, the session ID is retained locally; retry with `--session`.
If SSH times out or is interrupted during capture, check Pi history before
retrying. The remote capture is bounded, but its final state must be verified.

## Verification on 2026-09-30

The plot was generated from the real saved 592-record clean-motion session.
Offline checks cover cadence, smoothing, invalid records, timer rollover/reset,
and timing gaps. A new end-to-end device capture could not be verified because
SSH to the Pi timed out. The tool does not substitute demonstration data when
live access fails.
