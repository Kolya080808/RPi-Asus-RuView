# AX58 raw reader candidate

## Offline structure inspection — November 2, 2026

Use scripts/inspect_ax58_payload.py --input <retained-stdout.bin> --output
<new-report.json> for a bounded, non-decoding audit. It preserves the source,
rejects malformed/truncated/error-marked frames and reports payload-relative
fields separately from opaque Netlink metadata and reader receive time.
Nine observed frames match the Pi/AP addresses but have a different profile word
from GT. Timer units and coefficient packing remain hypotheses. See the offline
structure audit in EXPERIMENTS.md for exact observations and tests.

## Active source confirmed; decoding pending — November 2, 2026

The single authorized wl0.1/Pi trial ee8a83f9ee78 produced nine complete
2,064-byte raw datagrams through protocol 23/group 2. The source radio counter
independently increased by nine. Cleanup, unchanged boot and Pi return were
verified. Full conditions, retained evidence and limitations: EXPERIMENTS.md.
This confirms acquisition only for the observed firmware/interface/peer; it does
not qualify sustained operation or the AX58 payload format. The GT decoder was
not applied. Next: offline interpretation, then scoped Pi transport integration.
Sections below describe historical preflight and earlier restrictions.

## Historical preflight - November 1-2, 2026

The user explicitly accepted one short active trial on the in-service AX58,
including hang/reboot and temporary client interruption. This overrides the
historical blanket active block for one operation only. It does not establish
driver safety or authorize firmware, topology changes, retries or continuous
capture. The trial has not been dispatched.

The selected candidate is virtual AP `wl0.1` (radio 0/protocol 23) and the
identified Pi peer `88:A2:9E:94:7D:80`. Initial preflight observed Pi on that AP;
later preparation correctly refused because the association list became empty.
Pi's cached NetworkManager active-BSSID read independently shows
`A0:36:BC:16:85:B9` (the documented AX56 radio). No scan was requested.
Do not activate CSI for an absent Pi or substitute the Managed upstream GT link.

Added `active_reader_probe.py`, a separate native supervisor, and an optional
reader `--ready-fd=3` handshake after bind. The supervisor is fixed to the Pi/AP
pair: ADD at 500 ms, enable, a five-second window, disable, exact-peer delete.
It bounds child command waits and attempts cleanup on HUP/INT/TERM. Kernel
hangs remain unrecoverable by these userspace bounds. Commands and child PIDs
go to stderr; raw stdout stays separate. Full scope is in ROLLBACK.md.

Builds: `recordings/ax58-active-build-20261101/build.json`; private preflight and
tests: `recordings/ax58-active-20261101/`. Initial Linux test failures were a
CRLF fake-wl shebang problem, corrected locally; no device commands ran there.
Five supervisor tests and four native-reader tests pass on local WSL. Five
Python plan guards pass; full suite before the last added guard: 183 tests,
174 passed/nine opt-in skips.
No helper upload or monitor mutation occurred, and failed preparation created
no active manifest entry. The one-shot authorization remains unused.

## Historical scope — October 28, 2026

Follow the ordinary-acquisition plan in NEXT-STEPS.md. The user asked to stop
expanding driver-failure investigations. Earlier findings below remain evidence
and limitations, not instructions to run more failure scenarios. Active capture
is still unvalidated; no reordered activation sequence is qualified by them.
Pi access and basic runtime/storage checks succeeded on October 28, but live
AX58 receipt, payload interpretation and continuous decoding remain open.

Guarded-ADD follow-up: the existing null guard is real, but ADD success may leave
a retained MAC without an SCB binding/timer. Offline association-callback tests
show why readiness must include those invariants and allocation-failure handling.
This is not evidence to deploy a reordered activation sequence. The active
design remains blocked; details and controls are in REPEATER-CSI-RESEARCH.md.

Latest October 28: bounded local ARM emulation with original peer-lookup code
reproduced the conditional ENB invalid write for a retained slot/absent peer.
Sequential deferred-timer-free controls passed in one synthetic runtime mode.
The proposed active sequence remains blocked; a short supervisor/precheck does
not resolve the activation failure path. See REPEATER-CSI-RESEARCH.md for method,
controls and limits. No active device experiment or firmware change occurred.

October 28 continuation traced AP deinit registration and the disabled-ADD /
disabled-teardown / ENB paths. A nonempty retained slot with an absent peer
reaches an unchecked store; a userspace peer snapshot does not rule this out.
Other callback slot-invalidation coverage and runtime reachability are unproven.
The active design below is still blocked; no live reproduction was attempted.

October 28 offline continuation found matching ioctl/callback lock offsets,
deferred-free task bookkeeping and AP CSI timer teardown. Full activation and
shutdown lifetime safety is still unvalidated: remaining coverage is documented
in REPEATER-CSI-RESEARCH.md, "Wrapper locks and AP teardown". The prerequisites
below are narrowed, not closed. No active runner or remote change was made.

Latest October 22: the separately authorized passive protocol-23 trial completed
with expected no-data exit 3 and verified cleanup (`b9821d3edd5f`). The socket
was opened and closed with CSI disabled. Active acquisition and AX58 decoding
remain unvalidated; the older socket-free checkpoint below describes October 15.

## Passive check preparation — October 22, 2026

`scripts/passive_reader_probe.py prepare --protocol 23` prepares a separate
read-only baseline and plan; it does not upload or execute the helper. Protocol
22 is an explicit alternative, not an automatic retry. The first planned run
is two seconds, group mask 2, at most 64 datagrams, with the existing helper's
four-second emergency alarm and one-second stdout deadline. The SSH collector
must retain stdout, stderr and exit metadata, including partial failures.

The plan is stored under `deployment.json:passive_reader_checks`, with its own
`/tmp/ruview-passive-<12hex>` path. `rollback.py --passive-reader-only --check`
checks that scope independently of the completed socket-free self-tests.
Preparation is `prepared-blocked` by default. Later on October 22 the user
explicitly accepted the explained residual uncertainty for one passive trial.
The `run --plan ID --accept-passive-risk` command now records that acceptance,
checks the exact plan and baseline, uploads/verifies the reviewed helper and
runs it once. The CLI flag records an already authorized decision; it is not
standing authorization for future experiments. No active CSI command is included.

Expected no-data acceptance requires exit 3, exactly the `RUVRAW1` magic and
the helper's zero-record diagnostic, followed by verified cleanup. Other exits,
partial frames or unexpected data must retain evidence and stop acceptance.
No-data alone neither proves CSI capability nor constitutes a failed CSI test.
Full acceptance additionally requires unchanged boot/monitor state, no userspace
listeners on protocols 22/23 and no process using the owned executable path.
Closing SSH is not evidence that the socket/process has terminated.

The execution implementation rechecks the baseline immediately before upload
and receive, records upload/receive states before those actions, and invokes
the separate cleanup verification on complete transport results. Unknown or partial
files and still-running processes are retained for inspection; no monitor
changes or broad process kills are allowed. Continuous Pi forwarding and AX58
payload interpretation remain separate unimplemented work.

The receive evidence directory is saved before execution. A transport exception
leaves the plan at its last known state for narrow rollback inspection; no retry
or cleanup success is invented. A complete unexpected result retains exit/output
metadata and attempts verified cleanup, then reports failed acceptance. Even a
clean no-data exit establishes only this bounded passive trial.

October 15, 2026: built locally and socket-free self-test passed on AX58;
temporary deployment removed and baseline verified. Live acquisition and
decoding remain incomplete. No Netlink socket or CSI monitor was activated.

`native/ax58_netlink_reader.c` is a minimal Linux C transport helper because
the checked AX58 executable directories contain no Python. The application,
storage, decoding and panel remain Python on Pi/PC. The helper does not invoke
`wl`, enable CSI, transmit packets, fork, write files or install services.
It is not the foreign GT `csimond` binary.

## Proposed isolated ordinary-acquisition bench — October 28

Status: not selected. On October 28 the user explicitly required AX58 to remain
in the home network and declined a separate bench. The proposal below is
historical context, not the current next action or authorization.
This is the next concrete source-acquisition option after the ordinary-document
review, not authorization to activate CSI on the current home repeater. An
isolated bench limits household impact but does not establish driver safety.

1. Establish that AX58 no longer carries household clients/backhaul before
   changing its role. Keep GT-AX11000/RP-AX56 serving the home network. The user
   must confirm available cabling and a management path that survives loss of
   the experimental radio; do not assume a spare Ethernet adapter or infer
   isolation from an SSID name. No factory reset or firmware replacement.
2. Plan the exact reversible topology/configuration changes only after that
   confirmation. Record the current role and changed values privately; never
   dump credentials into the repository. Any persistent mode/address/SSID change
   needs its own baseline, manifest scope and restoration verification before
   application. This draft contains no such configuration change or command.
3. Candidate topology: PC manages AX58 through its LAN port; one identified
   authorized lab peer uses its AP radio. Pi may be that peer/collector if its
   management and recovery access are confirmed. One link, not multiple sources.
   Loss of the experimental radio must not remove control of the home router.
4. Prepare a separate active operation with exact interface/module/helper,
   owned supervisor/processes, reader readiness, full raw output and a bounded
   stop/cleanup implementation. Retain the October 22 candidate limits (five
   seconds, 500 ms requested interval, at most 64 datagrams) as design limits,
   not validated runtime guarantees. Choose no command order solely from the
   synthetic matrices. No forced departure, allocation failure or load testing.
5. Before any activation, explicitly record the accepted possibility of an
   AX58 restart/hang and its local recovery route. A userspace timeout cannot
   prevent or recover a stuck kernel. Stop after one attempt; no automatic retry.
   Preserve stdout/stderr/exit and all partial raw data. Independently verify
   device boot/state and exact cleanup, then restore any separately planned
   temporary topology change. Failure does not authorize a factory reset.

Successful acceptance requires actual AX58 records and verified cleanup;
subsequent source-specific interpretation remains separate. If isolation is
unavailable or the remaining device risk is unacceptable, active AX58 acquisition
remains blocked rather than being replaced silently by another project task.

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

The journal now also accepts `live-stream` provenance, and a bounded channel
receiver is locally tested. Pi runtime/storage passed a synthetic check. Sharing
an envelope still does not implement active source orchestration. That integration must retain
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

### Active acquisition preparation — October 22

This is a bounded design, not an implemented active runner. Passive acceptance
is complete for protocol 23; it does not exercise monitor timers or peer lifetime.
The earlier passive risk acceptance does not extend to active monitoring.

Two exact-build prerequisites remain before a device activation plan:

1. Establish the locking/lifetime contract between the CSI ioctl, AP peer lookup
   and association/disassociation. A fresh AP/up/authorized-peer query is only
   a snapshot; it cannot guarantee the pointer at the unguarded enable store.
2. Establish serialization of timer callbacks with cancellation and freeing.
   DSB deletes/frees per-peer timers before clearing enabled, and a callback
   seeing disabled can still reach rearm. The wrapper calls `del_timer` and
   conditionally frees through a freelist or directly. Without the caller locks
   this proves neither a defect nor a reliable active rollback. Exact addresses
   and reproduction are in REPEATER-CSI-RESEARCH.md.

Historical October 22 inspection targets were the ioctl dispatcher, timer
wrapper/free-list lifetime and AP peer teardown. Later results are retained in
REPEATER-CSI-RESEARCH.md. They are not a current queue of failure investigations.
Do not substitute enable-before-ADD, firmware patching, an absent peer or a
forced disconnect as an experiment to bypass these prerequisites.

Once those prerequisites are resolved, the proposed first active trial is:

| Item | Proposed constraint / required evidence |
|---|---|
| Source | AX58 only, exact installed module and helper hashes |
| Link | One freshly verified AP/up interface and one identified authorized peer; verify radio unit/protocol mapping |
| Duration | One 5-second acquisition window, 500 ms requested CSI interval; no repeat or fallback interface |
| Reader | Existing raw envelope, explicit readiness after bind, maximum 64 datagrams; no GT decoder |
| Storage | Full envelopes plus stdout/stderr/exit metadata and source identity; retain partial failures |
| Stop | Source-local owned supervisor and bounded cleanup, independent of PC/SSH continuity |
| Rollback | Disable only the monitor enabled by this operation, remove only its exact peer, wait for owned tasks and remove only verified files |
| Acceptance | Raw frames, lengths/times/error counters, unchanged boot, baseline monitor/peer/socket state and exact cleanup |

These limits are proposals to validate locally, not current runtime guarantees.
The reader alarm alone does not stop an enabled monitor; a userspace watchdog
cannot recover a stuck kernel. The supervisor, readiness handshake, failure
tests and active rollback scope must exist before upload or monitor changes.
Failure cases include bind failure, blocked output, lost SSH, partial upload,
monitor-command failure, unexpected peer state and cleanup verification failure.
Do not use blanket peer deletion, unknown PID kills or automatic retries.

The future manifest entry must be distinct from `passive_reader_checks`, with
exact owned files/processes/settings, initial state, command/cleanup evidence and
an explicit acceptance outcome separate from restoration. No active manifest
entry or remote mutation was created by this preparation. Continuous Pi receipt,
durable live journaling and independently validated AX58 decoding are subsequent
integration steps; an offline import is not their replacement.

Before any upload: record the unique temporary path and its absence, build
hash, boot/monitor/peer/socket baseline in `deployment.json`; implement and
dry-check exact cleanup in `scripts/rollback.py`. Then test socket-free
`--self-test`, followed by a separately bounded passive receive check with CSI
still disabled. Verify cleanup and baseline after each operation. Socket-free
self-test deployment and rollback are now implemented in `scripts/reader_probe.py`
and `scripts/rollback.py --reader-only`. This wrapper still exposes only
`--self-test`. Passive reception uses `passive_reader_probe.py` and the separate
`--passive-reader-only` rollback scope documented above.

Active CSI additionally needs a lifecycle/peer review and reversible activation
plan. AP/up/authorized-peer observations do not prove absence of disconnect races
or other driver faults. Do not bypass the old capture block by changing command
order. Actual AX58 records must establish their own decoder profile before
live interpretation on Pi.
