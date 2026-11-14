"""Narrated demo video: speak video/narration.json over the dashboard tour.

    uv run --project core python tools/make_video.py            # macOS `say` voice (draft)
    uv run --project core python tools/make_video.py --voice Daniel --rate 170
    uv run --project core python tools/make_video.py --backend openai   # hosted voice
    uv run --project core python tools/make_video.py --backend openai --audio-only

One narration text per tour step, in tour order. Each step of the recorded tour is made as
long as its spoken clip plus a pause, so picture and voice stay together. Output:
video/out/receipts_demo.mp4 (git-ignored, with the clips and the long silent tour).

The voice is a backend. `say` is the macOS system voice: free and offline, but Apple's
licence limits it to personal, non-commercial use, so treat that video as a draft. A hosted
voice needs only a `speak_*` function that writes one audio file per step. `openai` is
one: OpenAI text-to-speech, a few cents for the whole narration, key in .env
(OPENAI_API_KEY). It sends the narration text to OpenAI, and the video or its description
must say that the voice is AI-generated.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "video" / "out"
PAUSE_MS = 700
# How the system voice should read names it would otherwise mangle.
SAY = {"PJM": "P J M", "AEP": "A E P", "Chronos-2": "Chronos 2", "arXiv": "archive"}


def run(cmd: list[str], **kw) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit(f"{cmd[0]} failed: {r.stderr.strip()[-400:]}")
    return r.stdout


def speak_say(text: str, path: Path, voice: str, rate: int) -> None:
    for k, v in SAY.items():
        text = text.replace(k, v)
    run(["say", "-v", voice, "-r", str(rate), "-o", str(path), text])


OPENAI_URL = "https://api.openai.com/v1/audio/speech"
OPENAI_MODEL = "gpt-4o-mini-tts"  # checked 2026-11-14; OpenAI lists it for shutdown on 2027-01-06
OPENAI_STYLE = (
    "A calm, clear narrator presenting a technical demo. Even pace, plain delivery, "
    "no excitement. Read ratios such as 0.73 as 'zero point seven three'."
)


def openai_key() -> str:
    """OPENAI_API_KEY from .env, else from the environment (the project file wins, so a
    stale key exported by a shell profile does not shadow it). The value is never printed."""
    from dotenv import dotenv_values

    key = (dotenv_values(ROOT / ".env").get("OPENAI_API_KEY") or "").strip()
    key = key or os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        sys.exit("the openai voice needs OPENAI_API_KEY in .env or in the environment")
    return key


def speak_openai(text: str, path: Path, voice: str, key: str) -> None:
    """One clip from OpenAI text-to-speech. The narration text is sent to OpenAI. Its usage
    policy requires telling the audience that the voice is AI-generated."""
    import requests

    r = requests.post(
        OPENAI_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": OPENAI_MODEL,
            "input": text,
            "voice": voice,
            "instructions": OPENAI_STYLE,
            "response_format": "wav",
        },
        timeout=120,
    )
    if r.status_code != 200:
        sys.exit(f"OpenAI speech request failed: HTTP {r.status_code} {r.text[:300]}")
    path.write_bytes(r.content)


def seconds(path: Path) -> float:
    return float(
        run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["say", "openai"], default="say")
    ap.add_argument("--voice", default="", help="default: Samantha for say, marin for openai")
    ap.add_argument("--rate", type=int, default=175, help="words a minute for `say`")
    ap.add_argument("--audio-only", action="store_true", help="make the clips, skip the video")
    a = ap.parse_args()
    voice = a.voice or ("marin" if a.backend == "openai" else "Samantha")
    key = openai_key() if a.backend == "openai" else ""
    steps = json.loads((ROOT / "video" / "narration.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    ms, padded = [], []
    for i, s in enumerate(steps):
        if a.backend == "openai":
            clip = OUT / f"{i + 1:02d}_openai.wav"
            speak_openai(s["text"], clip, voice, key)
        else:
            clip = OUT / f"{i + 1:02d}.aiff"
            speak_say(s["text"], clip, voice, a.rate)
        ms.append(round(seconds(clip) * 1000) + PAUSE_MS)
        pad = OUT / f"{i + 1:02d}.wav"  # the clip followed by silence, exactly one step long
        dur = f"{ms[-1] / 1000:.3f}"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip, "-af", f"apad=whole_dur={dur}",
             "-t", dur, "-ar", "44100", "-ac", "1", pad])  # fmt: skip
        padded.append(pad)
    (OUT / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in padded))
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt",
         "-c", "copy", "narration.wav"], cwd=OUT)  # fmt: skip
    if a.audio_only:
        print(f"steps (s): {[round(m / 1000, 1) for m in ms]}")
        print(f"narration {seconds(OUT / 'narration.wav'):.1f} s in {OUT.relative_to(ROOT)}")
        return
    # The tour itself, with each step as long as its narration.
    env = os.environ | {"TOUR_QUERY": "?tourms=" + ",".join(map(str, ms))}
    silent = OUT / "tour_long.webm"
    print(run(["node", "tools/record_tour.mjs", str(OUT / "rec"), str(silent)], cwd=ROOT, env=env))
    final = OUT / "receipts_demo.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", OUT / "narration.wav",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24", "-c:a", "aac", "-b:a", "128k",
         "-shortest", final])  # fmt: skip
    print(f"steps (s): {[round(m / 1000, 1) for m in ms]}")
    print(f"narration {seconds(OUT / 'narration.wav'):.1f} s, picture {seconds(silent):.1f} s")
    print(f"wrote {final.relative_to(ROOT)} ({final.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
