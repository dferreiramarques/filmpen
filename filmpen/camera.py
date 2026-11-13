"""Client for the Olympus / OM System Wi-Fi HTTP API (the one OI.Share uses).

When the camera is in "Connection to Smartphone" mode it creates its own
Wi-Fi access point and serves a small CGI API at http://192.168.0.10/.
The camera only answers requests that carry an OI.Share-like User-Agent.

Image list format (get_imglist.cgi):
    VER_100
    /DCIM/100OLYMP,P1010001.JPG,4851234,0,20825,38213
    dir, name, size, attribute, FAT date, FAT time
attribute bit 0x10 = directory.
"""
from __future__ import annotations

import datetime as dt
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_URL = "http://192.168.0.10"
USER_AGENT = "OI.Share v2"
IMAGE_EXTS = {".jpg", ".jpeg"}


class CameraError(Exception):
    pass


@dataclass(frozen=True)
class RemoteFile:
    directory: str
    name: str
    size: int
    attribute: int
    taken: dt.datetime | None

    @property
    def is_dir(self) -> bool:
        return bool(self.attribute & 0x10)

    @property
    def path(self) -> str:
        return f"{self.directory.rstrip('/')}/{self.name}"


def _fat_datetime(d: int, t: int) -> dt.datetime | None:
    try:
        return dt.datetime(1980 + (d >> 9), (d >> 5) & 0xF, d & 0x1F,
                           t >> 11, (t >> 5) & 0x3F, (t & 0x1F) * 2)
    except ValueError:
        return None


def parse_imglist(text: str) -> list[RemoteFile]:
    files = []
    for line in text.splitlines():
        parts = line.strip().split(",")
        if len(parts) < 6:
            continue  # header ("VER_100") or blank
        try:
            size, attr, d, t = (int(p) for p in parts[-4:])
        except ValueError:
            continue
        directory = parts[0]
        name = ",".join(parts[1:-4])  # names never contain commas, but be safe
        files.append(RemoteFile(directory, name, size, attr, _fat_datetime(d, t)))
    return files


class Camera:
    def __init__(self, base_url: str = DEFAULT_URL, timeout: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # -- low level ---------------------------------------------------------
    def _get(self, path: str, params: dict | None = None, timeout: float | None = None) -> bytes:
        url = f"{self.base_url}{path}"
        if params:
            # The camera wants literal slashes in DIR=, so don't escape them.
            url += "?" + urllib.parse.urlencode(params, safe="/")
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
                return r.read()
        except (urllib.error.URLError, OSError) as e:
            raise CameraError(f"{url}: {e}") from e

    # -- API -----------------------------------------------------------------
    def info(self) -> str:
        """Returns the camera model XML snippet, e.g. <caminfo><model>E-PL9</model>..."""
        return self._get("/get_caminfo.cgi").decode("utf-8", "replace")

    def model(self) -> str:
        xml = self.info()
        start, end = xml.find("<model>"), xml.find("</model>")
        return xml[start + 7:end] if start >= 0 and end > start else "Olympus camera"

    def play_mode(self) -> None:
        """Switch to playback mode; required before listing on most bodies."""
        try:
            self._get("/switch_cammode.cgi", {"mode": "play"})
        except CameraError:
            pass  # some bodies are already in play mode or reject the repeat

    def list_dir(self, directory: str) -> list[RemoteFile]:
        text = self._get("/get_imglist.cgi", {"DIR": directory}).decode("utf-8", "replace")
        return parse_imglist(text)

    def list_images(self) -> list[RemoteFile]:
        """All JPEGs under /DCIM, oldest first."""
        images: list[RemoteFile] = []
        for entry in self.list_dir("/DCIM"):
            if entry.is_dir:
                for f in self.list_dir(entry.path):
                    if not f.is_dir and Path(f.name).suffix.lower() in IMAGE_EXTS:
                        images.append(f)
        images.sort(key=lambda f: (f.taken or dt.datetime.min, f.name))
        return images

    def download(self, f: RemoteFile, dest: Path, resize: int | None = None) -> Path:
        """Download a file. `resize` (1024/1600/1920/2048) asks the camera for a
        smaller JPEG, which is much faster over the camera's slow Wi-Fi."""
        if resize:
            data = self._get("/get_resizeimg.cgi", {"DIR": f.path, "size": resize}, timeout=60)
        else:
            data = self._get(f.path, timeout=120)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(dest)
        return dest

    def power_off(self) -> None:
        self._get("/exec_pwoff.cgi")
