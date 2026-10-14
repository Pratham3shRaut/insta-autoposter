"""Daily Instagram auto-poster.

Commands:
  python -m poster prepare            pick today's tip, render the image, write the caption
  python -m poster publish --image-url URL --caption-file FILE
  python -m poster preview [--count N]   render tips into ./preview to check the design
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

from .generate import generate_tip
from .instagram import Instagram, InstagramError
from .render import render

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "poster", "content.json")
STATE = os.path.join(ROOT, "state.json")
POSTS = "posts"

BASE_TAGS = ["webdevelopment", "webdev", "programming", "coding", "developer", "frontenddeveloper", "100daysofcode"]


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


def today() -> str:
    return datetime.now(ZoneInfo(os.environ.get("POST_TIMEZONE", "Asia/Kolkata"))).strftime("%Y-%m-%d")


def build_caption(tip: dict) -> str:
    tags = []
    for t in list(tip.get("tags", [])) + BASE_TAGS:
        t = t.lstrip("#").lower().replace(" ", "")
        if t and t not in tags:
            tags.append(t)
    lines = [tip["title"], "", tip["caption"], "", tip["note"]]
    if handle():
        lines += ["", f"Follow @{handle()} for a new web dev tip every day."]
    lines += ["", " ".join(f"#{t}" for t in tags[:12])]  # Instagram allows max 30
    return "\n".join(lines)


def set_output(**kv):
    out = os.environ.get("GITHUB_OUTPUT")
    for k, v in kv.items():
        print(f"{k}={v}")
        if out:
            with open(out, "a", encoding="utf-8") as f:
                f.write(f"{k}={v}\n")


# --- commands --------------------------------------------------------------
def cmd_prepare(args):
    state = load_json(STATE, {"next_index": 0, "last_published_date": None, "history": []})
    date = today()
    if state.get("last_published_date") == date and not args.force:
        print(f"already posted today ({date}); skipping")
        set_output(skip="true")
        return

    bank = load_json(BANK, [])
    idx = state.get("next_index", 0)
    tip, source = None, "bank"
    if idx < len(bank):
        tip = bank[idx]
    else:
        tip = generate_tip([h["title"] for h in state.get("history", [])])
        source = "gemini"
        if tip is None:  # no API key or generation failed: cycle the bank again
            tip, source = bank[idx % len(bank)], "bank-repeat"

    number = len(state.get("history", [])) + 1
    image_path = f"{POSTS}/{date}.jpg"
    caption_path = f"{POSTS}/{date}.txt"
    render(tip, number, handle(), os.path.join(ROOT, image_path))
    with open(os.path.join(ROOT, caption_path), "w", encoding="utf-8") as f:
        f.write(build_caption(tip))
    save_json(os.path.join(ROOT, POSTS, f"{date}.json"), tip)

    state["next_index"] = idx + 1
    save_json(STATE, state)
    print(f"prepared tip #{number} from {source}: {tip['title']}")
    set_output(skip="false", image_path=image_path, caption_path=caption_path, title=tip["title"].replace("\n", " "))


def cmd_publish(args):
    with open(args.caption_file, encoding="utf-8") as f:
        caption = f.read()
    try:
        media_id = Instagram().publish_image(args.image_url, caption)
    except InstagramError as e:
        print(f"PUBLISH FAILED: {e}")
        sys.exit(1)
    print(f"published! media id {media_id}")

    state = load_json(STATE, {"next_index": 0, "history": []})
    tip = load_json(args.caption_file.replace(".txt", ".json"), {})
    state["last_published_date"] = today()
    state.setdefault("history", []).append({"date": today(), "title": tip.get("title", ""), "media_id": media_id})
    save_json(STATE, state)


def cmd_preview(args):
    bank = load_json(BANK, [])
    os.makedirs(os.path.join(ROOT, "preview"), exist_ok=True)
    for i, tip in enumerate(bank[args.start : args.start + args.count], start=args.start + 1):
        p = render(tip, i, handle() or "yourhandle", os.path.join(ROOT, "preview", f"tip-{i:02d}.jpg"))
        print(p)


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

    s = sub.add_parser("prepare"); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_prepare)
    s = sub.add_parser("publish")
    s.add_argument("--image-url", required=True); s.add_argument("--caption-file", required=True)
    s.set_defaults(fn=cmd_publish)
    s = sub.add_parser("preview")
    s.add_argument("--count", type=int, default=5); s.add_argument("--start", type=int, default=0)
    s.set_defaults(fn=cmd_preview)
    sub.add_parser("whoami").set_defaults(fn=cmd_whoami)
    sub.add_parser("refresh-token").set_defaults(fn=cmd_refresh)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
