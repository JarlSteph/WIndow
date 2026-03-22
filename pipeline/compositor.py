"""
compositor.py — Composite video frames into window panes and render an MP4.

The panes are treated as one continuous window: the source frame is scaled
to cover the total combined pane width, then each pane receives its slice —
so it looks like a real window rather than two copies of the same image.
"""

import os
from datetime import date
from PIL import Image


def _combined_size(panes: list[tuple[int, int, int, int]]) -> tuple[int, int]:
    """Total pixel width and max height across all panes."""
    total_w = sum(x2 - x1 for x1, y1, x2, y2 in panes)
    max_h   = max(y2 - y1 for x1, y1, x2, y2 in panes)
    return total_w, max_h


def _center_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Crop to target aspect ratio (centre), then resize."""
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio    = src_w   / src_h

    if src_ratio > target_ratio:
        new_w  = int(src_h * target_ratio)
        offset = (src_w - new_w) // 2
        img    = img.crop((offset, 0, offset + new_w, src_h))
    elif src_ratio < target_ratio:
        new_h  = int(src_w / target_ratio)
        offset = (src_h - new_h) // 2
        img    = img.crop((0, offset, src_w, offset + new_h))

    return img.resize((target_w, target_h), Image.LANCZOS)


def composite(
    template_path: str,
    frame: Image.Image,
    panes: list[tuple[int, int, int, int]],
) -> Image.Image:
    """
    Paste one frame into the window panes as a single continuous scene.
    The template is composited on top so the window frame overlays the video.
    """
    template = Image.open(template_path).convert("RGBA")
    base     = Image.new("RGBA", template.size, (0, 0, 0, 255))

    total_w, total_h = _combined_size(panes)
    scaled = _center_crop(frame.convert("RGBA"), total_w, total_h)

    x_offset = 0
    for x1, y1, x2, y2 in panes:
        pw    = x2 - x1
        ph    = y2 - y1
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

    # Apply effects to raw frames first
    processed = apply_effects(frames, effects or [])

    # Build looping sequence
    looped = make_loop(processed, loop)
    print(f"  Loop style: {loop!r}  →  {len(processed)} → {len(looped)} frames")

    # Determine output size from first composited frame
    first = composite(template_path, looped[0], panes)
    h, w  = first.size[1], first.size[0]

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    writer.write(cv2.cvtColor(np.array(first), cv2.COLOR_RGB2BGR))

    for i, frame in enumerate(looped[1:], start=2):
        composited = composite(template_path, frame, panes)
        writer.write(cv2.cvtColor(np.array(composited), cv2.COLOR_RGB2BGR))
        if i % 24 == 0:
            print(f"  Rendered {i}/{len(looped)} frames...")

    writer.release()
    print(f"Saved: {output_path}")
    return output_path


def output_path(output_dir: str) -> str:
    """Return a dated .mp4 path inside output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, f"{date.today().isoformat()}.mp4")
