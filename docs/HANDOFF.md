# Project handoff

## Current checkpoint: October 5, 2026 — user accepted live refresh

The user accepted the live graph and separate current/library deletion controls.
The deployed version is operation `20261005T104835Z-2915cd`. It uses a 600-point
live cache and cursor-based updates with a target 100 ms client interval, instead
of repeatedly decoding the entire history. The measured browser median update
interval was 0.115 s; the first line appeared after 1.538 s. These short-run
observations are not an end-to-end latency or endurance guarantee.

27 Python and 6 JavaScript tests passed in the implementation turn. Deployment
hashes, preserved history and before/after rollback inspections passed. Ten Pi
sessions remained after verification, including the three retained test captures
from this chat. This is the last verified count, not a live inventory.

Current operation, evidence and limitations: [PANEL.md](PANEL.md). Next work:
[NEXT-STEPS.md](NEXT-STEPS.md). Exact local backups and restore scope:
[ROLLBACK.md](ROLLBACK.md). No new sensing capability or location estimate is claimed.

The dated entries below describe earlier checkpoints and their counts.

## Update: October 5, 2026 — capture polling and deletion

Fixed capture identity loss after the first poll, restored live polling after page
reload, and separated current-capture deletion from library-selection deletion.
Paused deletion stops and joins the worker first; failed joins retain history.
Deployed operation `20261005T102745Z-8897cc` with exact backups and successful
rollback checks. A real 30-second capture produced 299 valid CSI prefixes and a
growing browser graph; its raw data remain as the eighth Pi session. Original
history is retained. Tests, evidence and remaining collector limitations are in
[PANEL.md](PANEL.md#capture-controls-fix-2026-10-05). No new sensing claim is made.

## Update: October 4, 2026 — panel iteration

Read-only Pi inspection found an existing bootstrap panel on port 80, served by
the enabled `ruview-lab-panel.service`, which had not been synchronized to this
checkout or its documentation. There were seven sessions, 1,881 raw records,
and no saved points/routes/activity labels. Sources were recovered into ignored
local backups before work. Existing user edits in this checkout were preserved.

The new local panel implementation is documented in [PANEL.md](PANEL.md):
reference map/points/routes, device inventory, session filtering, causal signal
replay, timed reference labels and raw export. No new sensing capability is
claimed; later October 4 updates enabled manual bounded capture. Database layouts and raw records are
preserved. Original capture map layouts are unknown. Deployment and rollback
use the existing service with the exact scope in [ROLLBACK.md](ROLLBACK.md).

Pi access is available on user request; see AGENTS.md. Use the existing SSH key
and pinned host key. No password was added to the repository.

Deployed and verified on the Pi on 2026-10-04 (operation
`20261004T201213Z-29ab70`). All seven target hashes, service state, database
counts/integrity and raw-record digest passed verification. Twenty local tests
passed; desktop/mobile UI workflows passed on a separate history copy, and
read-only replay of every Pi session passed. No test labels were added to the
Pi. Exact checks and remaining limitations are in [PANEL.md](PANEL.md).

## Update: September 30, 2026

The user supplied a Polycam apartment scan and marked the main router and three
repeaters. Plans, approximate coordinates, model assignments, and reported heights
are saved under `maps/home/`. See [HOME-MAP.md](HOME-MAP.md) for confirmed facts
and [NEXT-STEPS.md](NEXT-STEPS.md) for the proposed continuation.

The first usable sensing version should estimate the position of a moving object;
the ultimate capability priority is a three-dimensional human skeleton. The map,
timed movement annotation, and aligned capture/replay are development steps toward
those capabilities. Triangulation has been set aside. Position estimates must be
compared against separate reference labels. The panel/API and location model are not
implemented. No new remote changes or captures were made in the map work.
Repository documentation and code comments are maintained in English.

## Existing sensing baseline

The project's end goal is to replace a conventional surveillance system with one
that observes the environment through Wi-Fi radio signals, using ASUS routers and
repeaters. The current phase tests whether the built-in CSI Monitor on an ASUS
GT-AX11000 can serve as a sensing source, with a Raspberry Pi Zero 2 W as a local
collector and history server. A human skeleton and RuView features with minimal power
consumption are desired capabilities, not yet validated results.

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
