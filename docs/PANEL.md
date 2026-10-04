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
  live CSI graph, pause/resume/stop controls, deletion of any selected session,
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
There is still no automatic background capture or claimed live sample age.
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
Metadata writes append points, routes and session annotations; no deletion,
overwrite, automatic retention, or record migration is introduced.
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

See [API.openapi.json](API.openapi.json) and `/api/openapi.json`.
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
panel service, takes a local history copy, uploads the planned panel/map files,
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
- `python -m compileall -q src scripts tests`: passed. The generated SVG map
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
No new capture, router change, log cleanup or model evaluation was performed.
