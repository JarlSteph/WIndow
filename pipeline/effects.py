"""
effects.py — Per-frame visual effects applied to video frames before compositing.

Each effect is a function:  (frame: Image, idx: int, total: int) -> Image
  - frame  : PIL RGB image
  - idx    : 0-based frame index within the clip
  - total  : total number of frames in the clip
"""

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw


# ── colour grading ────────────────────────────────────────────────────────────

def warm(frame: Image.Image, idx: int, total: int) -> Image.Image:
    """Strong warm grade — heavy golden/orange push."""
    arr = np.array(frame, dtype=np.float32)
    arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.35, 0, 255)   # red up strong
    arr[:, :, 1] = np.clip(arr[:, :, 1] * 1.10, 0, 255)   # green slightly up
    arr[:, :, 2] = np.clip(arr[:, :, 2] * 0.65, 0, 255)   # blue down hard
    return Image.fromarray(arr.astype(np.uint8))


def cool(frame: Image.Image, idx: int, total: int) -> Image.Image:
    """Strong cool grade — heavy blue/teal push."""
    arr = np.array(frame, dtype=np.float32)
    arr[:, :, 0] = np.clip(arr[:, :, 0] * 0.65, 0, 255)   # red down hard
    arr[:, :, 1] = np.clip(arr[:, :, 1] * 0.95, 0, 255)
    arr[:, :, 2] = np.clip(arr[:, :, 2] * 1.40, 0, 255)   # blue up strong
    return Image.fromarray(arr.astype(np.uint8))


def noir(frame: Image.Image, idx: int, total: int) -> Image.Image:
    """Black & white with very high contrast."""
    gray = ImageEnhance.Contrast(frame.convert("L")).enhance(2.0)
    return gray.convert("RGB")


def cinematic(frame: Image.Image, idx: int, total: int) -> Image.Image:
    """Heavy desaturation + crushed blacks + boosted contrast."""
    out = ImageEnhance.Color(frame).enhance(0.45)          # strong desaturation
    out = ImageEnhance.Contrast(out).enhance(1.4)
    arr = np.array(out, dtype=np.float32)
    arr = arr * 0.88 + 8
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


# ── texture / atmosphere ──────────────────────────────────────────────────────

def dreamy(frame: Image.Image, idx: int, total: int) -> Image.Image:
    """Heavy glow: strong blur blended over the original."""
    blurred = frame.filter(ImageFilter.GaussianBlur(radius=8))
    return Image.blend(frame, blurred, alpha=0.6)


def vignette(frame: Image.Image, idx: int, total: int) -> Image.Image:
    """Heavy dark vignette — deep black edges."""
    w, h   = frame.size
    arr    = np.array(frame, dtype=np.float32)
    xs     = np.linspace(-1, 1, w)
    ys     = np.linspace(-1, 1, h)
    xx, yy = np.meshgrid(xs, ys)
    mask   = 1.0 - np.clip((xx ** 2 + yy ** 2) * 1.1, 0, 0.97)
    arr   *= mask[:, :, np.newaxis]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def grain(frame: Image.Image, idx: int, total: int) -> Image.Image:
    """Heavy film grain — very visible noise."""
    arr   = np.array(frame, dtype=np.float32)
    noise = np.random.normal(0, 28, arr.shape)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


# ── motion ────────────────────────────────────────────────────────────────────

def ken_burns(frame: Image.Image, idx: int, total: int) -> Image.Image:
    """Slow zoom-in (1.0× → 1.30×) across the clip — clearly visible push."""
    w, h   = frame.size
    scale  = 1.0 + 0.30 * (idx / max(total - 1, 1))
    nw, nh = int(w * scale), int(h * scale)
    zoomed = frame.resize((nw, nh), Image.LANCZOS)
    ox, oy = (nw - w) // 2, (nh - h) // 2
    return zoomed.crop((ox, oy, ox + w, oy + h))


# ── utilities ────────────────────────────────────────────────────────────────

def crop_black_bars(frame: Image.Image, threshold: int = 12) -> Image.Image:
    """Crop native black letterbox / pillarbox bars from a frame."""
    arr = np.array(frame.convert("RGB"))
    h, w = arr.shape[:2]

    row_means = arr.mean(axis=(1, 2))
    col_means = arr.mean(axis=(0, 2))

    rows = np.where(row_means > threshold)[0]
    cols = np.where(col_means > threshold)[0]

    if len(rows) == 0 or len(cols) == 0:
        return frame

    top, bottom = int(rows[0]),  int(rows[-1]) + 1
    left, right = int(cols[0]),  int(cols[-1]) + 1

    if top > h * 0.02 or bottom < h * 0.98 or left > w * 0.02 or right < w * 0.98:
        return frame.crop((left, top, right, bottom))

    return frame


# ── registry ──────────────────────────────────────────────────────────────────

EFFECTS = {
    "warm":       warm,
    "cool":       cool,
    "noir":       noir,
    "cinematic":  cinematic,
    "dreamy":     dreamy,
    "vignette":   vignette,
    "grain":      grain,
    "ken_burns":  ken_burns,
}


def apply_effects(frames: list[Image.Image], effect_names: list[str]) -> list[Image.Image]:
    """Apply a list of named effects to every frame in order."""
    fns = [EFFECTS[n] for n in effect_names if n in EFFECTS]
    if not fns:
        return frames

    total = len(frames)
    result = []
    for idx, frame in enumerate(frames):
        for fn in fns:
            frame = fn(frame, idx, total)
        result.append(frame)
    return result


# ── looping ───────────────────────────────────────────────────────────────────

def make_loop(frames: list[Image.Image], style: str) -> list[Image.Image]:
    """
    pingpong  — play forward then reverse  (smooth, always works)
    crossfade — body + short blend from end back to start (cinematic)
    """
    if style == "pingpong":
        return frames + list(reversed(frames))

    if style == "crossfade":
        n    = min(18, len(frames) // 4)
        body = list(frames[:-n])
        for i in range(n):
            alpha   = i / n
            blended = Image.blend(frames[-(n - i)], frames[i], alpha)
            body.append(blended)
        return body

    return frames
