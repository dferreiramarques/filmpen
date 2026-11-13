"""Local web UI: gallery, look picker, re-develop, before/after."""
from __future__ import annotations

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .library import Library, Watcher
from .looks import LOOKS

UI_FILE = Path(__file__).with_name("ui.html")


def serve(lib: Library, watcher: Watcher | None, host: str = "0.0.0.0", port: int = 8080,
          max_size: int | None = None) -> None:
    jobs_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, body: bytes, ctype: str, code: int = 200, extra: dict | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(json.dumps(obj).encode(), "application/json", code)

        def _file(self, path: Path, download: bool = False):
            if not path.exists():
                return self._send(b"not found", "text/plain", 404)
            extra = {"Content-Disposition": f'attachment; filename="{path.name}"'} if download else None
            self._send(path.read_bytes(), "image/jpeg", extra=extra)

        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            parts = [urllib.parse.unquote(p) for p in url.path.strip("/").split("/")]
            if url.path in ("/", "/index.html"):
                return self._send(UI_FILE.read_bytes(), "text/html; charset=utf-8")
            if url.path == "/api/state":
                return self._json({
                    "current_look": lib.current_look,
                    "looks": [{"key": l.key, "name": l.name, "description": l.description}
                              for l in LOOKS.values()],
                    "shots": lib.shots(),
                    "camera": watcher.status if watcher else {"connected": False,
                                                              "message": "Offline mode (no camera)"},
                })
            # /thumb/<look|original>/<name>, /full/<look|original>/<name>, /download/<look>/<name>
            if len(parts) == 3 and parts[0] in ("thumb", "full", "download"):
                kind, look, name = parts
                name = Path(name).name  # no path traversal
                if look != "original" and look not in LOOKS:
                    return self._send(b"bad look", "text/plain", 400)
                if kind == "thumb":
                    return self._file(lib.thumb(name, look))
                path = lib.original(name) if look == "original" else lib.developed(name, look)
                return self._file(path, download=(kind == "download"))
            self._send(b"not found", "text/plain", 404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "bad json"}, 400)
            if self.path == "/api/look":
                try:
                    lib.set_current_look(body["look"])
                except KeyError:
                    return self._json({"error": "unknown look"}, 400)
                return self._json({"ok": True})
            if self.path == "/api/develop":
                name, look = Path(body.get("name", "")).name, body.get("look")
                if look not in LOOKS or not lib.has(name):
                    return self._json({"error": "unknown shot or look"}, 400)
                with jobs_lock:
                    lib.develop(name, look, max_size=max_size)
                return self._json({"ok": True})
            self._json({"error": "not found"}, 404)

    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"FilmPen UI at http://127.0.0.1:{port}  (from your phone: http://<this-machine-ip>:{port})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
