// Runs the real filmpen/looks.py (numpy + Pillow) in the browser via Pyodide.
importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");

const PY = `
import io, json, sys, zlib
sys.path.insert(0, "/tmp/fp")
import numpy as np
from PIL import Image, ImageOps
import looks

def looks_json():
    return json.dumps([{"key": l.key, "name": l.name, "description": l.description}
                       for l in looks.LOOKS.values()])

def develop(data, name, key, max_size, quality):
    src = Image.open(io.BytesIO(data.to_py()))
    exif = src.getexif()
    img = ImageOps.exif_transpose(src).convert("RGB")
    if max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
    rgb = np.asarray(img, dtype=np.float32) / 255.0
    out = looks.apply_look(rgb, looks.LOOKS[key], seed=zlib.crc32(name.encode()))
    res = Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGB")
    if 0x0112 in exif:
        exif[0x0112] = 1
    buf = io.BytesIO()
    res.save(buf, "JPEG", quality=quality, exif=exif.tobytes(),
             subsampling=0 if quality >= 90 else 2)
    return buf.getvalue()
`;

let py, develop;

async function init() {
  py = await loadPyodide();
  await py.loadPackage(["numpy", "Pillow"]);
  const src = await (await fetch("looks.py")).text();
  py.FS.mkdirTree("/tmp/fp");
  py.FS.writeFile("/tmp/fp/looks.py", src);
  py.runPython(PY);
  develop = py.globals.get("develop");
  const looks = JSON.parse(py.globals.get("looks_json")());
  postMessage({ type: "ready", looks });
}

onmessage = (e) => {
  const m = e.data;
  if (m.type !== "develop") return;
  try {
    const res = develop(new Uint8Array(m.buf), m.name, m.look, m.maxSize, 92);
    const bytes = new Uint8Array(res.toJs());
    res.destroy();
    postMessage({ type: "done", id: m.id, gen: m.gen, bytes }, [bytes.buffer]);
  } catch (err) {
    postMessage({ type: "error", id: m.id, gen: m.gen, message: String(err.message || err).split("\n").slice(-2).join(" ") });
  }
};

init().catch((err) => postMessage({ type: "fatal", message: String(err.message || err) }));
