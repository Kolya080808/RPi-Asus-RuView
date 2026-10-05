# Repeater CSI research and acquisition options

Updated 2026-10-05 after review of the user's submitted research and the AX58/AX56
observations. This document distinguishes measured facts from proposed designs.
The submitted file was named `deep-research-report.md`; its findings are retained
here with claims narrowed to the evidence available in the repository.

## Executive finding

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
or prove which kernel events it expects. Netlink messages can have protocol-
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

## Evidence locations

Device snapshots, returned ASUS support-page data, ELF metadata and incident logs
were retained under ignored local `recordings/repeater-inspection-20261005/`.
The probe's operation manifest and exact post-reboot state are in ignored
`deployment.json`. These local artifacts are not part of the Git report; where a
claim depends on them, the text above states the observed result and its limit.
