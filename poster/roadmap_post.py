"""One-off: 'Beginner's Roadmap to Web Development' premium explainer post.

Standalone from the carousel pipeline in render.py — a single 1080x1350 image
in a dark navy / electric blue editorial style. Run directly:
    python -m poster.roadmap_post
"""
from __future__ import annotations

import glob
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1350
MARGIN = 76

BG_TOP = (15, 18, 36)
BG_BOTTOM = (10, 12, 26)
CARD = (22, 26, 48)
CARD_BORDER = (41, 47, 82)
TEXT = (237, 239, 248)
MUTED = (148, 155, 186)
BLUE = (91, 140, 255)
PURPLE = (168, 115, 255)
GREEN = (84, 214, 160)

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
    "mono": [
        f"{FONT_DIR}/mono.ttf", f"{FONT_DIR}/mono.otf",
        "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
        "/usr/share/fonts/**/JetBrainsMono-Regular.*",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf",
        "/System/Library/Fonts/Menlo.ttc",
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


def vertical_gradient(w: int, h: int, top: tuple, bottom: tuple) -> Image.Image:
    base = Image.new("RGB", (1, h), 0)
    for y in range(h):
        t = y / max(h - 1, 1)
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        base.putpixel((0, y), row)
    return base.resize((w, h))


def glow(img: Image.Image, center: tuple, radius: int, color: tuple, alpha: int) -> None:
    blob = Image.new("RGBA", (radius * 2, radius * 2), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blob)
    bd.ellipse([0, 0, radius * 2, radius * 2], fill=(*color, alpha))
    blob = blob.filter(ImageFilter.GaussianBlur(radius // 2))
    img.paste(blob, (center[0] - radius, center[1] - radius), blob)


def rounded_gradient_pill(img: Image.Image, box: list, c1: tuple, c2: tuple) -> None:
    x0, y0, x1, y1 = box
    w, h = int(x1 - x0), int(y1 - y0)
    grad = Image.new("RGB", (w, 1), 0)
    for x in range(w):
        t = x / max(w - 1, 1)
        grad.putpixel((x, 0), tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    grad = grad.resize((w, h))
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, w, h], radius=h // 2, fill=255)
    img.paste(grad, (int(x0), int(y0)), mask)


def render() -> str:
    img = Image.new("RGB", (W, H))
    bg = vertical_gradient(W, H, BG_TOP, BG_BOTTOM)
    img.paste(bg, (0, 0))

    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow(glow_layer, (W - 60, 40), 260, BLUE, 70)
    glow(glow_layer, (40, H - 120), 240, PURPLE, 55)
    img = Image.alpha_composite(img.convert("RGBA"), glow_layer).convert("RGB")

    d = ImageDraw.Draw(img, "RGBA")
    content_w = W - 2 * MARGIN
    y = 64

    # Eyebrow pill
    pill_font = font("bold", 24)
    pill_text = "WEB DEVELOPMENT  \u00b7  ROADMAP"
    pw = d.textlength(pill_text, font=pill_font) + 44
    rounded_gradient_pill(img, [MARGIN, y, MARGIN + pw, y + 48], BLUE, PURPLE)
    d.text((MARGIN + 22, y + 24), pill_text, font=pill_font, fill=(255, 255, 255), anchor="lm")
    y += 48 + 40

    # Headline
    headline = "Your Beginner's Roadmap\nto Web Development"
    head_font = font("bold", 62)
    for line in headline.split("\n"):
        d.text((MARGIN, y), line, font=head_font, fill=TEXT)
        y += 70
    y += 6
    sub_font = font("regular", 30)
    sub_lines = wrap(d, "5 steps to go from zero to shipping your first website.", sub_font, content_w)
    for line in sub_lines:
        d.text((MARGIN, y), line, font=sub_font, fill=MUTED)
        y += 40
    y += 28

    steps = [
        ("01", "Learn HTML & CSS", "Structure and style your first web pages.", BLUE),
        ("02", "Pick up JavaScript", "Make pages interactive and dynamic.", PURPLE),
        ("03", "Build real projects", "A to-do app teaches more than 10 tutorials.", BLUE),
        ("04", "Learn Git & GitHub", "Track changes, collaborate, build a portfolio.", PURPLE),
        ("05", "Deploy it live", "Ship with Vercel, Netlify, or GitHub Pages.", GREEN),
    ]

    num_font = font("bold", 34)
    step_title_font = font("bold", 32)
    step_desc_font = font("regular", 26)
    row_h = 96

    for num, title, desc, accent in steps:
        # number badge
        bx0, by0 = MARGIN, y
        d.rounded_rectangle([bx0, by0, bx0 + 72, by0 + 72], radius=20, outline=accent, width=3)
        d.text((bx0 + 36, by0 + 36), num, font=num_font, fill=accent, anchor="mm")

        tx = bx0 + 72 + 28
        d.text((tx, by0 + 2), title, font=step_title_font, fill=TEXT)
        d.text((tx, by0 + 42), desc, font=step_desc_font, fill=MUTED)

        if (num, title, desc, accent) != steps[-1]:
            d.line([bx0 + 36, by0 + 80, bx0 + 36, by0 + row_h + 4], fill=CARD_BORDER, width=3)
        y += row_h

    y += 14

    # Pro tip card
    tip_label_font = font("bold", 24)
    tip_font = font("regular", 28)
    tip_text = "Don't wait until you \"know enough.\" Build your first project after week one — you'll learn 10x faster by doing."
    tip_lines = wrap(d, tip_text, tip_font, content_w - 112)
    tip_h = 56 + len(tip_lines) * 38 + 30
    d.rounded_rectangle([MARGIN, y, W - MARGIN, y + tip_h], radius=22, fill=CARD, outline=CARD_BORDER, width=2)
    d.rounded_rectangle([MARGIN, y, MARGIN + 10, y + tip_h], radius=5, fill=GREEN)
    d.text((MARGIN + 36, y + 24), "PRO TIP", font=tip_label_font, fill=GREEN)
    ty = y + 64
    for line in tip_lines:
        d.text((MARGIN + 36, ty), line, font=tip_font, fill=TEXT)
        ty += 38
    y += tip_h + 36

    # Code snippet strip
    code_font = font("mono", 26)
    code_text = "<h1>Hello, Web Dev!</h1>"
    code_h = 76
    d.rounded_rectangle([MARGIN, y, W - MARGIN, y + code_h], radius=18, fill=(13, 15, 30), outline=CARD_BORDER, width=2)
    for i, col in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        cx = MARGIN + 30 + i * 26
        d.ellipse([cx - 6, y + 22, cx + 6, y + 34], fill=col)
    d.text((MARGIN + 110, y + 38), code_text, font=code_font, fill=(195, 232, 141), anchor="lm")
    y += code_h + 40

    # Footer
    foot_y = H - 92
    d.line([MARGIN, foot_y - 28, W - MARGIN, foot_y - 28], fill=CARD_BORDER, width=2)
    handle_font = font("bold", 30)
    d.text((MARGIN, foot_y), "@pr.devtips", font=handle_font, fill=TEXT, anchor="lm")
    cta_font = font("bold", 28)
    d.text((W - MARGIN, foot_y), "Save this for later", font=cta_font, fill=BLUE, anchor="rm")

    out_dir = os.path.join(os.path.dirname(HERE), "preview")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "roadmap-webdev.jpg")
    img.save(out_path, "JPEG", quality=94, optimize=True)
    return out_path


if __name__ == "__main__":
    print(render())
