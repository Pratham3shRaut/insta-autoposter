"""Optional: generate a fresh tip with Gemini once the built-in content bank runs out."""
from __future__ import annotations

import json
import os

import requests

PROMPT = """You write daily Instagram posts with short web development tips for
junior-to-mid developers (JavaScript, TypeScript, React, Next.js, CSS, GSAP,
Node.js, SQL, Git, Tailwind).

Write ONE new tip that is NOT about any of these already-posted titles:
{recent}

Return only JSON with these keys:
- "topic": one of JavaScript, TypeScript, React, Next.js, CSS, GSAP, Node.js, SQL, Git, Tailwind CSS
- "title": a punchy hook, max 45 characters
- "lang": one of js, ts, jsx, tsx, css, html, bash, sql
- "code": a correct, runnable snippet, max 10 lines, each line max 46 characters, use \\n for newlines
- "note": one sentence, max 95 characters, explaining the key idea
- "caption": 1-2 sentences for the Instagram caption
- "tags": 3 lowercase hashtags without the # sign
The code must be accurate and current. No emojis."""

REQUIRED = {"topic", "title", "lang", "code", "note", "caption", "tags"}


def valid(tip: dict) -> bool:
    if not REQUIRED <= tip.keys():
        return False
    lines = tip["code"].split("\n")
    return (
        len(tip["title"]) <= 60
        and 1 <= len(lines) <= 12
        and all(len(l) <= 52 for l in lines)
        and len(tip["note"]) <= 130
        and isinstance(tip["tags"], list)
    )


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
