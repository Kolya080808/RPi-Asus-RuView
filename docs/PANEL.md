# Local sensing workspace

The panel runs on the Pi at `http://192.168.50.100/` using the existing
`ruview-lab-panel.service`. This service was already enabled when inspected on
2026-10-04; this update preserves its unit, port, user, and enablement state.
The older bootstrap was present on the Pi but absent from the local repository.
Its sources were recovered before implementing this version.

## Available workflows

- **Apartment map:** vector floor-region geometry in the scan coordinate frame,
  device inspection, zoom/reset, named reference points, and ordered routes
  through saved points. R01 is rendered as the rectangular room footprint from
  the 3D model; curved scan-boundary artifacts and internal triangulation seams
  are not shown as room walls. The scan itself and device positions are not edited.
- **Manual capture, sessions & replay:** bounded Pi recording from the panel,
  live CSI graph, pause/resume/stop controls, separate deletion of the current
  capture and the session selected in the library,
  paginated history, page-local search/status filters,
  normalized amplitude change and causal 1-second EMA, playback/scrubbing,
  actual cadence, decoding errors and timing gaps, activity intervals and raw export.
- **Devices & system:** documented capabilities and approximate placement,
  database size, free storage, and map/device revision hashes.

The header theme button switches between light and dark mode and stores the
choice locally in the browser.

The interface uses local HTML, CSS and JavaScript with no CDN, build step,
analytics, external fonts, or additional Pi packages. The backend is Python's
standard library. New modules are `src/web_panel.py` (HTTP API and metadata) and
`src/panel_signal.py` (read-only replay). Existing decoder and live-signal logic
are reused; the collector and legacy motion-event tables are not modified.

## Honest interpretation

Recording is manual and bounded. The panel can start one capture at a time for
5–1,800 seconds, stream the observed CSI trace into the session, pause by
safely stopping the temporary router monitor segment, resume with a new segment,
stop, and delete a finished session with its raw records and annotations.
There is no automatic background capture. The live endpoint reports time since
the Pi processed the last valid record, not RF acquisition age.
`Panel connected` means the HTTP API responded, not that a CSI source is online.
Refresh retrieves a new snapshot.

The map shows floor-region outlines, not surveyed walls; furniture is omitted
in this vector view. Scale is unverified, north is unknown, and R01–R08 are not
confirmed room names. Points are user references and routes are plans. Neither
is a detected person or trajectory. Coordinates inside the map bounding box
are accepted; region selection is manual and does not prove physical walkability.

Replay time uses the provisional microsecond-like device timer and begins at
the first valid record. EMA resets after decoding errors or gaps exceeding
1.8 times the requested capture interval. Timer resets/repeats make replay
unavailable instead of inventing a timeline. A quiet signal is not evidence
of an empty room. No calibrated detection threshold or probability is shown.
Raw export remains available even if the timeline cannot be reconstructed.

## Storage and compatibility

Existing SQLite table layouts are unchanged. GET requests do not update records.
Metadata writes append points, routes and session annotations. Explicit session
deletion removes its records and annotations; there is no automatic retention
or record migration.
New metadata uses a `ruview-panel-v2` JSON envelope in the existing `notes`
column. API responses unwrap human notes into `notes` and provenance into
`context`. Plain legacy notes remain readable with `context: null`.

Points retain geometry/device source hashes. Routes snapshot their ordered
points. Activity labels retain interval, source, planned/observed distinction,
provisional time basis, optional uncertainty, map hashes and the reference point
snapshot. Blank uncertainty means unknown, not zero. Historical captures did
not save their map or receive times: `map_at_capture` is explicitly null.
The currently selected reference map must not be described as their original
layout. Hashes identify reference versions but are not a geometry revision archive.

The API exports session metadata, raw bytes and annotations as JSON. Replay and
export are bounded to 10,000 records per request; use the collector CLI for
larger sessions. History pages contain at most 100 sessions. Existing raw CSI,
session logs and metadata are retained. Point/route editing, annotation
corrections, room names, and versioned geometry editing are follow-up work.

## API and access

See [API.openapi.json](API.openapi.json), the raw `/api/openapi.json` contract,
and the embedded Swagger UI at `/#api-docs`. Both links are available from the workspace.
Swagger UI assets are bundled locally in `web/` so the documentation works without a
third-party CDN. “Try it out” submits real requests to this Pi; writes require
the temporary API token, and some operations can start a capture or delete a
session. The legacy `/api/docs` address redirects into the workspace.
The API is for the trusted home LAN, with no public hosting or user login.
Writes require the current `write_token` returned by `/api/health`, sent as
`X-Panel-Token`, plus JSON content type. Browser Origin must match the panel.
The token changes on server restart: refresh before saving again.
This prevents unsolicited cross-origin writes; it is not user authentication
and does not restrict another authorized LAN client. Do not expose the port publicly.

The server serves only explicit assets and endpoints. Raw credentials and
diagnostic capture logs are not HTTP resources. No token, request body or raw
record content is logged. Expected invalid requests return structured errors;
unexpected server failures retain a traceback in the service journal.

## Local development and checks

Use a disposable database; do not point UI tests at operational history:

```powershell
python src/web_panel.py --port 8080 --history recordings/panel-test.sqlite3
python -m unittest discover -s tests -v
python -m compileall -q src scripts tests
node --test tests/test_panel_ui.cjs
```

An absent local database is initialized with the existing schema. No fake
measurements are displayed when it is empty. UI write tests use a separate local
copy or generated fixtures, never operational sessions on the Pi.

## Operation and rollback

```powershell
python scripts/deploy_panel.py --prepare
python scripts/rollback.py --panel-only --check
python scripts/deploy_panel.py --apply
python scripts/rollback.py --panel-only --check
```

Preparation reads remote state and stores exact file backups and an operation
entry in the ignored `deployment.json`. Application stops only the known existing
panel service, takes a local history copy, uploads the planned panel, map and
documentation files,
verifies hashes, and restarts that same service. Record counts and a digest over
all raw records must remain unchanged. See [ROLLBACK.md](ROLLBACK.md).

View diagnostics with `journalctl -u ruview-lab-panel.service --since today`.
INFO logs cover startup and successful metadata writes; routine GETs are DEBUG.
This update does not alter global journald settings or implement log deletion.
The requested several-week retention period still needs an exact duration and
a policy spanning both journal/capture logs and session-history diagnostics;
raw CSI must remain outside that cleanup. Manual deletion is available for
experiments; there is no automatic cleanup.

## Verification on 2026-10-04

- `python -m unittest discover -s tests -v`: 22 tests passed, including the
  pre-existing parser/signal checks, three capture intervals, invalid inputs,
  API round trips, raw-byte export, annotation validation, cross-origin write
  rejection, pagination and rollback against a disposable remote-filesystem model.
- `python -m compileall -q src scripts tests
node --test tests/test_panel_ui.cjs`: passed. The generated SVG map
  artifacts contain formatter trailing whitespace from the floorplan generator;
  this is an existing generated-file limitation, not a runtime error.
- Browser tests against a separate local history copy: create/reopen two points,
  save an ordered route, open a real capture, play/pause and save an activity
  label. No console errors. At the 390 px mobile viewport, the rendered document
  had no horizontal overflow. No test metadata was written to operational history.
- Deployment `20261004T201213Z-29ab70`: the initial seven file checksums verified. The
  existing service remained enabled and became active with API v2; no restart
  loop or server errors appeared in the journal after the update.
- Deployment `20261004T202640Z-3c8635`: the theme assets, rectangular R01/R04/R08
  geometry and renderer update were uploaded; service restart, file hashes and
  unchanged raw-history digest were verified. Browser checks confirmed both
  theme states, the rectangular R01 polygon, no horizontal overflow and no
  console errors.
- Deployment `20261004T203257Z-ff93e8`: served the missing `/theme.css` asset
  through the explicit static-file allowlist; the light/dark computed colors and
  stylesheet response were verified on the Pi, and raw history stayed unchanged.
- Deployment `20261004T204851Z-fac3ff`: manual capture controls, live polling,
  pause/resume/stop and session deletion were uploaded; API smoke testing on the
  Pi verified running → paused → running → stopped and deletion, returning the
  database to its original seven sessions and 1,881 raw records.
- Deployment `20261004T205207Z-84bf2d`: final capture implementation and panel
  documentation were applied after rollback preflight; service health, API v2,
  seven sessions and 1,881 raw records were verified unchanged.
- Deployment `20261004T205307Z-a1e1e0`: refreshed the device-page wording for
  manual versus always-on recording; service and raw-history checks passed.
- Deployment `20261004T205455Z-0d619a`: selecting any session now immediately
  enables the delete control; service and raw-history checks passed.
- `python scripts/rollback.py --panel-only --check`: passed both before and after
  deployment. Actual rollback was exercised on the disposable filesystem model,
  not applied to the running Pi after the successful upgrade.
- All seven Pi sessions opened through the API: five contain 1,881 valid records
  total; the failed and interrupted sessions contain none. Replay requests in
  one LAN pass took about 0.01–0.88 s (not a performance guarantee). Raw exports
  were independently unpacked as 112 signed values; `sqrt(sum(v*v)/56)` matched
  every reported amplitude RMS. This checks replay/export arithmetic, not the
  physical CSI interpretation or motion/localization accuracy.
- Before/after database counts, raw-record digest and SQLite quick-check match.
  Browser verification on the Pi confirmed the real 592-record trace, explicit
  interrupted-session empty state and working device/map navigation.

The private verification report and screenshots are under `recordings/`.
The initial map/replay-only verification did not start a capture. Later capture
checks are listed above; no persistent router settings, log cleanup or model
evaluation were introduced.

## Capture controls fix (2026-10-05)

The client previously replaced its capture object with a response lacking a
top-level ID, then requested `/api/captures/undefined`. This broke subsequent
status updates, the live graph, and deletion of the current recording. Snapshots
now carry a stable ID and lifecycle flags, and the client also derives identity
from `session.id`. Polling is serialized, ignores obsolete responses, and
resumes when an active capture is recovered on page reload. Signal errors remain
visible without disabling lifecycle controls. Gaps break the live trace.

The upper **Delete session** belongs only to the current capture; it is available
after Pause or Stop without library selection. The lower **Delete session**, next
to raw export, belongs only to the library selection. Deletion asks for confirmation.
A paused capture is stopped and joined before its rows are removed; a timeout
retains the data. Deleting the selected session clears its replay and labels.
Node's built-in test runner checks client polling and control regressions without
adding packages to the Pi. The local browser fixture uses a separate synthetic
database and does not demonstrate actual RF acquisition.

Verification of this fix:

- `python -m unittest discover -s tests -v`: 25 passed.
- `node --test tests/test_panel_ui.cjs`: 5 passed. `node --check web/app.js`,
  `python -m compileall -q src scripts tests`, and `git diff --check` passed.
- Browser on the disposable local synthetic fixture: Start, growing live path,
  Pause, reload, Resume, Stop, and current delete availability without a library
  selection passed. Local HTTP deletion of a paused fixture joined its worker
  and left zero sessions. Operational history was never used for deletion tests.
- Operation `20261005T102745Z-8897cc`: all ten file hashes, service state,
  SQLite integrity and unchanged original history digest passed. Narrow rollback
  inspection passed before and after deployment; restore was tested on fixtures.
- Real Pi/browser verification: session `8b3b0071-abd1-4959-b013-304bc192d229`,
  30-second bound at 100 ms, captured 299 valid records, zero decoder errors and
  zero detected timing gaps; device-relative duration 29.805493 s, median cadence
  100.018 ms. A running snapshot showed 166 records; the live SVG grew to 298
  plotted values and remained visible after completion. No browser console errors.
  The real pause click was attempted after the bounded capture had already ended;
  pause/resume/stop transitions for this change were verified on the local fixture.
- The current delete control was enabled with no library selection. Selecting a
  different saved session enabled the lower control independently. No Pi session
  was deleted; all seven original sessions plus the new test session remain.
- Router read-only inspection before/after: monitor disabled, empty peer list,
  no csimond process. Transfer counter increased by 300, ACK failures stayed at
  35, overflow stayed at zero. 299 saved versus 300 transferred is not lossless.
- Existing panel collection stores only each record's first 320 bytes through
  LiveParser, unlike the older complete 2,048-byte collector. The summary therefore
  reports 299 incomplete records even though all useful CSI prefixes decode. This
  pre-existing raw-tail retention limitation was not changed in the UI fix.
- Private evidence and screenshots: `recordings/panel-ui-check/`; router baseline
  and result also reside in the ignored deployment manifest's verification entry.

Remaining limitations: full replay still has a 10,000-record limit; a device timer
reset or pause exceeding the supported timer jump can make signal replay unavailable
while controls remain accessible. The remaining-time value is a segment budget,
not a continuously updated countdown. The follow-up below adds bounded live
streaming; long-run validation, complete raw-tail retention and verified timing
across pauses still need collector work.

## Live refresh follow-up (2026-10-05)

The user reported that the preceding graph still appeared in 30-second updates.
The previous verification proved a growing trace but did not measure frame latency.
The live browser path now requests incremental samples at a target 100 ms interval,
matching the desktop viewer refresh target. Processing occurs once per received
record; a 600-point ring replaces repeated full-history decode and transfer. The
chart displays the latest 60 seconds and a stale-data warning after two seconds.
No 30-second refresh timer exists in the client. Actual Pi timing is reported below;
this change does not guarantee transport latency or alter raw storage, collection
settings, pause semantics, or the two deletion controls.

Measured verification for operation `20261005T104835Z-2915cd`:

- `python -m unittest discover -s tests -q`: 27 passed; `node --test
  tests/test_panel_ui.cjs`: 6 passed. Compilation, JS syntax and diff checks passed.
  New regressions cover cursor deltas, ring overflow, cache recovery, and avoiding
  full replay on the live endpoint even after 11,000 sequence numbers.
- Real 30-second/100 ms Pi capture `86324778-b0d3-4238-9703-21310d44c9e2`:
  first valid API data at 1.669 s after request start; 190 nonempty updates,
  median update interval 0.135 s, maximum 1.696 s. Median HTTP response 0.0334 s,
  maximum 1.5946 s. 299 records retained. This includes concurrent browser loading;
  the 100 ms interval is a refresh target, not a latency guarantee.
- Independent browser-started capture `7623de1c-d0fa-4bf8-afd7-17304526f081`:
  a series of 250 read-only SVG observations found the first plotted line after
  1.538 s and 24 distinct updates, median interval 0.115 s, maximum 0.180 s.
  Browser Stop completed; 35 records retained. No browser console errors.
- Both tests retained their raw data. Router state after each: monitoring disabled,
  empty peer list, no csimond process; ACK failures remained 35, overflows zero.
  Transfers were 300/36 versus saved records 299/35: capture is not lossless.
- Before/after update file hashes, service settings, DB integrity and raw-history
  digest matched. Narrow rollback inspection passed before and after deployment.
  Original files and history recovery copy are in the manifest's exact backup folder.
- Private timing series, reports and live screenshot: `recordings/panel-live-latency/`.

This verifies live delivery/rendering in short tests, not 30-minute endurance,
RF acquisition-to-screen latency, or localization accuracy. Full replay retains
its 10,000-record limit; the live ring no longer depends on it. Existing timer-reset,
raw-tail storage and pause-timeline limitations are unchanged.

## Initial standalone Swagger UI deployment (2026-10-05, superseded)

The panel now serves Swagger UI at `http://192.168.50.100/api/docs`. The home
workspace sidebar has a separate `02: API` section linking to it. Swagger UI
5.33.1 and its Apache-2.0 license are bundled locally in `web/`; that initial
standalone page did not use a CDN or online validator. Its separate-page design
was replaced by the embedded workspace view below.

Verified deployment operation `20261005T180439Z-f02d7e` replaced 17 exact files.
The initial attempt `20261005T180209Z-d4259d` was rolled back after the Pi lacked
the planned nested asset directory; no database or raw history change occurred.
The final deployment targets the existing `web/` directory and passed rollback
inspection before and after apply. The service is active, API version is v2,
SQLite integrity is `ok`, and the raw-record digest is unchanged. Browser
verification from the Pi home page found the `02` link, rendered 16 Swagger
operations, and confirmed that no “Try it out” button is present. All page,
asset and contract requests returned HTTP 200. Backups and the manifest entry
remain in ignored `recordings/panel-deploy-20261005T180439Z-f02d7e/` and
`deployment.json`; no capture was started.

## Embedded API reference update (2026-10-05)

The current reference is part of the panel at `http://192.168.50.100/#api-docs`.
Its operation groups come from OpenAPI tags. Local bundled Swagger UI loads only
when the section is opened, inherits the workspace's light/dark theme, and has
“Try it out” enabled. The page warns that these controls send real Pi requests,
that writes need the ephemeral `X-Panel-Token`, and that some operations affect
captures or stored sessions. No API operation was submitted during verification.
The previous `/api/docs` route remains as a compatibility redirect.

The integrated-page deployment is `20261005T182058Z-b87df7`; theme styling is
`20261005T182459Z-1ea6df`; the final OpenAPI response correction is
`20261005T183004Z-5260ff`; the Swagger deep-link routing fix is
`20261005T183337Z-e75028`. Each uploaded 17 exact files to the existing panel
directory and restarted only the existing service. All applied file-only
operations passed preflight and post-deployment rollback inspection. The final
deployment reports API v2 active, SQLite integrity `ok`,
seven sessions and 1,881 records unchanged, and an unchanged raw-history digest.
Browser verification confirmed the embedded route, all 16 operations in four
groups, the `02: API` sidebar entry, direct operation deep links, and the
`/api/docs` compatibility redirect.
No capture, delete, or router/repeater action was performed. Exact backups and
state are retained in ignored `recordings/panel-deploy-20261005T182459Z-1ea6df/`
and `deployment.json`.

## Planned experiment workspace requirements

Consolidated from NEXT-STEPS on 2026-10-06; these are acceptance requirements,
not a claim of implemented functionality.

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
