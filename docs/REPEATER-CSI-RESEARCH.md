# Repeater CSI research and acquisition options

Updated 2026-10-15 with ordinary ADD, peer lookup and raw-reader contract inspection.
This document distinguishes measured facts from proposed designs.
The submitted file was named `deep-research-report.md`; its findings are retained
here with claims narrowed to the evidence available in the repository.

## Executive finding

October 16 update: [stock network exporter comparison](NETWORK-CSI-EXPORT.md)
completed for both AX58 and AX56. No validated direct IP/port CSI export setting
was identified. RemoteWL is a remote-command interface; it was not demonstrated
to forward CSI. AX56's installed module hash now matches the retained binary.
The shared source-local reader remains a candidate, with per-device runtime,
activation and payload validation still required.

Stage 2 has now started. The [static classification below](#stage-2-static-source-classification-2026-10-13)
finds NIC-side CSI Netlink export code in both exact-release firmware images,
but no standalone collector or validated acquisition in the observed Managed
mode. No device was contacted. The user's separate-acquisition/off-router
decoding direction is retained in [RECORDING.md](RECORDING.md).

The [October 14–15 continuation](#ordinary-add-and-reader-contract-2026-10-1415)
finds that ADD can succeed without activating a peer timer. Both modules use
`wlc_scbapfind`; AX58's enable path consumes its return without a null guard,
unlike AX56. This is a static safety concern, not a reproduced failure or a
replacement for the user's incident finding. Managed upstream-peer capture is
still unvalidated; keep both capture blocks in place.

Both RP-AX56 and RP-AX58 advertise `csimon`, and boot diagnostics show the
Broadcom CSIMON module initializing. This makes repeater-side CSI an avenue to
investigate. It does **not** demonstrate that the kernel is producing usable CSI,
that the firmware exposes it to a userspace reader, or that a collector can decode
it. No raw CSI record has been acquired from either repeater.

The only confirmed acquisition profile remains the GT-AX11000 on `eth6`. Its
retained `csimond` executable uses Netlink protocol 23 and prints Netlink data,
but its successful use on that router does not establish compatibility with either
repeater's different kernel, driver, hardware profile or CSI API.

The user's proposed architecture—repeater radio measures CSI, Raspberry Pi
collects/stores/processes it, then the panel replays it—is plausible as a design
goal. Netlink is local to a device kernel, so Pi software cannot directly open a
repeater's Netlink socket over the network. A repeater-side collector would need
to read the local kernel interface and forward framed raw data to the Pi, or an
already-supported network API would need to be found. The repeater is the proposed
radio measurement point; the Pi is the collector/processor unless its own radio's
CSI capability is separately demonstrated.

## Observations

### RP-AX56

- On 2026-10-05, read-only inspection identified firmware
  `3.0.0.4.386_51891-g12b4ca4`, Linux 4.1.52, ARMv7, Broadcom chip name 6755,
  and driver `17.10.157.2809`.
- `eth1` and `eth2` advertised `csimon`; the kernel boot log reported CSIMON
  1.1.0 initialization. Both monitors were disabled, peer lists empty and
  transfer/error counters zero.
- `/proc/net/netlink` included an entry for protocol 23 with port ID 0. This is
  an observation of a socket entry, **not** proof that CSI messages are emitted
  or that a userspace listener is available. Linux Netlink documentation
  describes port IDs and message formats, but the Broadcom protocol payload and
  behavior remain undocumented here.
- Both inspected interfaces operated in `Managed` mode, associated upstream to
  the main router. A search of standard executable directories found no filename
  containing `csi`; this bounded search does not prove that no relevant code
  exists elsewhere or inside another executable.
- Uptime increased during inspection. No file was uploaded, no collector run,
  no monitor enabled and no CSI captured.

### RP-AX58

- On 2026-10-05, read-only inspection identified firmware
  `3.0.0.4.388_24694-g71d4ea1`, ARMv7 and Broadcom driver `17.10.188.6401`.
- Both inspected radios advertised `csimon`; monitors were disabled and their
  peer lists empty before the probe. No persistent standalone `csimond` was
  found in the checked locations.
- One probe uploaded the retained GT-AX11000 `csimond` binary to a temporary
  `/tmp/ruview-csimond-<operation>` path and attempted an eight-second run with
  CSI monitoring. The node rebooted in the same time window. No CSI record was
  saved and the last completed remote step is unknown. This is a serious safety
  signal, not proof whether the collector, monitor, their interaction, or another
  event caused the reset. Both capture scripts remain disabled while the
  incident is unresolved. See [EXPERIMENTS.md](EXPERIMENTS.md) and
  [ROLLBACK.md](ROLLBACK.md).

### GT-AX11000 collector

The retained executable is a 9,716-byte ARM32 ELF using `/lib/ld-linux.so.3`
and `libc.so.6`; strings and disassembly show a Netlink socket and `recvmsg()`.
These static observations explain the broad purpose of the utility, but do not
document its full message framing, validate its binary against repeater firmware,
or prove which kernel events it expects. The October 12 GPL inspection below
provides some matching-build interface constants, but no runtime proof.
Netlink messages can have protocol-
specific headers and payloads; the generic Linux format is not a substitute for
the Broadcom CSI contract.

## Review of claims in the submitted draft

| Submitted claim | Evidence-based status |
|---|---|
| CSIMON initialization and Netlink 23 prove repeaters export CSI to userspace. | Not established. Module initialization and a protocol-23 `/proc/net/netlink` entry do not show a CSI payload, supported subscriber or working userspace API. |
| The GT-AX11000 `csimond` is compatible with the repeaters because all are ARM. | Not established. AX56/AX58 have different chips, driver/kernel builds and firmware profiles. The AX58 attempt coincided with a reboot. Matching architecture alone is insufficient. |
| The main router already records CSI from forwarded AX56 backhaul frames. | Not established. Association and channel observations show a link, not that the current `eth6` monitor captures those frames. The confirmed collection used a specifically configured peer on `eth6`; backhaul peer capture and other radio interfaces need their own evidence. |
| Two such CSI streams are compatible with triangulation or will improve location accuracy. | Hypothesis. Distinct, useful links, synchronization, geometry and held-out reference-position results have not been demonstrated. |
| A short probe bounds the risk of a repeater test. | Incorrect. The AX58 reboot shows that a short operation can still interrupt the mesh. No repeat of the failed probe is planned. |

The official [Linux Netlink introduction](https://docs.kernel.org/6.1/userspace-api/netlink/intro.html)
describes Netlink as a socket interface with protocol-specific message contents,
headers and payloads. It cannot confirm proprietary Broadcom CSI behavior. ASUS's
[RP-AX56 firmware page](https://www.asus.com/us/supportonly/rp-ax56/helpdesk_bios/)
lists the installed release; it does not specify a CSI userspace API. The checked
[ASUS RP-AX56 downloads page](https://www.asus.com/us/supportonly/rp-ax56/helpdesk_download/)
did not return a CSI collector or protocol specification in the categories
examined. This search is limited to those pages and is not proof that no other
vendor source or support material exists.

## Candidate architecture: repeater measurement, Pi processing

If an exact repeater firmware supports CSI export, the candidate data path is:

```mermaid
flowchart LR
    RF[Repeater radio and supported CSI interface] --> RC[Bounded local repeater collector]
    RC -->|framed raw samples over the home LAN| PI[Raspberry Pi: receive and retain raw data]
    PI --> DEC[Profile-specific decode and signal processing]
    DEC --> PANEL[Panel replay, map and reference labels]
```

Keep received CSI bytes unchanged on the Pi before decoding; attach device, radio,
peer, firmware, sequence, receive-time and drop/error metadata. Processed signal
features and eventual predictions should be reproducible from retained raw input.
The panel should distinguish a repeater-originated capture from the established
GT-AX11000 profile. Do not merge the records or reuse its decoder until the
format is validated independently.

Before choosing this path, establish from documentation or safe offline analysis
whether a local repeater reader can receive CSI at all, the message format and
buffer/drop behavior, and whether a bounded process can run without destabilizing
AiMesh. Then estimate Pi CPU, memory, storage and network load with local replay
of representative data. The Pi's current role as history server does not prove
that it can be an independent CSI radio source.

## Separate candidate: capture the backhaul at the main router

The observed AX56 upstream association makes its backhaul an interesting link to
study. CSI measured at the GT-AX11000 for frames from a repeater would still be a
main-router measurement, not CSI exported by the repeater. First prove that a
supported GT radio/interface can monitor the exact peer and produce records
attributed to it; the existing eth6 result does not prove that any other
interface or peer works. This path also does not automatically provide a second
spatially independent sensor, triangulation or improved localization.

Any later live evaluation needs a distinct plan that preserves initial monitor,
peer, process and service state, and a tested exact-scope rollback. Do not revive
the AX58 probe as part of this plan. A proposed collection path is not approval
to execute it.

## Next research and acceptance criteria

1. Check vendor or already available source materials for these exact models and
   firmware builds. Record a source and the exact supported interface; do not
   infer availability from `csimon`, module loading or protocol number alone.
2. Analyze any candidate receiver offline first. The illustrative C snippet in
   the submitted draft was only a sketch: it assumes message framing and omits
   robust truncation, drop detection, bounded shutdown and forwarding. It is not
   an implementation to upload or run.
3. Keep AX58 capture disabled during incident review. No AX56 collector has been
   run. Before any new device-side experiment, follow the device inventory and
   rollback rules in [AGENTS.md](../AGENTS.md) and [ROLLBACK.md](ROLLBACK.md).
4. Call repeater acquisition demonstrated only after raw records are repeatedly
   received with their source identified, timing/cadence measured, drops and
   errors reported, raw data retained, and device state verified after stop.
5. Call the source suitable for localization only after synchronized reference-
   point experiments and evaluation on held-out sessions. Call triangulation
   feasible only after showing the actual path geometry and independent
   information in the measurements.

## RP-AX58 incident review and exact-build evidence (2026-10-12–13)

Scope: PC-only analysis of operation `99256b673931`, saved October 5 evidence,
public ASUS downloads, and synthetic SSH failures. No device connection, probe,
collector execution, firmware installation or remote state change occurred.
The incident remains unresolved; local restoration is not evidence of safe CSI
acquisition. `deployment.json` retains `incident.resolved: false`.

### Compatibility findings

The saved device identity is RP-AX58 `3.0.0.4.388_24694-g71d4ea1`, Linux
4.19.183, ARMv7, Broadcom driver `17.10.188.6401 (r808804)`. The saved boot log
names GCC 9.2.0 / Buildroot 2019.11.1. The retained GT collector is ARM32 EABI,
requires `GLIBC_2.4` and `/lib/ld-linux.so.3`, and was built with GCC 5.5.0 /
Buildroot 2017.11.1. Different compiler versions alone do not prove an ABI fault.

The official [ASUS firmware listing](https://www.asus.com/us/supportonly/rp-ax58/helpdesk_bios/)
lists release `3.0.0.4.388_24694` dated 2024-12-09. Its notes do not specify CSI
compatibility. On the [ASUS downloads page](https://www.asus.com/us/supportonly/rp-ax58/helpdesk_download/),
selecting **Others** (OS ID 8) exposes **Source Code**, version
`3.0.0.4.388_24694`, dated 2024-12-17. This is a positive source discovery;
absence from the Windows utility category is not absence of GPL materials.

The [official GPL ZIP](https://dlcdnets.asus.com/pub/ASUS/wireless/RP-AX58/GPL_RP_AX58_300438824694.zip)
was downloaded to ignored local evidence, never executed. It contains
`GPL_RP-AX58_3.0.0.4.388.24694-g71d4ea1.tgz`: the suffix agrees with the saved
device build. ZIP size is 1,730,933,042 bytes; locally computed SHA-256 is
`a0a34f519cf620ff04189e9fac3bc0e7e6c770a80003a5ba968cddd2d03f691f`.
The ZIP CRC was checked and all 337,401 tar member entries were indexed without
installing or unpacking the full tree. The SHA identifies this local download;
ASUS's returned GPL entry supplied no publisher SHA-256 for comparison.

Within `asuswrt/release/src-rt-5.04axhnd.675x/bcmdrivers/broadcom/net/wl/impl87/`:

- `sys/src/include/bcm_csimon.h` declares CSIMON 1.1.0, maximum ring element
  2048 bytes, 32 ring elements, radio-specific Netlink IDs 23/22/24 and multicast
  group constant 2. The CSIMON version agrees with the independently saved
  boot messages. A constant does not prove that the installed build uses that
  branch, or which radio/interface maps to it.
- `sys/components/wlioctl/include/wlioctl.h` (also in `main/`) declares
  configuration/counter version 1 and a distinct `CSIMON_CFG_CMD_ADD_AP` command.
  This raises an explicit station-mode versus AP-mode compatibility question;
  it does not authorize substituting a different command on the live repeater.
- The shared header describes an extra guard region around the host-memory CSI
  ring as a workaround for memory corruption under investigation. This is a
  source-level risk clue, **not** a diagnosis of the AX58 reboot: applicability
  to its actual driver path and the failure signature are unverified.

The main-router collector's saved disassembly sets the Netlink subscription
mask to 2 and allocates `0x810` bytes (2048 plus 16). These constants are
consistent with the header. That is a static consistency check, not validation
of Netlink framing, receive lengths, ABI loading, radio mode or firmware safety.
No raw AX58 CSI exists to validate its format or reuse the GT decoder.

A bounded content search examined 3,555 regular `.c`, `.h`, `.mk` and `Makefile*`
files of at most 2 MiB under `impl87`, yielding 243 matching lines. The full
archive member index contains only one filename with `csimon` in it: the shared
header. `main/src/wl/config/wl.mk:3187–3193` conditionally adds `wlc_csimon.c`
and `BCM_CSIMON_AP`, but that implementation file is absent from this archive.
`sys/src/dhd/sys/dhd_msgbuf.c:1303–1345` does include a DHD Netlink sender and
framing code. That is a different driver path; its presence cannot establish
the missing NIC `wlc_csimon` implementation, active build flags, or safe use of
ADD/AP commands on this device. This is the concrete remaining source gap.

An offline ELF32 symbol/version-table comparison found all 18 strong imported
name/version pairs of the retained collector in the combined ARM libc/loader
exports from the GPL toolchains; all inspected ELF flags were `0x5000200`.
This preliminary check weakens a simple missing-GLIBC-symbol explanation, but
the toolchain libraries are not authenticated copies of the installed files
(even their sizes differ). No external ELF parser cross-check or runtime loader
test was performed. `elf-static-comparison.json` retains the exact symbol list
and library filenames; this result does not establish device ABI compatibility.

### Causal assessment

| Explanation | Evidence and limits | What would discriminate it |
|---|---|---|
| Monitor/driver failure | Probe and reboot overlap; no saved marker proves monitor enable completed. Shared-header guard comment is not a crash trace. | Applicable driver implementation/build flags and an existing pre-reset trace; no live reproduction. |
| Collector/subscription interaction | Collector was uploaded; ARM class, some Netlink constants agree. Successful startup/receive and runtime library versions remain unobserved. | Static symbol/ABI and exact driver subscription-path review; matching image artifacts, not execution. |
| Unsupported station-mode configuration | Saved AX58 radios were Managed; headers distinguish ADD and ADD_AP. Their exact semantics/build support have not been established. | Relevant `wl` parser and driver command-handler implementation for this build. |
| Watchdog or another software reboot path | Boot log reports SW reset `0x80000000`; this does not identify the initiating component. | Existing watchdog/reset-owner trace from the incident window. |
| Unrelated reboot | Cannot be ruled out; temporal association alone is not causality. | Independently dated reset request/event or other contemporaneous evidence. |

Uptime-derived boot time around 19:10:55 Moscow and GT association events
(first deauthentication 19:10:51, reassociation 19:11:23) independently support
the reboot/disruption. AX58's correctly dated pre-boot log ends at 19:07:27;
there is no saved per-step record for the probe. The eight-second intended
capture does not identify which stage was reached before SSH timed out.
No evidence-supported ranking selects one cause above the others.

### Separately reviewed next-test plan

This plan is a research/diagnostics checkpoint, **not approval to resume CSI
acquisition**. Capture remains disabled on AX58 and AX56; new preparation stays
blocked. Do not set the incident resolved merely because this review is written.

**A. PC-only tests and static follow-up (permitted in this task).** Exercise the
SSH reader with real local SSH channels: small/no-newline stdout and stderr,
disconnect, missing exec acknowledgement, absent exit status, delayed tail,
nonzero exit, output cap and disk failure. Verify exact saved bytes, incomplete
status and no retries. Continue static GPL analysis of station/AP configuration,
radio-to-Netlink mapping and build selection, concentrating on the missing NIC
implementation or matching compiled artifacts rather than treating DHD as a
substitute. A loader/symbol audit
may use an official matching image offline; do not run its ARM programs.

**B. Optional read-only device inventory (not executed here).** Use only the
existing pinned AX58 login, one connection, no retries, and one command at a
time. No Pi is needed. Before execution, review this exact allowlist and confirm
that fresh inventory would fill a specific remaining evidence gap:

1. `nvram get productid`, `nvram get firmver`, `nvram get buildno`,
   `nvram get extendno`, `uname -r`, `uname -m` — verify against the saved build;
   stop on any mismatch before further diagnostics.
2. `cat /proc/uptime`, `cat /proc/sys/kernel/random/boot_id` — initial state.
3. `ls -l /lib/ld-linux.so.3 /lib/libc.so.6`,
   `sha256sum /lib/ld-linux.so.3 /lib/libc.so.6` — identify exact on-device files
   for comparison with official offline artifacts, without executing them.
4. `cat /proc/net/netlink` — snapshot existing sockets only, no new Netlink socket.
5. Repeat uptime and boot ID; require unchanged boot ID and increasing uptime.

Use the journaled reader with a 10-second network-wait budget and 256 KiB total output per command,
an overall 150-second session limit, and stop at the first nonzero status,
deadline, incomplete output or disconnect. Preserve the last acknowledged step
and unknown remote outcome. Do not reconnect automatically, interpret SSH loss
as proof of reboot, or send recovery commands. Closing SSH does not prove that
a dispatched remote command has terminated.
Use a dedicated client: a stalled channel close shuts down its transport
locally. Budgets do not impose hard real-time bounds on local disk I/O or
thread scheduling. The 150-second session limit must prevent dispatch of
another command after expiry; it is not a claim that device cleanup occurred.

There are no uploads, remote temporary files, background processes, `wl` calls,
CSI controls, collector starts, settings, service changes or log clearing in B.
Do not use `--prepare`, `--capture` or automatic `rollback --repeater-only` for
this read-only plan: the latter's inspection calls `wl`. Restoration is closing
the SSH session; preserve normal device audit logs/counters. If any mutation
becomes necessary, stop and write a separate exact-file/process/settings plan
and verified rollback before execution. Existing incident evidence is never
overwritten or deleted. A fresh inventory cannot reconstruct the lost 2026-10-05
failure window and cannot by itself establish safe CSI capture.

**C. Acquisition remains blocked.** Require an exact-build compatible reader and
driver/mode contract, an explicit review of remaining reset risk, and a distinct
user-reviewed experiment with manifest baseline, rollback implementation and
preflight verification. Neither the failed eight-second probe nor an add/enable
variant is part of A or B. Short duration does not bound a driver crash.

Review result and local test results are recorded in `EXPERIMENTS.md`. The
reviewer is a reasoning check, not an independent measurement of the device.
All downloaded source, extracted snippets, hashes and public API responses are
under ignored `recordings/ax58-review-20261012/`; earlier private incident
evidence remains under `recordings/repeater-inspection-20261005/`.

## User-supplied watchdog report and roadmap decision (2026-10-13)

The user supplied `dhd_watchdog_dos.zip`, described it as their explanation of
the incident, and requested documentation followed by the next roadmap stage.
The archive contains one 1,893-byte text report,
`F-01-dhd-csimon-watchdog.txt`; no executable, `dhd.ko`, full disassembly or
additional device logs were supplied. The original ZIP is preserved unchanged
and ignored by Git. ZIP SHA-256:
`9ab5a388aa4c036057184958c9b19b4f126e1fe79d748868a8b7747d1834e062`;
report SHA-256:
`11b0f8c711449e57c758d62f289290f592b3ecc8ab8d1153955cda17bcdd4dc6`.

**Author's explanation.** The report describes GT-AX11000 firmware
`3.0.0.4.388_24548` and an alleged DHD watchdog-timer defect. Its proposed
sequence is CSI-ring overflow, return `-0x28`, skipped timer restart, dongle
trap and emergency reboot, followed by AiMesh-wide disruption. It attributes
the condition to bitwise `&` instead of logical `&&` and suggests replacing
that operator and/or explicitly handling the return code. The author labels
this static RCA, explicitly not dynamically reproduced. Its broader-device
scope, vulnerability classification and severity estimate are author claims,
not verified project results. The proposed overload trigger was not executed
and is not adopted as an experiment or reproduced as operating instructions.

**Initial review of the short report and saved sources, before the user's
follow-up confirmation.** The checks below concern only the supplied excerpt
and inspected AX58 GPL files. They do not review or refute the user's additional
objdump/binary analysis, which was not included in the ZIP.

| Claim | Check and conclusion |
|---|---|
| Replacing `&` with `&&` restarts the timer for return `-0x28`. | In the supplied expression, the left operand is `(ret != -40)`. When `ret == -40` it is false: both `false & flag` and `false && flag` are false for every flag value. For Boolean flags 0/1 the two predicates agree for every return value. The operator replacement alone does not fix the described case. A non-Boolean flag could cause other differences, but no such value was supplied. |
| `-0x28` denotes CSI-ring overflow. | AX58 GPL `impl87/{main,sys}/src/include/bcmutils.h:428` defines `BCME_NODEVICE` as `-40`, meaning device absent. The inspected DHD `dhd_csimon_watchdog()` returns that value under the conditional file-output branch after repeated file-open failures. Netlink-send errors increment drop counters and the function returns `BCME_OK`; the report's overflow-to-`-40` path was not found in this source. This does not prove what a different compiled GT binary does. |
| The watchdog condition in our source has the erroneous operator. | AX58 GPL `sys/src/dhd/sys/dhd_linux.c:7444–7445` already uses logical `&&` with `csimon_ret != BCME_NODEVICE`. A decompiler may express a Boolean conjunction as a bitwise operation; that alone does not establish an erroneous source operator. The report's GT binary/disassembly is not included for independent verification. |
| This identifies the October 5 AX58 reset. | The report analyzes GT-AX11000/DHD, while the incident target was RP-AX58 `24694-g71d4ea1`. The active AX58 driver-path/build mapping remains unproven. The saved probe used one peer and a 500 ms interval, unlike the report's proposed overload scenario. There is no saved trap trace or last-step marker connecting the proposed sequence to the incident. |
| The main router and entire mesh rebooted in this incident. | The contemporaneous GT uptime was approximately 512,349 seconds and AX56 uptime approximately 434,250 seconds. These independent observations support an AX58-local reset with a connectivity/streaming interruption, not a confirmed mesh-wide reboot. A future wider failure remains a separate untested possibility. |

The predicate check was evaluated locally over representative return values
`-40`, `-1`, `0`, `1` and flags `0`, `1`; all eight cases agreed. The general
`ret == -40` result also follows directly from Boolean algebra and does not
depend on hardware. Header definitions and code branches provide a separate
source-level check. Extracted header hashes and the predicate results are in
ignored `recordings/user-incident-review-20261013/`. No hardware test, overload,
firmware patch or driver execution occurred.

**User confirmation and current decision.** Later on October 13, the user
explicitly confirmed that this is the incident cause and that they proved it
with objdump and additional tools. The project records the CSI/DHD watchdog
failure as the **user-confirmed causal finding** and proceeds on that planning
basis. The assistant has not inspected the full supporting binary analysis;
the exact operator/return-code interpretation in the short excerpt remains
unreconciled with the limited checks above. This is an evidence-provenance
distinction, not a request to reopen the same documentary milestone or repeat
the incident. No further claim that all nodes actually rebooted is inferred
from the user confirmation; the saved uptimes remain part of the record.

The user also prefers separate acquisition, both as a proposed mitigation and
to improve position estimation. The design decision is recorded in
`RECORDING.md`: separate source streams and raw storage, acquisition separated
from processing/panel work, initial single-link assessments, followed by
time-aligned multi-link evaluation only when supported. Its safety and accuracy
benefits require their own measurements. Moving processing to the Pi alone
does not establish that the on-device CSI/watchdog path is safe.

Documentary milestone 1 is complete; stage 2, per-repeater support classification
and selection of a safe acquisition architecture, is next. Repeater capture and
preparation safeguards remain unchanged pending a separately validated method.
The old manifest's `incident.resolved: false` is retained as an operational
safety block; this task does not reinterpret it as rejecting the user's causal
finding or automatically clear it. No driver patch, device-side experiment or
new simultaneous capture is performed by this documentation decision.

## Evidence locations

Device snapshots, returned ASUS support-page data, ELF metadata and incident logs
were retained under ignored local `recordings/repeater-inspection-20261005/`.
The probe's operation manifest and exact post-reboot state are in ignored
`deployment.json`. These local artifacts are not part of the Git report; where a
claim depends on them, the text above states the observed result and its limit.

## Stage 2 static source classification (2026-10-13)

This checkpoint examines official files on the PC. It does not repeat the
incident, enable monitoring, establish live compatibility, or clear the capture
blocks. The user-confirmed incident cause remains attributed as above. The
question here is which implementation can supply a separate raw stream.

### Exact-release artifacts and extraction

The ASUS RP-AX56 product API returned no drivers for Others (OS 8), Linux 32-bit
(39), or Linux 64-bit (5). Its OS list did not advertise Others. This bounded
catalog search found no GPL package; it does not prove that none exists.
The [official AX56 firmware](https://dlcdnets.asus.com/pub/ASUS/wireless/RP-AX56/FW_RP_AX56_300438651891.zip)
contains `RP-AX56_3.0.0.4_386_51891-g12b4ca4_pureubi.w`, matching the recorded
device release and suffix. The
[official AX58 firmware](https://dlcdnets.asus.com/pub/ASUS/wireless/RP-AX58/FW_RP_AX58_300438824694.zip)
contains `RP-AX58_3.0.0.4_388_24694-g71d4ea1_nand_squashfs.pkgtb`.
Both unpacked images matched the SHA-256 published in ASUS release descriptions:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| AX56 firmware image | 47,317,012 | `34e82526187b6c6bd0d81976b05f0999d0c2a38a4fca7a3d446418e7ffc06ef9` |
| AX58 firmware image | 36,157,344 | `701d40a64c37fc032ff3bb906dc4e02f182f83d80b1b7664dfb5e077724c8542` |
| AX56 `/lib/modules/4.1.52/extra/wl.ko` | 6,910,228 | `b82ffa419ce4d6910941ca3ed38cac5ded006f698d94a6d223f427fc5847f5ef` |
| AX58 `/lib/modules/4.19.183/extra/wl.ko` | 9,680,356 | `dabb2f7e716d63f4ffa9163773b7f87c15050cb442d021db528194f0b25e68a8` |

AX56 UBI volumes were separated before inspecting only `rootfs_ubifs`:
2,366 directory entries, zero bad blocks reported by the UBIFS index walker.
The official container has a 20-byte remainder beyond whole erase blocks;
UBI Reader warns about alignment. Its whole-image file lister initially tried
a non-UBIFS volume and failed. Listing the extracted rootfs through its CLI
also returned nothing because Windows `PurePath` treated `/` as `\\`.
The retained helper traverses inode directory entries directly with POSIX paths;
it does not suppress corrupt-block errors. No firmware files were executed.

AX58 contains a SquashFS 4.0 rootfs at image offset 10,135,456, with
26,020,498 used bytes and 2,521 directory entries beneath the root. An earlier
`hsqs` byte match at offset 86,020 fails superblock validation and was not used.
Neither indexed rootfs contains a filename with `csimon`, or a `dhd.ko` file.
This excludes a standalone file with that name in these images, not functionality
embedded in another executable or a different boot-time component.

### NIC implementation and the export contract

Both firmware `wl.ko` files are ARM32 relocatable ELF with symbol tables and
25 `wlc_csimon_*` functions. Driver strings and kernel vermagic agree with the
saved device inventory: AX56 `17.10.157.2809 (r801046) 12b4ca4` / 4.1.52;
AX58 `17.10.188.6401 (r808804)` / 4.19.183. This is a release-artifact match;
the installed module hashes were not read from either live device.

The AX58 GPL target `targets/96756GW/96756GW.RP-AX58` explicitly selects
`BRCM_CHIP=6756`, `BUILD_HND_NIC=y`, `BCM_WLIMPL=87`, and leaves
`BRCM_DRIVER_DHD` unset. Its `router-sysdep/hnd_extra/prebuilt/wl.o` has
byte-identical bodies for all 25 CSI functions compared with the official
firmware `wl.ko`; the GPL `wl` executable also matches the firmware copy exactly.
This closes the earlier *availability of NIC implementation evidence* gap for
static analysis, although the C source `wlc_csimon.c` remains absent. It does
not establish every runtime build condition or revise the user's incident finding.

In both firmware modules, ELF relocations connect `wlc_csimon_attach` to
`__netlink_kernel_create` and `wlc_csimon_wd_timer` to `netlink_broadcast`.
The examined sender copies `0x800` (2,048) bytes into a buffer of `0x810`
(2,064) bytes, after a 16-byte header, and broadcasts to group 2. In the
AX58 attach function, internal radio unit 0 selects protocol 23, unit 1 selects
22, and the remaining branch selects 24. These are static code observations;
mapping a Linux interface to the internal unit still requires evidence.
Do not infer the measured CSI layout, reliable Netlink sequence numbers,
losslessness, or GT decoder compatibility from these transport constants.

There is also a concrete limit on configuration commands. The AX58 shared
header declares `CSIMON_CFG_CMD_ADD_AP=5`, but **both examined firmware handlers
dispatch only values 0 through 4**. Once version/length checks pass, value 5
takes the default branch and returns -2. Thus, an ADD_AP-based workaround is
not supported by these binaries. This does not prove that the ordinary ADD
operation cannot work in Managed mode; its peer lookup and radio-mode
requirements still need analysis.

The narrow dispatch finding was cross-checked without pyelftools or Capstone:
a second reader parsed ELF32 sections with Python `struct`, checked the A32
words `e3530004` (CMP r3,#4), `979ff103` (conditional jump table), decoded the
default branch displacement, and found `e3e06001` (return value -2).
AX56 `.text` offsets are `0x202654` and `0x202c00`; AX58 offsets are
`0x2b5138` and `0x2b5770`. This independently checks a static conclusion, not
safe runtime acquisition. Linear disassembly stops at inline data in two
AX56 functions; it is not a complete control-flow audit. The command gate
precedes that data, and the separate check reads its default target directly.

### Method classification and next gate

| Device/method | Current evidence level | Remaining gate / disposition |
|---|---|---|
| AX56 local NIC Netlink reader, raw forwarding to Pi | Export code established in the exact-release image; no live records | Candidate. Establish ordinary ADD semantics in Managed mode, unit/interface mapping, compatible reader ABI, full framing and bounded stop/drop behavior. Keep capture disabled. |
| AX58 local NIC Netlink reader, raw forwarding to Pi | Export code established; GPL and firmware CSI function bodies agree | Candidate with incident/reset-risk gate. Review the same mode/reader requirements and the applicable failure paths before proposing any live run. |
| ADD_AP command 5 on either examined module | Static negative result: dispatcher rejects it | Blocked for these binaries; do not try a live command substitution. |
| Reuse the GT `csimond` binary on a repeater | Architecture/constants alone are insufficient; failed AX58 attempt remains recorded | Not validated; no repeat deployment. A separate reader must be assessed against the actual source profile. |
| Pi directly opens the repeater's Netlink socket | Netlink is local to the source kernel | Not an acquisition path. A device-side forwarder or a verified existing network export is needed. |
| GT eth6 receives from AX56 eth1; Pi stores/decodes | Existing receiver baseline, plus saved October 6 short-capture reports | Available baseline for later collector work; this is GT-originated CSI, not AX56-originated CSI. Fresh state and rollback checks are still required before a new run. |
| Other GT radio/peer links, or Pi's own radio | No validated profile here | Separate future assessment; no automatic substitution. |

The saved October 6 panel reports contain 59/29/11 valid prefixes at requested
100/200/500 ms respectively, in six-second captures; the first has one timing
gap. All are incomplete 320-byte stored records. These reports predate this
task and were read as metadata only; they do not supply repeater-originated CSI
or prove continuous capture quality.

**Selected continuation:** finish ordinary ADD/peer-mode and reader-contract
analysis against these identified modules, while preparing the off-router raw
storage/decoder boundary described in RECORDING.md. Do not spend another live
probe merely establishing that an exporter exists. A minimal forwarder remains
source-local; durable storage, profile decoding, signal processing and location
estimation belong on Pi/PC. No compatible forwarder has been implemented or
validated by this checkpoint. Classification is in progress, not a completed
multi-source acquisition milestone.

### Reproduction and retained evidence

Optional PC inspection dependencies are pinned in `requirements-research.txt`;
they are not runtime requirements and are never deployed by `deploy_panel.py`.
Sources/API responses, ZIP/image hashes, extracted modules, complete file
inventories, selected GPL member hashes, disassembly and the independent check
are under ignored `recordings/source-classification-20261013/`. Keep these
artifacts locally. `sources.json`, `ax56-firmware.json`, `ax58-firmware.json`,
`ax58-selection.json`, `elf-csimon-report.json` and
`static-independent-check.json` identify the evidence used above.

Inspection helpers in that directory read public artifacts only:
`inspect_sources.py`, `inspect_ax56_rootfs.py`, `inspect_ax58_rootfs.py`,
`inspect_elf.py`, and `verify_static.py`. Extraction/download helpers preserve
the downloaded originals; use a new evidence directory rather than overwriting
an existing acquisition. The independent check can be rerun with:

```powershell
.venv/Scripts/python.exe recordings/source-classification-20261013/verify_static.py
```

No router/repeater/Pi file, setting, monitor, process or service was changed;
`deployment.json` and operational rollback ownership remain unchanged. The
only environment additions are the optional analysis packages in the PC venv.

## Ordinary ADD and reader contract (2026-10-14–15)

Later October 15 update: the BSS audit below resolves the two configuration
byte meanings for AX58. Earlier uncertainty in this section is historical.

Scope: existing official AX56/AX58 release modules on the PC, with the same
SHA-256 values in the October 13 table. No device connection, binary execution,
new download or RF measurement. Local helpers and outputs are retained under
ignored `recordings/managed-contract-20261014/`; the directory date is the start
of the work, which continued on October 15.

### Command acceptance is not active acquisition

The saved AX58 GPL `wlioctl.h` defines DEL/ADD/ENB/DSB/RSTCNT as 0/1/2/3/4.
Its ordinary configuration has command at offset 0, six-byte peer at 4,
version at 10, length at 12 and interval at 16. Both release handlers check
version 1 and a minimum 20-byte supplied/declared length. This supports the
ordinary layout; it does not establish the conditional ADD_AP extension.

The new disassembly follows ELF `$a`/`$d` mapping symbols and resumes after
inline jump-table data. This resolves the earlier *linear-disassembly stop*
for the examined AX56 handler; it is not a whole-driver audit.

| Observation | AX56 `.text` offset | AX58 `.text` offset |
|---|---|---|
| ADD entry selected by command 1 | `0x20281c` | `0x2b5334` |
| Enable entry selected by command 2 | `0x202744` | `0x2b5310` |
| ADD's peer lookup when already enabled | `0x202a9c` | `0x2b5524` |
| Enable's peer lookup | `0x2027a4` | `0x2b560c` |
| `wlc_scbapfind` implementation | `0x27e4a8` | `0x33c724` |

Both ADD paths reject zero and multicast peer addresses, search ten configured
slots, and insert/update a peer before considering timer activation. Zero
requested interval selects 50 ms; a nonzero 32-bit interval is stored into a
16-bit field. These are implementation observations, not recommended settings.
The core-revision gate compares against 128. With monitoring disabled, ADD
returns success without a peer lookup. When enabled, both ADD paths require a
non-null `wlc_scbapfind` result and bit 1 at peer offset `0x2a` before creating
the per-peer timer; otherwise they can still return success. Consequently a
successful ADD/listed MAC does not demonstrate a usable measurement link.

Both lookup implementations traverse 16 configuration slots, skip null entries,
require nonzero bytes at configuration offsets 6 and 4, then call
`wlc_scbfindband` with the current band and requested MAC. They explicitly
return zero when no match is found. The symbol name suggests AP-side scope;
the exact names of the two C structure fields are **not established** by the
available headers. Do not label them definitively as AP/up flags or infer that
a Managed upstream association satisfies these tests.

A second possible activation entry, `wlc_csimon_scb_init`, checks the enabled
state and configured peer list. The ELF relocation survey found one reference
to it in each module, owned by `wlc_ap_scb_init` (AX56 `0x1b4218`, AX58
`0x262418`). This supports an AP association path, not a verified station-side
alternative. Relocations do not prove absence of indirect/unrelocated calls.
Managed-mode acquisition therefore remains unresolved, with concrete peer lookup
and association-path requirements rather than just a missing exporter.

### Enable-path safety difference

After its enable-path lookup, AX56 tests the pointer and peer-state bit before
using it, skipping that slot on failure. AX58's corresponding block performs
three register moves followed by a store through the returned pointer, with
no intervening null or state test. The helper itself has an explicit zero-return
path. A hypothetical zero return therefore reaches an invalid-pointer store in
this block. Whether this condition occurs in an operational configuration is
unverified; other caller/state invariants have not been proved.

This narrow finding was checked independently with standard-library ELF32
parsing, relocation names, exact A32 words and conditional-branch arithmetic,
without Capstone or pyelftools. It establishes the missing local guard, **not**
a live crash, exploitability, or the October 5 incident's cause. The user's
CSI/DHD watchdog finding remains separately attributed. Do not use a new live
probe to resolve this condition, substitute enable/ADD ordering as a safety fix,
or treat AX56's extra check as proof that its whole acquisition path is safe.

### Minimal reader contract narrowed

Both attach functions select Netlink protocol 23/22/24 for internal radio unit
0/1/other respectively. This now also has direct AX56 binary evidence. Linux
interface-to-unit mapping is still not verified. Both watchdog senders advance
the ring consumer before allocation/broadcast, copy 2,048 payload bytes after
a 16-byte header, and broadcast 2,064 bytes to group 2. Allocation/socket/send
failure paths increment an error counter and continue; no retransmission of
that consumed slot is apparent in the examined loop. Receiver counts therefore
cannot establish losslessness.

The sender explicitly writes length, flags and port ID, but the inspected
construction block does not assign header type or sequence. Preserve them as
opaque received bytes; do not rely on type as a validated control-message tag
or sequence as a loss counter. The clock function called before broadcast does
not by itself establish an acquisition timestamp in the exported payload.

The source-local reader must therefore retain the complete datagram and actual
length, receive/truncation/error status, source identity and its own monotonic
receive time/counter. It must not silently strip the header, normalize an
unexpected length, decode the repeater with the GT profile, or equate an
application counter with driver sequence/loss. Pi arrival time is separate.
The versioned transport must distinguish these datagrams from legacy 2,048-byte
payloads and 320-byte prefixes. These requirements refine the design in
[RECORDING.md](RECORDING.md); no compatible reader is implemented or deployed.

### Disposition and reproduction

Both methods remain blocked for live acquisition. AX56 needs verified
configuration/peer-mode semantics and the remaining lifecycle/reader checks.
AX58 additionally needs the unchecked lookup condition resolved without crash
reproduction. No repeater source may be marked selectable in the panel yet.
The next useful implementation is the offline raw-storage/processing boundary;
GT remains the validated receiver profile for separately planned integration.
Further binary work should identify the lookup configuration fields and
association call paths, not repeat exporter discovery or ADD_AP substitution.

Reproduce locally using the retained, hash-locked public modules:

```powershell
.venv/Scripts/python.exe recordings/managed-contract-20261014/inspect_contract.py
.venv/Scripts/python.exe recordings/managed-contract-20261014/verify_contract.py
```

The first emits mapping-aware disassembly, function references and caller
ownership in `contract-functions.json`; the second emits
`independent-contract-check.json`. The latter independently verifies dispatch,
lookup relocation/zero-return and guarded-versus-unguarded consumer instructions;
it does not independently verify every reader-contract or semantic inference.
The helpers only read firmware inputs and write their own analysis outputs.
Original images, raw CSI history, credentials and deployment state are untouched.

## Deferred acquisition acceptance procedure

Moved from NEXT-STEPS on 2026-10-06. This is a gated design, not authorization
to repeat the failed probe.

1. Confirm Pi availability with the user before connecting. Use existing access
   credentials and pinned host keys; do not install keys or change SSH settings
   to bypass an access problem.
2. Inspect current state without changes: device/firmware identity, relevant
   radio interfaces and associated peer identities, monitor state, existing
   collectors, and available userspace CSI facilities. Establish which MAC
   belongs to which radio/link; management IP and map placement alone do not
   identify the measured path.
3. Decide the extraction method from that evidence. Do not assume the main
   router's binary, Netlink protocol or decoder also works on either repeater.
   Before any temporary upload, process or monitor change, save exact initial
   state in the ignored deployment manifest, extend `scripts/rollback.py`,
   document restoration in `ROLLBACK.md`, and pass the rollback plan check.
4. Run one bounded 5–10-second probe at a time where supported. Preserve the
   complete available raw output and diagnostics, source/interface/peer identity,
   capture parameters and timing. Verify cleanup against the recorded initial
   state immediately afterward. No firmware change, permanent setting, service
   installation or always-on collection belongs to this stage.
5. Repeat successful probes. Report received records, lengths, freshness,
   observed cadence, errors and any measurable loss; mark unknown loss explicitly.
   Validate the format independently for each source before decoding or adding
   it to the panel. A working command or nonempty output is insufficient.

Done when each repeater has either repeatable raw CSI acquisition with verified
cleanup and documented format limits, or an evidence-backed blocking condition
and a concrete next experiment. If both work, proceed to coordinated short
captures and measure synchronization uncertainty before localization trials.
If only one or neither works, assess available main-router peer links and record
the revised experiment scope. Multiple sources do not by themselves establish
triangulation or recoverable human coordinates.


## AX58 BSS field audit and reader candidate (October 15)

The installed module hash matches the retained AX58 release module. Expanded
mapping-aware disassembly follows BSS type setter/getter and up/down paths;
the independent `scripts/audit_ax58_contract.py` uses only stdlib ELF32 parsing,
relocations, exact A32 words, branch arithmetic and hash-locked GPL enum values.
No firmware code is executed. Reproduce with:

```powershell
.\.venv\Scripts\python.exe scripts/audit_ax58_contract.py --module recordings/source-classification-20261013/ax58-a15a0ecf225d-wl.ko --header recordings/ax58-review-20261012/gpl-selected/e98af6096a2c-wlioctl.h
```

The setter at `.text+0x298038` writes byte +6 true for generic/AP (type 0,
subtype 2) or P2P/GO (type 1, subtype 4), using the enums in the retained
`wlioctl.h`. The independent getter at `0x2993e0` maps generic/+6 true back to
AP subtype 2. BSS up writes 1 at +4 (`0x29a99c`); BSS down writes 0 to the
same byte (`0x298830`). Together these establish the AP-role/up semantics
of the two lookup filters. These are semantic identifications, not recovered
C structure declarations. Ordinary station-role configurations fail the +6
filter; a physical radio can also host AP BSS configurations.

The guard defect remains at `0x2b561c`; live membership and getter observations
do not prove absence of a disconnect race. This audit does not authorize
activation or change the accepted historical incident finding. Unlike the
previous empty diagnostics, fresh queries after the SSH race fix show eth1
AP/up and the historical peer authenticated/associated/authorized. Details and
limits are in EXPERIMENTS.md. No monitor was enabled.

The source-local reader candidate is implemented and built locally. Its
socket-free ARM self-test passed on AX58; temporary deployment was removed and
baseline verified. Build, bounds and tests: [AX58-READER.md](AX58-READER.md).
This supersedes the earlier statement that no reader implementation exists,
not the requirement to validate live Netlink behavior and active CSI lifecycle.
