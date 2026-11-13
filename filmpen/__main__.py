"""FilmPen — film looks for the Olympus PEN E-PL9 (and other Olympus/OM Wi-Fi bodies).

    python -m filmpen run                     watch the camera + open the web UI
    python -m filmpen develop IN... --look bw develop JPEGs/folders offline
    python -m filmpen import /media/SDCARD    import a card folder into the library
    python -m filmpen mock ./test-photos      fake camera for testing
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .camera import DEFAULT_URL, Camera
from .looks import LOOKS, develop_file


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="filmpen", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    looks = sorted(LOOKS)

    r = sub.add_parser("run", help="watch the camera and serve the gallery UI")
    r.add_argument("--library", default="~/FilmPen", help="where photos are stored (default ~/FilmPen)")
    r.add_argument("--look", choices=looks, help="film to load at start")
    r.add_argument("--camera", default=DEFAULT_URL, help=f"camera URL (default {DEFAULT_URL})")
    r.add_argument("--port", type=int, default=8080)
    r.add_argument("--interval", type=float, default=4.0, help="seconds between camera checks")
    r.add_argument("--transfer", default="full", choices=["full", "1024", "1600", "1920", "2048"],
                   help="download full JPEGs or ask the camera for a smaller copy (faster)")
    r.add_argument("--max-size", type=int, help="cap developed images at N px on the long edge")
    r.add_argument("--no-camera", action="store_true", help="just browse/re-develop the library")
    r.add_argument("--open", action="store_true", help="open the gallery in the browser on start")

    d = sub.add_parser("develop", help="apply a look to JPEGs or folders")
    d.add_argument("inputs", nargs="+", type=Path)
    d.add_argument("--look", choices=looks + ["all"], default="negative")
    d.add_argument("--out", type=Path, default=Path("developed"))
    d.add_argument("--max-size", type=int)

    i = sub.add_parser("import", help="import JPEGs from a folder (SD card) into the library")
    i.add_argument("folder", type=Path)
    i.add_argument("--library", default="~/FilmPen")
    i.add_argument("--look", choices=looks)

    m = sub.add_parser("mock", help="run a fake camera that serves a folder of JPEGs")
    m.add_argument("folder", type=Path)
    m.add_argument("--port", type=int, default=8010)

    sub.add_parser("looks", help="list the available looks")

    a = p.parse_args(argv)

    if a.cmd == "looks":
        for l in LOOKS.values():
            print(f"{l.key:10} {l.name:20} {l.description}")
        return 0

    if a.cmd == "develop":
        files = []
        for inp in a.inputs:
            files += sorted(x for x in inp.rglob("*") if x.suffix.lower() in (".jpg", ".jpeg")) \
                if inp.is_dir() else [inp]
        keys = looks if a.look == "all" else [a.look]
        for f in files:
            for k in keys:
                out = a.out / k / f.name if len(keys) > 1 else a.out / f.name
                develop_file(f, out, k, max_size=a.max_size)
                print(f"{f} → {out}")
        return 0

    if a.cmd == "mock":
        from .mock import serve
        serve(a.folder, a.port)
        return 0

    from .library import Library, Watcher
    lib = Library(Path(a.library).expanduser())
    if a.look:
        lib.set_current_look(a.look)

    if a.cmd == "import":
        names = lib.import_folder(a.folder)
        print(f"Imported {len(names)} photos into {lib.root}")
        return 0

    from .server import serve
    watcher = None
    if not a.no_camera:
        resize = None if a.transfer == "full" else int(a.transfer)
        watcher = Watcher(lib, Camera(a.camera), a.interval, resize, a.max_size)
        watcher.start()
    print(f"Library: {lib.root} · film loaded: {LOOKS[lib.current_look].name}")
    if a.open:
        import threading
        import webbrowser
        threading.Timer(1.5, webbrowser.open, [f"http://127.0.0.1:{a.port}"]).start()
    serve(lib, watcher, port=a.port, max_size=a.max_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
