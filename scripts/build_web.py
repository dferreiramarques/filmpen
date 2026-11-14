"""Assemble the static site in _site/ (served by GitHub Pages; app lives at /app/).

looks.py is copied from the package so the web app and the desktop app share one
implementation of the film looks.
"""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
out = root / "_site"
if out.exists():
    shutil.rmtree(out)
shutil.copytree(root / "web", out)
shutil.copy(root / "filmpen" / "looks.py", out / "app" / "looks.py")
(out / ".nojekyll").touch()
print(f"Built {out}")
