"""
main.py — Entry point for the Daily Window pipeline.

Run manually:  python main.py
Run on a schedule: python scheduler.py
"""

from agent.selector import select_video
from pipeline.fetcher import fetch_frames
from pipeline.compositor import composite_video, output_path
from publisher import publish
from config import WINDOW_TEMPLATE_PATH, WINDOW_PANES, OUTPUT_DIR, FRAME_TIMESTAMP, VIDEO_DURATION


def run():
    print("=== Daily Window ===")

    print("1/4  Selecting video...")
    selection = select_video()

    print(f"2/4  Fetching {VIDEO_DURATION}s clip at {FRAME_TIMESTAMP}s ...")
    frames, fps = fetch_frames(selection.url, FRAME_TIMESTAMP, VIDEO_DURATION)

    print(f"3/4  Rendering  effects={selection.effects}  loop={selection.loop!r} ...")
    out = output_path(OUTPUT_DIR)
    composite_video(
        WINDOW_TEMPLATE_PATH,
        frames, fps,
        WINDOW_PANES,
        out,
        loop=selection.loop,
        effects=selection.effects,
    )

    publish(out, selection)

    print("Done.")


if __name__ == "__main__":
    run()
