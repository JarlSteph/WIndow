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
import shutil
import subprocess
import textwrap
from datetime import date

from agent.selector import Selection

DOCS_DIR   = "docs"
VIDEO_NAME = "latest.mp4"
DOCS_VIDEO = os.path.join(DOCS_DIR, VIDEO_NAME)
DOCS_INDEX = os.path.join(DOCS_DIR, "index.html")
SIZE_LIMIT = 90 * 1024 * 1024   # 90 MB — safe headroom below GitHub's 100 MB cap


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
    if size > SIZE_LIMIT:
        print(f"  Video is {size / 1e6:.1f} MB — compressing...")
        _compress(src, DOCS_VIDEO)
        print(f"  Compressed to {os.path.getsize(DOCS_VIDEO) / 1e6:.1f} MB → {DOCS_VIDEO}")
    else:
        shutil.copy2(src, DOCS_VIDEO)
        print(f"  Copied {size / 1e6:.1f} MB → {DOCS_VIDEO}")


# ── HTML generation ────────────────────────────────────────────────────────────

def _render_html(sel: Selection, display_date: str) -> str:
    effects_str = ", ".join(sel.effects) if sel.effects else "none"
    theme_str   = sel.theme.title() if sel.theme else "Daily Window"

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
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
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
              background: linear-gradient(to top, rgba(0,0,0,0.75) 0%, transparent 100%);
              color: #fff;
              pointer-events: none;
            }}
            .date {{
              font-size: clamp(0.75rem, 1.5vw, 1rem);
              font-weight: 300;
              letter-spacing: 0.18em;
              text-transform: uppercase;
              opacity: 0.7;
              margin-bottom: 0.5rem;
            }}
            .theme {{
              font-size: clamp(1.8rem, 5vw, 3.5rem);
              font-weight: 600;
              letter-spacing: -0.01em;
              line-height: 1.1;
              margin-bottom: 0.75rem;
            }}
            .meta {{
              font-size: clamp(0.65rem, 1.2vw, 0.8rem);
              font-weight: 400;
              opacity: 0.45;
              letter-spacing: 0.1em;
              text-transform: uppercase;
            }}
          </style>
        </head>
        <body>
          <video src="{VIDEO_NAME}" autoplay muted loop playsinline></video>
          <div class="overlay">
            <p class="date">{display_date}</p>
            <p class="theme">{theme_str}</p>
            <p class="meta">effects: {effects_str} &nbsp;&bull;&nbsp; loop: {sel.loop}</p>
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

def publish(video_path: str, selection: Selection) -> None:
    """Stage video + HTML to docs/ and push to GitHub Pages."""
    display_date = date.today().strftime("%B %d, %Y")
    date_slug    = date.today().isoformat()

    print("4/4  Publishing to GitHub Pages...")
    _stage_video(video_path)

    html = _render_html(selection, display_date)
    with open(DOCS_INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Generated {DOCS_INDEX}")

    _push(date_slug)
