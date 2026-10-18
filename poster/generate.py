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
      "points": [2-4 short bullet strings, each max 60 characters],
      "examples": [2-3 short real-world example strings, each max 30 characters]
    }}
    // 3 to 6 of these
  ],
  "cta": str (a question for the caption to invite comments, 1 sentence),
  "tags": [3 lowercase hashtags, no # sign]
}}

Content must be accurate and current. No emojis in heading/subtitle/points."""

REQUIRED_LESSON = {"topic", "title", "intro", "slides", "cta", "tags"}
REQUIRED_SLIDE = {"heading", "subtitle", "points", "examples"}


def valid(lesson: dict) -> bool:
    if not REQUIRED_LESSON <= lesson.keys():
        return False
    if len(lesson["title"]) > 70 or not isinstance(lesson["tags"], list):
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
    return True


def generate_lesson(recent_titles: list[str], taken: set[str]) -> dict | None:
    """taken: normalized titles already posted; a generated lesson matching one is rejected."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    unique_recent = list(dict.fromkeys(recent_titles))[-80:]
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(recent="\n".join(f"- {t}" for t in unique_recent))}]}],
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
                return lesson
        except Exception as e:  # network/format issues: fall back to the bank
            print(f"gemini generation failed: {e}")
    return None
