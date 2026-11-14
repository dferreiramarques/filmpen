# FilmPen

Film looks for the Olympus PEN E-PL9, applied automatically over the camera's Wi-Fi.
Take a photo, and a few seconds later it shows up on your laptop (or phone) already
"developed" with the film you have loaded.

Films in v0.1:

| key        | name              | feel |
|------------|-------------------|------|
| `negative` | Warm Negative 400 | Portra/Gold-style: lifted blacks, soft highlights, warm skin, gentle grain |
| `slide`    | Chrome 100        | Ektachrome/Velvia-style: deep blacks, punchy colour, cool shadows, fine grain |
| `bw`       | Tri-X 400         | High-speed B&W: yellow-filter mix, strong contrast, chunky grain |

## Install

Requires Python 3.10+ and an internet connection (do this *before* joining the camera's Wi-Fi).

**Windows:** double-click `install.bat`. It finds Python (or offers to install it with
winget), creates a `.venv`, installs numpy + Pillow, and can add a desktop shortcut.
Then double-click `start.bat` to start the server; it opens the gallery in your browser.
Edit the top of `start.bat` to change the port, the starting film, the transfer size
or the library folder. The first time, Windows Firewall may ask about Python: allow it
on private networks if you want to open the gallery from your phone.

**macOS / Linux:** `./install.sh`, then `./start.sh`
(e.g. `LOOK=bw TRANSFER=2048 ./start.sh`).

Manual: `pip install -r requirements.txt`, then `python -m filmpen run --open`.

## Standalone app (FilmPen.exe)

No Python needed on the machine that runs it.

- **Automatic:** every push to `main` builds `FilmPen.exe` on GitHub Actions
  (Actions tab ▸ latest run ▸ *Artifacts*). Push a tag like `v0.2.0` and the exe
  is attached to a GitHub Release.
- **Locally:** double-click `build_exe.bat` (needs Python once, on the build PC).
  The result is `dist\FilmPen.exe`.

Double-click `FilmPen.exe` to start the server and open the gallery; close its
window to stop it. Running it again while it's open just reopens the gallery.
Command-line arguments work as with `python -m filmpen`, e.g.
`FilmPen.exe run --transfer 2048 --look bw`.

It isn't code-signed, so the first time Windows SmartScreen may say
"Windows protected your PC": click *More info* ▸ *Run anyway*.

## Use it with the E-PL9

1. On the camera: **Menu ▸ Setup (wrench) ▸ Wi-Fi/Bluetooth Settings**, then make sure
   Wi-Fi is available.
2. Go to **Playback menu ▸ Connection to Smartphone** (or tap the Wi-Fi icon on the
   touchscreen). The camera shows its Wi-Fi name (starts with `E-PL9-`) and password.
   Menu names vary a little between firmware versions.
3. Join that Wi-Fi from your laptop. (While connected, the laptop has no internet.)
4. Run:

   ```bash
   python -m filmpen run --look negative
   ```

5. Open http://127.0.0.1:8080. New shots get downloaded and developed automatically.
   Tap a photo to switch film, **hold** it to compare with the original, or download it.

The camera can't shoot while it's in smartphone-connection mode. Shoot a few frames,
connect, and let FilmPen pull them (it only downloads shots it hasn't seen yet).
The **Loaded film** chips change the look used for *new* shots.

Useful options:

```bash
--transfer 2048      # ask the camera for a 2048px copy: much faster over Wi-Fi
--max-size 3000      # cap developed files at 3000px
--library ~/FilmPen  # where photos are stored (default)
--no-camera          # just browse / re-develop what's already in the library
```

## Without Wi-Fi

```bash
python -m filmpen import /Volumes/OM_SD/DCIM          # SD card → library, then `run --no-camera`
python -m filmpen develop photos/ --look all --out out # one-off batch, every look
python -m filmpen looks                               # list films
```

## Testing without the camera

```bash
python -m filmpen mock ./some-jpegs --port 8010
python -m filmpen run --camera http://127.0.0.1:8010 --library ./test-lib
```

Drop new JPEGs into `./some-jpegs` to simulate taking photos.

## How it talks to the camera

Olympus/OM bodies serve a small HTTP API at `http://192.168.0.10` while in
smartphone mode. It's the same API OI.Share uses, and it needs an `OI.Share`
User-Agent:

- `get_caminfo.cgi`: model
- `switch_cammode.cgi?mode=play`: playback mode (needed before listing)
- `get_imglist.cgi?DIR=/DCIM/100OLYMP`: CSV list (dir, name, size, attr, FAT date, FAT time)
- `/DCIM/100OLYMP/P1010001.JPG`: full file
- `get_resizeimg.cgi?DIR=…&size=2048`: resized copy

Only JPEGs are processed. Shooting RAW+JPEG keeps the ORF on the card untouched.
It should also work with other Wi-Fi Olympus/OM bodies (E-M10 II/III/IV, E-M5 II, PEN-F, E-PL7/8/10).

## Code map

```
filmpen/looks.py    film looks (curves, split tone, halation, grain, vignette); add new films here
filmpen/camera.py   Olympus Wi-Fi API client
filmpen/library.py  library on disk + background watcher
filmpen/server.py   local web UI / JSON API
filmpen/ui.html     the gallery
filmpen/mock.py     fake camera
filmpen_app.py      entry point for FilmPen.exe (filmpen.spec, build_exe.bat)
```

## Next ideas

- Roll mode: 24/36 exposures, no previews until you "develop" the roll
- Lo-fi extras: light leaks, date stamp, border/film rebate
- Pi Zero 2 W in a hot-shoe box: one Wi-Fi radio joins the camera, a USB dongle
  (or Bluetooth PAN) serves the gallery to your phone
- `.cube` LUT import so you can use looks made in Resolve/Lightroom
