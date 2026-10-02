# RuView Lab API

The panel and future clients use the same HTTP API. This is the contract for
the phone web app, a desktop program, and the current browser panel. The
service is local-only and currently has no user authentication; do not expose
port 80 outside the trusted home network or forward it from the router.

Base URL:

```text
http://raspberrypi.local/
```

The API is JSON and uses UTC ISO-8601 timestamps. `POST` requests must send
`Content-Type: application/json`. The map coordinates use the coordinate system
declared by `floorplan.json`; they are not screen pixels.

The machine-readable contract is also available from the running Pi at
`GET /api/openapi.json`.

`GET /api/map` includes `render.plot_rect` and `render.plot_bounds_m`. These
describe the normalized plot rectangle and its metre bounds inside the
2400x2400 exported image. Clients must use both when converting map coordinates
to screen positions; stretching the full image or using only the geometry
bounds produces incorrect device and experiment-point markers.

Network devices also include `source_pixel_center`. For device markers, clients
should use that original annotated pixel position when rendering the supplied
PNG. It preserves the user's device annotation even when the scan geometry and
the annotation image have different margins.

The browser panel displays device details in a hover tooltip containing the
model, map region, height, and placement notes. The tooltip is rendered as a
viewport-level fixed layer with a high stacking order, so it is not clipped by
the map container or neighboring panels. Other clients may use the same fields
to implement their own device information view.

## Current endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Service and feature status |
| GET | `/api/map` | Floor geometry, devices, source hashes, and map image URL |
| GET | `/api/points` | Saved experiment points |
| POST | `/api/points` | Save one experiment point |
| GET | `/api/routes` | Saved routes |
| POST | `/api/routes` | Save a route referencing existing point IDs |
| GET | `/api/sessions` | Read-only list of existing Pi sessions |
| GET | `/api/sessions/{id}` | One session and its annotations |
| POST | `/api/sessions/{id}/annotations` | Save a timed reference label |

`POST /api/captures` deliberately returns `501 Not Implemented`. Recording is
disabled in the bootstrap panel so the Pi storage cannot be filled before the
retention, export, and cleanup policy is agreed. The command-line recorder
remains available for controlled manual work, but it is not started by the
web service.

## Example requests

Create a point:

```json
POST /api/points
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

Create a route:

```json
POST /api/routes
{
  "id": "r08-r02",
  "label": "R08 to R02",
  "region": "R08-R02",
  "points": ["r08-still", "r02-still"],
  "notes": ""
}
```

Add a reference activity label:

```json
POST /api/sessions/{id}/annotations
{
  "point_id": "r08-still",
  "start_s": 8.0,
  "end_s": 18.5,
  "activity": "arm movement",
  "notes": "Observed action"
}
```

The API stores reference annotations separately from future model
predictions. A later capture API must add explicit map revision, time basis,
source, timing uncertainty, validity, gaps, and retention/export behavior
before recording is enabled from clients.

## Client responsibilities

The phone and desktop clients should treat `GET /api/map` as authoritative for
the current map source hashes, render `devices` separately from user points,
and refresh data after writes. They must not infer a probability from the
current motion indicator or treat an empty/unknown session as an empty room.

The planned next API layer is measurements and replay/export. It is not part
of this bootstrap implementation.
