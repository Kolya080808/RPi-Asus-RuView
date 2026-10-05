# Project handoff

## User research integrated: repeater CSI and Pi architecture — October 5, 2026

The user supplied a research draft named `deep-research-report.md`. Its claims
were reviewed and rewritten as `docs/REPEATER-CSI-RESEARCH.md`; this is a
reviewed synthesis, not a verbatim move. The root file is no longer present in
the working tree. The review narrows claims about Netlink 23 and main-router capture of backhaul frames,
records the Pi as proposed collector/processor pending proof of an export path,
and documents the AX58 reboot as causal uncertainty. README now links both the
readable API reference and this research report. The authorized test/device
boundaries requested by the user are in `AGENTS.md`. No new device capture or
commit/push was performed for the API presentation work below.

## Embedded API documentation deployed to Pi — October 5, 2026

The reference is integrated into the workspace at
`http://192.168.50.100/#api-docs`, under the `02: API` sidebar section. It serves
locally bundled Swagger UI 5.33.1 against the tagged OpenAPI contract. “Try it
out” is enabled and sends actual requests; no request was executed during
verification. The old `/api/docs` URL redirects into the workspace. Final Pi
operation `20261005T183337Z-e75028` passed deployment verification and rollback
inspection: API v2 active, seven sessions and 1,881 records unchanged, SQLite
integrity `ok`, and the raw-history digest unchanged. Browser verification found
all 16 operations in four groups and confirmed light/dark-aware styling. OpenAPI
responses were corrected against the handler implementation, and direct
operation links remain in the API workspace route. API and rollback details are
in `PANEL.md` and `ROLLBACK.md`. No capture or
router/repeater change was made; no commit or push was created.

## Latest follow-up: AX56 inspected without capture — October 5, 2026

The user postponed committing and requested separate AX56 research. Read-only
inspection confirmed its distinct chip/driver, client-mode upstream links and
registered CSI subsystem; uptime increased and monitor state stayed disabled.
No acquisition utility or supported export contract was found in the checked
device paths and ASUS support material. See `HARDWARE.md` for technical inventory
and `EXPERIMENTS.md` for evidence, external sources and limits. No uploads,
monitor changes, captures, commit or push occurred. Capture remains blocked.
The next research options are exact-platform acquisition documentation/source
and a separately planned extra peer link on the validated main-router receiver.

## Active checkpoint: RP-AX58 reboot incident — October 5, 2026

Password access to both ASUS repeaters is verified. One attempted AX58 CSI probe
coincided with a confirmed reboot and the user's streaming interruption. No CSI
was saved; no AX56 capture was attempted. The exact failure stage/cause is unknown.
`EXPERIMENTS.md` records the timing, independent main-router observations, reader
buffering limitation and evidence locations. Both repeater capture paths are now
disabled in `scripts/repeater_probe.py`; retain read-only inspection and narrow
`rollback.py --repeater-only` support. Configuration restoration was verified
after reboot, not through confirmed trap completion. Do not repeat the live probe.
At the time this checkpoint was written, next work was offline incident/compatibility
analysis. The subsequent research review is summarized above and documented in
`REPEATER-CSI-RESEARCH.md`.
Earlier access-blocker entries below are historical and superseded by this check.

Offline follow-up completed: the saved AX58 log has a gap from 19:07:27 to reboot;
main-router events place the first recorded disconnect at 19:10:51. ELF metadata
matches ARM32 but cannot prove firmware compatibility. A synthetic local Paramiko
test confirmed that partial diagnostics can remain unwritten on timeout. Exact
cause remains unresolved; see the expanded `EXPERIMENTS.md` assessment. New plan
preparation is blocked while the incident is unresolved, and restored operations
cannot disable a subsequently enabled monitor. No remote connections were made
during this follow-up.

## Planning and repeater access: October 5, 2026

The user authorized trying repeater CSI acquisition and prioritized short
feasibility probes before long collector runs. `NEXT-STEPS.md` now describes
per-device evidence, bounded captures and rollback gates. `AGENTS.md` records
the preferred answer length, with flexible paragraph/list structure.

Pi access was confirmed by the user and verified with the existing pinned key.
Both repeater addresses answered unauthenticated SSH handshakes. Trusted host
entries were not found in the checked local/Pi files; the existing repeater login
method is unresolved. Observed, unverified fingerprints are in `HARDWARE.md`.
The user subsequently clarified that they only used the main router's AiMesh UI.
Existing lab RSA-key authentication as `admin` was rejected by both nodes;
the main-router password hypothesis remains untested. See the follow-up in
`HARDWARE.md`. A local interactive password login is the next access step. No remote
configuration/files were changed, no CSI captured and no rollback applied;
`deployment.json` and `scripts/rollback.py` remain unchanged until a concrete
remote change can be planned from verified initial state. Local documentation
validation: `git diff --check` passed; no code tests were needed or run.

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
