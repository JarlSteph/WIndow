"""
publisher.py — Stage the daily video to docs/ and push to GitHub Pages.

Flow:
  1. Compress video with ffmpeg if > 90 MB (GitHub's limit is 100 MB)
  2. Copy to docs/latest.mp4
  3. Generate docs/index.html with today's metadata
  4. git add docs/, commit, push

Git push failures (offline, no remote) are logged but never crash the pipeline.
"""

import os
import subprocess
import textwrap
from datetime import date


DOCS_DIR   = "docs"
VIDEO_NAME = "latest.mp4"
DOCS_VIDEO = os.path.join(DOCS_DIR, VIDEO_NAME)
DOCS_INDEX = os.path.join(DOCS_DIR, "index.html")


# ── video staging ─────────────────────────────────────────────────────────────

def _compress(src: str, dst: str) -> None:
    """Re-encode src → dst with H.264, targeting ~20 MB."""
    cmd = [
        "ffmpeg", "-y", "-i", src,
        "-c:v", "libx264", "-preset", "slow", "-crf", "28",
        "-vf", "scale='min(1280,iw)':-2",   # cap width at 1280, keep AR
        "-an",                               # no audio (pipeline produces none)
        "-movflags", "+faststart",           # moov atom first → fast browser start
        dst,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg compression failed:\n{result.stderr.decode(errors='replace')}"
        )


def _stage_video(src: str) -> None:
    os.makedirs(DOCS_DIR, exist_ok=True)
    size = os.path.getsize(src)
    # Always re-encode: cv2's mp4v codec is not browser-compatible; H.264 is required
    print(f"  Re-encoding {size / 1e6:.1f} MB to H.264 for browser playback...")
    _compress(src, DOCS_VIDEO)
    print(f"  → {os.path.getsize(DOCS_VIDEO) / 1e6:.1f} MB saved to {DOCS_VIDEO}")


# ── HTML generation ────────────────────────────────────────────────────────────

def _render_html(display_date: str, title: str, poem_text: str) -> str:
    # Escape HTML special chars and preserve line breaks in poem
    import html as _html
    safe_title = _html.escape(title)
    safe_poem  = "<br>".join(_html.escape(line) for line in poem_text.splitlines())

    return textwrap.dedent(f"""\
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>Daily Window — {display_date}</title>
          <style>
            *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
            html, body {{
              width: 100%; height: 100%;
              background: #000;
              overflow: hidden;
              font-family: Georgia, "Times New Roman", serif;
            }}
            video {{
              position: fixed;
              inset: 0;
              width: 100%;
              height: 100%;
              object-fit: cover;
            }}
            .overlay {{
              position: fixed;
              bottom: 0; left: 0; right: 0;
              padding: 2.5rem 3rem;
              background: linear-gradient(to top, rgba(0,0,0,0.80) 0%, transparent 100%);
              color: #fff;
              pointer-events: none;
            }}
            .date {{
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
              font-size: clamp(0.65rem, 1.2vw, 0.85rem);
              font-weight: 300;
              letter-spacing: 0.2em;
              text-transform: uppercase;
              opacity: 0.6;
              margin-bottom: 0.6rem;
            }}
            .title {{
              font-size: clamp(1.6rem, 4vw, 3rem);
              font-weight: 400;
              font-style: italic;
              line-height: 1.15;
              margin-bottom: 0.8rem;
            }}
            .poem {{
              font-size: clamp(0.8rem, 1.6vw, 1.05rem);
              font-weight: 400;
              line-height: 1.7;
              opacity: 0.85;
            }}
          </style>
        </head>
        <body>
          <video src="{VIDEO_NAME}" autoplay muted loop playsinline></video>
          <div class="overlay">
            <p class="date">{display_date}</p>
            <p class="title">{safe_title}</p>
            <p class="poem">{safe_poem}</p>
          </div>
        </body>
        </html>
    """)


# ── git operations ─────────────────────────────────────────────────────────────

def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def _push(date_slug: str) -> None:
    if _git("rev-parse", "--git-dir").returncode != 0:
        print("  [publish] Not a git repo — skipping push.")
        return

    if _git("remote", "get-url", "origin").returncode != 0:
        print("  [publish] No remote 'origin' — skipping push.")
        print("  Run: git remote add origin https://github.com/YOUR/REPO.git")
        return

    _git("add", DOCS_DIR)

    result = _git("commit", "-m", f"window: {date_slug}")
    if result.returncode != 0:
        if "nothing to commit" in result.stdout + result.stderr:
            print("  [publish] Nothing new to commit.")
            return
        print(f"  [publish] git commit failed:\n{result.stderr}")
        return

    result = _git("push")
    if result.returncode != 0:
        print(f"  [publish] Push failed (offline?) — committed locally, push when online.")
        print(f"  Run: git push")
    else:
        print("  [publish] Pushed to origin ✓")


# ── public entry point ────────────────────────────────────────────────────────

def publish(video_path: str, title: str, poem_text: str) -> None:
    """Stage video + HTML to docs/ and push to GitHub Pages."""
    display_date = date.today().strftime("%B %d, %Y")
    date_slug    = date.today().isoformat()

    _stage_video(video_path)

    html = _render_html(display_date, title, poem_text)
    with open(DOCS_INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Generated {DOCS_INDEX}")

    _push(date_slug)
