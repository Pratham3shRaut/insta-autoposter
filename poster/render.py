"""Render a tip into a 1080x1350 JPEG (Instagram portrait size)."""
from __future__ import annotations

import glob
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import get_lexer_by_name
from pygments.token import Token
from pygments.util import ClassNotFound

W, H = 1080, 1350
MARGIN = 80

BG = (15, 17, 23)
CARD = (26, 29, 39)
CARD_BORDER = (42, 46, 58)
TEXT = (240, 240, 244)
MUTED = (161, 161, 170)
ACCENT = (163, 230, 53)  # lime

CODE_COLORS = [
    (Token.Comment, (103, 110, 149)),
    (Token.Keyword, (199, 146, 234)),
    (Token.Name.Function, (130, 170, 255)),
    (Token.Name.Builtin, (255, 203, 107)),
    (Token.Name.Tag, (240, 113, 120)),
    (Token.Name.Attribute, (255, 203, 107)),
    (Token.Name.Class, (255, 203, 107)),
    (Token.Literal.String, (195, 232, 141)),
    (Token.Literal.Number, (247, 140, 108)),
    (Token.Operator, (137, 221, 255)),
    (Token.Punctuation, (137, 221, 255)),
]
CODE_DEFAULT = (230, 230, 235)

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


def color_for(ttype) -> tuple[int, int, int]:
    for base, col in CODE_COLORS:
        if ttype in base:
            return col
    return CODE_DEFAULT


def lexer_for(lang: str):
    for name in (lang, "typescript" if lang in ("ts", "tsx") else "javascript"):
        try:
            return get_lexer_by_name(name, stripnl=False, ensurenl=False)
        except ClassNotFound:
            continue
    return get_lexer_by_name("text")


def render(tip: dict, number: int, handle: str, out_path: str) -> str:
    img = Image.new("RGB", (W, H), BG)
    # Content is drawn on its own layer first, then centered above the footer.
    layer = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(layer)
    content_w = W - 2 * MARGIN
    y = 0

    # Pill: topic + tip number
    pill_font = font("bold", 26)
    pill_text = f"{tip['topic'].upper()}  ·  TIP #{number}"
    pw = d.textlength(pill_text, font=pill_font) + 44
    d.rounded_rectangle([MARGIN, y, MARGIN + pw, y + 52], radius=26, outline=ACCENT, width=2)
    d.text((MARGIN + 22, y + 26), pill_text, font=pill_font, fill=ACCENT, anchor="lm")
    y += 52 + 44

    # Title (shrinks if it would need more than 3 lines)
    for size in (68, 60, 54, 48):
        title_font = font("bold", size)
        title_lines = wrap(d, tip["title"], title_font, content_w)
        if len(title_lines) <= 3:
            break
    lh = int(size * 1.18)
    for line in title_lines:
        d.text((MARGIN, y), line, font=title_font, fill=TEXT)
        y += lh
    y += 40

    # Code card: pick the largest mono size where every line fits
    code_lines = tip["code"].rstrip("\n").split("\n")
    inner_w = content_w - 2 * 40
    for size in (32, 30, 28, 26, 24, 22, 20):
        mono = font("mono", size)
        if max(d.textlength(l, font=mono) for l in code_lines) <= inner_w:
            break
    code_lh = int(size * 1.5)
    card_h = 64 + len(code_lines) * code_lh + 36
    d.rounded_rectangle([MARGIN, y, W - MARGIN, y + card_h], radius=24, fill=CARD, outline=CARD_BORDER, width=2)
    for i, col in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        cx = MARGIN + 36 + i * 30
        d.ellipse([cx - 8, y + 30, cx + 8, y + 46], fill=col)

    cx0, cy = MARGIN + 40, y + 76
    cx = cx0
    for ttype, value in lex(tip["code"].rstrip("\n"), lexer_for(tip.get("lang", "js"))):
        parts = value.split("\n")
        for j, part in enumerate(parts):
            if j > 0:
                cy += code_lh
                cx = cx0
            if part:
                d.text((cx, cy), part, font=mono, fill=color_for(ttype))
                cx += d.textlength(part, font=mono)
    y += card_h + 44

    # Note
    note_font = font("regular", 34)
    for line in wrap(d, tip["note"], note_font, content_w)[:4]:
        d.text((MARGIN, y), line, font=note_font, fill=MUTED)
        y += 46

    # Center the content block between the top edge and the footer
    foot_y = H - 96
    top, bottom = 80, foot_y - 70
    offset = max(top, top + (bottom - top - y) // 2)
    img.paste(layer.crop((0, 0, W, min(y, H - offset))), (0, offset))
    y += offset
    d = ImageDraw.Draw(img)

    # Footer
    d.line([MARGIN, foot_y - 34, W - MARGIN, foot_y - 34], fill=CARD_BORDER, width=2)
    f_foot = font("bold", 30)
    if handle:
        d.text((MARGIN, foot_y), f"@{handle.lstrip('@')}", font=f_foot, fill=TEXT, anchor="lm")
    d.text((W - MARGIN, foot_y), "Save for later  →", font=font("regular", 30), fill=ACCENT, anchor="rm")

    if y > foot_y - 50:
        print(f"warning: tip '{tip['title']}' is tall and may overlap the footer")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, "JPEG", quality=92, optimize=True)  # Instagram API only accepts JPEG
    return out_path
