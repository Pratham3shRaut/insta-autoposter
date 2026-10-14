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


def draw_pill(d: ImageDraw.ImageDraw, topic: str, number: int, y: int) -> int:
    pill_font = font("bold", 26)
    pill_text = f"{topic.upper()}  ·  TIP #{number}"
    pw = d.textlength(pill_text, font=pill_font) + 44
    d.rounded_rectangle([MARGIN, y, MARGIN + pw, y + 52], radius=26, outline=ACCENT, width=2)
    d.text((MARGIN + 22, y + 26), pill_text, font=pill_font, fill=ACCENT, anchor="lm")
    return y + 52 + 44


def draw_title(d: ImageDraw.ImageDraw, title: str, content_w: int, y: int) -> int:
    for size in (68, 60, 54, 48):
        title_font = font("bold", size)
        title_lines = wrap(d, title, title_font, content_w)
        if len(title_lines) <= 3:
            break
    lh = int(size * 1.18)
    for line in title_lines:
        d.text((MARGIN, y), line, font=title_font, fill=TEXT)
        y += lh
    return y + 40


def draw_note(d: ImageDraw.ImageDraw, note: str, content_w: int, y: int) -> int:
    note_font = font("regular", 34)
    for line in wrap(d, note, note_font, content_w)[:4]:
        d.text((MARGIN, y), line, font=note_font, fill=MUTED)
        y += 46
    return y


def draw_code_card(d: ImageDraw.ImageDraw, code: str, lang: str, content_w: int, y: int) -> int:
    code_lines = code.rstrip("\n").split("\n")
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
    for ttype, value in lex(code.rstrip("\n"), lexer_for(lang)):
        parts = value.split("\n")
        for j, part in enumerate(parts):
            if j > 0:
                cy += code_lh
                cx = cx0
            if part:
                d.text((cx, cy), part, font=mono, fill=color_for(ttype))
                cx += d.textlength(part, font=mono)
    return y + card_h + 44


def render_code(d: ImageDraw.ImageDraw, tip: dict, content_w: int, y: int) -> int:
    y = draw_code_card(d, tip["code"], tip.get("lang", "js"), content_w, y)
    return draw_note(d, tip["note"], content_w, y)


def render_fact(d: ImageDraw.ImageDraw, tip: dict, content_w: int, y: int) -> int:
    for size in (120, 100, 84, 70, 58):
        stat_font = font("bold", size)
        if d.textlength(tip["stat"], font=stat_font) <= content_w:
            break
    d.text((MARGIN, y), tip["stat"], font=stat_font, fill=ACCENT)
    y += int(size * 1.1) + 36
    return draw_note(d, tip["note"], content_w, y)


def render_comparison(d: ImageDraw.ImageDraw, tip: dict, content_w: int, y: int) -> int:
    col_w = (content_w - 32) // 2
    heading_font = font("bold", 32)
    body_font = font("regular", 30)
    cols = [("left", (240, 113, 120)), ("right", (130, 220, 150))]
    max_h = 0
    col_heights = []
    for key, _ in cols:
        side = tip[key]
        lines = wrap(d, side["body"], body_font, col_w - 48)
        h = 56 + 44 + len(lines) * 40 + 36
        col_heights.append((lines, h))
        max_h = max(max_h, h)

    for i, (key, accent) in enumerate(cols):
        x0 = MARGIN + i * (col_w + 32)
        side = tip[key]
        lines, _ = col_heights[i]
        d.rounded_rectangle([x0, y, x0 + col_w, y + max_h], radius=20, fill=CARD, outline=CARD_BORDER, width=2)
        d.text((x0 + 24, y + 28), side["label"].upper(), font=heading_font, fill=accent)
        ty = y + 28 + 56
        for line in lines:
            d.text((x0 + 24, ty), line, font=body_font, fill=TEXT)
            ty += 40
    y += max_h + 44
    return draw_note(d, tip["note"], content_w, y)


def render_quiz(d: ImageDraw.ImageDraw, tip: dict, content_w: int, y: int) -> int:
    q_font = font("regular", 38)
    opt_label_font = font("bold", 30)
    opt_font = font("regular", 30)

    question_lines = wrap(d, tip["question"], q_font, content_w - 80)
    option_lines = [wrap(d, opt, opt_font, content_w - 140) for opt in tip["options"]]

    card_top = y
    inner_y = card_top + 48
    for _ in question_lines:
        inner_y += 50
    inner_y += 20
    for lines in option_lines:
        inner_y += len(lines) * 42 + 14
    card_bottom = inner_y + 28

    d.rounded_rectangle([MARGIN, card_top, W - MARGIN, card_bottom], radius=24, fill=CARD, outline=CARD_BORDER, width=2)

    ty = card_top + 48
    for line in question_lines:
        d.text((MARGIN + 40, ty), line, font=q_font, fill=TEXT)
        ty += 50
    ty += 20
    for i, lines in enumerate(option_lines):
        letter = chr(65 + i)
        d.text((MARGIN + 40, ty), f"{letter}.", font=opt_label_font, fill=ACCENT)
        for line in lines:
            d.text((MARGIN + 90, ty), line, font=opt_font, fill=TEXT)
            ty += 42
        ty += 14

    y = card_bottom + 44
    return draw_note(d, tip.get("note", "Answer in the caption."), content_w, y)


RENDERERS = {
    "code": render_code,
    "fact": render_fact,
    "comparison": render_comparison,
    "quiz": render_quiz,
}


def render(tip: dict, number: int, handle: str, out_path: str) -> str:
    img = Image.new("RGB", (W, H), BG)
    # Content is drawn on its own layer first, then centered above the footer.
    layer = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(layer)
    content_w = W - 2 * MARGIN
    y = 0

    y = draw_pill(d, tip["topic"], number, y)
    y = draw_title(d, tip["title"], content_w, y)

    kind = tip.get("type", "code")
    y = RENDERERS.get(kind, render_code)(d, tip, content_w, y)

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
