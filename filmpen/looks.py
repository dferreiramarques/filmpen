"""Film emulation looks: tone curves, colour balance, grain, halation, vignette.

Everything works on float32 RGB arrays in 0..1 (sRGB-encoded, which is what
film-look tweaking is usually tuned against).
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


@dataclass
class Look:
    key: str
    name: str
    description: str
    # Tone curve as (input, output) control points, applied to all channels.
    curve: list[tuple[float, float]]
    # Optional extra per-channel curves (R, G, B), applied after the main curve.
    channel_curves: tuple[list, list, list] | None = None
    saturation: float = 1.0
    # Colour balance: multipliers for shadows / highlights per channel.
    shadow_tint: tuple[float, float, float] = (1.0, 1.0, 1.0)
    highlight_tint: tuple[float, float, float] = (1.0, 1.0, 1.0)
    # Black & white: channel mix weights (None = colour).
    mono_mix: tuple[float, float, float] | None = None
    mono_tone: tuple[float, float, float] = (1.0, 1.0, 1.0)
    grain: float = 0.03        # strength (std dev of noise in 0..1 units)
    grain_size: float = 1.0    # 1.0 = fine (~ISO 100-200), 2.0+ = coarse
    grain_color: float = 0.15  # 0 = pure luminance grain, 1 = full chroma
    halation: float = 0.0      # strength of red glow around highlights
    halation_radius: float = 0.012  # fraction of image width
    halation_threshold: float = 0.78
    vignette: float = 0.0
    extras: dict = field(default_factory=dict)


LOOKS: dict[str, Look] = {
    "negative": Look(
        key="negative",
        name="Warm Negative 400",
        description="Portra/Gold-style colour negative: lifted blacks, soft "
                    "highlight roll-off, warm skin, gentle grain.",
        curve=[(0.0, 0.075), (0.12, 0.16), (0.35, 0.38), (0.6, 0.64),
               (0.85, 0.86), (1.0, 0.94)],
        channel_curves=(
            [(0.0, 0.0), (0.5, 0.515), (1.0, 1.0)],   # R: slightly warm mids
            [(0.0, 0.0), (0.5, 0.505), (1.0, 0.99)],
            [(0.0, 0.025), (0.5, 0.48), (1.0, 0.95)],  # B: cooler shadows, warm highs
        ),
        saturation=0.86,
        shadow_tint=(0.95, 1.0, 1.02),
        highlight_tint=(1.07, 1.02, 0.91),
        grain=0.032,
        grain_size=1.4,
        grain_color=0.25,
        halation=0.18,
        halation_radius=0.010,
        vignette=0.12,
    ),
    "slide": Look(
        key="slide",
        name="Chrome 100",
        description="Ektachrome/Velvia-style slide film: deep blacks, punchy "
                    "contrast and saturation, cool clean shadows, fine grain.",
        curve=[(0.0, 0.0), (0.08, 0.035), (0.25, 0.19), (0.5, 0.5),
               (0.75, 0.81), (0.92, 0.955), (1.0, 1.0)],
        channel_curves=(
            [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)],
            [(0.0, 0.0), (0.5, 0.505), (1.0, 1.0)],
            [(0.0, 0.02), (0.5, 0.51), (1.0, 0.985)],
        ),
        saturation=1.28,
        shadow_tint=(0.96, 0.99, 1.06),
        highlight_tint=(1.01, 1.0, 0.99),
        grain=0.018,
        grain_size=1.0,
        grain_color=0.2,
        halation=0.08,
        halation_radius=0.007,
        halation_threshold=0.85,
        vignette=0.22,
    ),
    "bw": Look(
        key="bw",
        name="Tri-X 400",
        description="Classic high-speed black & white: yellow-filter channel "
                    "mix, strong mid contrast, chunky grain.",
        curve=[(0.0, 0.03), (0.1, 0.06), (0.3, 0.25), (0.5, 0.5),
               (0.72, 0.77), (0.9, 0.93), (1.0, 0.97)],
        mono_mix=(0.38, 0.5, 0.12),
        mono_tone=(1.0, 0.995, 0.975),  # very slight warm paper tone
        grain=0.075,
        grain_size=1.9,
        grain_color=0.0,
        vignette=0.18,
    ),
}


# --------------------------------------------------------------------------
# Building blocks
# --------------------------------------------------------------------------

def _apply_curve(x: np.ndarray, points) -> np.ndarray:
    xs, ys = zip(*points)
    return np.interp(x, xs, ys).astype(np.float32)


def _blur(channel: np.ndarray, radius: float) -> np.ndarray:
    """Gaussian blur a single float 0..1 channel via Pillow (fast, no scipy).

    The glow is soft, so it's blurred at quarter resolution and scaled back up:
    much faster on big files, and the upscale smooths away 8-bit banding."""
    h, w = channel.shape
    f = 4 if min(h, w) >= 400 else 1
    img = Image.fromarray(np.clip(channel * 255 + 0.5, 0, 255).astype(np.uint8), "L")
    if f > 1:
        img = img.resize((max(w // f, 1), max(h // f, 1)), Image.BILINEAR)
    img = img.filter(ImageFilter.GaussianBlur(radius / f))
    if f > 1:
        img = img.resize((w, h), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def _grain_field(h: int, w: int, size: float, rng: np.random.Generator) -> np.ndarray:
    """Gaussian noise with grain clumps roughly `size` pixels across (per 2000px)."""
    # Scale grain with resolution so it looks similar on 2MP previews and 16MP files.
    scale = max(w, h) / 2000.0
    px = max(size * scale, 1.0)
    sh, sw = max(int(h / px), 1), max(int(w / px), 1)
    noise = rng.standard_normal((sh, sw)).astype(np.float32)
    if (sh, sw) != (h, w):
        img = Image.fromarray(noise, "F").resize((w, h), Image.BICUBIC)
        noise = np.array(img, dtype=np.float32)
        noise /= max(noise.std(), 1e-6)
    return noise


def _vignette(h: int, w: int, amount: float) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    yy = (yy - h / 2) / (h / 2)
    xx = (xx - w / 2) / (w / 2)
    r = np.sqrt(xx * xx + yy * yy) / np.sqrt(2)
    return (1.0 - amount * np.clip(r, 0, 1) ** 2.2)[..., None]


# --------------------------------------------------------------------------
# Main pipeline
# --------------------------------------------------------------------------

def apply_look(rgb: np.ndarray, look: Look, seed: int | None = None) -> np.ndarray:
    """rgb: float32 HxWx3 in 0..1. Returns a new array in 0..1."""
    rng = np.random.default_rng(seed)
    h, w, _ = rgb.shape
    x = rgb.astype(np.float32, copy=True)

    # 1. Halation is computed from the *scene* highlights, before tone mapping.
    halo = None
    if look.halation > 0:
        lum0 = x @ LUMA
        mask = np.clip((lum0 - look.halation_threshold) / (1 - look.halation_threshold), 0, 1)
        halo = _blur(mask, look.halation_radius * w)

    # 2. Black & white conversion.
    if look.mono_mix is not None:
        mix = np.array(look.mono_mix, dtype=np.float32)
        mono = (x @ (mix / mix.sum()))[..., None]
        x = np.repeat(mono, 3, axis=2)

    # 3. Tone curve + per-channel curves.
    x = _apply_curve(x, look.curve)
    if look.channel_curves:
        for c in range(3):
            x[..., c] = _apply_curve(x[..., c], look.channel_curves[c])

    # 4. Split toning: tint shadows and highlights separately.
    lum = x @ LUMA
    hw = np.clip(lum, 0, 1)[..., None]
    sw = 1.0 - hw
    tint = sw * np.array(look.shadow_tint, np.float32) + hw * np.array(look.highlight_tint, np.float32)
    x = x * tint

    # 5. Saturation (around luminance).
    if look.mono_mix is None and look.saturation != 1.0:
        lum = (x @ LUMA)[..., None]
        x = lum + (x - lum) * look.saturation
    if look.mono_mix is not None:
        x = x * np.array(look.mono_tone, np.float32)

    # 6. Halation: add a red-orange glow, like light scattering off the film base.
    if halo is not None:
        glow = halo[..., None] * np.array([1.0, 0.32, 0.12], np.float32) * look.halation
        x = 1 - (1 - x) * (1 - glow)  # screen blend

    # 7. Vignette.
    if look.vignette > 0:
        x = x * _vignette(h, w, look.vignette)

    # 8. Grain, strongest in the midtones (as on real film).
    if look.grain > 0:
        lum = np.clip(x @ LUMA, 0, 1)
        mid = (0.35 + 2.6 * lum * (1 - lum))[..., None]
        g = _grain_field(h, w, look.grain_size, rng)[..., None]
        if look.grain_color > 0:
            chroma = np.stack([_grain_field(h, w, look.grain_size, rng) for _ in range(3)], axis=2)
            g = g * (1 - look.grain_color) + chroma * look.grain_color
        x = x + g * look.grain * mid

    return np.clip(x, 0, 1)


def load_rgb(path: Path, max_size: int | None = None) -> tuple[np.ndarray, Image.Image]:
    """Load a JPEG, apply EXIF rotation, optionally downscale. Returns (array, original PIL)."""
    src = Image.open(path)
    img = ImageOps.exif_transpose(src).convert("RGB")
    if max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0, src


def develop_file(src_path: Path, dst_path: Path, look_key: str,
                 max_size: int | None = None, quality: int = 92) -> Path:
    look = LOOKS[look_key]
    rgb, src = load_rgb(src_path, max_size)
    out = apply_look(rgb, look, seed=zlib.crc32(src_path.name.encode()))
    img = Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGB")

    # Keep the camera EXIF, but the pixels are already upright now.
    exif = src.getexif()
    if 0x0112 in exif:
        exif[0x0112] = 1
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst_path.with_suffix(".tmp.jpg")
    img.save(tmp, "JPEG", quality=quality, exif=exif.tobytes(), subsampling=0 if quality >= 90 else 2)
    tmp.replace(dst_path)
    return dst_path


def make_thumb(src_path: Path, dst_path: Path, size: int = 640) -> Path:
    img = ImageOps.exif_transpose(Image.open(src_path)).convert("RGB")
    img.thumbnail((size, size), Image.LANCZOS)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst_path, "JPEG", quality=82)
    return dst_path
