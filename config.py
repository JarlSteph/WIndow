import os
from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
WINDOW_TEMPLATE_PATH = "assets/window_template.png"
OUTPUT_DIR = "output"

# --- YouTube ---
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# --- Ollama ---
OLLAMA_MODEL = "ministral-3:3b"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# --- Video clip settings ---
FRAME_TIMESTAMP = 30  # seconds into the video to start the clip
VIDEO_DURATION = 12  # seconds of source footage to extract (looping doubles this)

# --- Window frame outer bounding box (x1, y1, x2, y2) ---
# Used to exclude the brown frame from wall colour tinting.
# Run calibrate.py and click the outermost corners of the frame to measure.
WINDOW_FRAME_RECT: tuple[int, int, int, int] = (448, 0, 1200, 832)

# --- Window pane bounding boxes ---
# Each entry is (x1, y1, x2, y2) in pixels relative to window_template.png
# Run `python calibrate.py` to view a coordinate grid and measure these values.
# Example placeholder — update after running calibrate.py with your template:
WINDOW_PANES: list[tuple[int, int, int, int]] = [
    (533, 0, 819, 756),  # left pane
    (878, 0, 1163, 751),  # right pane
]
