"""Cuts the real recorded session (apps/desktop/scripts/record-demos.mjs) into
short website clips: MP4 + WebM + GIF + poster per demo, plus the hero video and
the Open Graph image.

    python site/tools/make_media.py site/media <recording-dir> [<recording-dir> ...]

Each demo is cut from the first recording (in the order given) that contains all of
its marks, so a demo can come from a re-run when a step failed or was mis-timed in
an earlier one. Every clip is still one continuous take of one recording.

Honesty rule: only time is edited. Model waits are shortened and long streamed
answers play faster (the website says so); nothing is added, staged or re-ordered.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
RECS = [(Path(d), {m["name"]: m["t"] for m in json.loads((Path(d) / "marks.json").read_text())}) for d in sys.argv[2:]]
MAX_NORMAL = 14.0  # longer stretches are played faster, up to 3x
LAG = 1.7
HOLD = {"setup": 2.0}  # seconds to hold the final frame where the take ends quickly
STREAM = 10.0  # a long streamed answer plays faster so it lasts at most about 10 s (stated on the site)


def seg(a, b, target: float | None = None):
    return (a, b, target)


def resolve(marks: dict, a, b, target: float | None) -> tuple[float, float, float]:
    ta = a(marks) if callable(a) else marks[a] if isinstance(a, str) else a
    tb = b(marks) if callable(b) else marks[b] if isinstance(b, str) else b
    dur = max(0.1, tb - ta)
    if target is not None:  # a model wait: shorten to `target` seconds
        speed = max(1.0, dur / target)
    else:
        speed = min(3.0, max(1.0, dur / MAX_NORMAL))
    return ta, tb, speed


DEMOS = {
    # Starts after the Home screen (+LAG cancels the shift): Home can show a private local photo.
    "chat": [
        seg(lambda m: m["chat:start"] + LAG, "chat:wait"),
        seg("chat:wait", "chat:streaming", 1.5),
        seg("chat:streaming", "chat:end", STREAM),
    ],
    "docs": [seg("docs:start", "docs:wait"), seg("docs:wait", "docs:streaming", 1.5), seg("docs:streaming", "docs:end", STREAM)],
    "screen": [
        seg("screen:start", "screen:wait"),
        seg("screen:wait", "screen:streaming", 2.5),
        seg("screen:streaming", "screen:end", STREAM),
    ],
    "meeting": [
        seg("meeting:start", "meeting:listening"),
        seg("meeting:listening", "meeting:wait"),
        seg("meeting:wait", "meeting:notes", 2.0),
        seg("meeting:notes", "meeting:end", STREAM),
    ],
    "interview": [
        seg("interview:start", "interview:wait1"),
        seg("interview:wait1", "interview:question", 1.5),
        seg("interview:question", "interview:wait2"),
        seg("interview:wait2", "interview:feedback", 1.5),
        seg("interview:feedback", "interview:end", STREAM),
    ],
    "agents": [seg("agents:start", "agents:end")],
    # The whole guided setup, from the first screen to the first page after it.
    # Ends on "VEENA is ready." (just before the Home screen, which can show a private photo).
    "setup": [seg(0.5, lambda m: m["chat:start"] - 0.8, 12.0)],
}


def run(*args: str) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)


def pick(parts: list) -> tuple[Path, dict]:
    need = {x for a, b, _ in parts for x in (a, b) if isinstance(x, str)} | (
        {"chat:start"} if any(callable(a) or callable(b) for a, b, _ in parts) else set()
    )
    for d, marks in RECS:
        if need <= marks.keys():
            return d, marks
    sys.exit(f"no recording has all of {sorted(need)}")


def build(name: str, spec: list) -> Path:
    rec, marks = pick(spec)
    src = rec / "session.webm"
    # The recorded video runs about 1.7 s behind the step timestamps (measured: a page
    # change marked at 1128.0 s appears at 1126.3 s), so every cut is shifted by that.
    marks = {k: v - LAG for k, v in marks.items()}
    parts = [resolve(marks, *p) for p in spec]
    # The lag differs between recordings, and a clip must never open on the previous page,
    # so each clip starts at its unshifted start mark (the page has switched by then).
    a0, b0, s0 = parts[0]
    parts[0] = (min(a0 + LAG, b0 - 0.2), b0, s0)
    # Always end on the finished result at normal speed: at high speed-ups the last
    # seconds would otherwise last less than a frame and the clip would end mid-answer.
    a, b, speed = parts[-1]
    if speed > 1.0 and b - a > 4.0:
        parts[-1:] = [resolve(marks, a, b - 2.5, None if speed <= 3.0 else (b - 2.5 - a) / speed), (b - 2.5, b, 1.0)]
    print(f"{name}: from {rec.name}")
    # Cut each piece on its own (low memory), then join them: one take, only time edited.
    tmp = out / f".{name}-parts"
    tmp.mkdir(exist_ok=True)
    pieces = []
    for i, (a, b, speed) in enumerate(parts):
        piece = tmp / f"{i}.mp4"
        run(
            "-ss",
            f"{a:.2f}",
            "-to",
            f"{b:.2f}",
            "-i",
            str(src),
            "-an",
            "-vf",
            f"setpts=(PTS-STARTPTS)/{speed:.3f},fps=30,scale=1280:-2:flags=lanczos"
            + (f",tpad=stop_mode=clone:stop_duration={HOLD[name]}" if i == len(parts) - 1 and name in HOLD else ""),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            str(piece),
        )
        pieces.append(piece)
    listing = tmp / "list.txt"
    listing.write_text("".join(f"file '{x.name}'\n" for x in pieces))
    mp4 = out / f"{name}.mp4"
    run(
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(listing),
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "30",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(mp4),
    )
    for x in [*pieces, listing]:
        x.unlink()
    tmp.rmdir()
    run("-i", str(mp4), "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "42", "-row-mt", "1", "-an", str(out / f"{name}.webm"))
    # GIF: 12 fps, 720 px wide, palette tuned per clip.
    pal = out / f"{name}-palette.png"
    run("-i", str(mp4), "-vf", "fps=12,scale=720:-1:flags=lanczos,palettegen=max_colors=128:stats_mode=diff", str(pal))
    run(
        "-i",
        str(mp4),
        "-i",
        str(pal),
        "-lavfi",
        "fps=12,scale=720:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
        str(out / f"{name}.gif"),
    )
    pal.unlink()
    # Poster: the final frame (the finished result), for reduced-motion visitors and slow networks.
    run("-sseof", "-0.3", "-i", str(mp4), "-frames:v", "1", "-vf", "scale=960:-2", "-q:v", "4", str(out / f"{name}-poster.jpg"))
    total = sum((b - a) / s for a, b, s in parts)
    print(f"{name}: {total:.1f} s; " + ", ".join(f"{(b - a):.0f}s@{s:.1f}x" for a, b, s in parts))
    return mp4


for name, parts in DEMOS.items():
    build(name, parts)

# Hero: the chat clip in the laptop screen.
for ext in ("mp4", "webm"):
    (out / f"hero.{ext}").write_bytes((out / f"chat.{ext}").read_bytes())
(out / "hero-poster.jpg").write_bytes((out / "chat-poster.jpg").read_bytes())

# Open Graph image (LinkedIn preview): 1200x630 from the documents result frame.
run(
    "-sseof",
    "-0.3",
    "-i",
    str(out / "docs.mp4"),
    "-frames:v",
    "1",
    "-vf",
    "scale=1200:-2,crop=1200:630:0:0",
    "-q:v",
    "3",
    str(out / "og.jpg"),
)

for f in sorted(out.iterdir()):
    print(f"{f.name:28} {f.stat().st_size / 1e6:6.2f} MB")
