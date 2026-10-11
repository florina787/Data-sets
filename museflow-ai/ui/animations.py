"""Lightweight, CSS-only animations (no JavaScript). Reduced motion is always respected."""
from __future__ import annotations

import random

CONFETTI_COLORS = ("#B79CED", "#F7B7D2", "#C8F7E5", "#C9E8FF", "#FFF0D5", "#D9A5A0")

_CONSTELLATION = (
    '<svg class="constellation" viewBox="0 0 220 120" aria-hidden="true">'
    '<polyline points="10,90 60,60 100,75 150,30 205,45" fill="none" stroke="#DCC8FF" stroke-width="1"/>'
    + "".join(f'<circle cx="{x}" cy="{y}" r="2.6" fill="#FFF9FD"/>' for x, y in ((10, 90), (60, 60), (100, 75), (150, 30), (205, 45)))
    + "</svg>"
)


def sky_markup(intensity: str, reduced_motion: bool) -> str:
    """Background layers. 'Off' renders a static sky; motion classes only when allowed."""
    animated = intensity != "Off" and not reduced_motion
    rng = random.Random(7)  # deterministic layout
    parts = ['<div class="stars"></div>', '<div class="aurora"></div>', _CONSTELLATION]
    if intensity == "Sparkly":
        for _ in range(9):
            size = rng.randint(14, 46)
            parts.append(
                f'<span class="bubble" style="left:{rng.randint(2, 96)}vw;width:{size}px;height:{size}px;'
                f'--dur:{rng.randint(18, 34)}s;--delay:-{rng.randint(0, 30)}s"></span>'
            )
    sparkles = 10 if intensity == "Sparkly" else 5
    for _ in range(sparkles):
        parts.append(
            f'<span class="sparkle" style="left:{rng.randint(2, 97)}vw;top:{rng.randint(4, 92)}vh;'
            f'--delay:-{rng.uniform(0, 3):.1f}s">✦</span>'
        )
    classes = "mf-sky mf-anim" if animated else "mf-sky"
    return f'<div class="{classes}" aria-hidden="true">{"".join(parts)}</div>'


def confetti_markup(seed: int) -> str:
    rng = random.Random(seed)
    pieces = "".join(
        f'<i style="--x:{rng.randint(0, 100)}vw;--delay:{rng.uniform(0, .6):.2f}s;--c:{rng.choice(CONFETTI_COLORS)}"></i>'
        for _ in range(36)
    )
    return f'<div class="mf-confetti" aria-hidden="true">{pieces}</div>'


def typing_indicator() -> str:
    return '<span class="mf-typing" role="status" aria-label="Lumi is typing"><span></span><span></span><span></span></span>'
