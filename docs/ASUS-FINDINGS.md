# ASUS CSI probe — 2026-09-29

GT-AX11000 firmware 3.0.0.4.388_24548-gcb89015; Broadcom driver 17.10.121.41.
Three radios eth6/eth7/eth8 report chipnum 0xaaa4 (43684), revision 3.
`wl cap` advertises csimon. Stock `/usr/sbin/csimond` is present.

A bounded 8-second probe used eth6 and an associated ASUS WDS peer,
with csimon timer 500 ms. Driver reported 16 CSI transfers to DDR,
zero ACK failures and zero overflows. csimond received and printed
nonzero CSI records via netlink protocol 23. Output saved in
asus-csi-probe.txt. Printed data is capped at 2048 bytes per record;
stdio buffering can truncate the final record when the collector stops.
This is a diagnostic capture, not a validated decoder or pose measurement.

Cleanup: csimon disabled; experimental peer removed; collector stopped.
No firmware, NVRAM or Wi-Fi channel changes. Router diagnostic text
remains at /tmp/ruview-csi-probe.txt (about 90 KB).

Next: obtain complete binary netlink records; establish header and packed
CSI format against source; validate repeated captures with controlled
movement; integrate a collector with Pi. RuView compatibility unverified.
