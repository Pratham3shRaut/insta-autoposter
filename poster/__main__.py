"""Daily Instagram auto-poster.

Commands:
  python -m poster prepare            pick today's lesson, render the carousel, write the caption
  python -m poster publish --image-url URL [--image-url URL ...] --caption-file FILE
  python -m poster publish-reel --video-file FILE --caption-file FILE
  python -m poster preview [--count N]   render lessons into ./preview to check the design
  python -m poster whoami             check your token and see which account it posts to
  python -m poster refresh-token      refresh a 60-day Instagram Login token (and save it to GitHub)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from .generate import generate_lesson
from .instagram import Instagram, InstagramError
from .reel import build_reel
from .render import render_lesson

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "poster", "content.json")
STATE = os.path.join(ROOT, "state.json")
POSTS = "posts"

BASE_TAGS = ["webdevelopment", "webdev", "programming", "coding", "developer", "softwareengineering", "100daysofcode"]


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def handle() -> str:
    return os.environ.get("IG_HANDLE", "").strip().lstrip("@")


def now() -> datetime:
    return datetime.now(ZoneInfo(os.environ.get("POST_TIMEZONE", "Asia/Kolkata")))


def today() -> str:
    return now().strftime("%Y-%m-%d")


def norm_title(title: str) -> str:
    return " ".join(title.lower().split())


def posted_titles(state: dict, kind: str) -> set[str]:
    # Entries from before Reels existed have no "kind"; they were all carousels.
    return {norm_title(h["title"]) for h in state.get("history", []) if h.get("kind", "carousel") == kind}


def next_series_part(state: dict) -> dict | None:
    """The part that would continue the most recent series, so generated posts keep it going."""
    parts = [h for h in state.get("history", []) if h.get("series") and h.get("kind", "carousel") == "carousel"]
    if not parts:
        return None
    last = max(parts, key=lambda h: h["part"])
    return {
        "series": last["series"],
        "part": last["part"] + 1,
        "covered": [h["title"] for h in parts if h["series"] == last["series"]],
    }


def build_caption(lesson: dict) -> str:
    tags = []
    for t in list(lesson.get("tags", [])) + BASE_TAGS:
        t = t.lstrip("#").lower().replace(" ", "")
        if t and t not in tags:
            tags.append(t)

    series, part = lesson.get("series"), lesson.get("part")
    lines = [lesson["title"].strip()]
    if series:
        lines += [f"\U0001f4da Part {part} of our {series} series"]
    if lesson.get("intro"):
        lines += ["", lesson["intro"].strip()]

    covers = [s["heading"] for s in lesson["slides"]]
    if lesson.get("scenario"):
        covers.append("A real-world scenario")
    if covers:
        lines += ["", "In this post, you'll learn:"]
        lines += [f"✅ {c}" for c in covers]

    if lesson.get("cta"):
        lines += ["", lesson["cta"].strip()]
    lines += ["", "\U0001f4cc Save this post for later"]

    if handle() and series:
        lines += ["", f"Follow @{handle()} so you don't miss Part {part + 1}."]
        if part > 1:
            lines += [f"Missed the earlier parts? They're on our profile."]
    elif handle():
        lines += ["", f"Follow @{handle()} for more posts like this."]

    lines += ["", " ".join(f"#{t}" for t in tags[:12])]  # Instagram allows max 30
    return "\n".join(lines)


def set_output(**kv):
    out = os.environ.get("GITHUB_OUTPUT")
    for k, v in kv.items():
        print(f"{k}={v}")
        if out:
            with open(out, "a", encoding="utf-8") as f:
                # values may contain newlines (multiple image paths), so use GitHub's heredoc syntax
                if "\n" in str(v):
                    delim = "EOF_POSTER"
                    f.write(f"{k}<<{delim}\n{v}\n{delim}\n")
                else:
                    f.write(f"{k}={v}\n")


# --- commands --------------------------------------------------------------
def cmd_prepare(args):
    state = load_json(STATE, {"last_published_date": None, "history": []})
    date = today()
    if state.get("last_published_date") == date and not args.force:
        print(f"already posted today ({date}); skipping")
        set_output(skip="true")
        return

    history_titles = [h["title"] for h in state.get("history", [])]
    posted = posted_titles(state, "carousel")

    bank = load_json(BANK, [])
    lesson = next((l for l in bank if norm_title(l["title"]) not in posted), None)
    source = "bank"
    if lesson is None:
        lesson = generate_lesson(history_titles, posted, next_series_part(state))
        source = "gemini"
    if lesson is None:
        print("NO NEW LESSON: every lesson in poster/content.json has already been posted, and no new one")
        print("could be generated (GEMINI_API_KEY missing or generation failed). Refusing to repost.")
        print("Add new lessons to poster/content.json or set the GEMINI_API_KEY secret.")
        sys.exit(1)

    # Time in the name so several posts on one day don't overwrite each other.
    slug = now().strftime("%Y-%m-%d-%H%M%S")
    out_dir = os.path.join(ROOT, POSTS)
    image_paths = render_lesson(lesson, handle(), out_dir, slug)
    image_paths = [os.path.relpath(p, ROOT).replace(os.sep, "/") for p in image_paths]

    caption_path = f"{POSTS}/{slug}.txt"
    with open(os.path.join(ROOT, caption_path), "w", encoding="utf-8") as f:
        f.write(build_caption(lesson))
    save_json(os.path.join(ROOT, POSTS, f"{slug}.json"), lesson)

    print(f"prepared lesson from {source}: {lesson['title']} ({len(image_paths)} slides)")

    # The Reel is optional: any failure here must not stop the carousel from posting.
    reel_path = ""
    if args.no_reel or not os.environ.get("GEMINI_API_KEY"):
        print("skipping reel (disabled or GEMINI_API_KEY not set)")
    else:
        try:
            out = os.path.join(ROOT, POSTS, f"{slug}.mp4")
            build_reel(lesson, [os.path.join(ROOT, p) for p in image_paths], handle(), out)
            reel_path = f"{POSTS}/{slug}.mp4"
        except Exception as e:
            print(f"warning: reel not created, posting the carousel only ({e})")

    set_output(
        skip="false",
        image_paths="\n".join(image_paths),
        caption_path=caption_path,
        reel_path=reel_path,
        title=lesson["title"].replace("\n", " "),
    )


def cmd_publish(args):
    with open(args.caption_file, encoding="utf-8") as f:
        caption = f.read()
    lesson = load_json(args.caption_file.replace(".txt", ".json"), {})
    state = load_json(STATE, {"history": []})

    # Last line of defense: never publish a title that's already in the history.
    if norm_title(lesson.get("title", "")) in posted_titles(state, "carousel"):
        print(f"REFUSING TO PUBLISH: '{lesson.get('title')}' was already posted.")
        sys.exit(1)

    urls = args.image_url
    try:
        ig = Instagram()
        media_id = ig.publish_carousel(urls, caption) if len(urls) > 1 else ig.publish_image(urls[0], caption)
    except InstagramError as e:
        print(f"PUBLISH FAILED: {e}")
        sys.exit(1)
    print(f"published! media id {media_id}")

    state["last_published_date"] = today()
    entry = {"date": today(), "title": lesson.get("title", ""), "media_id": media_id, "kind": "carousel"}
    if lesson.get("series"):
        entry.update(series=lesson["series"], part=lesson["part"])
    state.setdefault("history", []).append(entry)
    save_json(STATE, state)


def cmd_publish_reel(args):
    with open(args.caption_file, encoding="utf-8") as f:
        caption = f.read()
    lesson = load_json(args.caption_file.replace(".txt", ".json"), {})
    state = load_json(STATE, {"history": []})

    if norm_title(lesson.get("title", "")) in posted_titles(state, "reel"):
        print(f"REFUSING TO PUBLISH: a reel for '{lesson.get('title')}' was already posted.")
        sys.exit(1)

    try:
        media_id = Instagram().publish_reel(args.video_file, caption)
    except InstagramError as e:
        print(f"REEL PUBLISH FAILED: {e}")
        sys.exit(1)
    print(f"reel published! media id {media_id}")

    state.setdefault("history", []).append(
        {"date": today(), "title": lesson.get("title", ""), "media_id": media_id, "kind": "reel"})
    save_json(STATE, state)


def cmd_preview(args):
    bank = load_json(BANK, [])
    out_dir = os.path.join(ROOT, "preview")
    os.makedirs(out_dir, exist_ok=True)
    for i, lesson in enumerate(bank[args.start : args.start + args.count], start=args.start + 1):
        paths = render_lesson(lesson, handle() or "yourhandle", out_dir, f"lesson-{i:02d}")
        print(f"lesson {i}: {lesson['title']} -> {len(paths)} slides")
        for p in paths:
            print(f"  {p}")


def cmd_whoami(args):
    try:
        print(Instagram().whoami())
    except InstagramError as e:
        print(f"FAILED: {e}")
        sys.exit(1)


def cmd_refresh(args):
    if not (os.environ.get("GH_TOKEN") and os.environ.get("GITHUB_REPOSITORY")):
        # Don't rotate the token if we can't store the new one.
        print("GH_PAT not configured, skipping token refresh. Add GH_PAT (see README) or")
        print("replace IG_ACCESS_TOKEN manually before it expires (60 days).")
        return
    try:
        token, expires = Instagram().refresh_token()
    except InstagramError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
    print(f"token refreshed; valid for {expires // 86400} more days")
    # gh reads the secret value from stdin, so it never appears in logs or argv
    res = subprocess.run(
        ["gh", "secret", "set", "IG_ACCESS_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"]],
        input=token, text=True, capture_output=True,
    )
    if res.returncode != 0:
        print(f"could not save refreshed token to GitHub: {res.stderr.strip()}")
        sys.exit(1)
    print("saved refreshed token to the IG_ACCESS_TOKEN repository secret")


def main():
    p = argparse.ArgumentParser(prog="poster")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("prepare")
    s.add_argument("--force", action="store_true")
    s.add_argument("--no-reel", action="store_true", help="only render the carousel")
    s.set_defaults(fn=cmd_prepare)
    s = sub.add_parser("publish-reel")
    s.add_argument("--video-file", required=True); s.add_argument("--caption-file", required=True)
    s.set_defaults(fn=cmd_publish_reel)
    s = sub.add_parser("publish")
    s.add_argument("--image-url", action="append", required=True, help="repeatable; 2+ makes a carousel")
    s.add_argument("--caption-file", required=True)
    s.set_defaults(fn=cmd_publish)
    s = sub.add_parser("preview")
    s.add_argument("--count", type=int, default=3); s.add_argument("--start", type=int, default=0)
    s.set_defaults(fn=cmd_preview)
    sub.add_parser("whoami").set_defaults(fn=cmd_whoami)
    sub.add_parser("refresh-token").set_defaults(fn=cmd_refresh)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
