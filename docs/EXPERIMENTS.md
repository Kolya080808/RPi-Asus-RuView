# Experiments

## Ordinary ADD and reader contract — October 14–15, 2026

PC-only static inspection of the existing official AX56/AX58 `wl.ko` files,
using their previously recorded SHA-256 values. No new CSI records or device
connections. Mapping-aware disassembly covered six relevant functions per
module and surveyed their ELF relocation callers. This avoids the October 13
linear disassembler's stop at AX56 inline data. Both lookups can return zero;
AX56's enable consumer checks that result, while AX58's corresponding consumer
does not. A separate stdlib ELF/A32 reader verified dispatch targets, relocation
names, zero-return instructions, byte gates and the consumer guard difference.
It does not prove a live failure or identify the prior incident's cause.

The ordinary ADD/peer-mode findings, AP-named association caller, reader framing
and loss limitations are documented once in
[REPEATER-CSI-RESEARCH.md](REPEATER-CSI-RESEARCH.md#ordinary-add-and-reader-contract-2026-10-1415).
Managed upstream support, exact lookup field names, runtime lifecycle safety,
interface/unit mapping and repeater payload interpretation remain unverified.
No source is newly enabled or classified as operational.

Evidence/helpers: ignored `recordings/managed-contract-20261014/` (the start date).
Original public modules/images and private history were not modified. The first
post-disassembly search used a Windows wildcard path unsupported by `rg` and
failed; the corrected directory plus `-g '*.asm'` search succeeded. No evidence
was inferred from the failed search. The saved GPL inventory had no matching
`wlc_bsscfg.h`, `wlc_scb.h` or `wlc_scb.c` names, so field names are not asserted.

Validation:

- `.venv/Scripts/python.exe recordings/managed-contract-20261014/inspect_contract.py`
  passed both input-hash checks and emitted mapping-aware disassembly/callers.
- `.venv/Scripts/python.exe recordings/managed-contract-20261014/verify_contract.py`
  passed both independent opcode/branch checks. Its evidence scope is narrower
  than the complete research conclusion.
- `.venv/Scripts/python.exe -m py_compile recordings/managed-contract-20261014/inspect_contract.py recordings/managed-contract-20261014/verify_contract.py`
  passed.
- `.venv/Scripts/python.exe -m unittest discover -s tests -q` passed all 65
  tests in 8.683 seconds. Expected exceptions/logs came from simulated failure
  fixtures; printed cleanup messages are mock results, not device actions.
- `git diff --check` passed. Application code and dependencies are unchanged;
  UI tests, hardware checks and remote rollback commands were not run.

The next implementation checkpoint is the offline raw-storage/processing
boundary in RECORDING.md. Repeater deployment requires the remaining static
and operational safety gates plus a separately recorded reversible plan.

## Stage 2 exact-release firmware inspection — October 13, 2026

Scope: official public firmware downloads, the existing AX58 GPL archive,
saved panel report metadata and PC-only static analysis. No device connection,
monitor change, new capture, firmware execution, deployment or rollback action.
Per-image/module hashes, source URLs, method classification and limits are in
REPEATER-CSI-RESEARCH.md under the stage 2 checkpoint. Originals and inspection
helpers are retained in ignored `recordings/source-classification-20261013/`.

Both official firmware image hashes matched ASUS release descriptions; ZIP
CRC checks passed. AX56 rootfs traversal indexed 2,366 entries with zero bad
blocks reported; AX58 traversal indexed 2,521 entries. NIC sender functions
were found in both release modules. All 25 AX58 CSI function-body hashes match
the GPL prebuilt object. A second reader using only `struct` confirmed the
0..4 command dispatcher and -2 default return in each firmware module, separately
from the pyelftools/Capstone disassembly. This independently checks the narrow
static ADD_AP rejection, not runtime mode support or safe acquisition.

Tool limitations were retained rather than interpreted as device failures:
the AX56 whole-container listing hit a non-UBIFS volume, the CLI's Windows path
handling produced an empty root listing, and its official image has a 20-byte
erase-block remainder. Explicit volume selection and POSIX inode traversal
resolved listing. A false AX58 SquashFS magic match was rejected by the
superblock version check. Linear disassembly stops on inline data in two AX56
functions; conclusions are limited to verified code regions. No new sensor data
exists to validate payload decoding, timing, loss, station mode or localization.

The local inspection environment adds only the optional packages pinned in
requirements-research.txt. Existing application requirements and device software
are unchanged. The user's follow-up requires off-router receipt/storage and
decoding; the planned boundary and offline failure scenarios are in RECORDING.md.

Validation after installing the optional inspection dependencies:
`.venv/Scripts/python.exe -m pip check` reported no broken requirements;
`.venv/Scripts/python.exe recordings/source-classification-20261013/verify_static.py`
passed both command-dispatch checks and the 25-function AX58 comparison;
`.venv/Scripts/python.exe -m unittest discover -s tests -q` passed all 65 tests.
Expected failure-path logs came from local fixtures, including simulated storage
and SSH failures; cleanup messages do not represent device operations.
`git diff --check` passed. No application code changed in this checkpoint.
Device behavior, full raw acquisition and the proposed processing boundary
remain untested at runtime.

## User-supplied DHD watchdog report review — October 13, 2026

Input: `dhd_watchdog_dos.zip`, containing only `F-01-dhd-csimon-watchdog.txt`.
The user describes it as the incident explanation and asks to proceed to the
next roadmap stage after documentation. No reported trigger was executed.
The archive remains unchanged locally; hashes, claim-by-claim assessment and
the distinction between the GT/DHD report and the AX58 incident are in
`REPEATER-CSI-RESEARCH.md`, under the user-supplied watchdog report section.

Local checks found that both timer predicates are false for return `-40`;
replacing the operator cannot fix the proposed failure case. Eight representative
return/Boolean-flag combinations were evaluated and agreed, independently of
the Boolean-algebra argument. Matching AX58 GPL headers define `BCME_NODEVICE`
as `-40`; the inspected DHD watchdog uses logical `&&` and its conditional
file-output branch, not the described ring-overflow path, can return that code.
Those sources do not independently verify the report's different compiled GT
binary. The contemporaneous GT and AX56 uptimes also do not support a mesh-wide
reboot during the saved incident. Results and extracted header hashes are in
ignored `recordings/user-incident-review-20261013/`.

Initial outcome: the short report alone left causal links unverified. The user
then explicitly confirmed the incident cause based on objdump and additional
analysis. The current record therefore attributes the CSI/DHD watchdog cause
to the user's confirmed finding; the full binary evidence was not inspected by
the assistant. The preceding excerpt checks retain their limited scope and do
not substitute for reviewing that evidence. Documentary milestone 1 is complete;
stage 2 classification is next at the user's direction. The preference for
separate source acquisition and processing is in `RECORDING.md`, with safety and
localization benefits still requiring validation. Runtime capture/preparation blocks and the unresolved manifest
incident are unchanged. No device was contacted or changed, and no dynamic
reproduction, driver patch or new CSI capture was performed.

Validation: archive inventory/read and local predicate/source checks completed;
`git diff --check` passed. This follow-up changes documentation and the ignore
entry for the input archive only; application tests were not rerun. The earlier
65-test result below belongs to the preceding diagnostic-code task.

## RP-AX58 offline incident review and diagnostic repair — October 12–13, 2026

Scope was entirely on the PC: retained October 5 logs/ELF, public ASUS source
downloads and local SSH simulations. No router, repeater or Pi connection was
made; no CSI was captured, history removed, device state changed or rollback
executed. Operation `99256b673931` remains restored with an unresolved incident.

The ASUS **Others** download category supplied the exact GPL archive for
`3.0.0.4.388_24694`, including build suffix `g71d4ea1`. Its indexed 337,401
members include CSIMON headers and a DHD sender, but not the NIC
`wlc_csimon.c` implementation referenced by `wl.mk`. Shared constants agree
with parts of the retained collector, without proving installed-build safety.
The static ELF symbol comparison uses GPL toolchain libraries, not copies of
the installed libraries, and remains preliminary. Sources, hashes, search
scope, hypothesis table and the separately reviewed A/B/C test plan are in
[REPEATER-CSI-RESEARCH.md](REPEATER-CSI-RESEARCH.md), in the October 12–13 review.
Downloaded artifacts and comparison reports are retained locally under ignored
`recordings/ax58-review-20261012/`. No proprietary binaries or raw device logs
were added to Git or submitted to external services.

Two diagnostic failure mechanisms are distinguished from the reboot cause:
the old BufferedFile read could retain a short fragment on timeout, and Paramiko
exec acknowledgement could wait indefinitely despite the supplied channel
timeout. The new reader owns the channel before dispatch, drains both streams
incrementally, syncs each received chunk, bounds acknowledgement/output waiting,
and records incomplete outcomes instead of fabricating success or retrying.

Validation on 2026-10-13:

- `.venv/Scripts/python.exe -m unittest discover -s tests -p test_ssh_diagnostics.py -q`:
  18 passed. Direct Paramiko buffers and actual local SSH over socket pairs
  cover short/binary/no-newline output, channel close, transport loss, missing
  exec acknowledgement, missing exit status, late output, nonzero status,
  size limits, disk errors, fast-command dispatch races and stalled channel
  close. No lab device is involved.
- `.venv/Scripts/python.exe -m unittest discover -s tests -v`: 65 passed;
  full output is in the ignored evidence folder as `tests-final-20261013.txt`.
  The suite's printed capture-cleanup messages come from mocked rollback tests,
  not live device inspection.
- `git diff --check`: passed. No dependency or UI changes required JavaScript
  checks; no live rollback check was run.

A separate reviewer approved the A/B/C plan and final code after identifying
the unbounded exec acknowledgement and a fast-command completion race; both
were repaired and covered by regressions. The reviewer independently reran the
18 diagnostic tests and reported no remaining substantial findings. This is a
review of reasoning/code, not a new measurement of the AX58 incident. The local
rekey/close fallback test is synthetic; real device rekey behavior is untested.

These tests establish local output-preservation/error behavior, not recovery
of the missing incident bytes, elimination of radio reset risk or usable CSI.
Cause remains undetermined. The operational incident gate is still closed.

## RP-AX56 capability research — October 5, 2026

After the AX58 incident, the user requested a separate AX56 investigation.
Only authenticated read-only diagnostics were performed: model/firmware/kernel,
radio driver/revisions/modes, CSI state, associated links, program-file inventory,
boot messages, help and uptime. `HARDWARE.md` records the device-specific results.
No capture attempt was made. Final monitor state remained disabled/empty with
zero counters, and increasing uptime independently supports that this inspection
did not reboot the node. The existing capture block remains in force.

External check on the same date: the official
[ASUS RP-AX56 firmware page](https://www.asus.com/us/supportonly/rp-ax56/helpdesk_bios/)
and its public product API list installed release `3.0.0.4.386_51891`, dated
June 30, 2023. The release notes discuss AiMesh/GUI and security fixes; they do
not supply a CSI acquisition interface or establish compatibility with the
GT-AX11000 collector. The checked
[driver/download page](https://www.asus.com/us/supportonly/rp-ax56/helpdesk_download/)
and Linux 32/64-bit API results supplied no GPL/CSI collector package. This is
limited to those returned pages/categories, not proof that ASUS has no source
release or support information elsewhere. Page/API responses were retained in
the ignored local evidence folder; firmware was not downloaded or installed.

**Conclusion:** AX56 has a registered CSI subsystem, a different chip/driver
profile from AX58, and identified upstream radio links. There is still no
verified compatible userspace acquisition method or raw record. The lack of a
CSI-named executable and the presence of monitor commands do not settle whether
acquisition is possible. A repeat of the failed AX58 procedure would add network
risk without resolving the compatibility gap first.

Next research branches: seek vendor-provided exact-platform acquisition/format
documentation or matching source artifacts, and assess whether the already
working GT-AX11000 receiver can observe the AX56 peer as an additional radio
link. The latter would still be CSI received at the main router, not CSI exported
by AX56, and requires a separately reviewed experiment and rollback plan before
changing monitoring. Neither branch establishes triangulation or localization.

## RP-AX58 reboot during CSI feasibility probe — October 5, 2026

The user confirmed administrator password access to RP-AX58; the same credentials
also authenticated RP-AX56. Both devices reported ARMv7, disabled CSI monitors,
empty monitor peer lists and a kernel Netlink 23 endpoint. Associated upstream
links were identified separately for the two radios. These observations did not
establish a working capture API or binary compatibility.

A single RP-AX58 experiment, operation `99256b673931`, attempted the retained stock
GT-AX11000 collector on eth1 with a bounded eight-second observation. Local
checksum verification passed after the temporary upload; the rollback plan check
passed before execution. The SSH capture started around 19:10:38 Moscow time and
timed out at 19:11:03. The saved capture file contains zero bytes; no CSI record
was obtained. The reader requested 4096-byte chunks, so a timeout could discard
an internally buffered partial chunk. Consequently the empty file does not prove
the remote program emitted nothing, and the last completed remote step is unknown.

The user reported a likely node reboot and streaming interruption. At 19:14:04
Moscow time the node's uptime was 189.26 seconds, implying boot around 19:10:55
(approximate, subject to device clock synchronization). The current boot log says
`Last RESET due to SW reset`, reason `0x80000000`. Independently, the main router
logged node reconnection events after 19:11; its own uptime was about 512349 seconds,
and RP-AX56 uptime about 434250 seconds. The evidence establishes a recent AX58
reboot with strong temporal association to the probe, not a proven exact trigger.
No panic/oops trace explaining the reset was identified in the saved logs.
Watchdog/driver failure remains a hypothesis; a software-reset label alone does
not distinguish it from other reboot paths. Retrieved crashlog text includes boot
messages and must not be presented as a causal crash backtrace.

After reboot: both monitors disabled, no monitored peers or collector, temporary
file absent. This is recovery after reboot, not verified shell-trap cleanup.
The ignored deployment manifest stores initial state, file hash, final inspection
and the unresolved incident. Local raw diagnostic logs and filtered main-router
events are retained under `recordings/repeater-inspection-20261005/`.

Capture execution has been removed/disabled for both repeaters; no AX56 capture
was attempted. Next work is offline compatibility and incident analysis, with
read-only health checks as needed. Do not reproduce the failing probe on the live
mesh. Any future device experiment needs a separate reviewed plan and explicit
discussion of possible connectivity loss; a short duration does not bound driver
crash impact.

Local checks after disabling capture: `.venv/Scripts/python.exe -m unittest
discover -s tests -v` passed all 34 tests, including seven repeater safety tests.
`python scripts/rollback.py --repeater-only --check` passed against AX58 after
recovery, and `git diff --check` passed. These checks validate local safeguards
and the observed restored state, not firmware safety or a successful capture.

### Offline follow-up (same day; no device connections)

The saved main-router log places the first recorded AX58 deauthentication at
19:10:51 Moscow time, followed by disassociation at 19:10:52 and re-association
on one radio at 19:11:23. Together with the uptime-derived boot estimate this
narrows the disruption window, but neither source identifies the last completed
probe step. The final correctly dated pre-boot AX58 syslog line is an SSH login
at 19:07:27. There are no saved AX58 syslog entries for 19:10. This evidence gap
means absence of a panic, watchdog or collector message cannot exclude a failure
in any of those components. Post-boot watchdog firmware-check messages occur
after recovery and are not evidence that a firmware update caused this incident.

Static inspection of the retained collector found an ELF32 little-endian ARM
executable, 9,716 bytes, with interpreter `/lib/ld-linux.so.3`, dependencies
`libc.so.6` and `ld-linux.so.3`, and referenced symbol version `GLIBC_2.4`.
Embedded attributes name Cortex-A9; the compiler string reports GCC 5.5.0 from
Buildroot 2017.11.1. The previously saved repeater inspection reports ARMv7 and
both library paths exist. This rules out a simple claim that an AArch64-only
executable was copied to ARMv7, but does not verify library symbol versions,
instruction/ABI compatibility, or the driver/userspace CSI contract. No collector
startup output or successful receive was saved. Netlink endpoint numbering alone
does not fill that gap. The metadata agrees with the earlier retained strings
report, while neither source proves runtime compatibility.

The installed Paramiko source shows that `BufferedFile.read(4096)` accumulates
data until the requested size, EOF or an exception. An independent, local
in-memory stream test returned 39 diagnostic bytes and then raised a timeout:
zero bytes reached the caller, while all 39 remained inside its buffer. The old
capture loop did not flush that buffer on failure. This establishes a diagnostic
loss mechanism, not that 39 bytes (or any bytes) arrived during the real incident.
Artifacts `collector-elf-metadata.json` and `buffering-check.json` are retained
alongside the ignored incident logs. No live crash reproduction was performed.

**Assessment:** the reboot and its temporal association with the probe are
confirmed; a precise causal attribution to collector startup, monitor operation,
driver failure or watchdog action is not possible from the saved evidence.
Do not label this a proven ABI mismatch or a proven kernel panic. Before any
future live work, obtain authoritative compatibility information for the exact
firmware and assess a diagnostic path that preserves output during disconnects.
The next research can use offline vendor documentation or already obtained
firmware/source artifacts; it must not silently turn into a repeated live probe.

Local safeguards now also reject preparing a new operation while an incident
is unresolved. A restored operation cannot claim ownership of a later enabled
monitor, even when the peer happens to match. These changes preserve the incident
manifest and prevent stale rollback from affecting later device activity.

Follow-up validation: `.venv/Scripts/python.exe -m unittest discover -s tests -v`
passed all 36 tests (nine repeater safeguards); `git diff --check` passed. A scan
of tracked and non-ignored candidate files found one numeric substring match in
an existing hexadecimal illustration in `RESEARCH.md` (line 541), not a stored
credential. No other supplied-password matches or OpenSSH/RSA private-key headers
were found. Credentials, deployment state, raw
incident logs and the proprietary binary remain ignored. This is a targeted
current-file check, not an audit of all historical commits or all possible secrets.

## Format capture

GT-AX11000, eth6, monitored peer `A0:36:BC:9B:BF:89`, channel 4, interval
500 ms: 16 records. A second check at 100 ms: 98 records. In both cases,
the dynamic words occupy bytes `0x60..0x13f`, and the tail alternates between
two values. In the second capture, the driver reported 99 transfers, 1 ACK
failure, and 0 overflows; 98 records were saved.

## Motion test

Session `a184adec-4489-4322-996e-41b059851ed4`, 60 seconds, 592 records.
One person stood in the long room, then waved both arms, then stood still again.
According to the user, no other people were moving. Median change in
normalized amplitude: 0.0189 initially, 0.1316 during motion, 0.0181 afterward.
The interval with high change was approximately 13.0–38.6 s. Chat commands were not
synchronized with the recording clock, so the boundaries are approximate.

## Position test

Session `60d03eaf-0351-4b28-ad17-d169bc5f2ac1`, 60 seconds, 595 records.
Three coarse segments: near the router, the middle of the room, and the far end.
Estimated median RMS amplitudes: 1586, 1545, and 1527 raw units. Distances
between mean normalized profiles: 0.597, 0.759, and 0.315. Transitions
between positions fall within the windows, and annotations were made through chat commands.
The result shows sensitivity to scene position, but does not provide a person's
coordinates and is not a trained room classifier.

## Confounded test

The first session, `c2cd2e65-6601-4b07-be59-2bb2a41773c3`, includes the user's father
moving in the same room throughout the recording. It is retained as a collection check,
but is not used to draw conclusions about the user's hand movements.

## Planned localization validation protocol

Moved from NEXT-STEPS on 2026-10-06; no new experiment results are implied.

### 5. Collect a small repeatable dataset

Start with points in R08, R07, and R02 after the user selects their exact locations.
Use separate bounded sessions and repeat each condition:

- Stillness and arm movement at a fixed point.
- Walking between marked points, including stops and changes of direction.
- An empty apartment/room baseline with the user's exit interval labeled.
- Motion elsewhere in the apartment to test cross-room confusion.

Record other occupants, doors, facing direction, changed furniture/devices, and
unusual network activity. Vary route order, speed, and stops. Keep whole later
sessions, preferably from another day, out of threshold/model tuning. Neighboring
frames from one recording must not be split randomly into train and test sets.

Done when recordings and labels can be replayed and independently checked,
including transitions and uncertain intervals.

### 6. Evaluate simple location estimates before expanding scope

First compare room/zone classification against simple baselines on held-out
sessions. Report confusion between zones, false motion events per hour, missed
motion, detection delay, and the fraction of time with insufficient data.
If testing continuous positions later, report distance errors and uncertainty.
The runtime predictor must not receive the test's reference route or cue sequence.

Use the earlier repeater feasibility results when choosing the sensing sources.
If observations do not distinguish zones reliably, investigate additional
supported peer links on the ASUS or revisit the documented repeater blockers.
Identify the current monitored peer before treating its link as a
known path on the map. Device placement does not establish a working sensor.
