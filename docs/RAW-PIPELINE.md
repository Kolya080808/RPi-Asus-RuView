# Offline raw-storage and processing prototype

Implemented October 15, 2026 in `src/raw_pipeline.py` and `src/raw_recovery.py`,
with a local-file CLI in `scripts/raw_pipeline.py`. This is an executable part of the
[separate acquisition design](RECORDING.md#off-router-processing-boundary-for-the-next-implementation).
It does not open sockets, run SSH/commands on devices, enable CSI, change the
panel, or migrate existing history. It is not a live repeater reader.

## Boundary and guarantees

`ingest(binary_stream, new_database, source_descriptor)` reads at most 65,536
bytes per blocking read. Each returned chunk is committed in a new SQLite
journal before any interpretation. No decoder or framing parser runs in this
operation. Chunks retain exact bytes, contiguous stream offsets and local
monotonic arrival times. SQLite `synchronous=FULL` is used; actual power-loss
durability still depends on storage and OS behavior and was not hardware-tested.

The byte budget defaults to 64 MiB of input. The last returned chunk is saved
before an exceeded budget stops ingestion, so the retained input can exceed
the budget by at most one chunk. Database size includes SQLite overhead and
is not bounded by that input budget. The output path must be absent, including
for derived results; existing files are never overwritten. Parent directories
must already exist. No resume, append-to-existing, migration or cleanup API is
provided by ingestion. Recovery/import below create separate new journals.
Each source/link uses a separate journal.

`process(raw_database, new_derived_database)` opens the journal read-only in a
single snapshot, verifies chunk continuity, total length and SHA-256, then
parses and decodes into a separate database. It accepts only terminal journals,
so a slow/failed decoder cannot block this prototype's acquisition. Processing
can be rerun into another new output with a different decoder later. Source
metadata, raw-stream SHA-256, decoder-file and pipeline-file SHA-256 are saved
with the results. Frames reference exact raw stream byte offsets and lengths;
they do not replace or rewrite the original bytes.

This checkpoint validates **deferred offline processing**, not a simultaneous
live worker, transport backpressure, radio timing, sustained throughput or Pi
capacity. There is no receiver queue or network producer in this implementation.

## Version 1 envelope

This is a project import/fixture format, **not** the device's native Netlink
wire format or an implemented device-side forwarder contract. The stream starts
with the eight bytes `RUVRAW1\n`. Each subsequent frame is:

| Field | Encoding |
|---|---|
| Metadata byte length | Little-endian unsigned 32-bit; 1–4096 |
| Payload byte length | Little-endian unsigned 32-bit; 0–65536 |
| Metadata | Exactly that many UTF-8 JSON bytes |
| Payload | Exactly that many untouched input bytes |

`encode_frame(bytes, ...)` produces one frame, without the stream magic. Frame
metadata has exactly four fields:

- `source_sequence`: nonnegative reader counter below 2^63, or null. It is not
  a validated driver sequence and does not establish loss or clock alignment.
- `source_monotonic_ns`: source-reader clock below 2^63, or null. It is separate
  from the journal's local chunk arrival clock and is not RF acquisition time.
- `truncated`: Boolean source-reported truncation flag.
- `receive_error`: short source error code (up to 128 characters), or null.

Duplicate metadata keys, invalid clocks/types and oversized lengths are rejected
by processing; their original bytes remain in the journal. No resynchronization
is attempted after invalid framing. A partial final prefix/metadata/payload is
retained as input evidence, with processing marked failed and earlier committed
frame results preserved. Complete frames marked truncated or receive-error are
stored as invalid derived results, not decoded.

The source JSON descriptor has exactly these fields; use explicit null for
unknown values rather than inventing device facts:

```json
{
  "source_id": "synthetic-link",
  "operation_id": "offline-example",
  "device": null,
  "interface": null,
  "peer": null,
  "firmware": null,
  "profile": null,
  "layout_revision": null,
  "configuration": {},
  "kind": "netlink-datagram",
  "origin": "synthetic"
}
```

`source_id` and `operation_id` must be nonempty; the descriptor is limited to
4096 UTF-8 bytes. `origin` is `synthetic` or `offline-import`, never a claim of
a new live measurement. `configuration` records non-secret capture parameters;
do not place credentials or full device configurations here. Other fields are
nonempty strings or null. `kind` is one of:

| Kind | Expected payload length for this checkpoint | Processing |
|---|---:|---|
| `netlink-datagram` | 2064 | Raw-only, even if someone labels it with the GT profile |
| `csimond-payload` | 2048 | Decode only the explicitly declared existing GT profile |
| `legacy-prefix` | 320 | Same GT decoder, preserving the prefix classification |

An unexpected length becomes an invalid frame without changing its raw bytes.
The 2064-byte expectation is the inspected repeater transport candidate, not a
general Netlink rule. Unknown profiles remain raw-only. Netlink headers are
never stripped/interpreted and their type/sequence fields are not trusted.
Raw `csimond` **text** is not directly accepted as frames: the implemented legacy
adapter reads existing SQLite record BLOBs instead. Declaring a profile is not proof of source
compatibility; imports must retain honest provenance.

## Files and status

Both new databases use SQLite `user_version=1` and separate table names from
operational history. The raw journal contains `acquisition` (descriptor, status,
byte count, SHA-256, error class) and `chunks` (sequence, byte offset, local
arrival clock, exact bytes). `received` means EOF was observed, not valid CSI or
complete framing. Empty, malformed and truncated files can therefore be fully
received but fail subsequent processing. `failed` preserves prior commits.

The derived database contains `processing` (provenance and status) and `frames`
(offsets, length, metadata, status and result). `processed` means framing and
supported interpretation finished; frames may all be `raw-only`. `partial`
means invalid frames or a failed acquisition, even when the committed prefix
contains complete frames. Neither status establishes sensing capability or
zero loss. Invalid framing or an unexpected decoder/storage exception produces
`failed` and raises the error.

Disk-full cannot guarantee storage of the current uncommitted chunk; earlier
transactions remain. If persisting the failure state also fails, the API raises
and the journal may remain `running`. After abrupt process/PC termination such
a journal is refused by the processor; use the bounded recovery tool below to
create a separate incomplete snapshot, not manual relabeling as completed. Input errors are never retried.
External corruption is detected by integrity checks, not automatically repaired.

Both databases also have an append-only `events` table with local UTC seconds,
stage transitions, counts and full exception tracebacks (when storage permits).
Diagnostics use standard Python logging on stderr without dumping input bytes.
The short-lived CLI creates no log service/file or retention job. The project's
several-week log-retention duration remains undecided; events and raw CSI are
retained indefinitely until an explicit policy is implemented. No automatic
deletion or silent diagnostic truncation is introduced. On disk-full even the
failure event may be unwritable, so the raised error/stderr must be retained.

## Local commands and validation

Given a prepared version-1 envelope and matching source descriptor:

```powershell
.venv/Scripts/python.exe scripts/raw_pipeline.py ingest --input recordings/example.bin --source recordings/example-source.json --output recordings/example-raw.sqlite3
.venv/Scripts/python.exe scripts/raw_pipeline.py process --raw recordings/example-raw.sqlite3 --output recordings/example-derived.sqlite3
.venv/Scripts/python.exe -m unittest discover -s tests -p test_raw_pipeline.py -q
```

These CLI commands accept local files only. A processing `partial` result exits
1; exceptions also exit nonzero. Ingestion `received` exits 0 even for an invalid
envelope, because ingestion deliberately does not parse it. Always inspect the
separate processing result. The commands never fall back to a device source.

Tests use generated bytes/disposable databases. They cover fragmented input,
late/slow decoding, complete/partial frames, unknown profiles, source-reported
errors, transport interruption, real SQLite `SQLITE_FULL` via a page limit,
byte budgets, decoder failure, integrity failure, existing-output refusal and
CLI round trips. This is not a physical disk-full/power-loss or hardware test.

The bounded recovery and legacy GT SQLite import checkpoint below is complete
for local fixture validation. Next is separately planned collector integration. The source-local
repeater reader and live queue/drop/time behavior still need implementation,
device compatibility evidence and a recorded rollback plan. No device change
or rollback procedure is introduced by this offline checkpoint.

## Interrupted journal recovery (completed local checkpoint, October 15)

`raw_recovery.recover(input_path, new_output, ...)` accepts exactly one version-1
acquisition still marked `running`. It opens the input read-only in one SQLite
snapshot, checks chunk sequence/offsets, SHA-256 and recorded byte count, arrival
clocks, bounded diagnostic events, and SQLite `quick_check`. It copies the exact
committed chunk rows (including original import arrival times) and events into
a new database. It never trims the incomplete final frame, guesses lost bytes
or reinterprets a corrupt input as a valid prefix. A failed integrity check
refuses recovery before creating the output.

The new acquisition is `failed` with `InterruptedAcquisition`, plus a recovery
event containing the input digest, committed count and explicit unknown loss.
The CLI reports `recovered-partial` and exits **1** even when this copy succeeded:
completion of the original acquisition is unconfirmed. A subsequent `process`
returns `partial` for complete frames or raises on incomplete framing, retaining
previously processed frames. Recovery is not completion or a new measurement.

The copy is one transaction. A copy failure leaves no terminal acquisition row
in the newly reserved file; source data are unchanged. Do not retry into that
existing output. Use a new path and retain the failed output if diagnostic review
is needed. No existing file is removed automatically.

Defaults: 64 MiB committed input, 100,000 chunks, 10,000 events and 16 MiB total
event details. Descriptors and event names are bounded before loading them.
`--max-bytes` and `--max-rows` explicitly adjust the first two limits. A 30-second
work deadline (configurable up to 300 seconds) checks Python loops and SQLite
progress; SQLite lock waits are limited to one second. Filesystem I/O/scheduling
are not hard real-time bounded. Database/transaction overhead is additional.

Use a quiescent, clean **offline** SQLite file. If `-wal`, `-shm` or `-journal`
exists beside it, recovery/import refuses before opening it. Do not delete these
sidecars: they may hold committed data or require SQLite crash recovery. This
tool does not ignore WAL contents, checkpoint databases, repair hot journals,
salvage corrupt pages or recover uncommitted writes. Obtain a proper consistent
SQLite snapshot separately when needed. Other processes must not modify inputs
during these offline operations.

```powershell
.venv/Scripts/python.exe scripts/raw_pipeline.py recover --raw recordings/interrupted.sqlite3 --output recordings/recovered-copy.sqlite3
.venv/Scripts/python.exe scripts/raw_pipeline.py process --raw recordings/recovered-copy.sqlite3 --output recordings/recovered-derived.sqlite3
```

## Existing GT history import (completed local checkpoint, October 15)

`raw_recovery.import_legacy(history_path, session_id, new_output, descriptor, ...)`
reads one session from the existing `sessions`/`records` SQLite schema. This is
an adapter for the recorder's 2048-byte BLOBs and the panel's 320-byte prefixes;
it is not a text-log parser, export-JSON importer or migration of the history DB.
Only the selected session is imported; no private operational history was used
for this checkpoint's fixture tests.

The source descriptor must explicitly declare `origin: offline-import`,
`device: GT-AX11000`, the existing
`gtax11000-eth6-ch4-20mhz-i16-candidate-v1` profile, and either
`csimond-payload` or `legacy-prefix`. The selected session's `metadata.decoder`
must match that profile too. Supplied interface/peer values must agree with
saved values when both are known. Unknown firmware, physical layout and source
clocks remain null; do not substitute today's layout for a historical capture.
These declarations preserve provenance, not independently verify the device.

Each legacy BLOB is copied exactly into a new envelope. Original `seq` values
are retained as `source_sequence` (including gaps); they are legacy record
indices, not validated driver counters. Source time remains null; new chunk
arrival time records the import only. Original session ID, start/end/status,
metadata string and full log are stored in an `import_provenance` event, along
with record/byte counts, adapter SHA-256 and a digest of ordered
`<uint64 seq, uint32 length, raw bytes>` entries. Legacy derived results are
not reused; processing reruns the current decoder independently.

The full-payload mode refuses known 320-byte prefixes. Prefix mode refuses
larger records. Mixed 320/2048 sessions are therefore rejected rather than
silently promoted, split or dropped. Other shorter BLOBs (including empty ones)
are retained with the envelope truncation flag; acquisition is marked `failed`
and subsequent processing stays `partial`. Unexpected profiles are refused by
this specifically GT-only adapter; the general raw pipeline still supports
raw-only storage for unknown profiles.

An original status of `failed`, `running`, `paused` or `stopped` remains an
incomplete import even if every copied record is full-sized. Only `captured`
with no short records can yield `received`. This still does not establish
losslessness or valid CSI; profile/content errors are checked by `process`.
The provenance is committed **before** any imported stream bytes, and incomplete
upstream status is included in the terminal transaction. A process crash cannot
leave a terminal successful import with missing provenance.

Limits: 64 MiB raw BLOB bytes and 100,000 records by default, plus bounded
envelope overhead; 64 KiB session metadata and 8 MiB original log. The serialized
provenance must also fit 16 MiB. Oversized/malformed data, empty sessions,
negative/repeated record numbers and conflicting identities are refused before
creating output. Session selection is parameterized SQL. Reads and conversion
use the same deadline/snapshot controls as recovery. No logs are truncated.

```powershell
.venv/Scripts/python.exe scripts/raw_pipeline.py import-legacy --history recordings/local-history-copy.sqlite3 --session SESSION_ID --source recordings/gt-import-source.json --output recordings/imported-raw.sqlite3
.venv/Scripts/python.exe scripts/raw_pipeline.py process --raw recordings/imported-raw.sqlite3 --output recordings/imported-derived.sqlite3
```

An incomplete import exits 1 with JSON `status: failed`; this is distinct from a
raised exception, which logs a traceback and exits 1 without a result JSON.
Check both exit status and result. Existing outputs are always refused. All
input sources and their original private diagnostic logs remain unchanged.

Local acceptance tests include forced child-process exit immediately after a
committed chunk, nonmutation hashes, independent envelope unpacking, exact
BLOB/sequence/log comparisons, CLI round trips, failed/incomplete inputs,
corruption, size/deadline limits and sidecar refusal. Physical power loss,
damaged SQLite recovery, real legacy history and devices are **not** claimed
tested. These limitations do not block the defined offline checkpoint; live
capture and broader import formats are separate work.
