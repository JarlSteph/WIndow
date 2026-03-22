"""
compositor.py — Composite video frames into window panes and render an MP4.

The panes are treated as one continuous window: the source frame is scaled
to cover the total combined pane width, then each pane receives its slice —
so it looks like a real window rather than two copies of the same image.
"""

import os
from datetime import date
from PIL import Image

# Muted, painterly wall colours the LLM can choose from
WALL_COLORS: dict[str, tuple[int, int, int]] = {
    "red": (172, 72, 58),  # original warm red
    "yellow": (180, 155, 75),  # muted ochre/mustard
    "terracotta": (170, 100, 62),  # terracotta
    "sage": (100, 120, 85),  # muted sage green
    "teal": (62, 118, 112),  # muted teal
    "blue": (78, 105, 142),  # dusty blue
    "lavender": (128, 108, 148),  # dusty lavender
    "rose": (160, 100, 100),  # dusty rose
    "sand": (175, 158, 128),  # warm sand
}


def _tint_template(template: Image.Image, color_name: str) -> Image.Image:
    """
    Hue-shift the wall colour, then restore the frame region pixel-perfectly.
    The frame area (WINDOW_FRAME_RECT) is never touched — it's stamped back
    from the original after tinting, making it impossible for it to change.
    """
    import cv2
    import numpy as np
    from config import WINDOW_FRAME_RECT

    target_rgb = WALL_COLORS.get(color_name, WALL_COLORS["red"])

    arr   = np.array(template.convert("RGBA"), dtype=np.uint8)
    alpha = arr[:, :, 3].copy()

    # Measure wall colour from pixels OUTSIDE the frame rect
    fx1, fy1, fx2, fy2 = WINDOW_FRAME_RECT
    h_img, w_img = alpha.shape
    ys, xs = np.mgrid[0:h_img, 0:w_img]
    wall_mask = (alpha > 128) & ((xs < fx1) | (xs > fx2) | (ys < fy1) | (ys > fy2))

    if not wall_mask.any():
        return template

    bgr = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)

    t_bgr = np.uint8([[[target_rgb[2], target_rgb[1], target_rgb[0]]]])
    t_hsv = cv2.cvtColor(t_bgr, cv2.COLOR_BGR2HSV)[0, 0]
    tgt_h, tgt_s, tgt_v = float(t_hsv[0]), float(t_hsv[1]), float(t_hsv[2])

    src_h = float(np.median(hsv[wall_mask, 0]))
    src_s = float(np.median(hsv[wall_mask, 1]))
    src_v = float(np.median(hsv[wall_mask, 2]))

    # Tint ALL visible pixels (wall + frame) — we'll fix the frame next
    visible = alpha > 128
    hsv[visible, 0] = (hsv[visible, 0] + (tgt_h - src_h)) % 180
    if src_s > 0:
        hsv[visible, 1] = np.clip(hsv[visible, 1] * (tgt_s / src_s), 0, 255)
    if src_v > 0:
        hsv[visible, 2] = np.clip(hsv[visible, 2] * (tgt_v / src_v), 0, 255)

    result_bgr = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
    out = Image.fromarray(np.dstack([result_rgb, alpha]), "RGBA")

    # Restore the frame region from the original — guaranteed pixel-perfect
    frame_crop = template.crop((fx1, fy1, fx2, fy2))
    out.paste(frame_crop, (fx1, fy1))
    return out


def _combined_size(panes: list[tuple[int, int, int, int]]) -> tuple[int, int]:
    """Total pixel width and max height across all panes."""
    total_w = sum(x2 - x1 for x1, y1, x2, y2 in panes)
    max_h = max(y2 - y1 for x1, y1, x2, y2 in panes)
    return total_w, max_h


def _center_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Crop to target aspect ratio (centre), then resize."""
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        offset = (src_w - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, src_h))
    elif src_ratio < target_ratio:
        new_h = int(src_w / target_ratio)
        offset = (src_h - new_h) // 2
        img = img.crop((0, offset, src_w, offset + new_h))

    return img.resize((target_w, target_h), Image.LANCZOS)


def composite(
    template_path: str,
    frame: Image.Image,
    panes: list[tuple[int, int, int, int]],
    wall_color: str = "red",
) -> Image.Image:
    """
    Paste one frame into the window panes as a single continuous scene.
    The template is composited on top so the window frame overlays the video.
    """
    template = Image.open(template_path).convert("RGBA")
    if wall_color and wall_color != "red":
        template = _tint_template(template, wall_color)
    base = Image.new("RGBA", template.size, (0, 0, 0, 255))

    total_w, total_h = _combined_size(panes)
    scaled = _center_crop(frame.convert("RGBA"), total_w, total_h)

    x_offset = 0
    for x1, y1, x2, y2 in panes:
        pw = x2 - x1
        ph = y2 - y1
        # Slice the correct horizontal strip from the scaled scene
        slice_ = scaled.crop((x_offset, 0, x_offset + pw, total_h))
        # Fit slice height to pane height (handles minor height differences between panes)
        if slice_.size[1] != ph:
            slice_ = slice_.resize((pw, ph), Image.LANCZOS)
        base.paste(slice_, (x1, y1))
        x_offset += pw

    base.alpha_composite(template)
    return base.convert("RGB")


def composite_video(
    template_path: str,
    frames: list[Image.Image],
    fps: float,
    panes: list[tuple[int, int, int, int]],
    output_path: str,
    loop: str = "pingpong",
    effects: list[str] | None = None,
    wall_color: str = "red",
) -> str:
    """
    Render all frames into the window and save as an MP4.
    Applies effects and looping before compositing.
    Returns the output path.
    """
    import cv2
    import numpy as np
    from pipeline.effects import apply_effects, make_loop

    if not frames:
        raise ValueError("No frames provided")

    # Apply effects to raw frames first; grain is always added last
    effect_list = list(effects or [])
    if "grain" not in effect_list:
        effect_list.append("grain")
    processed = apply_effects(frames, effect_list)

    # Build looping sequence
    looped = make_loop(processed, loop)
    print(f"  Loop style: {loop!r}  →  {len(processed)} → {len(looped)} frames")

    # Pre-tint the template once (avoids re-loading + re-tinting every frame)
    template = Image.open(template_path).convert("RGBA")
    if wall_color and wall_color != "red":
        print(f"  Wall colour: {wall_color!r}")
        template = _tint_template(template, wall_color)
    import tempfile, shutil

    _tinted_tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    template.save(_tinted_tmp.name)
    tinted_path = _tinted_tmp.name

    # Determine output size from first composited frame
    first = composite(tinted_path, looped[0], panes)
    h, w = first.size[1], first.size[0]

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    writer.write(cv2.cvtColor(np.array(first), cv2.COLOR_RGB2BGR))

    for i, frame in enumerate(looped[1:], start=2):
        composited = composite(tinted_path, frame, panes)
        writer.write(cv2.cvtColor(np.array(composited), cv2.COLOR_RGB2BGR))
        if i % 24 == 0:
            print(f"  Rendered {i}/{len(looped)} frames...")

    writer.release()
    os.unlink(tinted_path)
    print(f"Saved: {output_path}")
    return output_path


def output_path(output_dir: str) -> str:
    """Return a dated .mp4 path inside output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, f"{date.today().isoformat()}.mp4")
