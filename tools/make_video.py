"""Narrated demo video: speak video/narration.json over the dashboard tour.

    uv run --project core python tools/make_video.py            # macOS `say` voice (draft)
    uv run --project core python tools/make_video.py --voice Daniel --rate 170

One narration text per tour step, in tour order. Each step of the recorded tour is made as
long as its spoken clip plus a pause, so picture and voice stay together. Output:
video/out/receipts_demo.mp4 (git-ignored, with the clips and the long silent tour).

The voice is a backend. `say` is the macOS system voice: free and offline, but Apple's
licence limits it to personal, non-commercial use, so treat that video as a draft. A hosted
voice (for example Fish Audio through Treg, notes/hackathon_tools.md) needs only a new
`speak_*` function that writes one audio file per step.
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


def seconds(path: Path) -> float:
    return float(
        run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="Samantha")
    ap.add_argument("--rate", type=int, default=175, help="words a minute for `say`")
    a = ap.parse_args()
    steps = json.loads((ROOT / "video" / "narration.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    ms, padded = [], []
    for i, s in enumerate(steps):
        clip = OUT / f"{i + 1:02d}.aiff"
        speak_say(s["text"], clip, a.voice, a.rate)
        ms.append(round(seconds(clip) * 1000) + PAUSE_MS)
        pad = OUT / f"{i + 1:02d}.wav"  # the clip followed by silence, exactly one step long
        dur = f"{ms[-1] / 1000:.3f}"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip, "-af", f"apad=whole_dur={dur}",
             "-t", dur, "-ar", "44100", "-ac", "1", pad])  # fmt: skip
        padded.append(pad)
    (OUT / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in padded))
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt",
         "-c", "copy", "narration.wav"], cwd=OUT)  # fmt: skip
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
