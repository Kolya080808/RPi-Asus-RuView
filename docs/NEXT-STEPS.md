# Next steps: moving-object localization, map, and CSI replay

Updated 2026-10-04 after inspecting the Pi. The map-first direction is agreed.
The first usable sensing version must estimate the position of a moving object; a
three-dimensional human skeleton is the ultimate capability priority. The detailed
implementation below is proposed, not already delivered.

## Current checkpoint

- [Apartment map and device placement](HOME-MAP.md) are documented.
- The collector supports bounded 5–60 second sessions on the documented Pi setup.
- The decoder handles the observed ASUS profile; motion was demonstrated in a
  limited experiment. General motion accuracy and location inference are unverified.
- The Pi had a bootstrap panel and API absent from the local checkout. The new
  [panel iteration](PANEL.md) adds a responsive map/reference workspace, ordered
  routes, session library, real-signal replay/export, timed activity labels,
  and manually controlled bounded capture with live CSI polling. Geometry
  editing, timed route acquisition and a trained location model are not
  implemented. Capture is still manual; there is no always-on recording.
  A new session must not inherit earlier experiment labels.

## Immediate follow-up after panel review

1. Collect user feedback on the map, layout, reference-point and replay workflows.
2. Add reference/annotation correction with revision history and actual map
   snapshots; current hashes identify sources but historical capture layouts
   remain unknown. Confirm room names and a physical map length.
3. Agree the exact log retention period and cleanup/export policy, then complete
   the bounded collector/timing work below before enabling recording in the panel.
4. Continue controlled labeled experiments and evaluate localization independently.
5. After CSI access from at least two repeaters is demonstrated, add coordinated
   collection: start either source independently or both in one session, preserve
   per-source receive/device times and source identity, and show synchronized
   signal traces side by side. The panel should support one graph, several CSI
   graphs, all available graphs, and a map-only view of reference/predicted points.
   This is the prerequisite experiment for understanding whether triangulation
   and a point on the map are feasible; device placement alone is not evidence
   of triangulable paths.
6. Add bounded 30-minute recording sessions with a real-time CSI view. Keep the
   live trace and storage segmented into inspectable 30-minute windows, retain
   raw records, gaps and source availability, and allow later replay of each
   window with CSI-only, map-only, or combined views. A future live map may show
   a moving-object estimate only after that estimate is validated against
   separately recorded reference points; a quiet graph must not be treated as an
   empty room.
7. Define and implement automatic cleanup for the Pi history and diagnostics:
   choose the retention period, show the projected space that will be reclaimed,
   support export/archive before deletion, never delete an active session, and
   keep the cleanup auditable and reversible where possible. Manual deletion is
   already available in the panel; automatic cleanup must not remove raw CSI
   silently or use the database size limit as its only policy.

The remaining sections are the broader sensing roadmap, not a claim that all
recording, synchronization and localization requirements are delivered.

## First usable sensing deliverable

A position estimate for a moving object over time, evaluated against independently
recorded reference positions. A local panel should let the user select a point on the apartment map, record a
short experiment, attach timed activity labels, and replay that same session
with the map and CSI changes aligned. A first experiment can use one fixed
position with alternating stillness and arm movement; routes follow once the
timing and saving work reliably.

### 1. Make the existing map usable for experiments

- Load map geometry and device placements together, retaining their source hashes.
- Allow the user to name rooms, place experiment points, and draw planned routes.
- Preserve the supplied scan and retain corrections as versioned edits.
- Display device models and approximate heights; record placement changes so
  captures from different layouts are not silently combined.
- Confirm one physical length to check scale and mark obvious scan mistakes.
  Unknown north and approximate furniture do not block initial annotation.

Done when a point or route can be saved, reopened, and referenced by a session
in the same coordinate system.

### 2. Add session timing and the minimum collector fixes

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

### 3. Connect the panel and API

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
local access control; no public deployment is proposed.

Each annotation should retain session ID, map revision, point/route coordinates,
activity, start/end time, time basis, author/source, timing uncertainty, and
whether it is a planned instruction or an observed action. Interpolated positions
between confirmed waypoints must be labeled as estimates.

Store reference annotations separately from model predictions. Preserve raw CSI
so future processing does not require repeating every experiment.

Done when a saved session can be reopened with its original map, device layout,
reference labels, and signal trace, and exported through the API.

### 4. Collect a small repeatable dataset

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

### 5. Evaluate simple location estimates before expanding scope

First compare room/zone classification against simple baselines on held-out
sessions. Report confusion between zones, false motion events per hour, missed
motion, detection delay, and the fraction of time with insufficient data.
If testing continuous positions later, report distance errors and uncertainty.
The runtime predictor must not receive the test's reference route or cue sequence.

If observations do not distinguish zones reliably, investigate additional
supported peer links on the ASUS and then repeater CSI access as separate
experiments. Identify the current monitored peer before treating its link as a
known path on the map. Device placement does not establish a working sensor.

The map supplies reference geometry and labels. It does not by itself improve
RF measurements or establish that a person's exact position can be recovered.
Three-dimensional skeleton reconstruction is the ultimate capability priority and
depends on first validating sensing and moving-object localization. Coordinated
multi-repeater collection, synchronized multi-graph replay, triangulation, firmware
changes, hardware purchases, and permanent background capture are later stages;
the 30-minute bounded workflow must be validated before any always-on mode.

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
