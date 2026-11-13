"""A fake Olympus camera for testing without the real E-PL9.

Serves the same CGI endpoints from a local folder of JPEGs. Drop new JPEGs
into the folder while it runs to simulate taking photos.
"""
from __future__ import annotations

import datetime as dt
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

from PIL import Image

DIR_NAME = "100OLYMP"


def _fat(ts: float) -> tuple[int, int]:
    d = dt.datetime.fromtimestamp(ts)
    return (((d.year - 1980) << 9) | (d.month << 5) | d.day,
            (d.hour << 11) | (d.minute << 5) | (d.second // 2))


def serve(folder: Path, port: int = 8010) -> None:
    folder = Path(folder)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            print("[mock camera]", fmt % args)

        def _send(self, body: bytes, ctype="text/plain", code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if "OI.Share" not in self.headers.get("User-Agent", ""):
                return self._send(b"forbidden", code=403)  # mimic the real camera
            url = urllib.parse.urlparse(self.path)
            q = dict(urllib.parse.parse_qsl(url.query))
            if url.path == "/get_caminfo.cgi":
                return self._send(b"<?xml version=\"1.0\"?><caminfo><model>E-PL9 (mock)</model></caminfo>", "text/xml")
            if url.path in ("/switch_cammode.cgi", "/exec_pwoff.cgi"):
                return self._send(b"")
            if url.path == "/get_imglist.cgi":
                d = q.get("DIR", "")
                lines = ["VER_100"]
                if d == "/DCIM":
                    lines.append(f"/DCIM,{DIR_NAME},0,16,0,0")
                elif d == f"/DCIM/{DIR_NAME}":
                    for p in sorted(folder.glob("*")):
                        if p.suffix.lower() in (".jpg", ".jpeg"):
                            st = p.stat()
                            fd, ft = _fat(st.st_mtime)
                            lines.append(f"{d},{p.name},{st.st_size},0,{fd},{ft}")
                else:
                    return self._send(b"", code=404)
                return self._send(("\r\n".join(lines) + "\r\n").encode())
            if url.path == "/get_resizeimg.cgi":
                p = folder / Path(q.get("DIR", "")).name
                if not p.exists():
                    return self._send(b"", code=404)
                img = Image.open(p)
                exif = img.info.get("exif", b"")
                size = int(q.get("size", 2048))
                img.thumbnail((size, size))
                buf = BytesIO()
                img.save(buf, "JPEG", quality=90, exif=exif)
                return self._send(buf.getvalue(), "image/jpeg")
            if url.path.startswith(f"/DCIM/{DIR_NAME}/"):
                p = folder / Path(url.path).name
                if p.exists():
                    return self._send(p.read_bytes(), "image/jpeg")
            return self._send(b"not found", code=404)

    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Mock camera serving {folder} at http://127.0.0.1:{port}")
    srv.serve_forever()
