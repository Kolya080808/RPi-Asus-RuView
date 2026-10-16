# Collection and history on Raspberry Pi

For a one-command PC workflow that records, exports, and opens a motion PNG,
see [CAPTURE-PLOT.md](CAPTURE-PLOT.md). Direct Pi commands are below.

Access: ssh pi@192.168.50.100. On the Pi:

```sh
python3 /home/pi/ruview-lab/recorder.py capture --seconds 20 --interval-ms 100
python3 /home/pi/ruview-lab/recorder.py history
python3 /home/pi/ruview-lab/recorder.py export SESSION_ID
python3 /home/pi/ruview-lab/motion.py SESSION_ID
```

The collector connects directly from the Pi to the ASUS using a dedicated key.
A PC is not needed to acquire or save data. Python uses only the standard library.
The recorder CLI is limited to a single session of 5–60 seconds. After the session, the monitor
is disabled and the temporary peer entry is removed. Capture has no service or
autostart. The separate web panel is an existing enabled service; its manual
capture path supports 5–1,800 seconds, with no automatic recording on startup.

History: /home/pi/ruview-lab/history.sqlite3. It contains raw records, provisional
decoding results, session start/end times, parameters,
complete diagnostic output, and errors. The time of each record from field 0x14
has not yet been tied to UTC; future training with a camera requires synchronization.
After capture, `recorder.py` automatically runs `motion.py`: the first 8 seconds
serve as a baseline, after which a sustained increase in normalized amplitude change
is recorded as an event in the `motion_samples` and `motion_events` tables. This
indicates motion across the entire scene. It does not produce a skeleton, body parts, or heart rate.
There are no video recordings or computed skeletons yet. History is accessible
through the CLI and the local [panel](PANEL.md), which provides replay, raw export
and reference activity labels. The panel provides Start/Pause/Resume/Stop and
separate current/library deletion controls. Its incremental live graph uses the
same causal filter as the desktop viewer; see [PANEL.md](PANEL.md) for measured
refresh intervals and limitations.

The panel currently stores 320-byte CSI prefixes through `LiveParser`; unlike
the recorder CLI, it does not preserve the full printed 2,048-byte tail or complete
capture diagnostics. Existing records are retained unchanged. Full raw-stream and
diagnostic retention remain collector work, not a delivered panel capability.

The requirement is to retain all diagnostic logs for several weeks and then delete
them. The exact number of weeks and automatic cleanup policy are not implemented yet;
no logs are automatically deleted today. The 256 MiB database limit blocks new
captures until manual archival. Log retention must include diagnostics stored in
session history as well as capture log files, without deleting raw CSI records as a
side effect. Text diagnostic logs increase storage use; long-term requirements cannot
be estimated from the 320-byte useful block alone.

Verified 2026-09-29: session 40ddd901-0f56-44d4-bebd-0c74c4d6eb04,
10 seconds, 100 ms, 98 records. All are 2048 bytes. The 96:320 region updates
in every packet; the tail repeats A/B. The driver counted 99 transfers,
1 ACK failure, and 0 overflows; the collector does not yet guarantee lossless acquisition.
An unsuccessful attempt was saved with failed status, not presented as a successful recording.

The decoder profile is limited to the current eth6/channel 4 setup. A different header is not
silently decoded: the original bytes are saved along with a profile error.
The dynamic region boundary has been confirmed twice; the physical meaning of I/Q,
subcarrier order, and compatibility with the pose model remain hypotheses.

Pi → ASUS access is currently added to the runtime file /root/.ssh/authorized_keys;
after an ASUS reboot, the firmware may recreate it from its settings.
Persistent SSH settings in NVRAM were not changed.

## Planned timing and collector requirements

Moved from NEXT-STEPS on 2026-10-06. Remaining work must be verified separately.

### 3. Add session timing and the minimum collector fixes

- Use elapsed time instead of fixed frame counts for baseline and smoothing.
  The current motion analyzer assumes 10 Hz while capture also allows 200/500 ms.
- Parse and persist records as they arrive; retain partial captures on errors.
- Distinguish received records, valid decoded records, gaps, and an unavailable source.
- Record Pi monotonic receive times and raw device timer values. SSH buffering
  means receive time is not automatically acquisition time; measure and expose
  synchronization uncertainty rather than claiming exact alignment.
- Add a preparation countdown and a recorded capture-start event. Planned cue
  time, cue delivery, and the user's actual action/confirmation are different events.
- Keep bounded recording, single active capture, cleanup, and rollback verification.
  Save initial remote state and update the deployment manifest before deployment.

Done when different capture intervals have correct time windows, interruption
preserves usable records, and a disconnected source is shown as unavailable.

## Separate acquisition and processing decision (2026-10-13)

Following the user's confirmed CSI/watchdog incident analysis, the preferred
design is to collect data separately for each supported source/link and to keep
acquisition independent of analysis and panel rendering. This is a design
direction and candidate mitigation, not an implemented or validated safety fix.
The goal is reliable evidence for estimating a moving object's position, with
the contribution of each radio link measurable independently.

In the stage 2 follow-up, the user reaffirmed that receipt/storage and decoding
must happen separately from the router. Adopt that as the implementation
direction, with Pi preferred for normal operation and the PC for development,
offline analysis and validation. The current GT path already decodes on Pi/PC;
its remaining coupling is that panel ingestion, decoding and display preparation
share a capture worker. The new boundary must separate these responsibilities
and preserve complete raw input before interpretation.

- Keep a bounded acquisition operation and unchanged raw stream per source,
  with stable source/device/interface/peer identity, firmware/profile, session
  and layout revision. Distinct peers at the same receiver are distinct links,
  not automatically independent physical sensors.
- Use the Pi for receipt/storage and later processing where capacity permits;
  assess the load before choosing the final process layout. Separate capture
  from expensive decoding, visualization and inference. A receiver or writer
  failure must be recorded explicitly, retaining partial data and diagnostics.
- Initially evaluate one supported link per experiment, without deliberately
  filling CSI rings or multiplying monitored peers. This limits experiment
  scope; it is not proof against a driver/watchdog failure. Each new device-side
  method still needs compatibility evidence, a baseline and verified rollback.
- Preserve per-source sequence, device timer, PC/Pi monotonic receive time,
  validity, gaps, drops and timing uncertainty. Later coordinated acquisition
  must retain the separate streams and establish a common time reference before
  combining them. Sequential runs cannot reconstruct one simultaneous movement.
- Compare single-link and combined estimates on independently labeled, held-out
  sessions. Report position/zone errors and failure cases; additional streams
  alone do not guarantee improved accuracy, triangulation or a 3D skeleton.

Separating the user-space collector or moving analysis off the router does not
remove an in-kernel CSI/watchdog fault. Stage 2 must determine whether a safe
source-local export path exists, or whether to use a separately verified
GT-AX11000 peer link or another explicitly evaluated project source. No firmware
patch, new service, deployment or permanent collection is authorized by this
design entry. GT-AX11000 remains the only verified receiver profile today.

### Off-router processing boundary for the next implementation

This is a design contract, not a deployed collector. The October 15
[offline prototype](RAW-PIPELINE.md) implements full input journaling and deferred
processing into separate databases. Its interrupted-journal recovery and legacy
GT SQLite import checkpoint is also complete locally: new outputs preserve the
source and incomplete status, without converting prefixes into full records.
Device readers, concurrent live consumers
and panel integration are still unimplemented:

1. **Source device:** the existing radio/driver produces measurements. If the
   only interface is local Netlink, a minimal compatible reader receives whole
   datagrams and forwards them unchanged over the authenticated LAN transport.
   It does no I/Q decoding, filtering, inference or plotting. It must not choose
   monitor settings automatically, share diagnostics with binary data, or hide
   truncation/receive errors. Moving this reader to Pi cannot make a remote
   kernel's Netlink socket local to Pi.
2. **Pi acquisition/storage process:** retain separate append-only source
   streams before invoking any decoder. A versioned envelope must distinguish
   complete Netlink datagrams from legacy csimond text/payload prefixes, record
   actual received lengths and transport errors, and bind data to the source,
   radio/peer, firmware, operation, configuration and layout revision. Keep
   source receive time and Pi arrival time separate; mark absent clocks and
   unknown loss explicitly. Preserve all received bytes, including an incomplete
   final frame, as failed/partial evidence rather than silently dropping it.
3. **Pi/PC processing worker:** consume committed raw records asynchronously,
   select an explicitly validated profile, and write derived results separately
   with decoder/version provenance. Unknown repeater profiles remain raw-only.
   A decoder failure must not destroy input or cause capture to claim success.
   A slow consumer uses the saved stream; bounded receiver queues must record
   overflow/failure rather than backpressure the radio indefinitely.
4. **Panel/API:** display source health, loss/gap and clock uncertainty, then
   derived signal results when available. Panel refresh, replay or inference
   must not be required to drain the source stream. Existing history stays
   readable; 320-byte prefixes must not be relabeled as full datagrams.

First verify this boundary locally with fragmented input, complete and partial
records, unsupported profiles, interrupted transport, full storage and a slow
decoder. Replayed fixture data are not new RF measurements. Then review the
exact device reader and rollback plan before any source-side execution. No
new network listener, permanent service, database migration or C++ rewrite is
introduced by this decision. Static per-device findings and the remaining
Managed-mode gate are in REPEATER-CSI-RESEARCH.md.

October 15 static refinement: both repeater images send a 16-byte header plus
2,048-byte payload, but header type/sequence are not established as trustworthy
tags/counters. Preserve the full received datagram and actual length; distinguish
source-reader counters from driver counters, and unknown loss from zero loss.
The examined driver loop consumes a ring slot before send success, so a fast
off-router consumer alone cannot guarantee retention. Peer activation and the
AX58 unchecked-lookup concern still block deployment. The detailed evidence is
in [repeater research](REPEATER-CSI-RESEARCH.md#ordinary-add-and-reader-contract-2026-10-1415).
