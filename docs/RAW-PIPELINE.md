# Offline raw-storage and processing prototype

Implemented October 15, 2026 in `src/raw_pipeline.py`, with a local-file CLI
in `scripts/raw_pipeline.py`. This is the first executable part of the
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
provided. Each source/link uses a separate journal.

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
Raw `csimond` **text** is not directly accepted as frames: a separately verified
import adapter is still needed. Declaring a profile is not proof of source
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
a journal is refused by the processor; a future read-only recovery tool is
needed, not manual relabeling as completed. Input errors are never retried.
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

Next: bounded recovery of interrupted journals and a verified legacy GT import
adapter, then a separately planned collector integration. The source-local
repeater reader and live queue/drop/time behavior still need implementation,
device compatibility evidence and a recorded rollback plan. No device change
or rollback procedure is introduced by this offline checkpoint.
