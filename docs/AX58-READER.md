# AX58 raw reader candidate

October 15, 2026: built locally and socket-free self-test passed on AX58;
temporary deployment removed and baseline verified. Live acquisition and
decoding remain incomplete. No Netlink socket or CSI monitor was activated.

`native/ax58_netlink_reader.c` is a minimal Linux C transport helper because
the checked AX58 executable directories contain no Python. The application,
storage, decoding and panel remain Python on Pi/PC. The helper does not invoke
`wl`, enable CSI, transmit packets, fork, write files or install services.
It is not the foreign GT `csimond` binary.

## Contract

Explicit arguments select protocol 22 or 23 and duration 1–8 seconds. The
helper binds Netlink group mask 2, reads with `recvmsg(MSG_TRUNC)` into 65,536
bytes and emits `RUVRAW1` envelopes (see [RAW-PIPELINE.md](RAW-PIPELINE.md)).
It retains the complete datagram, reader counter, monotonic receive time,
truncation and receive-error metadata. Unexpected sender, truncation and
receive errors stop the reader after attempting to preserve their evidence.
Kernel header fields stay opaque; the GT decoder is never applied. Reader
counters and successful exit do not prove zero driver loss.

Bounds: 64 datagrams, 1-second stdout write deadline, acquisition deadline,
and emergency alarm at duration + 2 seconds. Stdout is nonblocking; a blocked
or broken pipe fails and may leave a partial envelope. SIGINT/SIGTERM stop the
loop; the alarm also bounds blocked diagnostic writes. There is no unbounded
queue. The default kernel receive buffer is used; ENOBUFS is not suppressed.

Exit codes: 0 = interval finished with records; 2 = usage/I/O/receive failure;
3 = interval with no records; 4 = record limit; 124 = emergency alarm;
130 = stop signal. `--self-test` opens no socket and emits two synthetic
records, including one explicitly truncated fixture.

The existing Python CLI still accepts offline/synthetic origins only. Sharing
an envelope does not implement live orchestration. That integration must retain
source identity, executable hash, stderr, SSH exit, stop reason and failures.
A magic header alone is not a capture; EOF is not a zero-loss guarantee.

## Build and local tests

Optional PC-only compiler: `requirements-native-build.txt` pins Zig 0.15.2.
Create an ignored output directory, then build with the existing venv:

```powershell
.\.venv\Scripts\python.exe -m ziglang cc -target arm-linux-musleabi -mcpu=cortex_a7 -static -Os -Wall -Wextra -Werror native/ax58_netlink_reader.c -o recordings/ax58-reader-build-20261015/ax58-netlink-reader
.\.venv\Scripts\python.exe -m ziglang cc -target x86_64-linux-musl -static -Os -Wall -Wextra -Werror native/ax58_netlink_reader.c -o recordings/ax58-reader-build-20261015/reader-linux-test
```

ARM output: 28,516 bytes; SHA-256
`e54178c7e7a5159bf5902140bf3e087c8953f03ef32fe789e5c482ce417d393c`.
ELF verification: little-endian ARM32, EABI flags `0x5000200`, no dynamic or
interpreter segments, no hard-float ABI flag. This is not runtime validation.
Binary outputs and `elf-check.json` remain ignored.

The x86_64 build was tested on this PC's existing Ubuntu WSL, without sockets:

```sh
RUVIEW_READER_TEST_BINARY=/absolute/path/to/reader-linux-test python3 -m unittest discover -s tests -p test_native_reader.py -v
```

Four tests passed: independent envelope unpacking/exact data and metadata,
argument rejection, broken pipe and full-pipe timeout. Windows discovery skips
the opt-in Linux class. The subsequent ARM socket-free self-test passed on AX58,
validating execution/framing only. Actual Netlink delivery/drop handling, signals
during receive and forwarding to Pi remain unvalidated.

## Next device steps and rollback gate

Before any upload: record the unique temporary path and its absence, build
hash, boot/monitor/peer/socket baseline in `deployment.json`; implement and
dry-check exact cleanup in `scripts/rollback.py`. Then test socket-free
`--self-test`, followed by a separately bounded passive receive check with CSI
still disabled. Verify cleanup and baseline after each operation. Socket-free
self-test deployment and rollback are now implemented in `scripts/reader_probe.py`
and `scripts/rollback.py --reader-only`. Passive reception still needs its own
plan; this wrapper exposes only `--self-test`, with no Netlink or CSI mode.

Active CSI additionally needs a lifecycle/peer review and reversible activation
plan. AP/up/authorized-peer observations do not prove absence of disconnect races
or other driver faults. Do not bypass the old capture block by changing command
order. Actual AX58 records must establish their own decoder profile before
live interpretation on Pi.
