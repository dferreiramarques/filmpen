"""Local photo library + the background loop that pulls shots off the camera.

Layout:
    <root>/originals/P1010001.JPG          straight off the camera
    <root>/developed/<look>/P1010001.JPG   full-size film version
    <root>/thumbs/<look>/P1010001.JPG      gallery thumbnails
    <root>/thumbs/original/P1010001.JPG
    <root>/state.json                      chosen look per shot, settings
"""
from __future__ import annotations

import json
import threading
import time
import traceback
from pathlib import Path

from .camera import Camera, CameraError
from .looks import LOOKS, develop_file, make_thumb


class Library:
    def __init__(self, root: Path, default_look: str = "negative"):
        self.root = Path(root)
        self.lock = threading.RLock()
        self.state_path = self.root / "state.json"
        self.state = {"current_look": default_look, "shots": {}}
        if self.state_path.exists():
            self.state.update(json.loads(self.state_path.read_text()))
        for d in ("originals", "developed", "thumbs"):
            (self.root / d).mkdir(parents=True, exist_ok=True)

    # -- paths ---------------------------------------------------------------
    def original(self, name: str) -> Path:
        return self.root / "originals" / name

    def developed(self, name: str, look: str) -> Path:
        return self.root / "developed" / look / name

    def thumb(self, name: str, look: str) -> Path:
        return self.root / "thumbs" / look / name

    # -- state ---------------------------------------------------------------
    def save(self) -> None:
        with self.lock:
            tmp = self.state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.state, indent=1))
            tmp.replace(self.state_path)

    @property
    def current_look(self) -> str:
        return self.state["current_look"]

    def set_current_look(self, look: str) -> None:
        if look not in LOOKS:
            raise KeyError(look)
        with self.lock:
            self.state["current_look"] = look
            self.save()

    def has(self, name: str) -> bool:
        return name in self.state["shots"] and self.original(name).exists()

    def add_original(self, name: str, taken: str | None = None) -> None:
        with self.lock:
            self.state["shots"].setdefault(name, {"look": None, "taken": taken,
                                                  "added": time.time()})
            self.save()
        make_thumb(self.original(name), self.thumb(name, "original"))

    def develop(self, name: str, look: str | None = None, max_size: int | None = None) -> Path:
        look = look or self.current_look
        dst = self.developed(name, look)
        if not dst.exists():
            develop_file(self.original(name), dst, look, max_size=max_size)
            make_thumb(dst, self.thumb(name, look))
        with self.lock:
            self.state["shots"][name]["look"] = look
            self.save()
        return dst

    def import_folder(self, folder: Path, look: str | None = None) -> list[str]:
        """Import JPEGs from a folder (e.g. an SD card) without the camera."""
        names = []
        for p in sorted(Path(folder).rglob("*")):
            if p.suffix.lower() in (".jpg", ".jpeg") and not self.has(p.name):
                self.original(p.name).write_bytes(p.read_bytes())
                self.add_original(p.name)
                self.develop(p.name, look)
                names.append(p.name)
        return names

    def shots(self) -> list[dict]:
        with self.lock:
            items = [dict(name=n, **s) for n, s in self.state["shots"].items()]
        items.sort(key=lambda s: (s.get("taken") or "", s["added"]), reverse=True)
        return items


class Watcher(threading.Thread):
    """Polls the camera and develops every new shot with the current look."""

    def __init__(self, library: Library, camera: Camera, interval: float = 4.0,
                 resize: int | None = None, max_size: int | None = None):
        super().__init__(daemon=True)
        self.lib, self.cam = library, camera
        self.interval, self.resize, self.max_size = interval, resize, max_size
        self.status = {"connected": False, "model": None, "message": "Starting…",
                       "busy": None, "last_seen": None}
        self._halt = threading.Event()

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        was_connected = False
        while not self._halt.is_set():
            try:
                if not was_connected:
                    self.status["model"] = self.cam.model()
                    self.cam.play_mode()
                    was_connected = True
                remote = self.cam.list_images()
                self.status.update(connected=True, last_seen=time.time(),
                                   message=f"{len(remote)} photos on card")
                for f in remote:
                    if self._halt.is_set():
                        break
                    if self.lib.has(f.name):
                        continue
                    self.status["busy"] = f"Downloading {f.name}"
                    self.cam.download(f, self.lib.original(f.name), resize=self.resize)
                    self.lib.add_original(f.name, f.taken.isoformat() if f.taken else None)
                    self.status["busy"] = f"Developing {f.name}"
                    self.lib.develop(f.name, max_size=self.max_size)
                self.status["busy"] = None
            except CameraError as e:
                was_connected = False
                self.status.update(connected=False, busy=None,
                                   message="Camera not reachable — join its Wi-Fi "
                                           "(Menu ▸ Connection to Smartphone)")
                self.status["detail"] = str(e)
            except Exception as e:  # keep the loop alive whatever happens
                traceback.print_exc()
                self.status.update(busy=None, message=f"Error: {e}")
            self._halt.wait(self.interval)
