# Next steps: panel, API, continuous sensing, and repeater CSI

Updated 2026-10-02 from the user's task breakdown. The current panel and API
are a functional bootstrap, not the finished product. The order below is the
working priority for the project.

## Current checkpoint

- [Apartment map and device placement](HOME-MAP.md) are documented.
- The collector supports bounded 5–60 second sessions on the documented Pi setup.
- The decoder handles the observed ASUS profile; motion was demonstrated in a
  limited experiment. General motion accuracy and location inference are unverified.
- The panel and shared API are deployed on the Pi, but both are still rough
  drafts and need a complete product pass.
- Capture from the panel/API is disabled while the continuous-recording
  retention, export, and cleanup design is being finalized.
- Repeater CSI access is not demonstrated. The next sensing investigation must
  establish whether the ASUS repeaters can provide usable CSI before building
  the zone dataset and location evaluation around them.

## Product direction

The intended system is a camera replacement for apartment occupancy and
activity observation, not merely a short bounded experiment tool. It should
continuously observe whether somebody is in the apartment, reconstruct a
human skeleton from Wi-Fi sensing, show what the person did and how they moved,
and retain recordings for approximately two or three weeks. The final runtime
should operate without cameras; cameras may be used only for calibration,
training, or validation labels.

## Priority task breakdown

### 1. Fully improve the panel

The current web panel is only a draft. Make it a complete, reliable interface
for maps, devices, points, routes, sessions, recording state, annotations,
replay, export, errors, and history. Keep the phone browser as a supported
client and preserve a usable dark interface. This includes proper editing,
validation, responsive layout, loading/error states, and a clear distinction
between reference annotations and future model predictions.

### 2. Design continuous observation and retention

Replace the temporary bounded-capture mindset with a safe always-on observation
design. Define how the Pi records continuously, rotates data, exports sessions,
recovers after power/network failure, and retains roughly 2–3 weeks without
filling storage. Specify what raw CSI, decoded data, skeleton output, events,
and metadata are retained, and how old data is archived or deleted. Implement
this only after the policy and storage budget are measured.

### 3. Fully improve the API

The current HTTP API is also only a draft. Expand and stabilize the contract
for the panel, a phone client, and a PC program. It must cover map revisions,
devices, points, routes, continuous observation, sessions, measurements,
annotations, replay, export, retention, errors, source availability, and
authentication/access control for recording operations. Keep the OpenAPI
description synchronized with the implementation.

### 4. Implement the recording and session behavior described by task 3

Implement the API's session lifecycle and collector behavior: continuous
recording, start/stop/recovery states, elapsed-time processing, partial capture
preservation, receive and device timestamps, gaps, decode validity, source
availability, synchronization uncertainty, and safe cleanup. Do not enable
unbounded writes before the retention/export policy from task 2 is implemented.

### 5. Implement the panel behavior described by task 1

Use the improved panel as the operational client for task 4: live observation
status, history, map and device layout, reference annotations, skeleton/event
replay, export controls, and retention visibility. The phone browser and PC
program must be able to use the same API without panel-specific behavior.

### 6. Collect a repeatable dataset after repeater CSI is understood

Only after repeater CSI access is established, collect data at selected points
in R08, R07, and R02. Include stillness, arm movement, walking, stops, changes
of direction, an empty-room interval, and motion elsewhere in the apartment.
Keep complete later sessions held out from tuning and do not split neighboring
frames from one recording between train and test.

### 7. Evaluate zones and location after task 6

Compare room/zone classification with simple baselines on held-out sessions.
Report confusion between zones, false events per hour, missed motion, detection
delay, insufficient-data time, and uncertainty. Continuous position estimates
come later and must be evaluated without providing the test route to runtime.

### 8. Expand the sensing model after tasks 6–7

Only after the repeater-backed dataset and zone evaluation are understood,
investigate richer location estimates and the conditions needed for skeleton
reconstruction. The map is reference geometry; it does not prove RF
localization, triangulation, joint recognition, breathing, or heart rate.

### 9. Investigate CSI access on the repeaters first

This is the first sensing investigation. Determine whether RP-AX56 and RP-AX58
expose a usable userspace CSI stream, which peer/link each capture represents,
whether records can be collected without changing persistent configuration, and
whether the TP-Link device is relevant. Record exact firmware, interface,
peer identity, packet loss, format, cleanup, and rollback evidence. The mere
presence of `wl csimon` is not sufficient evidence of usable repeater CSI.

## Open questions for the next iteration

- What are the actual names of R01–R08, and which scan features need correction?
- Which physical device corresponds to the monitored peer MAC?
- Is the estimated router height consistent with a physical measurement?
- How will action timing be verified: confirmations, recorded cues, or optional
  calibration video? What timing error is acceptable for the intended task?
- What storage budget and export format support continuous two-to-three-week
  retention on the Pi?
- What repeater interfaces and peer links can provide usable CSI?

Task 9 is the immediate research priority. Tasks 1–5 are product and data
pipeline work that can proceed locally, while tasks 6–8 depend on the repeater
CSI investigation and should not be treated as validated until that dependency
is resolved.
