"""Local RuView lab panel and API.

The server uses only Python's standard library and is intended for the
Raspberry Pi on a trusted home LAN. It binds to port 80 when run as a service.
"""
import argparse
import datetime as dt
import hashlib
import json
import mimetypes
from pathlib import Path
import sqlite3
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


SRC = Path(__file__).resolve().parent
ROOT = SRC.parent if (SRC.parent / "maps").is_dir() else SRC
MAP_DIR = ROOT / "maps" / "home"
HISTORY = ROOT / "history.sqlite3"
STATIC = ROOT / "web"
MAX_BODY = 64 * 1024


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def db():
    connection = sqlite3.connect(HISTORY, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE IF NOT EXISTS map_points "
        "(id TEXT PRIMARY KEY, label TEXT NOT NULL, region TEXT NOT NULL, "
        "x REAL NOT NULL, y REAL NOT NULL, height REAL NOT NULL DEFAULT 0, "
        "notes TEXT NOT NULL DEFAULT '', created REAL NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS map_routes "
        "(id TEXT PRIMARY KEY, label TEXT NOT NULL, region TEXT NOT NULL, "
        "points TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', created REAL NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS session_annotations "
        "(id TEXT PRIMARY KEY, session TEXT NOT NULL, point_id TEXT, "
        "start_s REAL NOT NULL, end_s REAL, activity TEXT NOT NULL, "
        "source TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', created REAL NOT NULL)"
    )
    connection.commit()
    return connection


def ensure_recorder_tables(connection):
    connection.execute(
        "CREATE TABLE IF NOT EXISTS sessions "
        "(id TEXT PRIMARY KEY, started REAL, finished REAL, status TEXT, metadata TEXT, log TEXT)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS records "
        "(session TEXT, seq INTEGER, raw BLOB, decoded TEXT, PRIMARY KEY(session,seq))"
    )
    connection.commit()


def map_payload():
    floorplan = load_json(MAP_DIR / "floorplan.json")
    devices = load_json(MAP_DIR / "devices.json")
    return {
        "floorplan": floorplan,
        "devices": devices["devices"],
        "sources": {
            "floorplan_sha256": sha256(MAP_DIR / "floorplan.json"),
            "devices_sha256": sha256(MAP_DIR / "devices.json"),
            "image": "/maps/home/floorplan-furnished.png",
        },
        "render": {
            "image_size_px": [2400, 2400],
            "plot_rect": {"left": 0.08, "right": 0.96, "top": 0.12, "bottom": 0.88},
            "plot_bounds_m": [
                [floorplan["bounds_m"][0][0] - 0.45, floorplan["bounds_m"][0][1] - 0.45],
                [floorplan["bounds_m"][1][0] + 0.45, floorplan["bounds_m"][1][1] + 0.45],
            ],
        },
    }


def bounds():
    return map_payload()["floorplan"]["bounds_m"]


def validate_point(value):
    try:
        x, y = float(value["x"]), float(value["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("point requires numeric x and y") from exc
    lo, hi = bounds()
    if not (lo[0] <= x <= hi[0] and lo[1] <= y <= hi[1]):
        raise ValueError("point is outside map bounds")
    return x, y


def iso(timestamp):
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).isoformat() if timestamp else None


def sessions(connection):
    ensure_recorder_tables(connection)
    result = []
    for row in connection.execute(
        "SELECT s.id, s.started, s.finished, s.status, s.metadata, "
        "(SELECT count(*) FROM records r WHERE r.session=s.id) records "
        "FROM sessions s ORDER BY s.started DESC LIMIT 100"
    ):
        metadata = json.loads(row["metadata"] or "{}")
        result.append({
            "id": row["id"], "started": iso(row["started"]),
            "finished": iso(row["finished"]), "status": row["status"],
            "metadata": metadata, "records": row["records"],
        })
    return result


def annotations(connection, session_id):
    return [dict(row) for row in connection.execute(
        "SELECT id, session, point_id, start_s, end_s, activity, source, notes "
        "FROM session_annotations WHERE session=? ORDER BY start_s", (session_id,)
    )]


class Handler(BaseHTTPRequestHandler):
    server_version = "RuViewLab/1.0"

    def log_message(self, format, *args):
        print("%s - %s" % (self.address_string(), format % args))

    def send_json(self, value, status=HTTPStatus.OK):
        raw = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > MAX_BODY:
            raise ValueError("invalid request body size")
        return json.loads(self.rfile.read(length))

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            connection = db()
            if path == "/api/health":
                self.send_json({"status": "ok", "service": "ruview-lab-panel",
                                "api_version": "v1", "capture_enabled": False})
            elif path == "/api/openapi.json":
                self.send_file(ROOT / "docs" / "API.openapi.json")
            elif path == "/api/map":
                self.send_json(map_payload())
            elif path == "/api/points":
                self.send_json({"points": [dict(row) for row in connection.execute(
                    "SELECT id,label,region,x,y,height,notes FROM map_points ORDER BY id"
                )]})
            elif path == "/api/routes":
                self.send_json({"routes": [
                    {**dict(row), "points": json.loads(row["points"])}
                    for row in connection.execute(
                        "SELECT id,label,region,points,notes FROM map_routes ORDER BY id"
                    )
                ]})
            elif path == "/api/sessions":
                self.send_json({"sessions": sessions(connection)})
            elif path.startswith("/api/sessions/"):
                session_id = path.split("/")[-1]
                found = [item for item in sessions(connection) if item["id"] == session_id]
                if not found:
                    self.send_json({"error": "session not found"}, HTTPStatus.NOT_FOUND)
                else:
                    self.send_json({"session": found[0],
                                    "annotations": annotations(connection, session_id)})
            elif path == "/" or path == "/index.html":
                self.send_file(STATIC / "index.html")
            elif path == "/maps/home/floorplan-furnished.png":
                self.send_file(MAP_DIR / "floorplan-furnished.png")
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        finally:
            if "connection" in locals():
                connection.close()

    def do_POST(self):
        path = urlparse(self.path).path
        connection = None
        try:
            body = self.read_json()
            connection = db()
            if path == "/api/points":
                x, y = validate_point(body)
                point_id = str(body.get("id") or uuid.uuid4())
                if not point_id.replace("-", "").replace("_", "").isalnum():
                    raise ValueError("point id must contain letters, numbers, '-' or '_'")
                connection.execute(
                    "INSERT INTO map_points VALUES (?,?,?,?,?,?,?,?)",
                    (point_id, str(body.get("label") or point_id),
                     str(body.get("region") or "unknown"), x, y,
                     float(body.get("height", 0)), str(body.get("notes") or ""), time.time())
                )
                connection.commit()
                self.send_json({"point": point_id}, HTTPStatus.CREATED)
            elif path == "/api/routes":
                point_ids = body.get("points")
                if not isinstance(point_ids, list) or len(point_ids) < 2:
                    raise ValueError("route requires at least two point ids")
                existing = {row[0] for row in connection.execute("SELECT id FROM map_points")}
                if any(point_id not in existing for point_id in point_ids):
                    raise ValueError("route references an unknown point")
                route_id = str(body.get("id") or uuid.uuid4())
                connection.execute(
                    "INSERT INTO map_routes VALUES (?,?,?,?,?,?)",
                    (route_id, str(body.get("label") or route_id),
                     str(body.get("region") or "unknown"), json.dumps(point_ids),
                     str(body.get("notes") or ""), time.time())
                )
                connection.commit()
                self.send_json({"route": route_id}, HTTPStatus.CREATED)
            elif path == "/api/captures":
                self.send_json({
                    "error": "capture control is disabled in this panel build; "
                             "use the planned recording workflow after retention is defined"
                }, HTTPStatus.NOT_IMPLEMENTED)
            elif path.startswith("/api/sessions/") and path.endswith("/annotations"):
                session_id = path.split("/")[-2]
                ensure_recorder_tables(connection)
                if not connection.execute("SELECT 1 FROM sessions WHERE id=?",
                                          (session_id,)).fetchone():
                    self.send_json({"error": "session not found"}, HTTPStatus.NOT_FOUND)
                    return
                start = float(body["start_s"])
                end = body.get("end_s")
                if end is not None:
                    end = float(end)
                    if end < start:
                        raise ValueError("end_s must not precede start_s")
                annotation_id = str(uuid.uuid4())
                connection.execute(
                    "INSERT INTO session_annotations VALUES (?,?,?,?,?,?,?,?,?)",
                    (annotation_id, session_id, body.get("point_id"), start, end,
                     str(body.get("activity") or "unlabeled"), "user",
                     str(body.get("notes") or ""), time.time())
                )
                connection.commit()
                self.send_json({"annotation_id": annotation_id}, HTTPStatus.CREATED)
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except sqlite3.IntegrityError as exc:
            self.send_json({"error": f"already exists or invalid reference: {exc}"},
                           HTTPStatus.CONFLICT)
        except (KeyError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        finally:
            if connection:
                connection.close()

    def send_file(self, path):
        if not path.is_file():
            self.send_json({"error": "file not found"}, HTTPStatus.NOT_FOUND)
            return
        raw = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    with ThreadingHTTPServer((args.host, args.port), Handler) as server:
        print(f"RuView lab panel listening on http://{args.host}:{args.port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
