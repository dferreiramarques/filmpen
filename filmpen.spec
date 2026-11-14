# PyInstaller spec for FilmPen.exe — build with `build_exe.bat`
# or `pyinstaller filmpen.spec --noconfirm --clean`.
import sys

a = Analysis(
    ["filmpen_app.py"],
    pathex=["."],
    datas=[("filmpen/ui.html", "filmpen")],
    hiddenimports=[],
    excludes=["tkinter", "matplotlib", "scipy", "pandas", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FilmPen",
    icon="assets/filmpen.ico" if sys.platform == "win32" else None,
    console=True,          # the window shows status; closing it stops the server
    upx=False,
    runtime_tmpdir=None,
)
