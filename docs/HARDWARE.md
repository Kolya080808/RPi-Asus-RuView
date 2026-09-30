# Hardware and verified state

State recorded on September 29, 2026. Repeater diagnostics
were performed through read-only SSH access; no settings were changed.

| Device | Address | Firmware | Interface | CSI observations |
|---|---|---|---|---|
| ASUS GT-AX11000 | `192.168.50.1` | `3.0.0.4.388_24548` | `eth6` (2.4 GHz), `eth7/eth8` also visible | `csimon` and `/usr/sbin/csimond` verified; capture works on `eth6` |
| ASUS RP-AX58 | `192.168.50.136` | `3.0.0.4.388_24694-g71d4ea1` | `eth1`, `eth2` | `wl ... cap` advertises `csimon`, `csimon state` responds; no standalone `csimond` found, capture not tested |
| ASUS RP-AX56 | `192.168.50.156` | `3.0.0.4.386_51891-g12b4ca4` | `eth1`, `eth2` | `csimon` advertised and responsive; no standalone `csimond` found, capture not tested |
| TP-Link RE200 AC750 | not established | unknown | unknown | not tested |
| Raspberry Pi Zero 2 W | `192.168.50.100` | Raspberry Pi OS Lite ARM64 | built-in Wi-Fi not used as a CSI source | local collector, SQLite history, and future web interface |

An unidentified candidate, `192.168.50.113`, was found in the ARP table
(`52:AF:97:B7:E3:D5`, ports 80/443/8080 open), but it must not be identified as the RE200
without checking its label or web interface. This is only an address to investigate
during the next inventory.

The presence of the `csimon` command on the RP-AX58 and RP-AX56 does not establish
that their firmware exposes CSI through an accessible userspace Netlink endpoint.
The next safe step is to determine separately whether such an endpoint exists,
then perform a short read-only capture. The main GT-AX11000 will not be reflashed,
and its persistent configuration will not be changed during this process.
