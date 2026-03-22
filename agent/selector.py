"""
selector.py — LLM agent that picks a YouTube video, visual effects, and loop style.

Returns a Selection dataclass with:
  url        — YouTube video URL
  effects    — list of effect names to apply (e.g. ["warm", "vignette"])
  loop       — loop style: "pingpong" | "crossfade"
"""

import json
import random
import re
from dataclasses import dataclass, field
from datetime import date

import requests
from googleapiclient.discovery import build

from config import YOUTUBE_API_KEY, OLLAMA_MODEL, OLLAMA_HOST
from pipeline.effects import EFFECTS
from pipeline.compositor import WALL_COLORS

# Rotate through these so the LLM gets a different subject each run
_THEMES = [
    "arctic glacier",
    "tropical rainforest",
    "Sahara desert dunes",
    "cherry blossom Japan",
    "Norwegian fjord",
    "Grand Canyon sunset",
    "volcanic lava flow",
    "Scottish highlands fog",
    "Patagonia mountains",
    "Icelandic waterfall",
    "Swiss Alps winter",
    "Namib desert sunrise",
    "New Zealand coast",
    "Venetian canal dawn",
    "Amazon river aerial",
    "Himalayan peak clouds",
    "Canadian Rockies lake",
    "Moroccan desert night",
    "Black Forest Germany",
    "Oregon coast storm",
    "Tuscany golden hour",
    "Greenland ice cap",
    "Faroe Islands cliff",
    "Atacama night sky",
]


@dataclass
class Selection:
    url: str
    effects: list[str] = field(default_factory=list)
    loop: str = "pingpong"
    theme: str = ""
    wall_color: str = "red"


_EFFECT_LIST = ", ".join(EFFECTS.keys())
_COLOR_LIST = ", ".join(WALL_COLORS.keys())

_SYSTEM_PROMPT = f"""You are a curator of cinematic nature and landscape videos for a daily living-window display.
Reply with ONLY a JSON object — no explanation, no markdown, no code fences.
Schema:
{{
  "query": "2-4 word YouTube search query",
  "effects": ["effect1"],
  "loop": "pingpong",
  "wall_color": "yellow"
}}
STRICT RULES:
- The query MUST be about scenery, nature, landscapes, or architecture — NEVER people, faces, vlogs, tutorials, or talking heads.
- Good subjects: mountains, ocean, forest, desert, city skyline, clouds, waterfalls, snow, fog, sunset, canyon.
- Available effects: {_EFFECT_LIST}
- Pick 1-2 effects that match the mood.
- Available loops: pingpong, crossfade
- Available wall colors: {_COLOR_LIST}
- Pick a wall color that complements the scene (e.g. yellow for desert, teal for ocean, lavender for twilight, sage for forest)."""

_USER_PROMPT = (
    "Today is {date}. The scene theme for today is: {theme}. "
    "Create a 2-4 word YouTube search query for a breathtaking cinematic video of that theme — "
    "NO people, NO talking, pure scenery only. "
    "Output only the JSON."
)


def _ask_ollama(date_str: str, theme: str) -> dict:
    """Call Ollama and return parsed JSON dict, with safe fallbacks."""
    payload = {
        "model": OLLAMA_MODEL,
        "system": _SYSTEM_PROMPT,
        "prompt": _USER_PROMPT.format(date=date_str, theme=theme),
        "stream": False,
        "temperature": 1.5,
    }
    resp = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=60)
    resp.raise_for_status()
    raw = resp.json().get("response", "").strip()

    # Extract JSON — handle models that wrap it in markdown or add commentary
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            query = " ".join(str(data.get("query", "")).split()[:6]).strip()
            effects = [e for e in data.get("effects", []) if e in EFFECTS][:2]
            loop = data.get("loop", "pingpong")
            wall_color = data.get("wall_color", "red")
            if loop not in ("pingpong", "crossfade"):
                loop = "pingpong"
            if wall_color not in WALL_COLORS:
                wall_color = "red"
            if query:
                print(f"LLM query:      {query!r}")
                print(f"LLM effects:    {effects}")
                print(f"LLM loop:       {loop}")
                print(f"LLM wall color: {wall_color}")
                return {
                    "query": query,
                    "effects": effects,
                    "loop": loop,
                    "wall_color": wall_color,
                }
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback: treat the whole response as a plain search query
    query = " ".join(re.sub(r'["\'\n{}]', "", raw).split()[:6]).strip()
    print(f"LLM query (plain fallback): {query!r}")
    return {
        "query": query or "golden hour landscape cinematic",
        "effects": ["warm"],
        "loop": "pingpong",
        "wall_color": "red",
    }


def _search_youtube(query: str) -> str:
    if not YOUTUBE_API_KEY:
        raise EnvironmentError("YOUTUBE_API_KEY is not set. Add it to your .env file.")

    # Always append cinematic qualifiers to bias results toward high-quality scenery
    search_query = f"{query} cinematic 4k"

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    # Try with progressively relaxed filters — always keep duration >= medium to avoid Shorts
    attempts = [
        dict(videoDuration="medium", videoDefinition="high", order="viewCount"),
        dict(videoDuration="long", videoDefinition="high", order="viewCount"),
        dict(videoDuration="medium", videoDefinition="any", order="viewCount"),
        dict(videoDuration="long", videoDefinition="any", order="viewCount"),
        dict(videoDuration="medium", videoDefinition="any", order="relevance"),
        dict(videoDuration="long", videoDefinition="any", order="relevance"),
    ]

    items = []
    for filters in attempts:
        response = (
            youtube.search()
            .list(q=search_query, part="id", type="video", maxResults=1, **filters)
            .execute()
        )
        items = response.get("items", [])
        if items:
            break

    if not items:
        raise RuntimeError(f"YouTube search returned no results for query: {query!r}")

    video_id = items[0]["id"]["videoId"]
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"Selected video: {url}")
    return url


def select_video() -> Selection:
    """Ask the LLM to choose a video, effects, and loop style. Return a Selection."""
    date_str = date.today().strftime("%B %d, %Y")
    theme = random.choice(_THEMES)
    print(f"Today's theme: {theme!r}")
    data = _ask_ollama(date_str, theme)
    url = _search_youtube(data["query"])
    return Selection(
        url=url,
        effects=data["effects"],
        loop=data["loop"],
        theme=theme,
        wall_color=data["wall_color"],
    )


def describe_image(image_path: str) -> str:
    """Use Ollama vision to generate a brief description of the image content."""
    import base64

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "model": OLLAMA_MODEL,
        "system": "You are an assistant that briefly describes the content of images.",
        "prompt": "Describe the content of this image",
        "stream": False,
        "temperature": 0.5,
        "max_tokens": 150,
        "images": [b64],
    }
    resp = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=60)
    resp.raise_for_status()
    description = resp.json().get("response", "").strip()
    print(f"Image description: {description}")
    return description


def poem(description: str) -> tuple[str, str]:
    """Use Ollama to generate a title and 4-line poem based on the image description.

    Returns (title, poem_text).
    """
    payload = {
        "model": OLLAMA_MODEL,
        "system": (
            "You are a poetic soul trapped in a window, seeing only a short daily glimpse of the world outside. "
            "Reply with ONLY a JSON object — no explanation, no markdown, no code fences.\n"
            'Schema: {"title": "short evocative title (3-6 words)", "poem": "4-line poem"}'
        ),
        "prompt": f"Write a title and a 4-line poem inspired by this image description: {description}",
        "stream": False,
        "temperature": 1.1,
        "max_tokens": 120,
    }
    resp = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=60)
    resp.raise_for_status()
    raw = resp.json().get("response", "").strip()

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            title_str = str(data.get("title", "")).strip()
            poem_text = str(data.get("poem", "")).strip()
            if title_str and poem_text:
                print(f"Title: {title_str}")
                print(f"Poem:\n{poem_text}")
                return title_str, poem_text
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback: use raw as poem with a generic title
    print(f"Poem (fallback):\n{raw}")
    return "Today's Window", raw
