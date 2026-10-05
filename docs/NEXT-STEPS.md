# Next steps: moving-object localization, map, and CSI replay

Updated 2026-10-05: the user set the work order to incident analysis, bounded
repeater CSI verification, then user-selectable multi-source capture in the
panel. The map remains the reference workspace.

Updated 2026-10-05 after review of the user's research in
[`REPEATER-CSI-RESEARCH.md`](REPEATER-CSI-RESEARCH.md). Repeater `csimon` and
Netlink observations do not prove usable CSI export. The proposed Pi collection
path and a second GT-AX11000 backhaul link are separate, unverified architectures.
Do not repeat the AX58 capture probe; see the documented incident and safeguards.

**Current gate:** RP-AX58 rebooted during the first feasibility probe. All repeater
capture execution is disabled pending incident/compatibility analysis. See
`EXPERIMENTS.md`; the next task is explaining the failure from saved evidence,
not another live probe. Password access to both nodes is now verified.

Offline review found no captured pre-reset failure trace and no verified
collector/driver compatibility contract. A local synthetic test confirmed that
the former buffered reader could lose diagnostic output on timeout. Next:
research exact-firmware compatibility from authoritative documentation/offline
artifacts and design disconnect-resilient diagnostics for review. Do not treat
that research as authorization to repeat a disruptive live experiment.

The prior probe temporarily uploaded and ran a stock GT-AX11000 `csimond` binary
beside `csimon`; its temporary path was absent after reboot. The reboot coincided
with the run, but evidence cannot isolate `csimond`, `csimon`, their interaction,
or another cause. There is no persistent repeater collector to remove now. The
idea that removing one process would have prevented the restart is unverified.

AX56 read-only research is now recorded in `HARDWARE.md` and `EXPERIMENTS.md`:
CSI registration is confirmed, but export and format compatibility are unverified.
Its checked interfaces are upstream clients (`Managed`), and its chip/driver
differs from AX58. Prioritize exact-platform documentation/source research;
in parallel planning, consider a second peer link measured at the existing
GT-AX11000 source. Do not call that alternative an AX56 CSI receiver or assume
either path is ready for a live capture. Repeater probes remain gated on step 1
of the execution order below.
The first usable sensing version must estimate the position of a moving object; a
three-dimensional human skeleton is the ultimate capability priority. The detailed
implementation below is proposed, not already delivered.

## Current checkpoint

- [Apartment map and device placement](HOME-MAP.md) are documented.
- The recorder CLI supports 5–60 seconds; manual panel capture accepts 5–1,800
  seconds. The incremental live ring is implemented; 30-minute endurance and
  full-session replay above 10,000 records still need validation/work.
- The decoder handles the observed ASUS profile; motion was demonstrated in a
  limited experiment. General motion accuracy and location inference are unverified.
- The readable API reference exists at [`API.md`](API.md), the machine-readable
  contract is [`API.openapi.json`](API.openapi.json), and the workspace embeds a
  styled, interactive OpenAPI reference at `/#api-docs`. “Try it out” sends real
  requests to the Pi; writes require its temporary token and may start or delete
  sessions. The sidebar exposes it as `02: API`. `/api/docs` is a compatibility
  redirect. Keep the link discoverable from the workspace and README. The Pi had
  a bootstrap panel and API absent from the local checkout. The new
  [panel iteration](PANEL.md) adds a responsive map/reference workspace, ordered
  routes, session library, real-signal replay/export, timed activity labels,
  and manually controlled bounded capture with live CSI polling. Geometry
  editing, timed route acquisition and a trained location model are not
  implemented. Capture is still manual; there is no always-on recording.
  A new session must not inherit earlier experiment labels.

## Current execution order
1. **Maybe** redo the next-steps (this) file. It is too big, and needs to be redone.
   Also some other problems, such as non-next steps things are here.
2. **Explain the RP-AX58 restart.** Continue offline analysis of saved logs,
   process history, firmware compatibility and the probe timeline. The available
   evidence does not identify `csimon`, the temporary `csimond`, their
   interaction, or another cause. Improve disconnect-resilient diagnostics and
   record either a specific, testable explanation or the remaining evidence gap.
   If the original cause cannot be established, close this gate only with a
   reviewed bounded-test plan that records initial state, limits the probe to
   one change at a time, defines an immediate stop condition, and verifies
   recovery. Do not remove or disable an unknown process based on the current
   hypothesis.
3. **Verify CSI acquisition from each repeater.** After step 1 closes its gate,
   test RP-AX58 and RP-AX56 separately with a bounded, reversible procedure and
   verified rollback. Preserve raw output and per-device format/timing evidence.
   Classify each as supported or blocked. If only one works, use that one. If
   neither works, stop repeating the same probe: document the blocker and choose
   the next concrete experiment from a supported second peer link on GT-AX11000
   or a separately evaluated Pi-based CSI source. Keep the confirmed
   GT-AX11000 source as the working baseline; do not represent an unverified
   source as available or infer triangulation from device placement.
4. **Add source selection and multi-source manual recording to the panel.** For
   each recording, let the user choose any single verified source, a subset, or
   all verified sources. Build the choices from the authoritative device/source
   registry and fixed map placements (currently the project map/device
   configuration; use the database if that becomes its authoritative store),
   with stable source IDs and readable device names. Do not hard-code a list of
   three choices. Record source selection, identity, placement/map revision,
   status, raw data, gaps, and per-source timing. Show selected signals together
   during a route or other manual test and support aligned replay with visible
   timing uncertainty. Unverified devices may be shown as unavailable, but must
   not be selectable as data sources. This enables comparison; it does not by
   itself prove triangulation or localization.
5. **Add password/OAuth(like passkey or hardware keys like fido ones) login on the Pi panel.** Implement and verify local user
   authentication before longer experiment work, and before any server tunnel
   can make the panel reachable outside the home. Protect panel reads and API
   writes; include secure password storage, session handling, recovery and
   revocation, and defenses against repeated login attempts.
6. **Make capture and reference data reliable for experiments.** Preserve
   complete raw records, validate the bounded live ring over a 30-minute run,
   handle pause timing and active-segment countdown correctly, and validate
   long-session replay. Add versioned map/reference corrections and actual map
   snapshots; confirm room names and one physical map length. Define the exact
   retention period and an auditable export/cleanup policy. Automatic cleanup
   must never silently delete raw CSI or an active session. See [PANEL.md](PANEL.md).
7. **Collect a small repeatable labeled dataset** across selected fixed points,
   stillness, arm movement, walking, stops, empty-room intervals and cross-room
   motion. Preserve uncertainty and changed device/furniture conditions. Keep
   whole later sessions out of model tuning.
8. **Evaluate localization independently.** Start with held-out room/zone
   estimates and report confusion, false/missed motion, delay and insufficient
   data. Proceed to continuous position only when the evidence supports it.
9. **Implement and validate a moving-object point on the map** against independently recorded
   reference positions. This is the first usable sensing deliverable and the
   gate for the next two milestones.
10. **Design the tunnel implementation and cryptography** after point tracking.
11. **Implement the tunnel** between the Pi and server.
12. **Add the tunnel functions to the panel.** Include a control to refuse
    Internet access while leaving the tunnel connected. Direct access to the Pi
    from the home LAN **always, even with the Internet access** remains available.
13. **Launch the tunnel and enable Internet access** after steps 9–11. Require
    the Pi panel login from step 4.
14. **Implement and validate 3D skeleton reconstruction** after moving-point
   tracking. Treat it as a separate capability with its own evidence and quality
   criteria; a motion score or point estimate is not pose recognition.
15. **Rewrite the full system in C++ and prepare its installers** after reviewing
    the Python implementation, fixing the bugs found, and making any useful
    small improvements. Then migrate the whole implementation when the user
    considers it ready. This includes low-level collection and decoding,
    processing, Pi/server services and API, and the native PC application that
    consumes the API. Target Windows, macOS and Linux for the PC client. Make
    installation packages for the Pi, server and PC; do not create a native
    phone application or phone installer. Phone access stays in the browser and
    the panel must be responsive and usable on a phone. Preserve formats and
    behavior through parity/regression checks and provide upgrade, recovery,
    uninstall and rollback procedures. The user's
    [DJI-Link repository](https://github.com/Kolya080808/DJI-Link) is a reference
    for the PC packaging approach only, not a requirement to
    copy its implementation or architecture wholesale as it is another project.

## Stage 2: verify each repeater's CSI source

The October 5 work identified advertised CSI Monitor support and a reboot during
the AX58 probe. The current assessment and safe follow-up are in
[`REPEATER-CSI-RESEARCH.md`](REPEATER-CSI-RESEARCH.md). Live capture remains
blocked until the incident gate in step 1 is closed. Then use this bounded
procedure independently for each node.

Check RP-AX58 and RP-AX56 separately. The September 29 inventory already records
their addresses, firmware and interfaces; map placement is approximate. Both
advertised `csimon`, but no standalone `csimond` was found and neither has a
verified capture. This is the starting evidence, not proof of usable CSI.

October 5 checkpoint: Pi access succeeded; both repeaters rejected the lab RSA
key but accepted the supplied administrator password. Authenticated read-only
inspection succeeded. The first AX58 probe coincided with a reboot and produced
no saved CSI. Access is no longer the blocker: incident analysis is the current
gate, and capture execution is disabled. See `HARDWARE.md` and `EXPERIMENTS.md`.

1. Confirm Pi availability with the user before connecting. Use existing access
   credentials and pinned host keys; do not install keys or change SSH settings
   to bypass an access problem.
2. Inspect current state without changes: device/firmware identity, relevant
   radio interfaces and associated peer identities, monitor state, existing
   collectors, and available userspace CSI facilities. Establish which MAC
   belongs to which radio/link; management IP and map placement alone do not
   identify the measured path.
3. Decide the extraction method from that evidence. Do not assume the main
   router's binary, Netlink protocol or decoder also works on either repeater.
   Before any temporary upload, process or monitor change, save exact initial
   state in the ignored deployment manifest, extend `scripts/rollback.py`,
   document restoration in `ROLLBACK.md`, and pass the rollback plan check.
4. Run one bounded 5–10-second probe at a time where supported. Preserve the
   complete available raw output and diagnostics, source/interface/peer identity,
   capture parameters and timing. Verify cleanup against the recorded initial
   state immediately afterward. No firmware change, permanent setting, service
   installation or always-on collection belongs to this stage.
5. Repeat successful probes. Report received records, lengths, freshness,
   observed cadence, errors and any measurable loss; mark unknown loss explicitly.
   Validate the format independently for each source before decoding or adding
   it to the panel. A working command or nonempty output is insufficient.

Done when each repeater has either repeatable raw CSI acquisition with verified
cleanup and documented format limits, or an evidence-backed blocking condition
and a concrete next experiment. If both work, proceed to coordinated short
captures and measure synchronization uncertainty before localization trials.
If only one or neither works, assess available main-router peer links and record
the revised experiment scope. Multiple sources do not by themselves establish
triangulation or recoverable human coordinates.

The remaining sections are the broader sensing roadmap, not a claim that all
recording, synchronization and localization requirements are delivered.

## First usable sensing deliverable

A position estimate for a moving object over time, evaluated against independently
recorded reference positions. A local panel should let the user select a point on the apartment map, record a
short experiment, attach timed activity labels, and replay that same session
with the map and CSI changes aligned. A first experiment can use one fixed
position with alternating stillness and arm movement; routes follow once the
timing and saving work reliably.

### 1. Select verified CSI sources for a manual recording

Implement the source selector only after repeater capability has been classified
in stage 2. Populate it from the project's authoritative device/source registry
and fixed map placement, with stable source IDs and user-readable names. The
current authoritative placement is the project map/device configuration, not a
separate database; if that changes, read from the new authoritative store.
Allow a manual session to select one source, any subset, or all verified sources.
Availability follows verified acquisition support, rather than the presence of a
device in the map. An unverified device can be labelled unavailable but cannot
produce a selectable capture source.

Persist the selected source set and map/device revision with the session. During
a route or other test, show the selected CSI streams together and retain separate
raw records, receive/device times, gaps and errors for each source. Replay them
on a shared timeline while exposing clock uncertainty and missing data. Preserve
single-source and map-only views. Treat the feature as an experiment for source
comparison; multi-source capture alone does not validate triangulation.

Done when a user can choose any supported combination for a bounded manual
session, inspect each source's status and trace, and reopen the session with the
same source identities and map placement.

### 2. Make the existing map usable for experiments

- Load map geometry and device placements together, retaining their source hashes.
- Allow the user to name rooms, place experiment points, and draw planned routes.
- Preserve the supplied scan and retain corrections as versioned edits.
- Display device models and approximate heights; record placement changes so
  captures from different layouts are not silently combined.
- Confirm one physical length to check scale and mark obvious scan mistakes.
  Unknown north and approximate furniture do not block initial annotation.

Done when a point or route can be saved, reopened, and referenced by a session
in the same coordinate system.

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

### 4. Connect the panel and API

The panel and scripts should use the same API. The current panel already exposes
the first read/write API version (`/api/map`, `/api/points`, `/api/routes`,
`/api/sessions`, `/api/sessions/{id}/measurements`, annotations, raw export,
manual capture control and session deletion). Automatic cleanup and retention
policy remain to be defined. Proposed operations:

| Resource | Operations |
|---|---|
| Maps | Read geometry/devices; save named points and routes |
| Sessions | Start, stop, list, inspect state and recording configuration |
| Measurements | Read samples, signal metrics, validity, cadence, and gaps |
| Annotations | Save/correct position, action, and time interval for a session |
| Replay/export | Retrieve aligned records, annotations, and map revision |

Show source/device identity, connection state, last valid sample age, actual
sample rate, gaps, decode errors, raw signal metrics, motion score/threshold,
capture state, and history. Do not label a motion score as a probability or
equate no motion with an empty room. API writes that control recording require
local access control. Any remote-access feature is a separate milestone after
validated moving-point tracking; see the gated server configurator below.

Each annotation should retain session ID, map revision, point/route coordinates,
activity, start/end time, time basis, author/source, timing uncertainty, and
whether it is a planned instruction or an observed action. Interpolated positions
between confirmed waypoints must be labeled as estimates.

Store reference annotations separately from model predictions. Preserve raw CSI
so future processing does not require repeating every experiment.

Done when a saved session can be reopened with its original map, device layout,
reference labels, and signal trace, and exported through the API.

### 5. Collect a small repeatable dataset

Start with points in R08, R07, and R02 after the user selects their exact locations.
Use separate bounded sessions and repeat each condition:

- Stillness and arm movement at a fixed point.
- Walking between marked points, including stops and changes of direction.
- An empty apartment/room baseline with the user's exit interval labeled.
- Motion elsewhere in the apartment to test cross-room confusion.

Record other occupants, doors, facing direction, changed furniture/devices, and
unusual network activity. Vary route order, speed, and stops. Keep whole later
sessions, preferably from another day, out of threshold/model tuning. Neighboring
frames from one recording must not be split randomly into train and test sets.

Done when recordings and labels can be replayed and independently checked,
including transitions and uncertain intervals.

### 6. Evaluate simple location estimates before expanding scope

First compare room/zone classification against simple baselines on held-out
sessions. Report confusion between zones, false motion events per hour, missed
motion, detection delay, and the fraction of time with insufficient data.
If testing continuous positions later, report distance errors and uncertainty.
The runtime predictor must not receive the test's reference route or cue sequence.

Use the earlier repeater feasibility results when choosing the sensing sources.
If observations do not distinguish zones reliably, investigate additional
supported peer links on the ASUS or revisit the documented repeater blockers.
Identify the current monitored peer before treating its link as a
known path on the map. Device placement does not establish a working sensor.

## After point tracking: server tunnel steps before skeleton work

After a moving object's estimated point is displayed on the map and validated
against independently recorded reference positions, complete these steps before
beginning three-dimensional skeleton reconstruction:

1. Design the tunnel implementation and cryptography.
2. Implement the tunnel between the Pi and server.
3. Add the tunnel functions to the panel, including a control that refuses
   Internet access while leaving the tunnel connected. Direct access to the Pi
   from the home LAN remains available.
4. Launch the tunnel and enable Internet access, using the Pi panel login.

Done when Internet access can be enabled or refused from the panel without
restarting the tunnel, direct home-LAN access remains available, and the Pi
panel login protects Internet access.

The map supplies reference geometry and labels. It does not by itself improve
RF measurements or establish that a person's exact position can be recovered.
Three-dimensional skeleton reconstruction is the ultimate capability priority and
depends on first validating sensing and moving-object localization. Set up server
access after point tracking and before skeleton work.
Offline repeater compatibility research comes before any newly reviewed live
collection. Multi-source capture and synchronized replay are stage 3; triangulation,
firmware changes, hardware purchases, and permanent background capture require
later evidence and review;
the 30-minute bounded workflow must be validated before any always-on mode.

## Stage 4: add password login to the Pi panel

Implement this stage after the multi-source panel selector and before the longer
data-collection/localization stages. It must be complete before configuring the
server tunnel after point tracking. The current panel has no user login. Keep
direct panel/API access within the home LAN available after login is added.

Start with a local username-and-password login. Store only a suitably slow,
salted password hash; use protected sessions, CSRF defenses for writes, account
recovery and revocation, and controls that limit repeated failed attempts.
Passkeys/security keys can be considered as a later additional login method.
Keep the panel's `X-Panel-Token` separate: it is not user authentication. Do not
send project data, device credentials, captures, or source records to an identity
provider.

Done when explicitly enrolled household users can authenticate, a lost
credential can be revoked and recovered safely, and unauthenticated requests
cannot read panel data or perform API actions. Verify locally and on the
authorized Pi before proceeding to the public server tunnel; record the access
toggle and a tested rollback.

## Open questions for the next iteration

- What are the actual names of R01–R08, and which scan features need correction?
- Where should the first fixed experiment points be placed?
- Which physical device corresponds to the monitored peer MAC?
- Is the estimated router height consistent with a physical measurement?
- How will action timing be verified: confirmations, recorded cues, or optional
  calibration video? What timing error is acceptable for the intended task?
- What exact retention period within the several-week log-retention requirement and
  what cleanup/export policy should be implemented before moving beyond bounded sessions?

These are items to resolve during implementation and experiments, not reasons
to postpone the initial map annotation workflow.
