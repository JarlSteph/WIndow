"""
make_template.py — Convert your window JPG into a transparent-pane PNG template.

Punches out the glass pane regions (defined in config.py) to full transparency
so the video frame shows through behind the window frame.

Usage:
    1. Run `python calibrate.py` first to measure pane coordinates.
    2. Update WINDOW_PANES in config.py with those values.
    3. Run this script:
           python make_template.py path/to/your_window.jpg

Output: assets/window_template.png  (ready to use as the compositing template)
"""

import sys
from PIL import Image
from config import WINDOW_PANES

INPUT = sys.argv[1] if len(sys.argv) > 1 else "assets/window_template.jpg"
OUTPUT = "assets/window_template.png"


def main():
    img = Image.open(INPUT).convert("RGBA")
    pixels = img.load()

    for x1, y1, x2, y2 in WINDOW_PANES:
        for x in range(x1, x2):
            for y in range(y1, y2):
                pixels[x, y] = (0, 0, 0, 0)   # fully transparent

    img.save(OUTPUT)
    print(f"Saved: {OUTPUT}  ({img.size[0]}x{img.size[1]} px)")
    print("Panes punched out:", WINDOW_PANES)


if __name__ == "__main__":
    main()
