"""
fetcher.py — Stream frames directly from YouTube via yt-dlp + OpenCV.

Primary path: yt-dlp -g gets the direct stream URL, OpenCV seeks into it.
No full download needed, no ffmpeg muxing, no codec issues.
"""

import subprocess
import tempfile
import os
from PIL import Image
from pipeline.effects import crop_black_bars

_FORMAT = "bestvideo[ext=mp4][height<=1080]/bestvideo[ext=mp4]/bestvideo[height<=1080]/best[ext=mp4]/best"


def fetch_frames(url: str, timestamp: int = 30, duration: int = 8) -> tuple[list[Image.Image], float]:
    """
    Stream `duration` seconds of video starting at `timestamp`.

    Returns:
        (frames, fps) — list of PIL Images and the source frame rate.
    """
    import cv2

    stream_url = _get_stream_url(url)
    print(f"  Stream URL obtained, opening with OpenCV...")

    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open stream: {stream_url[:80]}...")

    fps          = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total_ms     = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps * 1000

    # If the requested timestamp is past the video, start at 10% in instead
    seek_ms = timestamp * 1000
    if total_ms > 0 and seek_ms >= total_ms * 0.9:
        seek_ms = total_ms * 0.1
        print(f"  Timestamp {timestamp}s is near/past video end ({total_ms/1000:.0f}s) — seeking to {seek_ms/1000:.0f}s instead")

    cap.set(cv2.CAP_PROP_POS_MSEC, seek_ms)

    frames = []
    max_frames = int(fps * duration)
    while len(frames) < max_frames:
        ret, bgr = cap.read()
        if not ret:
            break
        frames.append(Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)))

    cap.release()

    if not frames:
        raise RuntimeError("OpenCV read 0 frames from the stream. The video may be unavailable or region-locked.")

    # Detect and crop native black bars (letterbox/pillarbox)
    original_size   = frames[0].size
    cropped_sample  = crop_black_bars(frames[0])
    if cropped_sample.size != original_size:
        cw, ch = cropped_sample.size
        ow, oh = original_size
        box    = ((ow - cw) // 2, (oh - ch) // 2, (ow + cw) // 2, (oh + ch) // 2)
        print(f"  Black bars removed: {ow}×{oh} → {cw}×{ch}")
        frames = [f.crop(box) for f in frames]

    w, h = frames[0].size
    print(f"  Extracted {len(frames)} frames at {fps:.1f} fps  ({w}×{h})")
    return frames, fps


def _get_stream_url(url: str) -> str:
    """Use yt-dlp -g to get a direct streamable URL (no download)."""
    result = subprocess.run(
        ["yt-dlp", "--quiet", "--no-warnings", "-g",
         "--format", _FORMAT, url],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp -g failed:\n{result.stderr.strip()}")

    # -g may return multiple lines (video+audio); take the first (video)
    stream_url = result.stdout.strip().splitlines()[0]
    if not stream_url:
        raise RuntimeError("yt-dlp -g returned an empty URL")
    return stream_url
