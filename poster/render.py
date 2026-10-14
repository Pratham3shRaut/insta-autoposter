"""Render a lesson into a carousel of 1080x1350 JPEGs (Instagram portrait size).

Light "explainer" style: a title slide followed by one slide per topic point,
each with a heading, subtitle, checklist bullets and an optional examples box.
"""
from __future__ import annotations

import glob
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
MARGIN = 72

BG = (253, 240, 196)
BG_ACCENT = (247, 209, 103)
NAVY = (26, 33, 56)
MUTED_NAVY = (90, 100, 128)
ACCENT = (240, 180, 41)
CHECK_BG = (46, 196, 122)
CARD_BG = (255, 250, 232)
CARD_BORDER = (235, 214, 150)
WHITE = (255, 255, 255)

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(os.path.dirname(HERE), "fonts")

FONT_CANDIDATES = {
    "bold": [
        f"{FONT_DIR}/bold.ttf", f"{FONT_DIR}/bold.otf",
        "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
        "/usr/share/fonts/**/Inter-Bold.*",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ],
    "regular": [
        f"{FONT_DIR}/regular.ttf", f"{FONT_DIR}/regular.otf",
        "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
        "/usr/share/fonts/**/Inter-Regular.*",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ],
}


@lru_cache(maxsize=None)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for pattern in FONT_CANDIDATES[kind]:
        for path in sorted(glob.glob(pattern, recursive=True)):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


def wrap(draw: ImageDraw.ImageDraw, text: str, f, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=f) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_background(img: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    d.ellipse([-180, -180, 260, 260], fill=BG_ACCENT)
    d.ellipse([W - 260, H - 260, W + 180, H + 180], fill=BG_ACCENT)


def draw_dots(d: ImageDraw.ImageDraw) -> None:
    for i in range(6):
        row, col = divmod(i, 3)
        cx = W - MARGIN - 70 + col * 24
        cy = 70 + row * 24
        d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=ACCENT)


def draw_footer(d: ImageDraw.ImageDraw, handle: str, slide_num: int, total: int) -> None:
    foot_y = H - 90

    if handle:
        follow_font = font("bold", 26)
        handle_font = font("bold", 22)
        handle_text = f"@{handle.lstrip('@')}"
        inner_pad = 24
        gap = 14
        logo_w = 38
        follow_w = d.textlength("Follow", font=follow_font)
        handle_w = d.textlength(handle_text, font=handle_font)
        badge_w = inner_pad + follow_w + gap + 16 + gap + logo_w + gap + handle_w + inner_pad

        d.rounded_rectangle([MARGIN, foot_y - 10, MARGIN + badge_w, foot_y + 48], radius=28, fill=NAVY)
        x = MARGIN + inner_pad
        d.text((x, foot_y + 19), "Follow", font=follow_font, fill=WHITE, anchor="lm")
        x += follow_w + gap
        d.line([x, foot_y + 2, x, foot_y + 36], fill=(255, 255, 255), width=2)
        x += 16 + gap
        d.rounded_rectangle([x, foot_y, x + logo_w, foot_y + 38], radius=8, fill=ACCENT)
        d.text((x + logo_w / 2, foot_y + 19), "</>", font=font("bold", 16), fill=NAVY, anchor="mm")
        x += logo_w + gap
        d.text((x, foot_y + 19), handle_text, font=handle_font, fill=NAVY, anchor="lm")

    if slide_num < total:
        d.text((W - MARGIN, foot_y + 19), "Swipe  \u2192", font=font("bold", 28), fill=NAVY, anchor="rm")
    else:
        d.text((W - MARGIN, foot_y + 19), "Save this post", font=font("bold", 28), fill=NAVY, anchor="rm")


def render_title_slide(out_path: str, title: str, topic: str, handle: str, slide_num: int, total: int) -> str:
    img = Image.new("RGB", (W, H), BG)
    draw_background(img)
    d = ImageDraw.Draw(img)
    draw_dots(d)

    content_w = W - 2 * MARGIN

    pill_font = font("bold", 24)
    pill_text = topic.upper()
    pw = d.textlength(pill_text, font=pill_font) + 44
    pill_y = 150
    d.rounded_rectangle([MARGIN, pill_y, MARGIN + pw, pill_y + 48], radius=24, fill=NAVY)
    d.text((MARGIN + 22, pill_y + 24), pill_text, font=pill_font, fill=ACCENT, anchor="lm")

    for size in (92, 80, 70, 60):
        title_font = font("bold", size)
        lines = wrap(d, title, title_font, content_w)
        if len(lines) <= 4:
            break
    lh = int(size * 1.12)
    total_h = len(lines) * lh
    y = (H - total_h) // 2
    for line in lines:
        d.text((MARGIN, y), line, font=title_font, fill=NAVY)
        y += lh
    d.line([MARGIN, y + 16, MARGIN + 220, y + 16], fill=ACCENT, width=8)

    draw_footer(d, handle, slide_num, total)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, "JPEG", quality=92, optimize=True)
    return out_path


def render_explainer_slide(
    out_path: str,
    heading: str,
    subtitle: str,
    points: list[str],
    examples: list[str],
    handle: str,
    slide_num: int,
    total: int,
) -> str:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    draw_dots(d)

    content_w = W - 2 * MARGIN
    y = 90

    for size in (56, 48, 42):
        head_font = font("bold", size)
        head_lines = wrap(d, heading, head_font, content_w)
        if len(head_lines) <= 2:
            break
    for line in head_lines:
        d.text((MARGIN, y), line, font=head_font, fill=NAVY)
        y += int(size * 1.15)
    y += 10
    d.line([MARGIN, y, MARGIN + 140, y], fill=ACCENT, width=6)
    y += 44

    if subtitle:
        sub_font = font("regular", 32)
        for line in wrap(d, subtitle, sub_font, content_w):
            d.text((MARGIN, y), line, font=sub_font, fill=MUTED_NAVY)
            y += 42
        y += 26

    point_font = font("regular", 30)
    for p in points:
        lines = wrap(d, p, point_font, content_w - 56)
        d.ellipse([MARGIN, y, MARGIN + 34, y + 34], fill=CHECK_BG)
        d.line([MARGIN + 9, y + 17, MARGIN + 15, y + 24], fill=WHITE, width=3)
        d.line([MARGIN + 15, y + 24, MARGIN + 26, y + 10], fill=WHITE, width=3)
        ty = y + 1
        for line in lines:
            d.text((MARGIN + 50, ty), line, font=point_font, fill=NAVY)
            ty += 38
        y = ty + 16

    y += 14
    if examples:
        ex_label_font = font("bold", 24)
        ex_font = font("regular", 28)
        ex_lines = [wrap(d, ex, ex_font, content_w - 88) for ex in examples]
        ex_h = 70 + sum(len(lines) * 36 + 12 for lines in ex_lines) + 20
        d.rounded_rectangle([MARGIN, y, W - MARGIN, y + ex_h], radius=20, fill=CARD_BG, outline=CARD_BORDER, width=2)
        d.text((MARGIN + 28, y + 24), "EXAMPLES", font=ex_label_font, fill=MUTED_NAVY)
        ey = y + 70
        for lines in ex_lines:
            d.ellipse([MARGIN + 28, ey + 10, MARGIN + 44, ey + 26], fill=ACCENT)
            ty = ey
            for line in lines:
                d.text((MARGIN + 60, ty), line, font=ex_font, fill=NAVY)
                ty += 36
            ey = ty + 12
        y += ex_h

    foot_y = H - 90
    if y > foot_y - 40:
        print(f"warning: slide '{heading}' is tall and may overlap the footer")

    draw_footer(d, handle, slide_num, total)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, "JPEG", quality=92, optimize=True)
    return out_path


def render_lesson(lesson: dict, handle: str, out_dir: str, slug: str) -> list[str]:
    """Render a full carousel (title slide + one per lesson['slides']) and return the image paths in order."""
    total = 1 + len(lesson["slides"])
    paths = [render_title_slide(
        os.path.join(out_dir, f"{slug}-1.jpg"), lesson["title"], lesson["topic"], handle, 1, total,
    )]
    for i, slide in enumerate(lesson["slides"], start=2):
        paths.append(render_explainer_slide(
            os.path.join(out_dir, f"{slug}-{i}.jpg"),
            slide["heading"],
            slide.get("subtitle", ""),
            slide.get("points", []),
            slide.get("examples", []),
            handle, i, total,
        ))
    return paths
