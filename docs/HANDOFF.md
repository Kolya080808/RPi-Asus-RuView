# Project handoff

## Stock network export comparison completed — October 16, 2026

The user selected investigation of CSI delivery directly to a Pi IP/port without
a helper, then comparison with AX56 and a stop for today with a commit title.
Both exact-release rootfs audits completed. No working stock network CSI export
setting was identified. RemoteWL IP/port options are remote command controls,
not an identified CSI stream sender; the inspected CSI paths use local Netlink.
This is a bounded negative finding, not a proof of universal impossibility.

Fresh read-only AX56 checks matched the installed module to the saved release
hash and found both radios AP/up, one peer each, disabled/empty CSI, zero
counters and kernel-only Netlink 22/23 entries. Boot ID unchanged. No device
mutation occurred in this investigation. The helper transport can potentially
be shared, but AX56 runtime/activation and its decoder are not validated by
AX58's socket-free self-test. See [NETWORK-CSI-EXPORT.md](NETWORK-CSI-EXPORT.md)
for evidence, commands, limits and the next per-device checks.

Correction after the user's inventory reminder: TP-Link is already recorded as
RE200 AC750 in R02 near the printer. A subsequent user-requested read-only check
identified `.155` through GT DHCP hostname RE200 and its TP-Link web page.
The subsequent normal browser visit and user-authorized login resolved hardware
`RE200 5.0` and firmware `1.0.4 Build 210408 Rel.37106n (8285)`; versions were
already visible before login. The direct HTTP 401 did not establish a credential
requirement. Credentials are now stored privately. No settings were changed.
An official V5 archive with matching version/build/release was retained locally;
region and installed-image equality remain unverified. The initial decompression
limit was resolved locally; the main stream shows VxWorks 5.5.1/MT7628 markers
and MIPS startup instructions. The existing ASUS Linux/ARM helper cannot run
unchanged on this candidate platform. No CSI sender was identified; capability
labels alone are not measurements. `scripts/audit_re200_profile.py` reproduces
the bounded hash-locked classification. See NETWORK-CSI-EXPORT.md for evidence.
Normal logout was verified, no settings changed. The comparison checkpoint is
complete; RE200 acquisition would require a separate platform-specific study.
Stop at the ASUS investigation checkpoint;
actual CSI reception and live decoding remain unfinished. No commit created.

## AX58 continuation: corrected diagnostics and reader build — October 15

Found and fixed an SSH terminal-state race: final bytes could arrive after
the empty-buffer sample but before EOF handling, returning a false empty success.
Two deterministic regression tests failed before the fix and passed afterward.
Earlier empty/partial diagnostic results are not reliable absence evidence.
Fresh checks with the fix report eth1 AP=1, BSS=up and the historical peer
authenticated/associated/authorized on channel 4/20 MHz. Boot ID is unchanged.
The new exact-build offline audit establishes the CSI lookup's AP-role/up
configuration gates; it does not prove lifecycle safety or remove capture blocks.

Built a minimal static ARM Netlink reader, separate from the Python application.
Its Linux build passed four socket-free local tests. The ARM build subsequently
passed the same socket-free framing self-test on AX58 (operation `54eb642bed79`).
The temporary file was removed and boot/CSI baseline verified unchanged. See
[AX58-READER.md](AX58-READER.md) for bounds, build, evidence and unvalidated areas.
An earlier upload (`794b24803b6e`) stopped at 24,576 bytes before execution due
to a nonblocking SSH window; its exact partial file was separately inspected
and removed through narrow rollback. Window-aware stdin sending now passes a
real local SSH test transferring 65,536 bytes through a 32,768-byte window.
Both plans are restored. The full Windows suite passed 122 discovered tests
(118 executed, 4 opt-in Linux cases skipped); all 4 Linux cases passed in WSL.
Next assess passive reception with CSI disabled under a separate bounded plan. Active
CSI and the AX58 decoder remain subsequent, uncompleted work. No user input is
currently required for that preparation; no commit was created.

## Active target: AX58 live acquisition — October 15, 2026

The user corrected the scope: acquire CSI on RP-AX58 and decode continuously on
Pi, as for the router. Offline import/recovery is supporting work, not completion
of this target. Commit only after the requested working result; no commit made.

Initial bounded read-only SSH checks reached AX58 and Pi. The installed AX58
module hash matches the previously inspected firmware module. Both monitors are
disabled, lists empty and counters zero. The eth1 association list contains the
same peer as the failed October 5 probe. The initial empty `sta_info` result
was superseded after fixing the SSH race above. Pi is available with
Python 3.13.5, low load and sufficient free disk for a short bounded experiment.
Exact observations, limitations and private evidence locations are in
[EXPERIMENTS.md](EXPERIMENTS.md#ax58-live-preflight--october-15-2026).

No remote mutation, upload, monitor enable, collector or service start occurred.
Acquisition remains blocked at the new-method reset-risk gate. The original
report in `dhd_watchdog_dos.zip` and the October 13 user-confirmed finding are
already retained; do not ask the user to resubmit them or reopen milestone 1.
Validate the exact AX58 activation/peer and reader path using the retained
firmware evidence before a new reversible device plan. A successful live result requires actual raw frames, separately
validated AX58 decoding, measured delivery/timing and verified cleanup. The
historical GT-integration recommendation below is superseded by this target.

## Completed: offline recovery and legacy GT import — October 15, 2026

The next local checkpoint is complete in `src/raw_recovery.py` and the
`recover`/`import-legacy` subcommands of `scripts/raw_pipeline.py`. Recovery
copies only verified committed chunks/events from a readable `running` journal
to a new database; arrival times and incomplete tails are preserved. The new
journal stays failed/incomplete and never claims confirmed EOF or zero loss.
Corruption, size/deadline violations and SQLite sidecars cause explicit refusal;
there is no damaged-page, hot-journal or uncommitted-write repair.

Legacy import reads one selected GT session from an offline SQLite copy. It
retains exact BLOBs, original sequence gaps, metadata/logs and an ordered-record
digest. Prefix and full-payload modes are explicit; mixed 320/2048 records are
refused. Short records and incomplete source sessions remain incomplete. Input
databases are opened read-only; existing outputs are never overwritten. The
provenance and upstream status are committed without a false-success window.

Twenty-one new tests passed, including an actual child-process `os._exit` after a
committed block, independent envelope unpacking, source nonmutation, fault/limit
checks and both CLI paths. A 70-record import also verified exact order/content
across multiple ingestion chunks. The full suite passed 106 tests; py_compile and
diff checks passed. Details and limitations: [RAW-PIPELINE.md](RAW-PIPELINE.md)
and [EXPERIMENTS.md](EXPERIMENTS.md). No real private history, devices, secrets,
network collection or deployment state was accessed/changed. No commit created.

This was the offline checkpoint, not completion of the live target above.
Stage 2 remains open;
Managed-mode/reset-risk gates and live queue/timing/Pi-load evidence are unchanged.

## Offline raw journal and deferred processing — October 15, 2026

Implemented `src/raw_pipeline.py` and local-file CLI `scripts/raw_pipeline.py`.
Ingestion commits complete input chunks before parsing or decoding, with source
provenance, offsets, local import clocks and integrity metadata. Processing uses
a read-only snapshot and writes results to a different new database. Partial
envelopes, receive errors and unsupported profiles remain recoverable as raw
bytes; Netlink frames are never fed to the GT decoder. Stage/error events retain
tracebacks when storage permits. Existing output paths are refused.

The version-1 envelope is a local fixture/import format, not a deployed device
protocol. Tests cover fragmentation, errors, actual SQLite page-limit failure,
late/slow processing and CLI operation. Details: [RAW-PIPELINE.md](RAW-PIPELINE.md).
Existing panel/history, device firmware/configuration and capture blocks remain
unchanged. No new dependencies, device connections, deployment or commits.
Pi was made available by the user but was not needed. The user attributes the
intervening PC BSoD to their graphics-driver update; no project cause is inferred.

Next: interrupted-journal recovery and a verified legacy GT import adapter.
Live reader/consumer integration, queue/drop/stop behavior and Pi load are still
unverified and need a separate reversible device plan. The prototype refuses
`running` journals after an abrupt interruption rather than claiming completion.
This checkpoint does not establish repeater acquisition or finish stage 2.

## Stage 2: ordinary ADD and reader contract — October 15, 2026

Offline work begun October 14 traced ADD, enable, peer lookup and Netlink export
in the two hash-verified release modules. ADD can succeed without activating a
peer timer. Both use `wlc_scbapfind`; the exact configuration-field semantics
and Managed upstream support remain unverified. A relocation survey links the
separate CSI association initializer to `wlc_ap_scb_init` in both images.

AX58's enable path uses the lookup result without the null/state checks present
in AX56. An independent stdlib ELF/A32 check confirms this local guard difference,
not a runtime failure or the incident cause. The user's prior watchdog finding
remains separately attributed. No device probe or command-order workaround is
authorized by these results; both capture paths stay blocked.

The raw-reader contract now covers both radio-unit/protocol selections, full
2,064-byte datagrams, opaque/unvalidated type/sequence fields and consumed-ring
failure behavior. Details and limits are in REPEATER-CSI-RESEARCH.md. Evidence
and reproducible local helpers are in ignored
`recordings/managed-contract-20261014/`. Next: offline raw-storage/processing
implementation and failure tests, with GT retained as the validated baseline;
resolve the remaining peer/lifecycle gates before any repeater integration.

No application code, device state, deployment manifest, credentials or history
changed. No new dependencies, device connections or commits. This checkpoint
does not complete stage 2 or implement the planned forwarder/storage workers.

## Stage 2 started: exact-release NIC export evidence — October 13, 2026

PC-only inspection downloaded official AX56/AX58 firmware images and verified
both published image hashes. Both NIC modules contain CSI Netlink export code;
AX58 GPL target selection and 25 byte-identical CSI function bodies link the
previously missing NIC implementation evidence to the release image. Both
handlers reject command 5, so the shared ADD_AP constant is not a viable
command substitution. A separate struct-based ELF/A32 check confirmed this
narrow static finding. Details, caveats and the method matrix are in
REPEATER-CSI-RESEARCH.md; checks and tool limitations are in EXPERIMENTS.md.

The user reaffirmed off-router receipt/storage and decoding. RECORDING.md now
defines a minimal source-local forwarder, separate Pi raw storage, asynchronous
Pi/PC decoding and a downstream panel. This is a design, not a deployed new
collector. Next: ordinary ADD/Managed-mode contract and offline raw-pipeline
validation. No repeater record, location estimate, live safety result or
operational incident resolution is claimed. All device capture blocks and
deployment state are unchanged; no device connection or commit occurred.

The user requested complete documentation reading after an incomplete initial
overview. The documentation, including the full decoder report and OpenAPI
contract, was read in full; AGENTS.md already requires the initial review, so
no duplicate rule was added. Optional PC-only analysis dependencies are in
requirements-research.txt. Existing untracked SSH-diagnostic files were preserved.

## User watchdog report documented; stage 2 is next — October 13, 2026

The user supplied `dhd_watchdog_dos.zip` as their incident analysis and asked to
document it and move the roadmap forward. The archive contains one static
GT-AX11000/DHD report, with no hardware reproduction or supporting binary.
The user subsequently confirmed the cause using their own objdump and additional
analysis. Record the CSI/DHD watchdog failure as a user-confirmed causal finding;
the assistant has not inspected that full evidence. The report, hashes and the
earlier limited excerpt/source checks remain in `REPEATER-CSI-RESEARCH.md` with
clear chronology and attribution, not as a rejection of the user's analysis.

The documentary review milestone is complete. Stage 2,
per-repeater support classification and alternatives, is now next in
`NEXT-STEPS.md`; it was not started by this documentation task. Capture safeguards
and `incident.resolved: false` are unchanged. No device connection, overload,
driver patch, firmware change, history deletion or commit occurred. The original
user ZIP is preserved locally and ignored by Git. See `EXPERIMENTS.md` for the
local review checks. This update supersedes the earlier recommendation to keep
the missing NIC implementation as the sole next roadmap task; that gap remains
relevant to assessing blocked acquisition methods in stage 2.
The user prefers separate data acquisition as a mitigation and to improve
localization. The candidate design in `RECORDING.md` separates source streams,
raw storage and processing; initial link assessments are sequential, whereas
later combined estimates require measured alignment. Safety and accuracy are
acceptance criteria still to test, not proven effects of this architecture.

## RP-AX58 offline review checkpoint — October 13, 2026

The user selected milestone 1 (AX58 incident review), not the panel repair.
PC-only work found the exact ASUS GPL build, narrowed the missing NIC-driver
source/ABI evidence and repaired incremental SSH diagnostics, including bounded
exec acknowledgement. Eighteen diagnostic tests and the full 65-test Python
suite passed; a separate reviewer approved the code and A/B/C plan after fixes.
No device connections, changes, captures, commit or push occurred;
the deployment manifest is unchanged. See `EXPERIMENTS.md` for validation and
`REPEATER-CSI-RESEARCH.md` for source hashes, hypotheses and the A/B/C plan.

The reboot cause remains unknown. `incident.resolved` is still false and both
repeater capture paths remain disabled. Next work is the exact-build NIC
implementation/build-selection gap, with optional narrowly scoped read-only
library identification only if needed; do not repeat the failed probe. Source
constants and a local diagnostic fix do not close the operational safety gate.

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
