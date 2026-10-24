"""Optional: generate a fresh carousel lesson with Gemini once the content bank runs out."""
from __future__ import annotations

import json
import os

import requests

PROMPT = """You write educational Instagram carousel posts that explain a software
development concept simply, in the style of a "swipe to learn" explainer thread.
Topics can span web development, backend, databases, system design, networking,
security, git, and general computer science. Aim for clarity a junior developer
can follow, broken into 3-6 distinct sub-topics (one per slide).

Write ONE new lesson that is NOT about any of these already-posted titles:
{recent}

Return ONLY JSON matching this shape:
{{
  "topic": str (short category label, e.g. "APIs", "Databases", "Git"),
  "title": str (the carousel's title-slide headline, max 50 characters),
  "intro": str (1-2 sentences introducing the topic, for the caption),
  "slides": [
    {{
      "heading": str (max 20 characters, the sub-topic name),
      "subtitle": str (max 60 characters, one-line description),
      "explain": str (2-3 plain sentences explaining the idea to a beginner, max 230 characters),
      "points": [2-3 short bullet strings, each max 60 characters],
      "flow": [optional: 2-4 short box labels (max 16 characters each) for a left-to-right
               diagram of how data or requests move, only when a flow genuinely helps],
      "examples": [0-3 short real-world example strings, each max 30 characters]
    }}
    // 3 to 6 of these
  ],
  "scenario": {{
    "situation": str (a realistic developer moment, max 140 characters),
    "problem": str (what goes wrong without this concept, max 140 characters),
    "fix": str (how applying the concept solves it, concrete, max 170 characters),
    "takeaway": str (one-line lesson, max 70 characters)
  }},
  "cta": str (a question for the caption to invite comments, 1 sentence),
  "tags": [3 lowercase hashtags, no # sign]
}}

The scenario must be a believable, specific story (a real bug, slowdown or mistake), not a
generic statement. Content must be accurate and current. No emojis anywhere."""

REQUIRED_LESSON = {"topic", "title", "intro", "slides", "scenario", "cta", "tags"}
REQUIRED_SLIDE = {"heading", "subtitle", "points", "examples"}
REQUIRED_SCENARIO = {"situation", "problem", "fix", "takeaway"}


def valid(lesson: dict) -> bool:
    if not REQUIRED_LESSON <= lesson.keys():
        return False
    if len(lesson["title"]) > 70 or not isinstance(lesson["tags"], list):
        return False
    scenario = lesson["scenario"]
    if not isinstance(scenario, dict) or not REQUIRED_SCENARIO <= scenario.keys():
        return False
    slides = lesson["slides"]
    if not isinstance(slides, list) or not 3 <= len(slides) <= 6:
        return False
    for s in slides:
        if not isinstance(s, dict) or not REQUIRED_SLIDE <= s.keys():
            return False
        if not isinstance(s["points"], list) or not isinstance(s["examples"], list):
            return False
        if len(s["heading"]) > 30:
            return False
        if "flow" in s and not (isinstance(s["flow"], list) and 2 <= len(s["flow"]) <= 4):
            return False
    return True


SERIES_PROMPT = """

This post is Part {part} of an ongoing "{series}" series that teaches the subject step by step.
Earlier parts covered, in order:
{covered}
Pick the natural next topic that builds on those parts, and do not repeat any of them."""


def generate_lesson(recent_titles: list[str], taken: set[str], series: dict | None = None) -> dict | None:
    """taken: normalized titles already posted; a generated lesson matching one is rejected.
    series: {"series", "part", "covered"} to generate the next part of a running series."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    unique_recent = list(dict.fromkeys(recent_titles))[-80:]
    prompt = PROMPT.format(recent="\n".join(f"- {t}" for t in unique_recent))
    if series:
        prompt += SERIES_PROMPT.format(
            part=series["part"], series=series["series"], covered="\n".join(f"- {t}" for t in series["covered"]),
        )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9},
    }
    for _ in range(3):
        try:
            r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=60)
            if r.status_code != 200:
                print(f"gemini error {r.status_code}: {r.text[:300]}")
                continue
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            lesson = json.loads(text)
            if isinstance(lesson, list):
                lesson = lesson[0]
            if not valid(lesson):
                print("generated lesson failed validation, retrying")
            elif " ".join(lesson["title"].lower().split()) in taken:
                print(f"generated lesson '{lesson['title']}' was already posted, retrying")
            else:
                if series:
                    lesson.update(series=series["series"], part=series["part"],
                                  topic=f"{series['series']} #{series['part']}")
                return lesson
        except Exception as e:  # network/format issues: fall back to the bank
            print(f"gemini generation failed: {e}")
    return None
