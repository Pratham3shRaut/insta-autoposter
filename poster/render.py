"""Render a lesson into a carousel of 1080x1350 JPEGs (Instagram portrait size).

Dark navy editorial style with electric blue / purple accents: a title slide
followed by one slide per sub-topic (heading, subtitle, checklist, examples).
"""
from __future__ import annotations

import glob
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1350
MARGIN = 76
CONTENT_W = W - 2 * MARGIN
CONTENT_TOP, CONTENT_BOTTOM = 150, H - 150
FOOT_Y = H - 84

BG_TOP = (15, 18, 36)
BG_BOTTOM = (10, 12, 26)
CARD = (22, 26, 48)
CARD_BORDER = (41, 47, 82)
TEXT = (237, 239, 248)
MUTED = (148, 155, 186)
BLUE = (91, 140, 255)
PURPLE = (168, 115, 255)
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


def fit_lines(draw: ImageDraw.ImageDraw, text: str, kind: str, sizes: tuple, max_w: int, max_lines: int):
    for size in sizes:
        f = font(kind, size)
        lines = wrap(draw, text, f, max_w)
        if len(lines) <= max_lines:
            break
    return f, size, lines


# --- shared visuals ---------------------------------------------------------
def background() -> Image.Image:
    col = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        col.putpixel((0, y), tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)))
    img = col.resize((W, H)).convert("RGBA")

    glows = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for (cx, cy), radius, color, alpha in (((W - 60, 40), 260, BLUE, 70), ((40, H - 120), 240, PURPLE, 55)):
        blob = Image.new("RGBA", (radius * 2, radius * 2), (0, 0, 0, 0))
        ImageDraw.Draw(blob).ellipse([0, 0, radius * 2, radius * 2], fill=(*color, alpha))
        blob = blob.filter(ImageFilter.GaussianBlur(radius // 2))
        glows.paste(blob, (cx - radius, cy - radius), blob)
    return Image.alpha_composite(img, glows)


def gradient_bar(img: Image.Image, box: tuple, radius: int | None = None) -> None:
    x0, y0, x1, y1 = (int(v) for v in box)
    w, h = x1 - x0, y1 - y0
    row = Image.new("RGB", (w, 1))
    for x in range(w):
        t = x / max(w - 1, 1)
        row.putpixel((x, 0), tuple(int(BLUE[i] + (PURPLE[i] - BLUE[i]) * t) for i in range(3)))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w, h], radius=h // 2 if radius is None else radius, fill=255)
    img.paste(row.resize((w, h)), (x0, y0), mask)


def draw_header(img: Image.Image, topic: str, slide_num: int, total: int) -> None:
    d = ImageDraw.Draw(img)
    f = font("bold", 24)
    text = f"{topic.upper()}  \u00b7  {slide_num}/{total}"
    pw = d.textlength(text, font=f) + 44
    gradient_bar(img, (MARGIN, 64, MARGIN + pw, 112))
    d.text((MARGIN + 22, 88), text, font=f, fill=WHITE, anchor="lm")


def draw_footer(img: Image.Image, handle: str, slide_num: int, total: int) -> None:
    d = ImageDraw.Draw(img)
    d.line([MARGIN, FOOT_Y - 38, W - MARGIN, FOOT_Y - 38], fill=CARD_BORDER, width=2)
    if handle:
        d.text((MARGIN, FOOT_Y), f"@{handle.lstrip('@')}", font=font("bold", 30), fill=TEXT, anchor="lm")

    # progress dots, the current slide drawn as a wider gradient pill
    dot, gap, active_w = 10, 12, 32
    widths = [active_w if i == slide_num else dot for i in range(1, total + 1)]
    x = W // 2 - (sum(widths) + gap * (total - 1)) // 2
    for i, w in enumerate(widths, start=1):
        box = (x, FOOT_Y - dot // 2, x + w, FOOT_Y + dot // 2)
        if i == slide_num:
            gradient_bar(img, box)
        else:
            d.ellipse(box, fill=CARD_BORDER)
        x += w + gap

    label = "Swipe  \u2192" if slide_num < total else "Save this post"
    d.text((W - MARGIN, FOOT_Y), label, font=font("bold", 28), fill=BLUE, anchor="rm")


def place_centered(img: Image.Image, layer: Image.Image, content_h: int, name: str) -> None:
    space = CONTENT_BOTTOM - CONTENT_TOP
    if content_h > space:
        print(f"warning: slide '{name}' is tall and may overlap the footer")
    offset = CONTENT_TOP + max(0, (space - content_h) // 2)
    img.alpha_composite(layer.crop((0, 0, W, content_h)), dest=(0, offset))


def save(img: Image.Image, out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.convert("RGB").save(out_path, "JPEG", quality=94, optimize=True)  # Instagram API only accepts JPEG
    return out_path


def draw_check(d: ImageDraw.ImageDraw, x: int, y: int, size: int = 40) -> None:
    d.rounded_rectangle([x, y, x + size, y + size], radius=12, outline=BLUE, width=3)
    d.line([x + 11, y + 21, x + 18, y + 28], fill=BLUE, width=4)
    d.line([x + 18, y + 28, x + 30, y + 13], fill=BLUE, width=4)


# --- slides -----------------------------------------------------------------
def render_title_slide(out_path: str, lesson: dict, handle: str, total: int) -> str:
    img = background()
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    y = 0

    title_font, size, lines = fit_lines(d, lesson["title"], "bold", (84, 74, 66, 58), CONTENT_W, 4)
    for line in lines:
        d.text((MARGIN, y), line, font=title_font, fill=TEXT)
        y += int(size * 1.15)
    y += 18
    gradient_bar(layer, (MARGIN, y, MARGIN + 180, y + 8))
    y += 44

    if lesson.get("intro"):
        intro_font = font("regular", 32)
        for line in wrap(d, lesson["intro"], intro_font, CONTENT_W)[:4]:
            d.text((MARGIN, y), line, font=intro_font, fill=MUTED)
            y += 44
        y += 40

    headings = [s["heading"] for s in lesson["slides"]]
    if headings:
        d.text((MARGIN, y), "INSIDE THIS POST", font=font("bold", 22), fill=PURPLE)
        y += 48
        chip_font = font("bold", 26)
        x = MARGIN
        for h in headings:
            cw = d.textlength(h, font=chip_font) + 44
            if x + cw > W - MARGIN:
                x = MARGIN
                y += 70
            d.rounded_rectangle([x, y, x + cw, y + 54], radius=27, fill=CARD, outline=CARD_BORDER, width=2)
            d.text((x + 22, y + 27), h, font=chip_font, fill=TEXT, anchor="lm")
            x += cw + 14
        y += 54

    place_centered(img, layer, y, lesson["title"])
    draw_header(img, lesson["topic"], 1, total)
    draw_footer(img, handle, 1, total)
    return save(img, out_path)


def render_explainer_slide(out_path: str, topic: str, slide: dict, handle: str, slide_num: int, total: int) -> str:
    img = background()
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    y = 0

    head_font, size, lines = fit_lines(d, slide["heading"], "bold", (68, 60, 52), CONTENT_W, 2)
    for line in lines:
        d.text((MARGIN, y), line, font=head_font, fill=TEXT)
        y += int(size * 1.15)
    y += 14
    gradient_bar(layer, (MARGIN, y, MARGIN + 140, y + 8))
    y += 40

    if slide.get("subtitle"):
        sub_font = font("regular", 34)
        for line in wrap(d, slide["subtitle"], sub_font, CONTENT_W):
            d.text((MARGIN, y), line, font=sub_font, fill=MUTED)
            y += 46
        y += 36

    point_font = font("regular", 32)
    for p in slide.get("points", []):
        draw_check(d, MARGIN, y)
        ty = y + 1
        for line in wrap(d, p, point_font, CONTENT_W - 64):
            d.text((MARGIN + 64, ty), line, font=point_font, fill=TEXT)
            ty += 42
        y = max(ty, y + 42) + 22

    examples = slide.get("examples", [])
    if examples:
        y += 18
        ex_font = font("regular", 30)
        ex_lines = [wrap(d, ex, ex_font, CONTENT_W - 100) for ex in examples]
        box_h = 78 + sum(len(lines) * 40 + 14 for lines in ex_lines) + 18
        d.rounded_rectangle([MARGIN, y, W - MARGIN, y + box_h], radius=22, fill=CARD, outline=CARD_BORDER, width=2)
        gradient_bar(layer, (MARGIN, y, MARGIN + 10, y + box_h), radius=5)
        d.text((MARGIN + 40, y + 28), "REAL-WORLD EXAMPLES", font=font("bold", 22), fill=PURPLE)
        ey = y + 78
        for lines in ex_lines:
            d.ellipse([MARGIN + 42, ey + 13, MARGIN + 54, ey + 25], fill=PURPLE)
            for line in lines:
                d.text((MARGIN + 74, ey), line, font=ex_font, fill=TEXT)
                ey += 40
            ey += 14
        y += box_h

    place_centered(img, layer, y, slide["heading"])
    draw_header(img, topic, slide_num, total)
    draw_footer(img, handle, slide_num, total)
    return save(img, out_path)


def render_lesson(lesson: dict, handle: str, out_dir: str, slug: str) -> list[str]:
    """Render a full carousel (title slide + one per lesson['slides']) and return the image paths in order."""
    total = 1 + len(lesson["slides"])
    paths = [render_title_slide(os.path.join(out_dir, f"{slug}-1.jpg"), lesson, handle, total)]
    for i, slide in enumerate(lesson["slides"], start=2):
        paths.append(render_explainer_slide(
            os.path.join(out_dir, f"{slug}-{i}.jpg"), lesson["topic"], slide, handle, i, total,
        ))
    return paths
