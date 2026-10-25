"""Render README charts from measured benchmark data (docs/benchmarks/latest.json).

python -m tests.performance.make_charts
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs" / "benchmarks" / "latest.json"
OUT = ROOT / "docs" / "images"

# VEENA palette: text and chrome in browns, marks in caramel / mocha / sand.
SURFACE, INK, MUTED, GRID = "#FCFAF7", "#2C1A12", "#99613E", "#EFE2D2"
MARK, MARK_DARK, MARK_LIGHT = "#99613E", "#4A2C1C", "#D6B79B"

# Screen analysis is measured end to end in the E2E suite (three runs, seconds).
E2E_SCREEN_S = [53.4, 48.3, 80.5]


def style(ax, title: str, subtitle: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=10, length=0)
    ax.grid(axis="x", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.figure.text(0.02, 0.95, title, fontsize=15, fontweight="bold", color=INK, ha="left")
    ax.figure.text(0.02, 0.895, subtitle, fontsize=10.5, color=MUTED, ha="left")
    for t in ax.get_yticklabels():
        t.set_color(INK)


def fmt_ms(ms: float) -> str:
    if ms >= 1000:
        return f"{ms / 1000:.1f} s"
    if ms >= 1:
        return f"{ms:.0f} ms"
    return f"{ms:.3f} ms"


def latency_chart(d: dict) -> None:
    rows = [
        ("Question detection (rules)", d["question_detection"]["rules_ms_per_utterance"]),
        ("Vector search, 100k passages", d["embeddings_faiss"]["faiss_flat_search_ms_100k"]),
        ("Voice activity detection, per 1 s audio", d["vad"]["ms_per_second_of_audio"]),
        ("Embed a question", d["embeddings_faiss"]["query_embed_ms"]),
        ("First word of an answer (warm)", d["llm"]["warm_first_token_ms"]["p50"]),
        ("OCR of a 1280×720 screenshot", d["ocr"]["ms"]["p50"]),
        ("Transcribe a 4.3 s question (whisper base)", d["asr"]["models"]["base"]["final_ms"]["p50"]),
        ("Analyse a full screenshot (qwen2.5vl:3b)", statistics.median(E2E_SCREEN_S) * 1000),
    ]
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=160)
    fig.subplots_adjust(left=0.36, right=0.93, top=0.8, bottom=0.12)
    labels, vals = zip(*rows)
    y = range(len(rows))
    ax.barh(y, vals, color=MARK, height=0.6, edgecolor=SURFACE, linewidth=2)
    ax.set_xscale("log")
    ax.set_xlim(0.005, 400_000)
    ax.set_yticks(list(y), labels, color=INK, fontsize=10.5)
    ax.invert_yaxis()
    ticks = [0.01, 1, 100, 10_000, 100_000]
    ax.set_xticks(ticks, ["0.01 ms", "1 ms", "100 ms", "10 s", "100 s"])
    ax.minorticks_off()
    ax.set_xlabel("log scale", color=MUTED, fontsize=10)
    for i, v in enumerate(vals):
        ax.text(v * 1.25, i, fmt_ms(v), va="center", fontsize=10, color=INK)
    style(ax, "Where the time goes", "Median latency per pipeline stage · 4-vCPU cloud VM, no GPU · measured, not estimated")
    fig.savefig(OUT / "chart-latency.png", facecolor=SURFACE)
    plt.close(fig)


def speech_chart(d: dict) -> None:
    models = d["asr"]["models"]
    stages = [("Final transcript\n(4.3 s of speech)", "final_ms"), ("Partial transcript\n(1.5 s of speech)", "partial_1_5s_ms")]
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=160)
    fig.subplots_adjust(left=0.2, right=0.93, top=0.7, bottom=0.14)
    h = 0.34
    for j, (name, color) in enumerate((("tiny", MARK_LIGHT), ("base", MARK_DARK))):
        vals = [models[name][key]["p50"] for _, key in stages]
        ys = [i + (j - 0.5) * h for i in range(len(stages))]
        ax.barh(ys, vals, height=h, color=color, edgecolor=SURFACE, linewidth=2, label=f"whisper {name}")
        for yy, v in zip(ys, vals):
            ax.text(v + 40, yy, fmt_ms(v), va="center", fontsize=10, color=INK)
    ax.set_yticks(range(len(stages)), [s for s, _ in stages], color=INK, fontsize=10.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 3000)
    ax.set_xlabel("milliseconds (median of 3 runs)", color=MUTED, fontsize=10)
    leg = ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=10)
    for t in leg.get_texts():
        t.set_color(INK)
    rtf = f"real-time factor: tiny {models['tiny']['real_time_factor']:.2f}, base {models['base']['real_time_factor']:.2f} (below 1 = faster than speech)"
    style(ax, "Local speech recognition", rtf)
    fig.savefig(OUT / "chart-speech.png", facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    d = json.loads(DATA.read_text())
    latency_chart(d)
    speech_chart(d)
    print("charts written to", OUT)


if __name__ == "__main__":
    main()
