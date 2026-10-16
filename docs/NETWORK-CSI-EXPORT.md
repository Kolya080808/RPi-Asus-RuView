# Native network CSI export: AX58 and AX56

Completed investigation checkpoint, October 16, 2026. Work began October 15;
the evidence directory retains that start date. The selected question was
whether the stock firmware can send CSI directly to an IP/port on Pi without
deploying a source-local forwarding helper. No working stock configuration for
that purpose was identified. This is a bounded negative result, not proof that
every undocumented or indirect export path is absent.

## Compared release profiles

| Observation | RP-AX58 | RP-AX56 |
|---|---|---|
| Firmware | 3.0.0.4.388_24694-g71d4ea1 | 3.0.0.4.386_51891-g12b4ca4 |
| Kernel | 4.19.183 | 4.1.52 |
| Rootfs | SquashFS | UBIFS |
| Directory entries checked | 2,521 | 2,366 |
| Regular files read | 1,769 | 1,651 |
| Uncompressed file bytes read | 78,091,074 | 76,206,302 |
| ELF files inspected | 541 | 498 |
| Files with selected network imports | 138 | 127 |
| Named CSI driver functions | 25 | 25 |
| CSI-related network relocation targets | `__netlink_kernel_create`, `netlink_broadcast` | Same |
| Known export envelope | 16-byte Netlink header + 2,048-byte payload, group 2 | Same |
| Direct UDP/TCP CSI destination setting | Not identified | Not identified |
| Our helper runtime test | Socket-free self-test passed; cleaned up | Not deployed/tested |

The selected network imports identify candidates, not 138/127 CSI exporters.
Rootfs entry counts agree with the earlier retained October 13 inventories;
this is a coverage consistency check, not an independent filesystem decoder.
Source image/module hashes and provenance are in [REPEATER-CSI-RESEARCH.md](REPEATER-CSI-RESEARCH.md).
The AX56 audit locks the previously extracted 41,902,080-byte UBIFS volume to
SHA-256 `56aac5855686dc994fed2885c471be6d75b420c2fb6a6a59789e4b24a4880bbf`.
It does not re-extract the firmware container or establish a new published hash.

## Candidate checks

Both `wl` binaries advertise CSI monitor add/delete/enable/disable and state
counters. Their CSI help contains no IP/port destination. Both `wl.ko` symbol
tables and relocations associate the named CSI functions with local Netlink;
no `kernel_sendmsg`, UDP/TCP send or IP-destination setting was found in that
examined path. `wlc_sendnulldata` initiates a radio measurement exchange; it
is not evidence of sending measured CSI to Pi over IP.

Both `dhd` utilities contain RemoteWL usage:

```text
wl/dhd --socket <IP ADDRESS> [<PORT>] <command>
```

This is a remote-command client interface, not an identified CSI stream sender.
In AX58's command table, `csimon` at VA `0x3d538` refers to handler `0x14210`,
shared by 87 parameter commands; AX56's corresponding handler `0x1400c` is
shared by 86. The AX58 handler examines an optional argument and otherwise
queries/prints a scalar value; it is not a dedicated datagram streaming loop.
The table/usage check is independent of merely finding the words IP/server/port.
It does not prove what a separate, undocumented RemoteWL server might implement.
No RemoteWL service was started, no command was sent through it, and no device
was configured to use Pi as a destination.

Other marker hits were classified rather than promoted to capabilities:
libc's unrelated error string, module aliases, and vendor names in the OUI
database are not radio CSI export evidence. AX56 also contains two 43684
dongle firmware blobs with CSI strings. Their presence does not establish that
the active AX56 NIC driver executes them or exports their data over IP.
No such blob was loaded, patched or executed.

Limits: rootfs files only; nested compressed data and kernel/bootloader image
contents were not recursively decoded. Runtime/downloaded additions, stripped
numeric clients and indirect calls may evade marker/import analysis. Shared
transport sizing does not establish identical radio payloads or decoder profiles.

## Fresh AX56 read-only verification

Pinned-host SSH on October 16 confirmed the recorded firmware/kernel and ARMv7.
`sha256sum` is unavailable; that command failed and the original batch stopped.
A separately recorded alternative read the 6,910,228-byte module with an 8 MiB
cap and computed SHA-256 on the PC. It matched the retained release module:
`b82ffa419ce4d6910941ca3ed38cac5ded006f698d94a6d223f427fc5847f5ef`.

Both eth1/eth2 report AP=1, BSS=up and one associated peer each. Both CSI monitors
are disabled with empty configured lists and zero transfer/ACK/overflow counters.
Netlink 22 and 23 have kernel port-ID-zero entries and no userspace listeners.
Boot ID was unchanged across the bounded inspection. Each command had a
10-second bound; ordinary outputs were capped at 256 KiB, with a 150-second
batch budget. There was no upload, helper execution, monitor change, service
start or persistent setting change on AX56, and no remote rollback was needed.

## Reproduction and evidence

Optional existing `requirements-research.txt` dependencies are sufficient.
Use new output paths; both tools refuse to overwrite an existing report:

```powershell
.\.venv\Scripts\python.exe scripts/audit_ax58_network_export.py --image recordings/source-classification-20261013/ax58-firmware-image.bin --output recordings/ax58-network-export-20261015/ax58-final-audit.json
.\.venv\Scripts\python.exe scripts/audit_ax56_network_export.py --volume recordings/source-classification-20261013/ax56-volumes/ax56-firmware-image.bin/img-1550021443_vol-rootfs_ubifs.ubifs --output recordings/ax58-network-export-20261015/ax56-final-audit.json
```

Local raw evidence: `recordings/ax58-network-export-20261015/` (versioned rootfs
reports, selected public firmware binaries, `remote-wl-check.json`, tests) and
`recordings/ax56-network-preflight-20261016/` (exact plans, command journals,
module readback and results). Nothing was uploaded externally. Three local
tests check candidate matching, long-line hit retention and invalid-input
refusal; full test results are recorded in EXPERIMENTS.md.

## Decision and next step

The stock direct-to-Pi approach has no validated implementation on either
repeater. Do not expose a Pi port and claim collection is ready. The existing
minimal helper architecture is a plausible shared solution: source-local
Netlink receipt, forwarding, and independent storage/decoding on Pi. Reuse its
transport code where verified; give each device its own baseline, activation,
reader-runtime, payload-format and cleanup validation. AX56's extra null guard
does not prove its whole CSI lifecycle safe, and the AX58 self-test does not
validate execution on AX56. All active capture blocks remain intact.

## TP-Link RE200 inventory and public-source check

Correction, October 16: the existing inventory already identifies **TP-Link
RE200 AC750**, placed in R02 near the printer (see HARDWARE.md, HOME-MAP.md and
`maps/home/devices.json`). The earlier claim that its model was missing was
incorrect. Hardware revision, installed firmware and confirmed IP are still
unrecorded. The unidentified address in HARDWARE.md is not a confirmed RE200.

The [official RE200 download page](https://www.tp-link.com/us/support/download/re200/)
lists several hardware revisions and regional differences. The
[official EU V1 manual](https://static.tp-link.com/res/down/doc/RE200%28EU%29_V1_UG.pdf),
section 4.1, documents read-only hardware/firmware version fields; its searchable
text contains no CSI match. This limited documentation check does not establish
the installed revision or prove that its driver lacks CSI. No matching local
RE200 firmware artifact was found by filename in recordings/evidence.

There is no evidence here that RE200 exposes the ASUS Netlink contract, runs
the ARM helper, or exports CSI directly to Pi. Identical implementation is
therefore unconfirmed, not ruled out. The next RE200 step is to establish its
revision, region, firmware and address from its label or an identified read-only
status page, then inspect the matching public firmware/driver offline. Do not
select a revision or probe an address by guesswork. No TP-Link was contacted,
no firmware was installed, and no remote state changed during this check.

### Follow-up: live identification, October 16

The first HTTP-only attempt below was superseded by successful normal browser
identification and login later the same day; see the final subsection.

At the user's request, bounded read-only inspection of the GT-AX11000 established
a current DHCP lease named `RE200`, MAC `54:af:97:b7:e3:d4`, at
`192.168.50.155`. An HTTP GET there independently returned the TP-Link repeater
web application. The old `.113` candidate has DHCP hostname `HPC7596B` and a
different lease MAC. Both IPs appear with the same translated MAC in router ARP;
ARP alone is not a reliable management-device identifier in this topology.
No request was sent to `.113`.

Fetched only the root page and referenced static login/application resources.
Bare asset requests returned 401; normal same-origin Referer requests returned
200. The static files do not identify the installed revision/firmware. The
served login controller loads `firmwareModel`, whose proxy requests device block
`0|1,0,0` using the read operation `POST /?code=2&asyn=0`, without login retries
or encryption. A single reproduction of that metadata read returned HTTP 401
(body codes `00007`, `00007`, `00000`), not version data. No authentication
bypass, password guessing, session manipulation or configuration write followed.
The private credential store has no TP-Link entry; ASUS credentials were not
tried on RE200. This client request did not establish whether an ordinary browser
with additional page/session state could expose the versions before login.

Private evidence and request plans: `recordings/re200-identification-20261016/`.
Router reads used pinned SSH, 10-second/256-KiB bounds per command. HTTP requests
were sequential, no redirects, with 5-second socket timeouts and response size
caps (16 KiB for metadata, 256 KiB or 1 MiB for static resources). These socket
timeouts are not whole-operation deadlines. No scans, services, uploads, CSI
activation or persistent changes occurred; no rollback action was necessary.

Result: management address identified from lease plus vendor page; hardware
revision, regional variant and firmware remain unverified. Next evidence needed
is the label/status-page version information or authorized RE200 login access.
Do not infer a chipset or reuse the ASUS ARM/Netlink ABI from these web assets.
The ASUS investigation checkpoint is complete; RE200 feasibility and actual
live repeater acquisition remain open. No commit was created.

### Identification resolved through the normal browser

The user supplied the local password and authorized its use. One normal login
succeeded. The login page already displayed `RE200 5.0` and
`1.0.4 Build 210408 Rel.37106n`; the authenticated firmware page confirmed both
and added suffix `(8285)`. The network page confirmed `.155` and MAC
`54-AF-97-B7-E3-D4`. Thus the previous direct HTTP 401 was a limitation of that
request, not evidence that version identification required credentials.
The password is saved only in the Git-ignored local credential store; no password
value or session token is included in research documentation. Normal logout
was selected after inspection. No update/check-for-updates, reboot, upload,
save-settings or cloud-login action was selected.

The [official V5 download page](https://www.tp-link.com/us/support/download/re200/v5/)
links [the 210408 archive](https://static.tp-link.com/2021/202105/20210526/RE200_V5_210408.zip).
It contains `re200v5-up-noboot-ver1-0-4-P1[20210408-rel37106].bin`, 2,593,412
bytes, SHA-256 `ad1743f5001abf10047603d4a6389fced9c1b942e9de20f50981d19e84ea4282`.
The filename agrees with the observed version/build/release; regional identity
and equality to installed firmware have not been established. It was downloaded
to the PC only, never installed. A preliminary offline parse found a CRC-valid
uImage header/data at offset 148 named `U-Boot 2014.04-rc1 for leopard_e`.
LZMA inspection stopped at the 64 MiB decoder memory cap. No driver extraction
or CSI capability conclusion follows from this bootloader component.

Evidence: `browser-identification.json`, `official-v5-us.html`,
`public-download.json` and the archive/image in the private evidence directory
above. Hardware/firmware identification is complete; regional matching and
bounded offline driver analysis remain separate work. No validated stock CSI
sender or ASUS-compatible Netlink reader interface has been established on RE200.

### Offline V5 platform classification completed

On continuation, the memory-cap failure was resolved on the PC only: the
bootloader declares a 64 MiB dictionary, so a 96 MiB decoder budget allowed its
132,124-byte stream to finish. Bootloader strings alone were not used to classify
the main OS. The first main-stream attempt at 49,262 failed because two padding
bytes precede its header; the confirmed LZMA-alone stream starts at 49,264.
Its 8 MiB dictionary decodes within a 32 MiB memory budget and 16 MiB output cap:
1,532,059 compressed bytes, 5,194,576 decoded bytes, EOF reached. Decoded SHA-256:
`2bbd40d51f1e6133ee50231843570aa2a7acd3afc1dd30333fb5dd6fc161e52a`.

The main stream contains `VxWorks5.5.1`, `taskSpawn`, `semBCreate`, VxWorks driver
source paths and MT7628 driver labels. Independent structural checking of its
entry instructions establishes MIPS little-endian startup (`lui`, `mtc0`, stack
and global-pointer initialization), also decoded with the installed Capstone.
Thus this public matching-build candidate is a VxWorks/MIPS platform, not the
ASUS Linux/ARM environment. The existing static ARM Linux helper cannot run
unchanged on that platform. Applying this finding to the installed unit remains
conditional on the matching version/build/release, not a live memory/hash read.

No `csimon` string was found. The 19 case-insensitive `csi` substring hits include
beamforming capability labels (`ExpCSICapable`, `ExpCSIFbk`, `CSIBFAntSup`,
`CSIRowBFSup`) and unrelated strings such as SCSI/allocation/ioctl names. Generic
Netlink strings are also present; they do not establish Linux Netlink 22/23 or
the ASUS 2,064-byte record contract. No usable CSI extraction or direct-to-Pi
setting was identified. This is platform classification and marker review,
not proof that every proprietary CSI path is absent or a full driver audit.

Reproduce with the standard-library, exact-image/hash-locked local tool:

```powershell
.\.venv\Scripts\python.exe scripts/audit_re200_profile.py --image recordings/re200-identification-20261016/public-v5-210408.bin --output recordings/re200-identification-20261016/profile-audit-new.json
```

The CLI completed against the retained image. Invalid-image refusal and
existing-output preservation checks passed; `py_compile` and `git diff --check`
passed. New reports use exclusive creation. No firmware code is executed.
Raw component inspections and `profile-audit.json` remain in the private evidence
directory. Normal browser logout was verified by the return to the login page.
No device configuration changed, so no rollback action or manifest owner was
added. The comparison checkpoint is complete with this result: RE200 needs a
separate VxWorks/MIPS acquisition investigation; identical ASUS helper reuse is
not supported by the inspected build. Actual live CSI from all repeaters remains
an unfinished milestone.
