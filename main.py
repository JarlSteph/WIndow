"""
main.py — Entry point for the Daily Window pipeline.

Run manually:  python main.py
Run on a schedule: python scheduler.py
"""

import os
import tempfile

from agent.selector import select_video, describe_image, poem as generate_poem
from pipeline.fetcher import fetch_frames
from pipeline.compositor import composite_video, output_path
from publisher import publish
from config import (
    WINDOW_TEMPLATE_PATH,
    WINDOW_PANES,
    OUTPUT_DIR,
    FRAME_TIMESTAMP,
    VIDEO_DURATION,
)


def run():
    print("=== Daily Window ===")

    print("1/5  Selecting video...")
    selection = select_video()

    print(f"2/5  Fetching {VIDEO_DURATION}s clip at {FRAME_TIMESTAMP}s ...")
    frames, fps = fetch_frames(selection.url, FRAME_TIMESTAMP, VIDEO_DURATION)

    print(f"3/5  Rendering  effects={selection.effects}  loop={selection.loop!r} ...")
    out = output_path(OUTPUT_DIR)
    composite_video(
        WINDOW_TEMPLATE_PATH,
        frames,
        fps,
        WINDOW_PANES,
        out,
        loop=selection.loop,
        effects=selection.effects,
        wall_color=selection.wall_color,
    )

    print("4/5  Generating poem...")
    mid = frames[len(frames) // 2]
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
    mid.save(tmp_path, "JPEG")
    description = describe_image(tmp_path)
    os.unlink(tmp_path)
    title, poem_text = generate_poem(description)

    print("5/5  Publishing to GitHub Pages...")
    publish(out, title, poem_text)

    print("Done.")


if __name__ == "__main__":
    run()
