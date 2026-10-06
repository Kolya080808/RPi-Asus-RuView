# RuView Lab API v2

This document describes the API implemented by `src/web_panel.py`. The
machine-readable contract is served at `GET /api/openapi.json` and is deployed
with the panel. The workspace embeds a locally served Swagger UI reference at
`/#api-docs`, showing parameters, request body fields, schemas and documented
HTTP responses. “Try it out” sends actual requests to this Pi; write operations
require its temporary token and may change or delete local data. Swagger UI
5.33.1 is bundled locally in `web/` with its Apache-2.0 license; no CDN or
online spec validator is used. The old `/api/docs` URL redirects to the embedded
workspace section.

The API is intended for the trusted home LAN. It has no user authentication,
TLS, or Internet access control. Do not port-forward the panel or expose port
80 outside the trusted network. The API can control bounded CSI recording and
delete sessions, so clients must treat the write token as a capability rather
than as an identity system.

Keep external access disabled until the panel's user-authentication milestone
is complete and verified; the `X-Panel-Token` is not a substitute. The planned
order and acceptance criteria are in [NEXT-STEPS.md](NEXT-STEPS.md).

## Transport and common rules

- Base URL: `http://raspberrypi.local/` (or the Pi's configured address).
- JSON responses use UTF-8 and UTC ISO-8601 timestamps.
- `POST` requests require `Content-Type: application/json` and a JSON object.
- Every write requires `X-Panel-Token`, obtained from `GET /api/health` after
  loading the panel. The token is generated when the Python process starts and
  is not a persistent credential.
- If an `Origin` header is sent, it must match the request `Host`.
- Request bodies are limited to 64 KiB. Responses use `Cache-Control: no-store`.
- Successful write operations return HTTP `201`.
- Errors are JSON objects of the form `{"error": "message"}`. Common status
  codes are `400` invalid input, `403` missing/invalid token or cross-origin
  write, `404` missing resource, `409` state or identifier conflict, `413`
  oversized request/replay/export, `415` wrong content type, `422` unusable
  timeline or unsupported replay interval, and `507` history storage limit.

The API currently operates on the documented GT-AX11000 `eth6` CSI profile.
It does not establish CSI support on ASUS repeaters. A motion or signal change
must not be interpreted as presence, position, pose, or skeleton output.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Service state, storage counts, active capture, and the ephemeral write token |
| GET | `/api/map` | Floorplan geometry, devices, source hashes, and image URL |
| GET | `/api/points` | Saved reference points |
| POST | `/api/points` | Create a reference point |
| GET | `/api/routes` | Saved ordered routes |
| POST | `/api/routes` | Create a route from existing point IDs |
| GET | `/api/sessions?offset=N` | Up to 100 sessions, newest first; includes `total` and `offset` |
| GET | `/api/sessions/{id}` | Session metadata and reference annotations |
| GET | `/api/sessions/{id}/measurements` | Decoded replay samples and signal summary |
| GET | `/api/sessions/{id}/export` | Download session metadata, annotations, and raw records |
| POST | `/api/sessions/{id}/annotations` | Add a timed reference annotation |
| POST | `/api/sessions/{id}/delete` | Delete a stopped session, its records, and annotations |
| POST | `/api/captures` | Start one bounded manual CSI capture |
| GET | `/api/captures/{id}` | Session snapshot and replay for a capture |
| GET | `/api/captures/{id}/live?after=N` | Incremental live samples and lifecycle state |
| POST | `/api/captures/{id}/pause` | Pause an active capture safely |
| POST | `/api/captures/{id}/resume` | Resume a paused capture |
| POST | `/api/captures/{id}/stop` | Stop an active capture and clean up the router monitor |

Static resources are served at `/`, `/index.html`, `/app.js`, `/app.css`,
`/theme.css`, `/api/docs` (legacy redirect), `/api-docs.js`, `/api-docs.css`, `/swagger-ui.css`,
`/swagger-ui-bundle.js`, `/swagger-ui-standalone-preset.js`,
`/maps/home/floorplan-furnished.png`, and `/api/openapi.json`.

## Health and map

`GET /api/health` returns fields including:

```json
{
  "status": "ok",
  "service": "ruview-lab-panel",
  "api_version": "v2",
  "capture_enabled": true,
  "write_token": "ephemeral-token",
  "source_state": "not-monitored",
  "active_capture": null,
  "last_valid_sample_age_s": null,
  "history_bytes": 123456,
  "free_bytes": 987654321,
  "sessions": 7,
  "records": 1881,
  "server_time": "2026-10-05T12:00:00+00:00"
}
```

`write_token` is shown only as an ephemeral trusted-LAN write capability. Do
not persist it, put it in URLs, or log it. When a capture is active,
`active_capture` contains `session`, `paused`, and `remaining_s`.

`GET /api/map` returns `floorplan`, `devices`, and `sources`. The floorplan's
`bounds_m` and `render.plot_rect` define the coordinate conversion; map
coordinates are not image pixels. Device entries can include
`source_pixel_center`, model, region, height, and placement notes. The source
hashes must be retained with future annotations and exports.

## Points and routes

Create a point with `POST /api/points`:

```json
{
  "id": "r08-still",
  "label": "R08 stillness",
  "region": "R08",
  "x": 3.1,
  "y": 0.1,
  "height": 0,
  "notes": "To be confirmed physically"
}
```

`id` is optional and defaults to a UUID; explicit IDs may contain only letters,
digits, `_`, and `-`, up to 80 characters. `label` is required and may be up
to 200 characters. `region` is `unknown` or a known map room (`R01`–`R08`).
`x` and `y` must be inside the current map bounds. `height` is optional and
must be between 0 and 10 metres. `notes` may contain up to 2,000 characters.

The response is `{"point": "r08-still"}`. `GET /api/points` returns
`{"points": [...]}`. Point notes also contain a provenance context with the
map source hashes.

Create a route with `POST /api/routes`:

```json
{
  "label": "R08 to R02",
  "region": "unknown",
  "points": ["r08-still", "r02-still"],
  "notes": ""
}
```

The `points` array must contain 2–64 existing, distinct point IDs. The response
is `{"route": "generated-or-supplied-id"}`. Route records preserve point
snapshots and map-source hashes in their context.

## Sessions, measurements, and export

`GET /api/sessions` returns at most 100 newest sessions:

```json
{"sessions": [{"id": "...", "status": "captured", "records": 98}], "total": 7, "offset": 0}
```

Session objects include ISO-8601 `started`/`finished` values, decoded JSON
`metadata`, record and annotation counts, and `map_at_capture`. Historical
sessions currently return `map_at_capture: null` because the map was not
snapshotted at acquisition time.

`GET /api/sessions/{id}/measurements` returns `session`, `annotations`,
`samples`, and `summary`. Samples preserve sequence numbers, device-relative
time, validity, timer data, amplitude, RSSI-like values, and gap information.
The summary includes record counts, invalid/incomplete records, gap count,
duration, median interval, estimated sample rate, smoothing, threshold,
`time_basis`, timing uncertainty, and the explicit meaning:
`Radio-scene change; no location, pose or presence inference`.

Replay is limited to 10,000 records and only supports capture intervals of
100, 200, or 500 ms. The time basis and timing uncertainty remain provisional;
they must not be presented as synchronized ground truth.

`GET /api/sessions/{id}/export` returns a downloadable JSON attachment with
the session, annotations, raw records as `raw_hex`, `map_at_capture: null`,
and `export_version: 2`. Raw CSI records are retained so future analysis does
not require repeating the experiment.

## Reference annotations

Create an annotation with `POST /api/sessions/{id}/annotations`:

```json
{
  "point_id": "r08-still",
  "start_s": 8.0,
  "end_s": 18.5,
  "activity": "arm movement",
  "kind": "observed",
  "timing_uncertainty_s": 0.3,
  "notes": "Observed action"
}
```

Allowed activities are `still`, `arm movement`, `walking`, `empty room`, and
`uncertain`. `kind` is `observed` or `planned` and defaults to `observed`.
The interval must lie inside the usable session timeline and have positive
length. `point_id` is optional but must reference an existing point when set.
Timing uncertainty, when supplied, is between 0 and 3,600 seconds.

Annotations are reference labels, not model predictions. The response contains
the generated `annotation_id`. Provenance includes map source hashes, point
snapshots, the provisional time basis, annotation kind, timing uncertainty,
and local-user source information.

## Manual bounded capture

`POST /api/captures` starts a manual capture on the documented GT-AX11000
profile:

```json
{"seconds": 60, "interval_ms": 100}
```

`seconds` must be 5–1,800 and defaults to 60. `interval_ms` must be 100, 200,
or 500 and defaults to 100. The response is `{"session": "uuid"}`. Only one
panel capture may be active at a time. The panel records raw data to the
existing SQLite history and runs the router cleanup trap when the segment ends,
is paused, stopped, or fails.

Pause, resume, and stop use the action endpoints listed above and return the
session ID and action. Invalid state transitions return `409`. The capture
status is also visible through `/api/health` and the session/capture endpoints.
Capture snapshots include a stable `id`, `session`, `paused`, `stopping`,
`remaining_s` (nullable), and `samples` (empty before data arrive). The countdown
starts when the router reports that CSI monitoring is enabled; SSH/setup time
is not charged. Pause/stop freezes the budget. This is a Pi monotonic estimate,
not an RF acquisition timestamp. Failed captures also return `capture_error`
with command diagnostics; zero records are not reported as a successful capture. A replay
error returns `signal_error` alongside lifecycle state, so a timer reset or
replay limit cannot hide pause/stop/delete controls. The measurements endpoint
still returns its original error for an unusable timeline.

The storage guard rejects a new capture with `507` when history files exceed
256 MiB. Automatic retention and cleanup are not implemented; bounded capture
must not be confused with continuous observation.

## Deleting sessions

`POST /api/sessions/{id}/delete` removes the session annotations, raw records,
and session row. A running capture must be paused or stopped first. For a paused
or already stopping capture, deletion requests stop and waits up to 12 seconds
for its worker to finish. If it remains alive, the API returns 409 and preserves
the session for retry. This is a
destructive operation and requires the write token. Raw CSI should be exported
before deletion when the session may be useful for later validation.

## Incremental live signal

`GET /api/captures/{id}/live?after=-1` returns lifecycle fields plus the latest
600 compact signal samples. Pass `next_seq` as `after` on the next request to
receive only newer points. `reset: true` means replace the local window (initial
connection, cursor older than the ring, or cache absent after server restart).
Samples are filtered once when a record is persisted, using the same causal
`LiveSignal` as the desktop viewer. This path does not replay the entire history
and is independent of the 10,000-record full-replay limit. The browser requests
updates 100 ms after each completed response; only one request is in flight.
This is a target refresh interval, not an end-to-end latency guarantee.
`last_sample_age_s` is time since the last valid record was processed on the Pi,
not RF acquisition age. A running capture with no valid sample processed for over two seconds shows
NO NEW DATA; before the first sample the graph shows a waiting message.
The most recent capture keeps a bounded in-memory cache after completion. Other
sessions recover a bounded 600-record window from disk; full replay is unchanged.
