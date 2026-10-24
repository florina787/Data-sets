"""Hardware profiles and the free local models each one recommends.

These are starting points only. The wizard benchmarks the machine and the
user can pick any model Ollama has installed.
"""

from __future__ import annotations

from typing import Any

PROFILES: dict[str, dict[str, Any]] = {
    "lite": {
        "label": "Lite",
        "target": "8 GB RAM, CPU only",
        "text_model": "qwen2.5:1.5b",
        "vision_model": "qwen2.5vl:3b",
        "asr_model": "tiny",
        "num_ctx": 2048,
        "continuous_interval_s": 10,
        "notes": "Small quantized text model, tiny Whisper, vision loaded on demand.",
        "download_gb": 1.0 + 3.2 + 0.08,
    },
    "balanced": {
        "label": "Balanced",
        "target": "16 GB RAM, CPU or entry GPU",
        "text_model": "qwen2.5:3b",
        "vision_model": "qwen2.5vl:3b",
        "asr_model": "base",
        "num_ctx": 4096,
        "continuous_interval_s": 5,
        "notes": "Mid-sized quantized model, base Whisper, 3B vision model.",
        "download_gb": 1.9 + 3.2 + 0.15,
    },
    "performance": {
        "label": "Performance",
        "target": "32 GB+ RAM or GPU with 8 GB+ VRAM",
        "text_model": "qwen2.5:7b",
        "vision_model": "qwen2.5vl:7b",
        "asr_model": "small",
        "num_ctx": 8192,
        "continuous_interval_s": 3,
        "notes": "7B text and vision models, small Whisper.",
        "download_gb": 4.7 + 6.0 + 0.5,
    },
}


def recommend_profile(hw: dict[str, Any]) -> dict[str, Any]:
    ram = hw.get("ram_gb", 0)
    vram = max((g.get("vram_mb") or 0 for g in hw.get("gpus", []) if g.get("accelerated")), default=0) / 1024
    reasons = [f"{ram:.0f} GB RAM detected"]
    if vram:
        reasons.append(f"accelerated GPU with {vram:.0f} GB memory")
    else:
        reasons.append("no accelerated GPU detected; inference runs on the CPU")
    if ram >= 30 or vram >= 8:
        key = "performance"
    elif ram >= 14:
        key = "balanced"
    else:
        key = "lite"
    if key != "lite" and hw.get("disk_free_gb", 0) < PROFILES[key]["download_gb"] + 2:
        reasons.append("not enough free disk for the larger models")
        key = "lite"
    return {
        "profile": key,
        "reasons": reasons,
        "caveat": "Recommendation is from detected specs only. Run the benchmark to measure this machine.",
    }
