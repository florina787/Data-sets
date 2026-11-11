"""Turn the frame folders written by e2e/record-media.mjs into README GIFs (Pillow only).

    python scripts/make_gifs.py <frames-dir> docs/media

Each sub-folder of <frames-dir> becomes <name>.gif. Frames share one palette so the GIF
stays small and does not flicker; identical consecutive frames are merged.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops

WIDTH = 960
DURATION_MS = {"executive": 150, "orbit": 250, "globe": 110, "map2d": 150, "tour": 160, "inspection": 140,
               "copilot": 110, "agents": 150}
HOLD_LAST_MS = 1800


def build(folder: Path, out: Path) -> tuple[int, int]:
    paths = sorted(folder.glob("*.png"))
    frames = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        w = min(WIDTH, im.width)
        frames.append(im.resize((w, round(im.height * w / im.width)), Image.LANCZOS))
    # one shared palette, taken from a strip of sampled frames
    sample = frames[:: max(1, len(frames) // 8)]
    strip = Image.new("RGB", (frames[0].width, sum(f.height for f in sample)))
    y = 0
    for f in sample:
        strip.paste(f, (0, y))
        y += f.height
    palette = strip.quantize(colors=192, method=Image.MEDIANCUT)
    step = DURATION_MS.get(folder.name, 140)
    merged, durations = [], []
    for f in frames:
        q = f.quantize(palette=palette, dither=Image.Dither.NONE)
        if merged and not ImageChops.difference(q.convert("RGB"), merged[-1].convert("RGB")).getbbox():
            durations[-1] += step
            continue
        merged.append(q)
        durations.append(step)
    if folder.name != "orbit":  # the orbit loops seamlessly; everything else pauses on its last frame
        durations[-1] += HOLD_LAST_MS
    merged[0].save(out, save_all=True, append_images=merged[1:], duration=durations, loop=0, optimize=True, disposal=1)
    return len(merged), out.stat().st_size


def main() -> None:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.mkdir(parents=True, exist_ok=True)
    for folder in sorted(p for p in src.iterdir() if p.is_dir() and any(p.glob("*.png"))):
        if folder.name == "stills":
            continue
        n, size = build(folder, dst / f"{folder.name}.gif")
        print(f"{folder.name}.gif: {n} frames, {size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
