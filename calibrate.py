"""
calibrate.py — Draw a coordinate grid over the window template so you can
               measure the exact pixel bounding boxes of each glass pane.

Usage:
    python calibrate.py

Opens a window with the template overlaid with a grid + coordinates.
Hover your mouse over the pane corners and note the (x, y) values shown
in the terminal. Then update WINDOW_PANES in config.py.
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont

GRID_STEP = 50       # pixels between grid lines
OUTPUT = "assets/calibration_grid.png"

_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"]


def _find_template(arg: str | None) -> str:
    """Return image path from CLI arg, or auto-detect first image in assets/."""
    if arg:
        return arg
    for name in sorted(os.listdir("assets")):
        if any(name.lower().endswith(ext) for ext in _EXTENSIONS):
            return os.path.join("assets", name)
    raise FileNotFoundError(
        "No image found in assets/. "
        "Drop your window JPG/PNG there, or pass the path as an argument:\n"
        "  python calibrate.py path/to/image.jpg"
    )


def draw_grid(img: Image.Image, step: int) -> Image.Image:
    out = img.copy().convert("RGB")
    draw = ImageDraw.Draw(out)
    w, h = out.size

    # Try to load a small font; fall back to default if not available
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 10)
    except Exception:
        font = ImageFont.load_default()

    # Vertical lines
    for x in range(0, w, step):
        draw.line([(x, 0), (x, h)], fill=(255, 0, 0, 180), width=1)
        draw.text((x + 2, 2), str(x), fill=(255, 255, 0), font=font)

    # Horizontal lines
    for y in range(0, h, step):
        draw.line([(0, y), (w, y)], fill=(255, 0, 0, 180), width=1)
        draw.text((2, y + 2), str(y), fill=(255, 255, 0), font=font)

    return out


def interactive_coords(img: Image.Image):
    """
    Show the image with scroll-to-zoom and click-to-print real pixel coordinates.

    Controls:
      + or =          — zoom in (centred on cursor)
      -               — zoom out
      Left click      — print the real image coordinate to terminal
      R               — reset zoom
      Q               — quit
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        print("OpenCV not installed — saving grid image instead.")
        return False

    WIN = "Calibrate  |  +/-=zoom  click=print coords  R=reset  Q=quit"
    source = np.array(img)[:, :, ::-1].copy()   # RGB → BGR
    ih, iw = source.shape[:2]

    # Viewport state
    state = {
        "zoom": 1.0,
        "ox": 0,      # top-left corner of view in image coords
        "oy": 0,
        "mx": 0,      # last mouse position in window coords
        "my": 0,
    }

    ZOOM_STEP = 1.25
    MIN_ZOOM  = 1.0
    MAX_ZOOM  = 16.0

    def clamp_origin(ox, oy, zoom):
        vw = int(iw / zoom)
        vh = int(ih / zoom)
        ox = max(0, min(ox, iw - vw))
        oy = max(0, min(oy, ih - vh))
        return ox, oy

    def get_real(wx, wy):
        """Window pixel → real image pixel."""
        vw = int(iw / state["zoom"])
        vh = int(ih / state["zoom"])
        # current viewport is source[oy:oy+vh, ox:ox+vw] scaled to window size
        win_img = current_frame()
        wh, ww = win_img.shape[:2]
        rx = state["ox"] + int(wx * vw / ww)
        ry = state["oy"] + int(wy * vh / wh)
        return max(0, min(rx, iw - 1)), max(0, min(ry, ih - 1))

    def current_frame():
        zoom = state["zoom"]
        ox, oy = state["ox"], state["oy"]
        vw = max(1, int(iw / zoom))
        vh = max(1, int(ih / zoom))
        crop = source[oy:oy + vh, ox:ox + vw]
        # Scale up to a fixed display size (max 1400 wide)
        disp_w = min(iw, 1400)
        disp_h = int(disp_w * vh / vw)
        return cv2.resize(crop, (disp_w, disp_h), interpolation=cv2.INTER_LINEAR)

    def zoom_around_cursor(direction):
        """Zoom in (direction=1) or out (direction=-1) centred on the mouse."""
        old_zoom = state["zoom"]
        new_zoom = old_zoom * (ZOOM_STEP if direction > 0 else 1 / ZOOM_STEP)
        new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, new_zoom))
        rx, ry = get_real(state["mx"], state["my"])
        state["zoom"] = new_zoom
        vw = int(iw / new_zoom)
        vh = int(ih / new_zoom)
        state["ox"], state["oy"] = clamp_origin(rx - vw // 2, ry - vh // 2, new_zoom)

    def on_mouse(event, x, y, flags, param):
        state["mx"], state["my"] = x, y
        if event == cv2.EVENT_LBUTTONDOWN:
            rx, ry = get_real(x, y)
            print(f"  Clicked: x={rx}, y={ry}")

    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, min(iw, 1400), min(ih, 900))
    cv2.setMouseCallback(WIN, on_mouse)

    print("+ / =  : zoom in (centred on cursor)")
    print("-      : zoom out")
    print("R      : reset zoom")
    print("Q      : quit")
    print("Click  : print real image coordinates")

    while True:
        frame = current_frame()

        # Draw crosshair at mouse position
        h, w = frame.shape[:2]
        mx, my = state["mx"], state["my"]
        cv2.line(frame, (mx, 0), (mx, h), (0, 255, 0), 1)
        cv2.line(frame, (0, my), (w, my), (0, 255, 0), 1)

        # Show real coordinates in corner
        rx, ry = get_real(mx, my)
        label = f"x={rx}  y={ry}   zoom={state['zoom']:.1f}x   (+/- to zoom, R reset, Q quit)"
        cv2.putText(frame, label, (10, 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 255, 0), 1, cv2.LINE_AA)

        cv2.imshow(WIN, frame)
        key = cv2.waitKey(16) & 0xFF
        if key == ord("q"):
            break
        elif key in (ord("+"), ord("=")):
            zoom_around_cursor(1)
        elif key == ord("-"):
            zoom_around_cursor(-1)
        elif key == ord("r"):
            state["zoom"], state["ox"], state["oy"] = 1.0, 0, 0

    cv2.destroyAllWindows()
    return True


def main():
    try:
        template_path = _find_template(sys.argv[1] if len(sys.argv) > 1 else None)
        img = Image.open(template_path)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"Template size: {img.size[0]} x {img.size[1]} px")
    grid_img = draw_grid(img, GRID_STEP)

    if not interactive_coords(grid_img):
        grid_img.save(OUTPUT)
        print(f"Grid saved to {OUTPUT} — open it and note the pane corner coordinates.")
        print("Then update WINDOW_PANES in config.py.")


if __name__ == "__main__":
    main()
