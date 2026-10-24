"""Build a short vertical Reel (under 30s) for a lesson.

Layout: a Veo-generated intro clip with the title overlaid, then the lesson's
carousel slides with crossfades, all under a Gemini text-to-speech voiceover.
If Veo fails, the Reel is still built from the slides alone.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
import time
import wave

import imageio_ffmpeg
import requests
from PIL import Image, ImageDraw

from .render import BLUE, MUTED, TEXT, background, font, gradient_bar, wrap

API = "https://generativelanguage.googleapis.com/v1beta"
RW, RH = 1080, 1920
FPS = 30
MAX_SECONDS = 29.5
INTRO_MAX = 6.0
FADE = 0.4
TAIL = 0.6


class ReelError(RuntimeError):
    pass


# --- Gemini API ----------------------------------------------------------------
def _key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise ReelError("GEMINI_API_KEY is not set")
    return key


def _request(method: str, path: str, body: dict | None = None, timeout: int = 120) -> dict:
    url = path if path.startswith("http") else f"{API}/{path}"
    try:
        r = requests.request(method, url, headers={"x-goog-api-key": _key()}, json=body, timeout=timeout)
    except requests.RequestException as e:
        raise ReelError(f"network error calling Gemini: {type(e).__name__}") from None
    if r.status_code != 200:
        raise ReelError(f"Gemini {method} {path.split('?')[0]} failed ({r.status_code}): {r.text[:400]}")
    return r.json()


SCRIPT_PROMPT = """You write the voiceover for a short Instagram Reel that explains a developer
concept to beginners.

Lesson title: {title}
Key points, in order:
{points}

Return ONLY JSON: {{"narration": str, "veo_prompt": str}}

narration: {words} words, spoken naturally, friendly and clear. Open with a one-sentence hook,
explain the key ideas in order, and end with "Follow pr dot devtips for more."
No emojis, hashtags, markdown, or code symbols that are awkward to read aloud.

veo_prompt: a prompt for an AI video model describing an abstract, cinematic visual metaphor
for this concept: dark navy background, glowing electric blue and purple light, smooth slow
camera motion, vertical framing. It must not contain any text, letters, numbers, logos,
screens with writing, or human faces."""


def write_script(lesson: dict, words: str = "55 to 65") -> dict:
    points = "\n".join(f"- {s['heading']}: {s.get('subtitle', '')}" for s in lesson["slides"])
    if lesson.get("scenario"):
        sc = lesson["scenario"]
        points += f"\n- Real-world scenario (mention briefly at the end): {sc['problem']} Fix: {sc['fix']}"
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    data = _request("POST", f"models/{model}:generateContent", {
        "contents": [{"parts": [{"text": SCRIPT_PROMPT.format(title=lesson["title"], points=points, words=words)}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
    })
    script = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
    if isinstance(script, list):
        script = script[0]
    if not script.get("narration") or not script.get("veo_prompt"):
        raise ReelError("Gemini returned an incomplete script")
    return script


def synthesize(text: str, out_wav: str) -> float:
    """Gemini text-to-speech to a WAV file. Returns the duration in seconds."""
    model = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
    voice = os.environ.get("GEMINI_TTS_VOICE", "Kore")
    data = _request("POST", f"models/{model}:generateContent", {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }, timeout=180)
    inline = data["candidates"][0]["content"]["parts"][0]["inlineData"]
    pcm = base64.b64decode(inline["data"])
    match = re.search(r"rate=(\d+)", inline.get("mimeType", ""))
    rate = int(match.group(1)) if match else 24000  # Gemini TTS returns 16-bit mono PCM
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return len(pcm) / (2 * rate)


def veo_clip(prompt: str, out_path: str) -> str:
    """Generate one short clip with Veo and download it."""
    model = os.environ.get("VEO_MODEL", "veo-3.0-fast-generate-001")
    negative = "text, letters, words, numbers, captions, logos, watermark, people, faces"
    attempts = [
        {"aspectRatio": "9:16", "negativePrompt": negative},
        {"aspectRatio": "16:9", "negativePrompt": negative},  # older models may not support portrait
        {"aspectRatio": "16:9"},
    ]
    op, last = None, None
    for params in attempts:
        try:
            op = _request("POST", f"models/{model}:predictLongRunning",
                          {"instances": [{"prompt": prompt}], "parameters": params})
            break
        except ReelError as e:
            last = e
    if op is None:
        raise last

    deadline = time.time() + 600
    while True:
        status = _request("GET", op["name"])
        if status.get("done"):
            break
        if time.time() > deadline:
            raise ReelError("Veo did not finish within 10 minutes")
        time.sleep(10)
    if "error" in status:
        raise ReelError(f"Veo failed: {status['error']}")
    try:
        uri = status["response"]["generateVideoResponse"]["generatedSamples"][0]["video"]["uri"]
    except (KeyError, IndexError):
        raise ReelError(f"Veo returned no video (it may have been filtered): {str(status)[:300]}") from None

    r = requests.get(uri, headers={"x-goog-api-key": _key()}, timeout=300)
    if r.status_code != 200:
        raise ReelError(f"downloading the Veo clip failed ({r.status_code})")
    with open(out_path, "wb") as f:
        f.write(r.content)
    return out_path


# --- frames ---------------------------------------------------------------------
def slide_frame(slide_path: str, out_path: str) -> str:
    """Center a 1080x1350 slide on a 1080x1920 canvas in the same dark style."""
    canvas = background(RW, RH)
    slide = Image.open(slide_path).convert("RGBA")
    canvas.alpha_composite(slide, dest=(0, (RH - slide.height) // 2))
    canvas.convert("RGB").save(out_path)
    return out_path


def intro_overlay(title: str, handle: str, out_path: str) -> str:
    """Transparent PNG with the title over a dark scrim, laid over the Veo clip."""
    img = Image.new("RGBA", (RW, RH), (0, 0, 0, 0))
    scrim = Image.new("RGBA", (RW, RH), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    for y in range(RH // 2, RH):
        alpha = int(215 * (y - RH // 2) / (RH // 2))
        sd.line([(0, y), (RW, y)], fill=(10, 12, 26, alpha))
    img.alpha_composite(scrim)

    d = ImageDraw.Draw(img)
    margin = 76
    for size in (88, 76, 66):
        f = font("bold", size)
        lines = wrap(d, title, f, RW - 2 * margin)
        if len(lines) <= 4:
            break
    lh = int(size * 1.15)
    y = RH - 360 - len(lines) * lh
    for line in lines:
        d.text((margin, y), line, font=f, fill=TEXT)
        y += lh
    gradient_bar(img, (margin, y + 18, margin + 180, y + 26))
    if handle:
        d.text((margin, RH - 230), f"@{handle.lstrip('@')}", font=font("bold", 36), fill=MUTED)
    d.text((RW - margin, RH - 230), "Watch till the end", font=font("bold", 32), fill=BLUE, anchor="ra")
    img.save(out_path)
    return out_path


# --- assembly -------------------------------------------------------------------
def _ffmpeg(args: list[str]) -> None:
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", *args]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise ReelError(f"ffmpeg failed: {res.stderr.strip()[-600:]}")


def assemble(slide_paths: list[str], audio_path: str, audio_secs: float, veo_path: str | None,
             title: str, handle: str, out_path: str, work: str) -> float:
    """Combine the intro clip, slides and voiceover into an MP4. Returns the video length."""
    tempo = 1.0
    if audio_secs + TAIL > MAX_SECONDS:
        tempo = min(1.25, (audio_secs + TAIL) / MAX_SECONDS)
    total = min(MAX_SECONDS, audio_secs / tempo + TAIL)

    intro = 0.0
    if veo_path:
        _, veo_secs = imageio_ffmpeg.count_frames_and_secs(veo_path)
        intro = max(0.0, min(INTRO_MAX, veo_secs - 0.1, total * 0.3))
    segments = len(slide_paths) + (1 if intro else 0)
    per_slide = (total - intro + (segments - 1) * FADE) / len(slide_paths)
    if per_slide < 1.8:
        raise ReelError(f"voiceover too short for {len(slide_paths)} slides")

    args, chains, durations = [], [], []
    inputs = 0
    if intro:
        overlay = intro_overlay(title, handle, os.path.join(work, "overlay.png"))
        args += ["-i", veo_path, "-loop", "1", "-i", overlay]
        inputs += 2
        chains.append(
            f"[0:v]trim=0:{intro:.3f},setpts=PTS-STARTPTS,"
            f"scale={RW}:{RH}:force_original_aspect_ratio=increase,crop={RW}:{RH},fps={FPS},setsar=1[vi];"
            f"[vi][1:v]overlay=0:0:shortest=1,format=yuv420p,settb=AVTB[s0]"
        )
        durations.append(intro)
    for path in slide_paths:
        n = len(durations)
        frame = slide_frame(path, os.path.join(work, f"frame-{n}.png"))
        args += ["-loop", "1", "-t", f"{per_slide:.3f}", "-i", frame]
        chains.append(f"[{inputs}:v]fps={FPS},setsar=1,format=yuv420p,settb=AVTB[s{n}]")
        inputs += 1
        durations.append(per_slide)

    prev, acc = "s0", durations[0]
    for k in range(1, len(durations)):
        chains.append(f"[{prev}][s{k}]xfade=transition=fade:duration={FADE}:offset={acc - FADE:.3f}[x{k}]")
        prev, acc = f"x{k}", acc + durations[k] - FADE

    audio_index = inputs
    args += ["-i", audio_path]
    audio_filter = f"atempo={tempo:.3f}," if tempo != 1.0 else ""
    chains.append(f"[{audio_index}:a]{audio_filter}apad[aout]")

    _ffmpeg([
        *args,
        "-filter_complex", ";".join(chains),
        "-map", f"[{prev}]", "-map", "[aout]",
        "-t", f"{total:.3f}", "-r", str(FPS),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-movflags", "+faststart",
        out_path,
    ])
    return total


def build_reel(lesson: dict, slide_paths: list[str], handle: str, out_path: str) -> str:
    with tempfile.TemporaryDirectory() as work:
        script = write_script(lesson)
        wav = os.path.join(work, "voice.wav")
        secs = synthesize(script["narration"], wav)
        if secs + TAIL > MAX_SECONDS * 1.25:  # too long even when sped up: ask for a shorter script
            script = write_script(lesson, words="40 to 48")
            secs = synthesize(script["narration"], wav)
        print(f"voiceover: {secs:.1f}s")

        veo_path = None
        try:
            veo_path = veo_clip(script["veo_prompt"], os.path.join(work, "intro.mp4"))
            print("veo intro clip generated")
        except ReelError as e:
            print(f"warning: no Veo intro, building the Reel from slides only ({e})")

        total = assemble(slide_paths, wav, secs, veo_path, lesson["title"], handle, out_path, work)
        print(f"reel built: {out_path} ({total:.1f}s)")
    return out_path
