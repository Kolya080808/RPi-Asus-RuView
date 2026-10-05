# Hardware and verified state

## RP-AX56 detailed read-only check: October 5, 2026

Authenticated diagnostics confirmed model RP-AX56, firmware
`3.0.0.4.386_51891-g12b4ca4`, ARMv7 and Linux 4.1.52. The boot log reports
chip name 6755; both radios report chipnum `0xf6ca`, core revision 130.1,
and Broadcom driver `17.10.157.2809`. For comparison, the earlier AX58
inspection reports chip name 6756 and driver `17.10.188.6401`; these devices
must not be treated as an identical runtime profile.

Both AX56 interfaces report `Managed` mode with upstream main-router peers:
eth1 is 2.4 GHz channel 4 / 20 MHz, eth2 is 5 GHz primary channel 100 / 80 MHz.
These are observed client-side interfaces, not proof that CSI monitoring supports
the same operation as the previously tested main-router path. Other virtual
interfaces were not evaluated as CSI sources.

`csimon` is advertised by both radios, and boot messages report CSIMON 1.1.0
initialization. A prior same-day inspection found kernel Netlink 23. Both monitors
remain disabled, peer lists empty and transfer/error counters zero. A filename
search under `/bin`, `/sbin`, `/usr/bin`, `/usr/sbin` found no `*csi*` entry;
this does not exclude CSI handling embedded in another binary. The command help
describes monitor control only, with no collection/output-format contract.

Uptime increased from 434863.08 to 435044.51 seconds across this inspection;
no reboot was observed. No binary was uploaded or run, no monitor enabled,
no settings changed and no CSI collected. Evidence is retained locally in
`recordings/repeater-inspection-20261005/ax56-detailed-readonly.json` and
`ax56-final-readonly.json`. This is a verified capability inventory, not a
negative proof that AX56 cannot supply CSI.

## Repeater access checkpoint: October 5, 2026

Latest: administrator password access now works on both RP-AX58 and RP-AX56.
Both report ARMv7 and the expected firmware; their `/proc/net/netlink` snapshots
included a numeric protocol-23 entry.
One AX58 collection attempt coincided with a confirmed reboot; no CSI obtained.
All repeater capture is disabled pending incident review; see `EXPERIMENTS.md`.
The access exploration below is historical, not a current credential blocker.
Reviewed research and the corrected limits of these observations are in
[`REPEATER-CSI-RESEARCH.md`](REPEATER-CSI-RESEARCH.md).

The user confirmed Pi availability; SSH using the existing lab key and pinned
host key succeeded. Both documented repeater addresses answered an SSH handshake
on port 22 with a Dropbear banner. No repeater authentication was attempted.
The local standard and lab known-hosts files and the Pi collector known-hosts
file had no trusted entry for either repeater. Device identity at those addresses
therefore remains unverified in this check; no new CSI capability is established.

Observed ED25519 fingerprints (unverified; not authorization to trust them):

- RP-AX58 address: `SHA256:H7QJxf8Mk1QZV9OtMcWauDnvD0TSd5pyC3aVBVdY6ck`.
- RP-AX56 address: `SHA256:An/5Vi554F18ohxFv6UtYNJfk8LZe7Owuotn6c08kKM`.

Follow-up: the user had never logged into the nodes directly; they were configured
through the main router's AiMesh interface. The main router accepted the existing
lab key and its ARP table mapped the documented node addresses to the expected
management MACs. This supports address mapping, not cryptographic host identity.
The observed SSH fingerprints remained unchanged and were pinned in memory for
an existing-key login check; no known-hosts files were modified. Both nodes rejected
`admin` with the existing lab RSA key. The initial Paramiko key-file attempt ended
in a misleading key-format exception; an explicit RSAKey retry confirmed
authentication rejection. No password was attempted or retrieved.

ASUS's [SSH/terminal access FAQ](https://www.asus.com/us/support/faq/1048201/)
(checked October 5) documents router administrator login and SSH settings, but
does not establish credential synchronization for these AiMesh node versions.
The user's hypothesis that the router password works on the nodes remains untested.
Next: user enters that password locally in an SSH client, then establishes an
authenticated session for the read-only capability inspection. No device files,
monitor settings, access keys or services were changed.

On 2026-10-04, SSH access to the Pi was verified using the existing lab key.
An enabled `ruview-lab-panel.service` was already serving a bootstrap interface
on port 80. The panel update preserves that configuration; see [PANEL.md](PANEL.md).
No new router or repeater capability checks were performed in this UI task.

Physical placement was documented from the user's map and description on
September 30, 2026: GT-AX11000 in R08 on a cabinet at approximately 3 m;
RP-AX56 in R07 and RP-AX58 in R02 at floor level near PCs; TP-Link in R02
near a printer at approximately 1.40–1.50 m. See [HOME-MAP.md](HOME-MAP.md)
and [device coordinates](../maps/home/devices.json). These are approximate
placement observations, not new network or CSI capability checks.

State recorded on September 29, 2026. Repeater diagnostics
were performed through read-only SSH access; no settings were changed.

| Device | Address | Firmware | Interface | CSI observations |
|---|---|---|---|---|
| ASUS GT-AX11000 | `192.168.50.1` | `3.0.0.4.388_24548` | `eth6` (2.4 GHz), `eth7/eth8` also visible | `csimon` and `/usr/sbin/csimond` verified; capture works on `eth6` |
| ASUS RP-AX58 | `192.168.50.136` | `3.0.0.4.388_24694-g71d4ea1` | `eth1`, `eth2` | `csimon` advertised; one foreign-collector probe coincided with a reboot and yielded no CSI. Capture disabled pending incident review. |
| ASUS RP-AX56 | `192.168.50.156` | `3.0.0.4.386_51891-g12b4ca4` | `eth1`, `eth2` | `csimon` advertised and responsive; no collector run and no CSI capture. |
| TP-Link RE200 AC750 | not established | unknown | unknown | not tested |
| Raspberry Pi Zero 2 W | `192.168.50.100` | Raspberry Pi OS Lite ARM64 | built-in Wi-Fi not used as a CSI source | local collector, SQLite history, and future web interface |

An unidentified candidate, `192.168.50.113`, was found in the ARP table
(`52:AF:97:B7:E3:D5`, ports 80/443/8080 open), but it must not be identified as the RE200
without checking its label or web interface. This is only an address to investigate
during the next inventory.

The presence of `csimon`, a boot-time CSIMON initialization message or a protocol
23 socket-table entry does not establish that useful CSI can be read in userspace.
The earlier AX58 foreign-collector attempt coincided with a reboot and must not be
repeated. See [`REPEATER-CSI-RESEARCH.md`](REPEATER-CSI-RESEARCH.md) for the
corrected evidence levels and research-only next steps.
