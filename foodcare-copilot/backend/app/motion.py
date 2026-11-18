"""Motion Story GIF export, rendered on the server from the same validated story the UI animates.

Frames are drawn with Pillow from the story's nodes, edges and steps only, so a GIF can never
contain more than the policy-filtered story itself. Each frame carries the story's disclaimer.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

W, H = 960, 540
BG, CARD, LINE, INK, MUTED = (9, 19, 33), (23, 40, 60), (58, 85, 115), (243, 240, 233), (163, 174, 188)
GOLD, TEAL = (215, 183, 122), (69, 197, 184)
ORDER = [
    "input",
    "agent",
    "policy",
    "tools",
    "supplier",
    "source",
    "factory",
    "farm",
    "distribution_centre",
    "evidence",
    "market",
    "output",
]


def _font(size: int):
    for name in ("DejaVuSans.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _layout(nodes: list[dict]) -> dict[str, tuple[int, int]]:
    groups: dict[str, list[dict]] = {}
    for n in nodes:
        groups.setdefault(n["group"], []).append(n)
    cols = sorted(groups, key=lambda g: ORDER.index(g) if g in ORDER else len(ORDER))
    pos = {}
    for ci, g in enumerate(cols):
        items = groups[g][:6]
        x = 70 + ci * ((W - 200) // max(1, len(cols) - 1)) if len(cols) > 1 else W // 2
        for ri, n in enumerate(items):
            y = 120 + (ri + 0.5) * ((H - 210) / len(items))
            pos[n["id"]] = (int(x), int(y))
    return pos


def render(story: dict, frames_per_step: int = 6) -> bytes:
    pos = _layout(story["nodes"])
    title_f, node_f, small_f = _font(24), _font(13), _font(14)
    frames, lit = [], set()
    for si, step in enumerate(story["steps"]):
        lit |= set(step["nodes"])
        for k in range(frames_per_step):
            im = Image.new("RGB", (W, H), BG)
            d = ImageDraw.Draw(im)
            d.text((32, 24), story["title"][:70], font=title_f, fill=INK)
            d.text(
                (32, 60),
                f"Step {si + 1}/{len(story['steps'])}: {step['title']} — {step['text']}"[:120],
                font=small_f,
                fill=GOLD,
            )
            for e in story["edges"]:
                if e["source"] in pos and e["target"] in pos:
                    on = e["source"] in lit and e["target"] in lit
                    d.line([pos[e["source"]], pos[e["target"]]], fill=TEAL if on else LINE, width=3 if on else 1)
            pulse = (k % frames_per_step) / frames_per_step
            for n in story["nodes"]:
                if n["id"] not in pos:
                    continue
                x, y = pos[n["id"]]
                active = n["id"] in step["nodes"]
                if active:
                    r = 18 + int(10 * pulse)
                    d.ellipse([x - r, y - r, x + r, y + r], outline=GOLD, width=2)
                fill = GOLD if active else (TEAL if n["id"] in lit else CARD)
                d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=fill, outline=LINE)
                label = n["label"][:26] + (f" · {n['state'].replace('_', ' ')}" if n.get("state") else "")
                d.text((x - 60, y + 16), label[:40], font=node_f, fill=INK if n["id"] in lit else MUTED)
            d.rectangle([0, H - 40, W, H], fill=CARD)
            d.text((32, H - 30), story["disclaimer"][:130], font=small_f, fill=MUTED)
            frames.append(im.convert("P", palette=Image.ADAPTIVE, colors=64))
    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:], duration=160, loop=0, optimize=True)
    return buf.getvalue()
