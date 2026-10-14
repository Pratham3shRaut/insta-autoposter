"""Optional: generate a fresh tip with Gemini once the built-in content bank runs out."""
from __future__ import annotations

import json
import os

import requests

PROMPT = """You write daily Instagram posts for intermediate-to-senior developers.
Topics can span JavaScript, TypeScript, React, Next.js, CSS, GSAP, Node.js, SQL,
databases, system design, networking, debugging, git, security, and developer
career advice. Go beyond basic syntax — prefer internals, tradeoffs, performance,
and "most people don't know this" angles over beginner syntax tips.

Write ONE new post that is NOT about any of these already-posted titles:
{recent}

Pick ONE "type" and return ONLY JSON matching that type's shape:

type "code" (a before/after or illustrative snippet):
{{"type": "code", "topic": str, "title": str (max 45 chars), "lang": one of
  js/ts/jsx/tsx/css/html/bash/sql, "code": str (\\n-joined, max 10 lines, each
  line max 46 chars), "note": str (max 95 chars), "caption": str (1-2 sentences),
  "tags": [3 lowercase hashtags, no #]}}

type "fact" (one striking number or short phrase + explanation, no code):
{{"type": "fact", "topic": str, "title": str (max 45 chars), "stat": str (max 24
  chars, the big headline number/phrase), "note": str (max 220 chars, explains
  the stat), "caption": str (2-3 sentences), "tags": [3 lowercase hashtags]}}

type "comparison" (two-sided tradeoff):
{{"type": "comparison", "topic": str, "title": str (max 45 chars),
  "left": {{"label": str (max 16 chars), "body": str (max 140 chars)}},
  "right": {{"label": str (max 16 chars), "body": str (max 140 chars)}},
  "note": str (max 160 chars), "caption": str (1-2 sentences),
  "tags": [3 lowercase hashtags]}}

type "quiz" (a question with options; the image must NOT reveal the answer,
only the caption does — so people engage before scrolling to the answer):
{{"type": "quiz", "topic": str, "title": str (max 45 chars),
  "question": str (max 160 chars), "options": [2-4 short strings],
  "note": str (max 60 chars, a neutral prompt like "Answer in the caption",
  must NOT contain the answer), "caption": str (starts with "Answer: X, ..."
  and explains why), "tags": [3 lowercase hashtags]}}

Vary which type you pick across requests. The content must be accurate and
current. No emojis."""

REQUIRED_BY_TYPE = {
    "code": {"topic", "title", "lang", "code", "note", "caption", "tags"},
    "fact": {"topic", "title", "stat", "note", "caption", "tags"},
    "comparison": {"topic", "title", "left", "right", "note", "caption", "tags"},
    "quiz": {"topic", "title", "question", "options", "note", "caption", "tags"},
}


def valid(tip: dict) -> bool:
    kind = tip.get("type", "code")
    required = REQUIRED_BY_TYPE.get(kind)
    if not required or not required <= tip.keys():
        return False
    if len(tip["title"]) > 60 or not isinstance(tip["tags"], list):
        return False
    if kind == "code":
        lines = tip["code"].split("\n")
        return 1 <= len(lines) <= 12 and all(len(l) <= 52 for l in lines) and len(tip["note"]) <= 130
    if kind == "fact":
        return len(tip["stat"]) <= 40 and len(tip["note"]) <= 260
    if kind == "comparison":
        sides = tip["left"], tip["right"]
        return all(isinstance(s, dict) and "label" in s and "body" in s for s in sides) and len(tip["note"]) <= 200
    if kind == "quiz":
        return isinstance(tip["options"], list) and 2 <= len(tip["options"]) <= 4 and len(tip["note"]) <= 200
    return False


def generate_tip(recent_titles: list[str]) -> dict | None:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(recent="\n".join(f"- {t}" for t in recent_titles[-60:]))}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9},
    }
    for _ in range(3):
        try:
            r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=60)
            if r.status_code != 200:
                print(f"gemini error {r.status_code}: {r.text[:300]}")
                continue
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            tip = json.loads(text)
            if isinstance(tip, list):
                tip = tip[0]
            if valid(tip):
                return tip
            print("generated tip failed validation, retrying")
        except Exception as e:  # network/format issues: fall back to the bank
            print(f"gemini generation failed: {e}")
    return None
